#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ALAS 飞牛 fnOS 控制台后端（阶段2）。

职责：
  1. 监听 "${TRIM_APPDEST}/app.sock"，由 fnOS 统一网关注入登录态后转发。
  2. 控制面 API：状态 / 启动 / 停止 / 日志，用打包内的可移植 CPython 3.7 起停 Alas。
  3. 反代 Alas 的 PyWebIO 配置界面："{prefix}/alas/*" -> 127.0.0.1:<port>（含 WebSocket）。
  4. 其余一切路径（应用根、任意子路径）一律 308 到 "{prefix}/alas/"。
  5. 反代前校验 127.0.0.1:<port> 的监听者**确属本包**。历史上出现过「root 权限手工
     启动的旧 gui.py 一直占着 22267」，健康检查只看端口通不通，于是网关照旧把浏览器
     请求反代给老代码 —— 表现是「重装后版本没变、配置还在」这种最难查的故障。
     判定不出来时一律放行，绝不让校验本身变成新的故障源。

本应用**不自带前端**：桌面入口点开即落到 Alas 自己的配置界面。因此这里没有任何静态
文件托管，也没有 SPA 回退 —— 只保留控制面 API 与反代两条路由，缩小暴露面。
控制面 API 只校验网关注入的登录态（X-Trim-Userid），不区分管理员。

数据落盘与脚本热更新：
  Alas 源码树运行在 "$TRIM_PKGVAR/alas"（可写），安装目录里的 alas 只作「出厂种子」。
  其 ./config 与 ./log 软链到 "$TRIM_PKGVAR"，安装目录始终保持只读语义。
  这样上游的「检查更新 / 立即更新」面板就能在不写安装目录的前提下工作：
  <target>/patch 注入的补丁把 git 流程换成源码包交换（见 app/patch/alas_fnos.py）。
  deploy.yaml 中的 InstallDependencies / EnableReload 等键在每次启动前强制写死。

只用打包运行时里已有的 uvicorn + websockets，不引入新依赖。
运行：<runtime>/bin/python3.7 console_server.py [--prepare]
"""

import argparse
import asyncio
import http.client
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time

APPNAME_DEFAULT = "alas-fnos"
WEBUI_PORT_DEFAULT = 22267

# 反代时不能透传的逐跳首部
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

# 每次启动 Alas 前强制写死的 deploy 配置：
#   AutoUpdate=true          允许更新面板工作（真实实现由 <target>/patch 注入，不依赖 git）
#   EnableReload=true        由上游 gui.py 建立重启循环，更新完成后自动重载新代码
#   CheckUpdateInterval=0    不注册后台轮询，只在用户点按钮时检查（否则会周期性报错）
#   InstallDependencies=false 依赖随运行时冻结，禁止 pip 改动安装环境
FORCED_DEPLOY = {
    "InstallDependencies": "false",
    "EnableReload": "true",
    "AutoUpdate": "true",
    "CheckUpdateInterval": "0",
    "AutoRestartTime": "null",
    "ReplaceAdb": "false",
    "AdbExecutable": "adb",
    "WebuiHost": "127.0.0.1",
    "Password": "null",
}

# 应用根与任何未匹配的路径一律 308 到 {prefix}/alas/：桌面入口的 url 只写 /app/<appname>，
# 点开即进入 Alas 配置界面，无需使用者手动补 /alas。

# 单个应用日志文件超过这个大小就滚成 <path>.1（只保留一代，占用上界 ≈ 2×）。
# 本应用是 7x24 挂机的，alas.log 里还有 uvicorn 的每请求 access log，必须封顶。
LOG_ROTATE_BYTES = 16 * 1024 * 1024

# $TRIM_PKGVAR/log 是 Alas 自己的任务日志目录，上游只增不减（一天一份 txt），
# 这里给它一个总量上限，只有超了才从最旧的开始删。可用 ALAS_FNOS_LOG_MAX_MB 覆盖，
# 设为 0 或负数表示不做任何清理（完全交给使用者自己管）。
ALAS_LOG_MAX_MB = 512

# 监听者身份判定的缓存时长：反代是热路径，不能每个请求都扫一遍 /proc。
LISTENER_TTL = 5.0

# 同一类告警的最小间隔，避免 7x24 跑下来把日志刷爆。
LOG_THROTTLE_SECONDS = 120.0

_throttle_lock = threading.Lock()
_throttle_state = {}


def log(msg):
    sys.stdout.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    sys.stdout.flush()


def log_throttled(key, msg, interval=LOG_THROTTLE_SECONDS):
    """按 key 限流地打日志；返回本次是否真的打出来了。"""
    now = time.time()
    with _throttle_lock:
        last = _throttle_state.get(key)
        if last is not None and now - last < interval:
            return False
        _throttle_state[key] = now
    log(msg)
    return True


def ensure_runtime_lib(ctx):
    """运行时的 OpenSSL 等系统库在 <runtime>/lib，不设 LD_LIBRARY_PATH 连 uvicorn 都导不进来。
    若未生效则带路径重新执行自身（execv 保留 PID 与已打开的文件描述符）。"""
    lib = os.path.join(ctx.runtime, "lib")
    if not os.path.isdir(lib):
        return
    current = os.environ.get("LD_LIBRARY_PATH", "")
    if lib in current.split(":"):
        return
    os.environ["LD_LIBRARY_PATH"] = lib + (":" + current if current else "")
    log("re-exec with LD_LIBRARY_PATH=%s" % lib)
    os.execv(sys.executable, [sys.executable] + sys.argv)


class Context:
    """路径、端口与运行环境。命令行参数优先，其次 TRIM_* 环境变量。"""

    def __init__(self, args):
        self.appname = args.appname or os.environ.get("TRIM_APPNAME") or APPNAME_DEFAULT
        self.appdest = os.path.abspath(
            args.appdest or os.environ.get("TRIM_APPDEST") or os.getcwd()
        )
        self.pkgetc = os.path.abspath(
            args.pkgetc or os.environ.get("TRIM_PKGETC") or os.path.join(self.appdest, "etc")
        )
        self.pkgvar = os.path.abspath(
            args.pkgvar or os.environ.get("TRIM_PKGVAR") or os.path.join(self.appdest, "var")
        )
        self.socket_path = os.path.abspath(
            args.socket or os.environ.get("ALAS_FNOS_SOCK") or os.path.join(self.appdest, "app.sock")
        )
        self.runtime = os.path.join(self.appdest, "runtime")
        self.python = os.path.join(self.runtime, "bin", "python3.7")
        self.patch_dir = os.path.join(self.appdest, "patch")

        # 安装目录里的 alas 只作「出厂种子」；真正运行的是 PKGVAR 下的可写副本，
        # 这样上游的在线更新才能在不写安装目录的前提下替换源码。
        self.alas_seed = os.path.join(self.appdest, "alas")
        self.alas_dir = os.path.join(self.pkgvar, "alas")
        self.deploy_template = os.path.join(self.alas_dir, "deploy", "template")
        self.version_file = os.path.join(self.pkgvar, "alas_version.json")
        self.fpk_version_file = os.path.join(self.appdest, "alas_version.json")

        self.webui_port = int(args.port or os.environ.get("ALAS_WEBUI_PORT") or WEBUI_PORT_DEFAULT)
        self.autostart = str(
            args.autostart or os.environ.get("ALAS_FNOS_AUTOSTART", "1")
        ).lower() not in ("0", "false", "no")

        # 网关下的公开前缀，网关会带前缀转发
        self.prefix = "/app/" + self.appname
        self.alas_path = self.prefix + "/alas"

        # 所有可变数据都在 PKGVAR
        self.config_dir = os.path.join(self.pkgvar, "config")
        self.log_dir = os.path.join(self.pkgvar, "log")
        self.alas_log = os.path.join(self.pkgvar, "alas.log")
        self.pid_file = os.path.join(self.pkgvar, "alas.pid")
        self.console_log = os.path.join(self.pkgvar, "console.log")

        # 监听者身份判定的缓存（反代热路径，不能每请求都扫 /proc）
        self._listener_cache = {"at": 0.0, "value": None}
        self._listener_lock = threading.Lock()
        # adb 需要可写 HOME，按优先级探测（见 resolve_home）
        self._home_dir = None

    # -- 准备 ---------------------------------------------------------------

    def prepare(self):
        """幂等准备：PKGVAR 目录、Alas 源码树、config/log 软链、deploy.yaml 强制键。"""
        os.makedirs(self.pkgvar, exist_ok=True)
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        self.seed_alas()
        self._link_into_pkgvar("config")
        self._link_into_pkgvar("log")
        self.force_deploy_config()
        # Alas 自己的任务日志只增不减，超过上限就从最旧的开始删
        max_mb = os.environ.get("ALAS_FNOS_LOG_MAX_MB", ALAS_LOG_MAX_MB)
        prune_log_dir(self.log_dir, max_mb)

    def seed_alas(self):
        """确保 $TRIM_PKGVAR/alas 存在：首次从安装目录播种，安装包升级时按需重播。

        播种策略由 alas_version.json 的 ``source`` 决定：

        * 源码树不存在 → 从安装目录复制（首次安装）
        * ``source == "update"`` → 用户已在运行期更新过，保留（reset_alas 可丢弃）
        * ``source == "fpk"`` 且安装包基线变了 → 随安装包重播

        复制而非移动：安装目录里保留一份只读种子，reset_alas 才有东西可回退。
        """
        seed = self.alas_seed
        target = self.alas_dir

        fpk_version = _read_json(self.fpk_version_file) or {}
        installed = _read_json(self.version_file) or {}
        log(
            "alas 版本记录：包内=%s（%s）；运行=%s/%s（%s）"
            % (
                (fpk_version.get("base_commit") or "无")[:8],
                self.fpk_version_file,
                (installed.get("base_commit") or "无")[:8],
                installed.get("source") or "-",
                self.version_file,
            )
        )
        if not fpk_version.get("base_commit") and os.path.isdir(target):
            log(
                "警告：包内版本记录缺失或不可读（%s），无法判断是否需要随安装包重播，"
                "本次沿用现有源码树" % self.fpk_version_file
            )

        if not os.path.isdir(target):
            if not os.path.isdir(seed):
                raise RuntimeError("安装包内缺少 Alas 源码：%s" % seed)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copytree(seed, target, symlinks=True)
            self._write_version(dict(fpk_version, source="fpk"))
            log("alas 首次播种：%s -> %s" % (seed, target))
            return "seeded"

        current = installed.get("base_commit") or ""
        incoming = fpk_version.get("base_commit") or ""

        if installed.get("source") == "update":
            log("alas 已在运行期更新过（%s），保留用户版本" % (current[:8] or "未知"))
            return "kept"

        if incoming and incoming != current:
            previous = os.path.join(self.pkgvar, ".alas-prev-%d" % int(time.time()))
            os.replace(target, previous)
            try:
                shutil.copytree(seed, target, symlinks=True)
            except Exception:
                os.replace(previous, target)
                raise
            shutil.rmtree(previous, ignore_errors=True)
            self._write_version(dict(fpk_version, source="fpk"))
            log("alas 随安装包重播：%s -> %s" % (current[:8] or "未知", incoming[:8]))
            return "reseeded"

        log("alas 沿用现有源码树（%s）" % (current[:8] or "未知"))
        return "kept"

    def reset_alas(self):
        """丢弃运行期更新过的脚本，回到安装包自带的版本。"""
        target = self.alas_dir
        if os.path.islink(target):
            os.unlink(target)
        elif os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
        if os.path.exists(self.version_file):
            os.remove(self.version_file)

        outcome = self.seed_alas()
        # 新树里的 config/log 是种子目录，必须重新指回 PKGVAR（保留用户数据）
        self._link_into_pkgvar("config")
        self._link_into_pkgvar("log")
        return outcome

    def reset_alas_and_restart(self):
        """恢复出厂脚本：先停 Alas，再回退源码树，最后重新拉起。"""
        self.stop_alas()
        try:
            self.reset_alas()
        except Exception as exc:
            return None, "恢复出厂脚本失败：%s" % exc
        return self.start_alas()

    def _write_version(self, data):
        temporary = self.version_file + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, self.version_file)

    def _link_into_pkgvar(self, name):
        """把 alas/<name> 落到 PKGVAR/<name>，源码树里以软链指过去。"""
        src = os.path.join(self.alas_dir, name)
        dst = os.path.join(self.pkgvar, name)

        if os.path.islink(src):
            if os.path.realpath(src) == os.path.realpath(dst):
                return
            os.unlink(src)
        elif os.path.isdir(src):
            # 首次运行：把包内种子文件迁移（不覆盖 PKGVAR 已有内容）
            if not os.path.isdir(dst):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                # PKGVAR 可能位于另一设备（独立卷），rename 会跨设备失败
                shutil.move(src, dst)
            else:
                _merge_seed(src, dst)
                _rmtree(src)
        elif os.path.exists(src):
            os.remove(src)

        os.makedirs(dst, exist_ok=True)
        os.symlink(dst, src)
        log("link: %s -> %s" % (src, dst))

    def force_deploy_config(self):
        """按 deploy/template 生成（或修正）$PKGVAR/config/deploy.yaml。"""
        target = os.path.join(self.config_dir, "deploy.yaml")
        if os.path.exists(target):
            with open(target, "r", encoding="utf-8") as f:
                text = f.read()
        elif os.path.exists(self.deploy_template):
            with open(self.deploy_template, "r", encoding="utf-8") as f:
                text = f.read()
        else:
            text = ""

        forced = dict(FORCED_DEPLOY)
        forced["WebuiPort"] = str(self.webui_port)
        for key, value in forced.items():
            pattern = re.compile(r"^(\s*)%s\s*:.*$" % re.escape(key), re.MULTILINE)
            if pattern.search(text):
                text = pattern.sub(lambda m: "%s%s: %s" % (m.group(1), key, value), text)
            else:
                text = text.rstrip("\n") + "\n%s: %s\n" % (key, value)

        with open(target, "w", encoding="utf-8") as f:
            f.write(text)
        log("deploy config forced: %s" % ", ".join(sorted(forced)))

    # -- Alas 进程 ----------------------------------------------------------

    def read_pid(self):
        """返回 (pid, start_ts)；文件缺失或损坏返回 (None, None)。"""
        try:
            with open(self.pid_file, "r", encoding="utf-8") as f:
                pid, start = f.read().strip().split("|", 1)
            return int(pid), float(start)
        except Exception:
            return None, None

    def process_alive(self):
        pid, start = self.read_pid()
        if not pid:
            return False
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        if self.owns_pid(pid) is False:
            # PID 被复用给了别的进程：不能再把它当成「Alas 还活着」，
            # 否则 stop 时会对着无关进程组开刀。
            log_throttled(
                "pid-reuse-%d" % pid,
                "PID %d 已不属于本应用（cmdline 不匹配），按未运行处理" % pid,
            )
            return False
        return start

    # -- 身份校验 -----------------------------------------------------------

    def owns_pid(self, pid):
        """pid 是否确属本包启动的进程。

        返回 ``True``（确认是）/ ``False``（确认不是）/ ``None``（读不到 /proc，判不出来）。
        调用方必须把 ``None`` 当作「按原逻辑继续」，不能让探针本身成为故障源。
        """
        cmdline = _proc_cmdline(pid)
        cwd = _proc_cwd(pid)
        if not cmdline and not cwd:
            return None
        if cwd.endswith(" (deleted)"):
            # 源码树已被换掉/卸载，这个进程已经不该继续服务了
            return False

        for token in (self.runtime, self.alas_dir, self.pkgvar, self.appdest):
            if token and token in cmdline:
                return True
        if cwd:
            try:
                if os.path.realpath(cwd) == os.path.realpath(self.alas_dir):
                    return True
            except OSError:
                pass
        if not cmdline:
            return None
        return False

    def listener_owner(self, force=False):
        """判定 ``127.0.0.1:<port>`` 的监听者是不是本包启动的 Alas。

        返回 ``(state, detail)``，state 取值：

        * ``"ours"``    确认是本包
        * ``"foreign"`` 确认不是本包（socket 属别人 / cmdline 明确不匹配 / cwd 已失效）
        * ``"none"``    压根没有监听者
        * ``"unknown"`` 判不出来 —— 一律放行

        判定顺序有意从「不需要权限就能拿到」的信息开始：``/proc/net/tcp`` 里的
        socket uid 属于 socket 本身，所以即使占用者以 root 运行、我们无权读它的
        ``/proc/<pid>``，也能一眼看出「这不是我的」。
        """
        now = time.time()
        with self._listener_lock:
            cached = self._listener_cache["value"]
            if not force and cached and now - self._listener_cache["at"] < LISTENER_TTL:
                return cached

        result = self._probe_listener()

        with self._listener_lock:
            previous = self._listener_cache["value"]
            self._listener_cache["at"] = time.time()
            self._listener_cache["value"] = result
        if result[0] == "foreign" and (not previous or previous[0] != "foreign"):
            log("警告：%d 端口的监听者不是本应用 —— %s" % (self.webui_port, result[1]))
        return result

    def _probe_listener(self):
        sockets = listen_sockets(self.webui_port)
        if sockets is None:
            return ("unknown", "读不到 /proc/net/tcp，无法判定监听者身份")
        if not sockets:
            return ("none", "无监听者")

        mine = os.getuid()
        foreign_uids = sorted({uid for _inode, uid in sockets if uid not in (mine, -1)})
        if foreign_uids:
            return (
                "foreign",
                "监听 socket 属 uid=%s，本应用以 uid=%d 运行"
                % (",".join(str(u) for u in foreign_uids), mine),
            )

        owners = socket_owners({inode for inode, _uid in sockets})
        if not owners:
            return ("unknown", "监听者 uid 与本应用相同，但无权定位其进程（不阻断）")
        pid = sorted(owners.values())[0]
        owned = self.owns_pid(pid)
        if owned is True:
            return ("ours", "pid=%d" % pid)
        if owned is None:
            return ("unknown", "pid=%d 的 /proc 不可读（不阻断）" % pid)
        detail = _proc_cmdline(pid) or _proc_cwd(pid) or "无 cmdline"
        return ("foreign", "pid=%d 不属于本应用：%s" % (pid, detail[:160]))

    def guard_upstream(self):
        """反代前的最后一道闸：返回 None 表示放行，否则返回拒绝原因。"""
        state, detail = self.listener_owner()
        if state == "foreign":
            return "%s 端口的监听者不是本应用启动的 Alas（%s）" % (self.webui_port, detail)
        return None

    def webui_reachable(self):
        try:
            with socket.create_connection(("127.0.0.1", self.webui_port), timeout=0.3):
                return True
        except OSError:
            return False

    def state(self):
        start = self.process_alive()
        if not start:
            return "stopped"
        if self.listener_owner()[0] == "foreign":
            # 自己的进程还活着但端口被别人占着（bind 失败），如实报冲突
            return "conflict"
        return "running" if self.webui_reachable() else "starting"

    def status(self):
        pid, start = self.read_pid()
        state = self.state()
        uptime = None
        if state != "stopped" and start:
            uptime = int(time.time() - start)
        payload = {
            "state": state,
            "pid": pid if state != "stopped" else None,
            "uptime": uptime,
            "port": self.webui_port,
            "prefix": self.prefix,
        }
        if state == "conflict":
            payload["detail"] = self.listener_owner()[1]
        return payload

    def resolve_home(self):
        """挑一个可写的 HOME（adb start-server 要在这里生成 ~/.android/adbkey）。

        优先级：平台给的 ``$TRIM_PKGHOME``（官方语义就是「应用用户数据」，必然可写）
        → ``<appdest>/home``（平台确实会建） → ``$PKGVAR/home``（数据目录必可写）。
        结果缓存，避免每次启动都探测一遍。
        注意：平台拉起本进程时的 ``$HOME`` 往往不可写，不能用。
        """
        if self._home_dir:
            return self._home_dir

        candidates = []
        platform_home = (os.environ.get("TRIM_PKGHOME") or "").strip()
        if platform_home:
            candidates.append(platform_home)
        candidates.append(os.path.join(self.appdest, "home"))
        candidates.append(os.path.join(self.pkgvar, "home"))

        for candidate in candidates:
            try:
                os.makedirs(candidate, exist_ok=True)
            except OSError as exc:
                log("警告：HOME 候选 %s 不可用：%r" % (candidate, exc))
                continue
            if os.path.isdir(candidate) and os.access(candidate, os.W_OK):
                if candidate != candidates[0]:
                    log("HOME 采用 %s（%s 不可用）" % (candidate, candidates[0]))
                else:
                    log("HOME 采用 %s" % candidate)
                self._home_dir = candidate
                return candidate

        log("警告：无可写 HOME（尝试过 %s），adb start-server 可能失败" % ", ".join(candidates))
        return ""

    def start_alas(self):
        if self.process_alive():
            return self.status(), None
        if not os.path.isfile(self.python):
            return None, "运行时缺失：%s" % self.python
        if not os.path.isfile(os.path.join(self.alas_dir, "gui.py")):
            return None, "Alas 源码缺失：%s" % self.alas_dir

        # 端口被别人占着时不要假装启动成功：gui.py 会 bind 失败然后退出，
        # 而健康检查只看端口通不通 —— 于是网关照旧把请求反代给占用者（4.12.8）。
        conflict = self.guard_upstream()
        if conflict:
            log("拒绝启动 Alas：%s" % conflict)
            return None, conflict

        self.prepare()

        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = os.path.join(self.runtime, "lib")
        env["PYTHONUNBUFFERED"] = "1"
        # 包内自带 adb（决策 #1 修订版）：前插 <appdest>/bin，默认 AdbExecutable=adb
        # 直接命中，不依赖外部环境；序列号等仍由使用者在 WebUI 配置。
        adb_bin_dir = os.path.join(self.appdest, "bin")
        has_adb = os.path.isfile(os.path.join(adb_bin_dir, "adb"))
        if has_adb:
            env["PATH"] = adb_bin_dir + os.pathsep + env.get("PATH", "")
        home_dir = self.resolve_home()
        if home_dir:
            env["HOME"] = home_dir
        # 注入更新补丁：sitecustomize.py 会在解释器启动时接管更新面板
        env["ALAS_FNOS_PKGVAR"] = self.pkgvar
        env["ALAS_FNOS_APPDEST"] = self.appdest
        if os.path.isdir(self.patch_dir):
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = self.patch_dir + ((":" + existing) if existing else "")
        else:
            log("警告：未找到更新补丁目录 %s，更新面板将不可用" % self.patch_dir)

        # 用上游 gui.py 启动：EnableReload=true 时它会建立重启循环，
        # 更新完成后由 updater 触发事件即可自动加载新代码（无需我们介入）。
        cmd = [
            self.python,
            os.path.join(self.alas_dir, "gui.py"),
            "--host",
            "127.0.0.1",
            "-p",
            str(self.webui_port),
        ]
        log("start alas: %s (cwd=%s)" % (" ".join(cmd), self.alas_dir))

        # 预启动包内 adb server（best-effort）：保证首次 DETECT DEVICE 无冷启动
        # 延迟；失败不阻塞 Alas 启动（adbutils 会再自行拉起）。
        if has_adb:
            try:
                subprocess.run(
                    [os.path.join(adb_bin_dir, "adb"), "start-server"],
                    env=env, timeout=15,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception as exc:
                log("adb start-server 预启动失败（不阻塞）：%r" % (exc,))

        # 打开之前先轮转，保证 alas.log 有明确上界（uvicorn 的 access log 也在里面）
        rotate_log(self.alas_log)

        with open(self.alas_log, "ab") as out:
            proc = subprocess.Popen(
                cmd,
                cwd=self.alas_dir,
                env=env,
                stdout=out,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        with open(self.pid_file, "w", encoding="utf-8") as f:
            f.write("%d|%f" % (proc.pid, time.time()))
        return self.status(), None

    def stop_alas(self, timeout=20):
        pid, _ = self.read_pid()
        if not pid:
            self._cleanup()
            return self.status(), None
        if self.owns_pid(pid) is False:
            # PID 已被复用给无关进程：killpg 会连带杀掉别人的进程组，绝不能开这一刀
            log("放弃停止 PID %d：它已不属于本应用（PID 复用），仅清理 PID 文件" % pid)
            self._cleanup()
            return self.status(), None
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except OSError:
            pass

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(0.5)
        else:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except OSError:
                pass
            time.sleep(0.5)

        self._cleanup()
        return self.status(), None

    def _cleanup(self):
        if os.path.exists(self.pid_file):
            os.remove(self.pid_file)

    def tail_log(self, lines=200):
        """读日志末尾若干行。

        从尾部 seek 往回读，而不是 ``deque(f, maxlen)``：后者内存有界，但会把
        **整个文件**过一遍。alas.log 是 7x24 追加的，几百 MB 时这个接口会把线程
        占住很久。这里只读尾部需要的字节，并留一个内存上限兜底超大单行。
        """
        lines = max(1, min(int(lines), 5000))
        try:
            total = os.path.getsize(self.alas_log)
        except OSError:
            return ""
        if total <= 0:
            return ""

        block = 8192
        cap = 16 * 1024 * 1024  # 正常情况下远用不到，只防「一行几百 MB」这种畸形文件
        data = b""
        position = total
        try:
            with open(self.alas_log, "rb") as f:
                while position > 0 and data.count(b"\n") <= lines and len(data) < cap:
                    step = min(block, position)
                    position -= step
                    f.seek(position)
                    data = f.read(step) + data
        except OSError:
            return ""

        text = data.decode("utf-8", errors="replace")
        return "".join(text.splitlines(True)[-lines:])


def _read_json(path):
    """读一个 JSON 对象；文件缺失或损坏时返回 None（调用方一律要有回退）。"""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _merge_seed(src, dst):
    """把源目录中目标缺失的文件补进目标目录（不覆盖已有文件）。"""
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        out = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(out, exist_ok=True)
        for name in files:
            target = os.path.join(out, name)
            if not os.path.exists(target):
                with open(os.path.join(root, name), "rb") as f:
                    data = f.read()
                with open(target, "wb") as f:
                    f.write(data)


def _rmtree(path):
    shutil.rmtree(path, ignore_errors=True)


# --------------------------------------------------------------------------- #
# 日志轮转（7x24 场景下不能让日志无限增长）
# --------------------------------------------------------------------------- #


def rotate_log(path, max_bytes=LOG_ROTATE_BYTES):
    """文件超过 max_bytes 就改名为 <path>.1（覆盖上一代）。返回是否滚动过。

    只保留一代是为了让占用有上界（≈ 2×阈值）又不丢最近的历史。调用点都在
    「打开日志之前」，所以不涉及句柄语义问题。
    """
    try:
        if os.path.getsize(path) <= max_bytes:
            return False
    except OSError:
        return False

    backup = path + ".1"
    try:
        if os.path.exists(backup):
            os.remove(backup)
        os.replace(path, backup)
    except OSError as exc:
        log("日志轮转失败 %s：%r" % (path, exc))
        return False
    log("日志轮转：%s → %s（阈值 %.0f MB）" % (path, backup, max_bytes / 1048576.0))
    return True


def prune_log_dir(log_dir, max_mb):
    """把日志目录的总量压到 max_mb 以内，最旧的先删；返回 (删除数, 释放字节数)。

    上游 Alas 的 log/ 是只增不减的（`./log/{date}_{name}.txt`，一天一份），
    7x24 跑下去会把数据目录吃满。只有**超过上限**才动手，且逐条留痕。
    传 0 或负数表示关闭该策略。
    """
    try:
        max_bytes = int(max_mb) * 1024 * 1024
    except (TypeError, ValueError):
        return 0, 0
    if max_bytes <= 0:
        return 0, 0

    entries = []
    total = 0
    for root, _dirs, files in os.walk(log_dir):
        for name in files:
            path = os.path.join(root, name)
            try:
                stat = os.lstat(path)
            except OSError:
                continue
            if not os.path.isfile(path) or os.path.islink(path):
                continue
            entries.append((stat.st_mtime, stat.st_size, path))
            total += stat.st_size

    if total <= max_bytes:
        return 0, 0

    entries.sort()  # 最旧的在前
    removed = 0
    freed = 0
    for _mtime, size, path in entries:
        if total <= max_bytes:
            break
        try:
            os.remove(path)
        except OSError:
            continue
        removed += 1
        freed += size
        total -= size
    if removed:
        log(
            "日志目录超限（%.0f MB > %.0f MB），已删除 %d 个最旧文件，释放 %.0f MB：%s"
            % (
                (total + freed) / 1048576.0,
                max_bytes / 1048576.0,
                removed,
                freed / 1048576.0,
                log_dir,
            )
        )
    return removed, freed


# --------------------------------------------------------------------------- #
# 监听者身份校验（/proc 解析，Linux；判不出来一律放行）
# --------------------------------------------------------------------------- #

_PROC = "/proc"


def _proc_cmdline(pid):
    """读 /proc/<pid>/cmdline；读不到返回空串。"""
    try:
        with open(os.path.join(_PROC, str(pid), "cmdline"), "rb") as handle:
            raw = handle.read()
    except OSError:
        return ""
    return raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()


def _proc_cwd(pid):
    """读 /proc/<pid>/cwd 链接；读不到返回空串。"""
    try:
        return os.readlink(os.path.join(_PROC, str(pid), "cwd"))
    except OSError:
        return ""


def listen_sockets(port, proc_net=None):
    """返回本机监听 <port> 的 ``[(inode, socket_uid)]``；/proc/net 不可读返回 None。

    只看状态 LISTEN（``0A``）。uid 字段是关键：它属于 socket 而非进程，
    所以**即使监听者以 root 运行、我们无权读它的 /proc/<pid>，也能判出「这不是我的」** ——
    4.12.8 那次翻车正是「root 僵尸 gui.py 占着 22267」。
    """
    net_dir = proc_net or os.path.join(_PROC, "net")
    found = False
    sockets = []
    for table in ("tcp", "tcp6"):
        try:
            handle = open(os.path.join(net_dir, table), "r")
        except OSError:
            continue
        with handle:
            found = True
            next(handle, None)  # 表头
            for line in handle:
                fields = line.split()
                if len(fields) < 10 or fields[3] != "0A":
                    continue
                raw_port = fields[1].rpartition(":")[2]
                try:
                    if int(raw_port, 16) != int(port):
                        continue
                except ValueError:
                    continue
                try:
                    uid = int(fields[7])
                except ValueError:
                    uid = -1
                sockets.append((fields[9], uid))
    if not found:
        return None
    return sockets


def socket_owners(inodes):
    """把 socket inode 映射到持有它的 pid（扫 /proc/<pid>/fd）；无权读的进程会缺席。"""
    owners = {}
    if not inodes:
        return owners
    try:
        names = os.listdir(_PROC)
    except OSError:
        return owners
    for name in names:
        if not name.isdigit():
            continue
        fd_dir = os.path.join(_PROC, name, "fd")
        try:
            fds = os.listdir(fd_dir)
        except OSError:
            continue
        for fd in fds:
            try:
                link = os.readlink(os.path.join(fd_dir, fd))
            except OSError:
                continue
            if len(link) > 9 and link.startswith("socket:[") and link.endswith("]"):
                inode = link[8:-1]
                if inode in inodes and inode not in owners:
                    owners[inode] = int(name)
    return owners


class ConsoleApp:
    """手写 ASGI 应用：控制面 API + PyWebIO 反代（HTTP/WS）。

    本应用不自带前端、不做静态托管（1.2.1 起），所以这里只有这两类路由。
    """

    def __init__(self, ctx):
        self.ctx = ctx

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            await self.http(scope, receive, send)
        elif scope["type"] == "websocket":
            await self.websocket(scope, receive, send)

    # -- 工具 ---------------------------------------------------------------

    @staticmethod
    def header(scope, name, default=None):
        name = name.lower().encode()
        for key, value in scope.get("headers", []):
            if key.lower() == name:
                return value.decode("latin-1")
        return default

    def identity(self, scope):
        """登录态只信任网关注入的 X-Trim-* 首部。"""
        uid = self.header(scope, "x-trim-userid")
        if not uid:
            return None
        return {
            "uid": uid,
            "admin": self.header(scope, "x-trim-isadmin", "0") in ("1", "true", "True"),
            "name": self.header(scope, "x-trim-username", ""),
        }

    async def send_json(self, send, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(body)).encode()),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    @staticmethod
    def raw_path(scope):
        """uvicorn 的 http scope 里 raw_path 是 bytes，websocket scope 里是 str。"""
        raw = scope.get("raw_path")
        if raw is None:
            return scope.get("path", "/")
        if isinstance(raw, bytes):
            return raw.decode("latin-1")
        return raw

    async def read_body(self, receive):
        body = b""
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                break
            body += message.get("body", b"")
            if not message.get("more_body"):
                break
        return body

    # -- HTTP --------------------------------------------------------------

    async def http(self, scope, receive, send):
        ctx = self.ctx
        path = self.raw_path(scope)

        if path.startswith(ctx.prefix + "/api/"):
            await self.api(scope, receive, send)
        elif path == ctx.alas_path or path.startswith(ctx.alas_path + "/"):
            await self.proxy_http(scope, receive, send)
        else:
            # 本应用不自带前端：应用根与任意未匹配路径一律落到 Alas 配置界面
            await self.redirect(send, ctx.alas_path + "/")

    async def api(self, scope, receive, send):
        ctx = self.ctx
        route = self.raw_path(scope)[len(ctx.prefix):]
        await self.read_body(receive)  # 必须消费请求体，否则连接状态异常
        identity = self.identity(scope)
        if identity is None:
            await self.send_json(send, 403, {"error": "forbidden", "msg": "缺少网关登录态"})
            return

        if route == "/api/status" and scope["method"] == "GET":
            await self.send_json(send, 200, ctx.status())
        elif route == "/api/start" and scope["method"] == "POST":
            status, error = await asyncio.get_event_loop().run_in_executor(None, ctx.start_alas)
            log("start by uid=%s -> %s" % (identity["uid"], error or status["state"]))
            await self.send_json(send, 500 if error else 200, {"error": error} if error else status)
        elif route == "/api/stop" and scope["method"] == "POST":
            status, error = await asyncio.get_event_loop().run_in_executor(None, ctx.stop_alas)
            log("stop by uid=%s -> %s" % (identity["uid"], error or status["state"]))
            await self.send_json(send, 500 if error else 200, {"error": error} if error else status)
        elif route == "/api/log" and scope["method"] == "GET":
            query = _parse_query(scope.get("query_string", b""))
            text = await asyncio.get_event_loop().run_in_executor(
                None, ctx.tail_log, query.get("lines", 200)
            )
            await self.send_json(send, 200, {"log": text})
        elif route == "/api/alas/reset" and scope["method"] == "POST":
            # 恢复出厂脚本：丢弃运行期更新，回到安装包自带版本
            status, error = await asyncio.get_event_loop().run_in_executor(
                None, ctx.reset_alas_and_restart
            )
            log("alas reset by uid=%s -> %s" % (identity["uid"], error or status["state"]))
            await self.send_json(send, 500 if error else 200, {"error": error} if error else status)
        else:
            await self.send_json(send, 404, {"error": "not_found", "route": route})

    async def redirect(self, send, location):
        await send(
            {
                "type": "http.response.start",
                "status": 308,
                "headers": [(b"location", location.encode()), (b"content-length", b"0")],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    async def send_html(self, send, status, title, detail):
        """给人看的一页说明。反代被拒时用它，比一段裸 JSON 清楚得多。"""
        from html import escape

        body = (
            "<!doctype html><meta charset=\"utf-8\">"
            "<title>%s</title>"
            "<body style=\"font:15px/1.7 -apple-system,'PingFang SC','Microsoft YaHei',sans-serif;"
            "max-width:44em;margin:12vh auto;padding:0 1.5em;color:#222\">"
            "<h2 style=\"margin:0 0 .6em\">%s</h2>"
            "<p style=\"color:#555\">%s</p>"
            "<p style=\"color:#888;font-size:13px\">处置：在 NAS 上确认没有手工启动过的 "
            "<code>python gui.py</code>（尤其是 root 身份的僵尸进程），杀掉后重新启动本应用。</p>"
            "</body>"
        ) % (escape(title), escape(title), escape(detail))
        payload = body.encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"text/html; charset=utf-8"),
                    (b"content-length", str(len(payload)).encode()),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})

    # -- 反代 ---------------------------------------------------------------

    def upstream_target(self, scope):
        """把 {prefix}/alas/xxx 映射为上游 /xxx。"""
        ctx = self.ctx
        path = self.raw_path(scope)[len(ctx.alas_path):]
        if not path:
            path = "/"
        query = scope.get("query_string", b"").decode("latin-1")
        return path, query

    async def proxy_http(self, scope, receive, send):
        ctx = self.ctx
        # PyWebIO 页面用相对路径引用静态资源，URL 必须以 / 结尾，否则会解析到错误的上级路径
        if self.raw_path(scope) == ctx.alas_path:
            await self.redirect(send, ctx.alas_path + "/")
            return

        # 反代之前先确认对面确实是我们自己启动的 Alas：端口被外部进程占着时，
        # 静默转发会让人看到「老代码 + 老数据」的假象（4.12.8）。
        conflict = ctx.guard_upstream()
        if conflict:
            log_throttled("proxy-conflict", "拒绝反代：%s" % conflict)
            await self.send_html(send, 503, "ALAS 端口被其它进程占用", conflict)
            return

        path, query = self.upstream_target(scope)

        body = await self.read_body(receive) if scope["method"] in ("POST", "PUT", "PATCH") else None

        headers = []
        host = self.header(scope, "host", "127.0.0.1")
        for key, value in scope.get("headers", []):
            name = key.decode("latin-1")
            if name.lower() in HOP_BY_HOP or name.lower() in ("host", "content-length"):
                continue
            headers.append((name, value.decode("latin-1")))
        headers.append(("Host", host))

        try:
            status, resp_headers, data = await asyncio.get_event_loop().run_in_executor(
                None, _proxy_request, scope["method"], path, query, headers, body, ctx.webui_port
            )
        except Exception as exc:  # 上游未就绪
            log("proxy http failed: %s %s (%s)" % (scope["method"], path, exc))
            await self.send_json(send, 502, {"error": "bad_gateway", "msg": str(exc)})
            return

        out = []
        for key, value in resp_headers:
            if key.lower() in HOP_BY_HOP or key.lower() == "content-length":
                continue
            out.append((key.encode("latin-1"), value.encode("latin-1")))
        out.append((b"content-length", str(len(data)).encode()))
        await send({"type": "http.response.start", "status": status, "headers": out})
        await send({"type": "http.response.body", "body": data})

    async def websocket(self, scope, receive, send):
        ctx = self.ctx
        path = self.raw_path(scope)
        if not (path == ctx.alas_path or path.startswith(ctx.alas_path + "/")):
            await send({"type": "websocket.close", "code": 1008})
            return
        if self.header(scope, "x-trim-userid") is None:
            await send({"type": "websocket.close", "code": 1008})
            return

        # 与 HTTP 反代同一道闸：端口被外部进程占着时不建连
        conflict = ctx.guard_upstream()
        if conflict:
            log_throttled("proxy-ws-conflict", "拒绝 WebSocket 反代：%s" % conflict)
            await send({"type": "websocket.close", "code": 1011})
            return

        import websockets

        await receive()  # websocket.connect
        rest, query = self.upstream_target(scope)
        uri = "ws://127.0.0.1:%d%s%s" % (ctx.webui_port, rest, ("?" + query) if query else "")
        try:
            upstream = await websockets.connect(uri, max_size=None, ping_interval=20)
        except Exception as exc:
            log("proxy ws connect failed: %s (%s)" % (uri, exc))
            await send({"type": "websocket.close", "code": 1011})
            return

        await send({"type": "websocket.accept"})

        async def client_to_upstream():
            try:
                while True:
                    message = await receive()
                    if message["type"] == "websocket.disconnect":
                        return
                    if message.get("text") is not None:
                        await upstream.send(message["text"])
                    elif message.get("bytes") is not None:
                        await upstream.send(message["bytes"])
            finally:
                await upstream.close()

        async def upstream_to_client():
            try:
                async for message in upstream:
                    if isinstance(message, bytes):
                        await send({"type": "websocket.send", "bytes": message})
                    else:
                        await send({"type": "websocket.send", "text": message})
            except Exception:
                pass
            finally:
                try:
                    await send({"type": "websocket.close", "code": 1000})
                except Exception:
                    pass

        await asyncio.gather(client_to_upstream(), upstream_to_client())


def _proxy_request(method, path, query, headers, body, port):
    """阻塞式上游请求，放到线程池执行。返回 (status, headers, body)。"""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=120)
    url = path + (("?" + query) if query else "")
    conn.putrequest(method, url, skip_host=True, skip_accept_encoding=True)
    for name, value in headers:
        conn.putheader(name, value)
    if body is not None:
        conn.putheader("Content-Length", str(len(body)))
    conn.endheaders(body if body is not None else None)
    response = conn.getresponse()
    data = response.read()
    result = (response.status, list(response.getheaders()), data)
    conn.close()
    return result


def _parse_query(query_string):
    from urllib.parse import parse_qs

    if isinstance(query_string, bytes):
        query_string = query_string.decode("latin-1")
    return {k: v[0] for k, v in parse_qs(query_string).items()}


def main():
    parser = argparse.ArgumentParser(description="Alas fnOS console backend")
    parser.add_argument("--appname")
    parser.add_argument("--appdest")
    parser.add_argument("--pkgetc")
    parser.add_argument("--pkgvar")
    parser.add_argument("--socket")
    parser.add_argument("--port", type=int)
    parser.add_argument("--autostart")
    parser.add_argument("--prepare", action="store_true", help="只做准备工作后退出")
    args = parser.parse_args()

    ctx = Context(args)
    ensure_runtime_lib(ctx)
    log("appdest=%s pkgvar=%s socket=%s prefix=%s" % (
        ctx.appdest, ctx.pkgvar, ctx.socket_path, ctx.prefix))

    if args.prepare:
        ctx.prepare()
        return 0

    ctx.prepare()
    if ctx.autostart and not ctx.process_alive():
        _status, error = ctx.start_alas()
        if error:
            log("autostart failed: %s" % error)

    if os.path.exists(ctx.socket_path):
        os.remove(ctx.socket_path)

    import uvicorn

    config = uvicorn.Config(
        app=ConsoleApp(ctx),
        uds=ctx.socket_path,
        log_level="info",
        ws_max_size=64 * 1024 * 1024,
    )
    server = uvicorn.Server(config)
    log("listening on unix socket %s" % ctx.socket_path)
    server.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())