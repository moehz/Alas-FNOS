# -*- coding: utf-8 -*-
"""Alas 脚本热更新的 fnOS 补丁实现。

背景
----
上游的「在线更新」面板（``module/webui/app.py`` 的 ``dev_update``）完全建立在 git 之上，
四个数据点无一例外：

    UI 元素              底层调用
    ------------------   ------------------------------------------------
    当前 / 上游版本号     ``updater.get_commit()``        → ``git log``
    最近 20 条更新历史    ``updater.get_commit(..., n=20)``
    「检查更新」按钮      ``updater.check_update()``      → ``git fetch``
    「立即更新」按钮      ``updater.run_update()``        → ``git_install()``

而 ``git_install()`` 最终落在 ``git reset --hard``：把工作树强制重建为上游快照。
原样照搬需要三样东西 —— ``git`` 二进制、完整 ``.git``（实测 328 MB）与可写的安装目录，
本包一个都不提供（fnOS 安装目录对应用用户只读）。

本模块的取舍
------------
**保留上游页面与流程，只替换数据来源。** 在 ``module.webui.updater`` 加载完成后，用本模块
的三个函数覆盖 ``Updater`` 的同名方法：

    ``get_commit``      读 ``alas_version.json`` / 上游版本缓存
    ``_check_update``  请求 GOC CDN 的 ``latest.json``（91 B）与本地记录比对
    ``git_install``    下载源码包 tarball → 校验 → 原子交换 ``$TRIM_PKGVAR/alas``

于是上游的按钮、进度提示、失败处理，以及基于 ``EnableReload`` 的「更新后自动重启」全部
原样生效，而我们既不需要 git，也不需要写安装目录。

更新来源与校验
--------------
版本探测**并发**请求多个端点（官方 GitHub API 在前，国内镜像在后），先返回者胜出；
因此镜像只影响速度，不影响最坏耗时。镜像返回的 commit 必须通过官方接口确认确实存在
于上游，被官方明确否认时本次「检查更新」直接报失败，而不是把一个来源可疑的 commit
写进本地记录。

下载到的源码包还有两道闸：包名必须以请求的 commit 结尾（``<repo>-<sha>``）；解压时拒绝
``..``、指向外部的链接与设备/FIFO 成员。这两道闸保证「下载源被换掉」也不会让更新落到
别的代码上。

端点列表可用 ``ALAS_FNOS_LATEST_URLS`` / ``ALAS_FNOS_TARBALL_URLS``（逗号或空白分隔）覆盖。

运行时布局
----------
    $TRIM_PKGVAR/alas                 实际使用的源码树（可写，也就是 Alas 的 cwd）
    $TRIM_PKGVAR/config, log          用户数据（被 alas/config、alas/log 软链引用）
    $TRIM_PKGVAR/alas_version.json    版本记录
    $TRIM_PKGVAR/.alas-prev-<ts>      上一次的源码树（保留一份，便于人工回退）
    $TRIM_PKGVAR/.alas-staging-<ts>   下载解压中的临时树

兼容性
------
只用标准库，且必须是 **Python 3.7** 可解析的语法（打包运行时为 CPython 3.7）。
"""

import json
import os
import queue
import re
import shutil
import ssl
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request

__all__ = ["install"]

REPO = "LmeSzinc/AzurLaneAutoScript"
BRANCH = "master"
USER_AGENT = "AlasFnosUpdater/1.0"

GITHUB_API = "https://api.github.com/repos/" + REPO

#: 官方版本端点（版本真值，同时也是交叉校验的依据）
OFFICIAL_LATEST = GITHUB_API + "/branches/" + BRANCH

#: 版本探测端点。官方在前、镜像在后；实际是并发探测、先到先得，顺序只决定「同样快时
#: 优先谁」。后两项是经 GitHub 代理的官方 API，响应形状与官方一致。
#: 可用 ALAS_FNOS_LATEST_URLS 覆盖（逗号或空白分隔）。
LATEST_URLS = (
    OFFICIAL_LATEST,
    "https://1818706573.cdn.123clouddisk.com/1818706573/pack/LmeSzinc_AzurLaneAutoScript_master/latest.json",
    "https://alas-goc-1254325529.cos.ap-shanghai.myqcloud.com/LmeSzinc_AzurLaneAutoScript_master/latest.json",
    "https://ghfast.top/" + OFFICIAL_LATEST,
    "https://gh-proxy.com/" + OFFICIAL_LATEST,
)

#: 源码包下载源，**串行**回退（官方 codeload 在前；镜像只用于加速）。
#: 可用 ALAS_FNOS_TARBALL_URLS 覆盖。
TARBALL_URLS = (
    "https://codeload.github.com/{repo}/tar.gz/{ref}",
    "https://ghfast.top/https://github.com/{repo}/archive/{ref}.tar.gz",
    "https://gh-proxy.com/https://github.com/{repo}/archive/{ref}.tar.gz",
)

#: 解压后必须存在的文件，用于判断源码包是否完整可用
REQUIRED_FILES = (
    "alas.py",
    "module/webui/app.py",
    "deploy/config.py",
    "deploy/template",
)

#: 需要软链到 PKGVAR 的运行期可写目录
LINKED_DIRS = ("config", "log")

_UPDATER_MODULE = "module.webui.updater"
_PROC_DIR = "/proc"
_REMOTE_TTL = 300.0
_HTTP_TIMEOUT = 20
_VERIFY_TIMEOUT = 8
_DOWNLOAD_TIMEOUT = 60
_CHUNK = 256 * 1024

#: 版本端点的返回值只接受 hex SHA：分支名、路径或任何其它字符串一律丢弃，
#: 避免把不可控内容拼进后面的下载 URL。
_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")

_state_lock = threading.Lock()
_pkgvar_cache = None
_remote_cache = {"at": 0.0, "info": None, "history": []}
_ssl_ctx_cache = None
_ssl_ctx_ready = False
_fallback_logged = False


# --------------------------------------------------------------------------- #
# 基础设施
# --------------------------------------------------------------------------- #


def _log(message):
    line = "[alas-fnos] %s" % (message,)
    try:
        from module.logger import logger

        logger.info(line)
    except Exception:
        sys.stderr.write(line + "\n")
        sys.stderr.flush()


def pkgvar():
    """应用数据目录（``$TRIM_PKGVAR``）的绝对路径。"""
    global _pkgvar_cache
    if _pkgvar_cache:
        return _pkgvar_cache

    value = os.environ.get("ALAS_FNOS_PKGVAR") or os.environ.get("TRIM_PKGVAR")
    if not value:
        # 回退：由 <PKGVAR>/alas/module/webui/updater.py 反推
        module = sys.modules.get(_UPDATER_MODULE)
        path = getattr(module, "__file__", None)
        if path:
            value = os.path.abspath(path)
            for _ in range(4):  # updater.py -> webui -> module -> alas -> PKGVAR
                value = os.path.dirname(value)

    if not value:
        raise RuntimeError("无法确定应用数据目录（TRIM_PKGVAR 未设置）")

    _pkgvar_cache = os.path.abspath(value)
    return _pkgvar_cache


def alas_dir():
    """实际使用的源码树目录。"""
    return os.path.join(pkgvar(), "alas")


def appdest():
    """安装目录（``$TRIM_APPDEST``）。

    只有 console_server 启动 Alas 时会设置 ``ALAS_FNOS_APPDEST``；拿不到就返回空串
    （此时不做任何回退推断 —— 源码树在 PKGVAR 里，反推不出安装目录）。
    """
    value = os.environ.get("ALAS_FNOS_APPDEST")
    return os.path.abspath(value) if value else ""


def version_file():
    return os.path.join(pkgvar(), "alas_version.json")


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def read_version():
    """运行期版本记录。

    记录缺失或不完整时回退到安装包自带的出厂记录：宁可让面板显示包内基线，
    也不要显示空白 —— 空白会让「本地版本」看起来像未知，而 console 的播种
    日志才是真正该看的地方。
    """
    global _fallback_logged
    data = _read_json(version_file())
    if data.get("base_commit"):
        return data

    root = appdest()
    if root:
        factory = _read_json(os.path.join(root, "alas_version.json"))
        if factory.get("base_commit"):
            if not _fallback_logged:
                _fallback_logged = True
                _log(
                    "运行期版本记录缺失，暂用出厂记录 %s（%s）"
                    % (factory["base_commit"][:8], version_file())
                )
            return factory
    return data


def write_version(data):
    target = version_file()
    temporary = target + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, target)


def _ssl_context():
    """HTTPS 校验上下文。

    本包的运行时是从构建镜像里拷出来的**裸解释器**：它没有系统 CA 目录
    （``/etc/ssl/certs`` 不在包内），而标准库 ``urllib`` 不认 ``certifi``。
    所以这里显式用 ``site-packages/certifi/cacert.pem`` 建上下文；
    拿不到时退回系统默认（依赖宿主机的 CA），再不行返回 ``None`` 让 urllib 自己决定。
    不做这一步的话，在缺 CA 的机器上所有 HTTPS 请求都会以证书错误失败，
    而失败又会被误判成「已是最新」—— 正是最难查的那种故障。
    """
    global _ssl_ctx_cache, _ssl_ctx_ready
    if _ssl_ctx_ready:
        return _ssl_ctx_cache
    _ssl_ctx_ready = True

    try:
        import certifi

        cafile = certifi.where()
        if cafile and os.path.exists(cafile):
            _ssl_ctx_cache = ssl.create_default_context(cafile=cafile)
            return _ssl_ctx_cache
    except Exception as exc:
        _log("certifi 不可用，退回系统 CA：%r" % (exc,))

    try:
        _ssl_ctx_cache = ssl.create_default_context()
    except Exception as exc:
        _log("无法建立 SSL 上下文：%r" % (exc,))
        _ssl_ctx_cache = None
    return _ssl_ctx_cache


def _http_get(url, timeout):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(
        request, timeout=timeout, context=_ssl_context()
    ) as response:
        return response.read()


def _http_download(url, path, timeout=_DOWNLOAD_TIMEOUT):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(
        request, timeout=timeout, context=_ssl_context()
    ) as response:
        with open(path, "wb") as handle:
            shutil.copyfileobj(response, handle, _CHUNK)


# --------------------------------------------------------------------------- #
# 版本探测
# --------------------------------------------------------------------------- #


def _env_urls(name, defaults):
    """端点列表：``$<name>`` 可覆盖默认值（逗号或空白分隔），为空则回落默认。"""
    raw = os.environ.get(name)
    if not raw:
        return tuple(defaults)
    items = tuple(part.strip() for part in raw.replace(",", " ").split() if part.strip())
    return items or tuple(defaults)


def latest_urls():
    return _env_urls("ALAS_FNOS_LATEST_URLS", LATEST_URLS)


def tarball_urls():
    return _env_urls("ALAS_FNOS_TARBALL_URLS", TARBALL_URLS)


def _valid_commit(value):
    return bool(value) and bool(_SHA_RE.match(value))


def _probe_first(urls, fetch, timeout):
    """并发请求多个端点，返回第一个成功的结果；全部失败返回 ``(None, None)``。

    串行回退的最坏耗时是「端点数 × 超时」，并发后只剩一个超时窗口。每个 worker
    无论成功还是抛异常都只投递一次结果，所以 ``results.get()`` 不会空等。
    """
    results = queue.Queue()

    def worker(url):
        try:
            results.put((True, url, fetch(url, timeout)))
        except Exception as exc:
            _log("端点探测失败 %s：%r" % (url, exc))
            results.put((False, url, None))

    for url in urls:
        thread = threading.Thread(target=worker, args=(url,), name="alas-fnos-probe")
        thread.daemon = True
        thread.start()

    for _ in urls:
        ok, url, value = results.get()
        if ok:
            return value, url
    return None, None


def _parse_latest(data):
    """解析版本探测响应，返回 ``(commit, time)``。

    兼容两种形状：

    * GOC ``latest.json`` —— ``{"commit": "<sha>", "time": "..."}``
    * GitHub ``/branches/<branch>`` —— ``{"commit": {"sha": ..., "commit": {...}}}``
    """
    if not isinstance(data, dict):
        return "", None

    commit = data.get("commit")
    if isinstance(commit, str) and commit.strip():
        return commit.strip(), data.get("time")

    if isinstance(commit, dict):
        sha = commit.get("sha")
        if isinstance(sha, str) and sha.strip():
            detail = commit.get("commit") or {}
            if not isinstance(detail, dict):
                detail = {}
            committer = detail.get("committer") or {}
            author = detail.get("author") or {}
            stamp = (committer.get("date") if isinstance(committer, dict) else None) or (
                author.get("date") if isinstance(author, dict) else None
            )
            return sha.strip(), stamp

    return "", None


def fetch_latest():
    """并发探测上游最新版本，返回 ``(commit, time, source)``。

    全部端点失败返回 ``(None, None, None)``。非 SHA 的返回值按失败处理（不计入候选），
    所以镜像即使返回分支名或别的字符串也不会被采信。
    """

    def probe(url, timeout):
        commit, stamp = _parse_latest(json.loads(_http_get(url, timeout).decode("utf-8")))
        commit = (commit or "").strip()
        if not _valid_commit(commit):
            raise ValueError("commit 非法：%r" % (commit,))
        return commit, stamp

    info, source = _probe_first(latest_urls(), probe, _HTTP_TIMEOUT)
    if not info:
        return None, None, None
    return info[0], info[1], source


def verify_commit(commit):
    """用官方接口确认 commit 确实存在于上游。

    返回 ``True``（官方确认）/ ``False``（官方明确否认）/ ``None``（不可达，无法判定）。
    只有「明确否认」才拒绝：国内访问不到官方接口时，不能被误判成「版本不存在」。
    """
    if not _valid_commit(commit):
        return False
    url = "%s/commits/%s" % (GITHUB_API, commit)
    try:
        _http_get(url, _VERIFY_TIMEOUT)
        return True
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 422):
            _log("官方接口否认该 commit：%s（HTTP %s）" % (commit[:8], exc.code))
            return False
        _log("官方接口校验返回 HTTP %s，本次不作判定" % exc.code)
        return None
    except Exception as exc:
        _log("官方接口不可达（%r），本次不作判定" % (exc,))
        return None


def _fetch_github_commits(limit=20):
    """拉取上游最近若干次提交，返回 ``[(sha, author, time, message)]``；失败返回空表。"""
    url = "%s/commits?sha=%s&per_page=%d" % (GITHUB_API, BRANCH, limit)
    try:
        data = json.loads(_http_get(url, 8).decode("utf-8"))
    except Exception as exc:
        _log("提交历史获取失败（不影响更新）：%r" % (exc,))
        return []

    rows = []
    for item in data if isinstance(data, list) else []:
        commit = item.get("commit") or {}
        author = commit.get("author") or {}
        date = (author.get("date") or "").replace("T", " ").replace("Z", "")
        message = (commit.get("message") or "").splitlines()
        rows.append(
            (
                item.get("sha") or "",
                author.get("name") or "",
                date,
                message[0] if message else "",
            )
        )
    return rows


def fetch_remote(force=False):
    """上游版本详情与提交历史（带 TTL 缓存），返回 ``(info, history)``。"""
    now = time.time()
    with _state_lock:
        cached = _remote_cache["info"]
        if not force and cached and now - _remote_cache["at"] < _REMOTE_TTL:
            return cached, list(_remote_cache["history"])

    commit, commit_time, source = fetch_latest()
    info = None
    history = []
    if commit:
        if source and source != OFFICIAL_LATEST:
            _log("上游版本来自镜像 %s：%s" % (source, commit[:8]))
        if verify_commit(commit) is False:
            _log("上游版本 %s 未获官方确认，本次丢弃该结果" % commit[:8])
            commit = ""
    if commit:
        info = (commit, "", commit_time or "", "")
        history = _fetch_github_commits()
        for row in history:
            if row[0] == commit:
                info = row
                break

    with _state_lock:
        _remote_cache["at"] = time.time()
        _remote_cache["info"] = info
        _remote_cache["history"] = history
    return info, list(history)


def _shorten(entry, short):
    if not entry or not short:
        return entry
    return ((entry[0] or "")[:7],) + tuple(entry[1:])


# --------------------------------------------------------------------------- #
# 替换 Updater 的三个方法
# --------------------------------------------------------------------------- #


def get_commit(self, revision="", n=1, short_sha1=False):
    """替代 ``Updater.get_commit``：不调用 git，改读本地记录与版本缓存。

    上游用它填充更新面板的两张表，返回 ``(sha1, author, time, message)``；
    ``n > 1`` 时返回该形状的列表。
    """
    revision = (revision or "").strip()

    if revision.startswith("origin") or revision == BRANCH:
        info, history = fetch_remote()
        if n == 1:
            return _shorten(info or ("", "", "", ""), short_sha1)
        rows = history or ([info] if info else [])
        return [_shorten(row, short_sha1) for row in rows[:n]]

    version = read_version()
    entry = (
        version.get("base_commit") or "",
        version.get("author") or "",
        version.get("base_time") or "",
        version.get("message") or "",
    )
    entry = _shorten(entry, short_sha1)
    return entry if n == 1 else [entry]


def check_update(self):
    """替代 ``Updater._check_update``：用 ``latest.json``（91 B）判断是否有更新。

    返回值直接就是 UI 状态：``True`` 有更新 / ``False`` 已是最新 / ``"failed"`` 检查失败。
    **探测不到上游时必须返回 ``"failed"``，不能返回 ``False``** —— 上游自己在这里
    返回 ``0``，于是「网络不通 / 证书校验失败」在面板上显示成「已是最新」，
    这是最容易被误判的一类故障（本次真机问题排查就从它开始）。
    """
    self.state = "checking"

    version = read_version()
    local = version.get("base_commit") or ""
    info, _history = fetch_remote(force=True)
    remote = (info[0] if info else "") or ""

    if not remote:
        _log(
            "检查更新失败：无法获取可信的上游版本"
            "（网络不可达、证书校验失败，或该 commit 未获官方接口确认），本次不作判断"
        )
        return "failed"
    if not local:
        _log("本地版本未知（%s 无记录），视为有更新" % version_file())
        return True

    behind = local != remote
    _log(
        "检查更新：本地 %s（%s）/ 上游 %s → %s"
        % (
            local[:8],
            version.get("source") or "?",
            remote[:8],
            "有更新" if behind else "已是最新",
        )
    )
    return behind


def git_install(self):
    """替代 ``Updater.git_install``：下载源码包并原子交换，等价于 ``git reset --hard``。"""
    from deploy.config import ExecutionError

    local = read_version().get("base_commit") or ""
    info, _history = fetch_remote(force=True)
    remote = (info[0] if info else "") or ""

    if not remote:
        raise ExecutionError("无法获取可信的上游版本信息（网络/证书问题，或官方校验未通过），更新中止")
    if local and local == remote:
        _log("已是最新（%s），无需更新" % remote[:8])
        return

    _log("开始更新 Alas 脚本：%s → %s" % (local[:8] or "(未知)", remote[:8]))
    staging = _download_and_extract(remote)
    try:
        _validate(staging)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    _swap(staging)
    write_version(
        {
            "base_commit": remote,
            "base_time": (info[2] if info else "") or "",
            "message": (info[3] if info else "") or "",
            "author": (info[1] if info else "") or "",
            "source": "update",
            "updated_at": int(time.time()),
        }
    )
    _log("更新完成：%s（旧版本保留在 .alas-prev-*）" % remote[:8])


# --------------------------------------------------------------------------- #
# 下载 / 解压 / 校验 / 交换
# --------------------------------------------------------------------------- #


def _download_and_extract(commit):
    var = pkgvar()
    staging = os.path.join(var, ".alas-staging-%d" % int(time.time()))
    archive = os.path.join(var, ".alas-download.tar.gz")
    last_error = None

    for template in tarball_urls():
        url = template.format(repo=REPO, ref=commit)
        shutil.rmtree(staging, ignore_errors=True)
        os.makedirs(staging)
        try:
            _log("下载源码包：%s" % url)
            _http_download(url, archive)
            _extract(archive, staging, commit)
            _log(
                "源码包就绪：%s（%.1f MB）"
                % (staging, _tree_size(staging) / 1024.0 / 1024.0)
            )
            return staging
        except Exception as exc:
            last_error = exc
            _log("下载源失败 %s：%r" % (url, exc))
        finally:
            if os.path.exists(archive):
                os.remove(archive)

    shutil.rmtree(staging, ignore_errors=True)
    from deploy.config import ExecutionError

    raise ExecutionError("源码包下载失败：%r" % (last_error,))


def _top_level(members):
    """源码包的顶层目录（形如 ``AzurLaneAutoScript-<sha>/``）。"""
    for member in members:
        head = member.name.lstrip("./").split("/", 1)
        if len(head) == 2 and head[0]:
            return head[0] + "/"
    raise RuntimeError("源码包结构异常：找不到顶层目录")


def _extract(archive, destination, commit=""):
    """解压源码包并剥掉顶层目录；拒绝越界路径、外部链接与特殊文件。

    顶层目录必须对应本次请求的 commit（GitHub 的包名形如 ``<repo>-<sha>``）：
    这样即便下载源被换成了缓存或镜像，也无法把一个「别的版本」的包塞进更新流程。
    """
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        prefix = _top_level(members)
        suffix = prefix.rstrip("/").rsplit("-", 1)[-1]
        if commit and not (suffix == commit or suffix.startswith(commit)):
            raise RuntimeError(
                "源码包与请求的版本不符：包内 %s / 请求 %s" % (suffix[:12], commit[:12])
            )
        for member in members:
            if not member.name.startswith(prefix):
                continue
            relative = member.name[len(prefix):].lstrip("/")
            if not relative:
                continue
            parts = relative.split("/")
            if ".." in parts:
                continue
            # 设备文件 / FIFO：源码包不该有，直接丢弃
            if member.isdev() or member.isfifo():
                continue
            if member.issym() or member.islnk():
                target = (member.linkname or "").replace("\\", "/")
                if target.startswith("/") or ".." in target.split("/"):
                    continue
            member.name = relative
            tar.extract(member, destination)


def _validate(tree):
    """确认源码包关键文件齐备；缺失则视为下载不完整。"""
    missing = [
        relative
        for relative in REQUIRED_FILES
        if not os.path.exists(os.path.join(tree, relative))
    ]
    if missing:
        from deploy.config import ExecutionError

        raise ExecutionError("源码包校验失败：缺少 %s" % "、".join(missing))


def _merge_seed(source, destination):
    """把种子目录里缺失的文件补进目标目录（不覆盖已有文件）。"""
    for root, _dirs, files in os.walk(source):
        relative = os.path.relpath(root, source)
        out = destination if relative == "." else os.path.join(destination, relative)
        os.makedirs(out, exist_ok=True)
        for name in files:
            target = os.path.join(out, name)
            if not os.path.exists(target):
                shutil.copyfile(os.path.join(root, name), target)


def _relink_dirs(tree, var):
    """把新源码树里的 ``config`` / ``log`` 重新指回 PKGVAR（保留用户数据）。"""
    for name in LINKED_DIRS:
        source = os.path.join(tree, name)
        destination = os.path.join(var, name)
        os.makedirs(destination, exist_ok=True)
        if os.path.islink(source):
            if os.path.realpath(source) == os.path.realpath(destination):
                continue
            os.unlink(source)
        elif os.path.isdir(source):
            _merge_seed(source, destination)
            shutil.rmtree(source, ignore_errors=True)
        elif os.path.exists(source):
            os.remove(source)
        os.symlink(destination, source)


def _swap(staging):
    """把暂存树换成正式源码树；旧树留作备份，任一步失败即回滚。"""
    var = pkgvar()
    current = os.path.join(var, "alas")
    previous = os.path.join(var, ".alas-prev-%d" % int(time.time()))

    replaced = False
    try:
        if os.path.exists(current) or os.path.islink(current):
            os.replace(current, previous)
            replaced = True
        os.replace(staging, current)
    except Exception:
        if replaced and not os.path.exists(current):
            os.replace(previous, current)
        raise

    try:
        _relink_dirs(current, var)
    except Exception as exc:
        _log("重建 config/log 软链失败（不影响代码更新）：%r" % (exc,))

    # 必须在 _prune 之前：当前进程（webui）的 cwd 还钉在旧树的 inode 上，
    # 不 reanchor 的话，更新收尾写 ./config/reloadalas 等相对路径全部落空
    # （FileNotFoundError，4.12.9 真机实锤）。
    _reanchor_cwd(current)

    _prune(var, keep=current)
    return previous


def _reanchor_cwd(target):
    """把当前进程的工作目录重新锚定到新源码树。

    源码树是整体 ``os.replace`` 换进来的：进程 cwd 仍指向旧目录 inode，
    与路径无关。必须显式 ``chdir`` 才能恢复 "cwd == $PKGVAR/alas" 的语义。"""
    try:
        if os.path.realpath(os.getcwd()) == os.path.realpath(target):
            return
        os.chdir(target)
        _log("工作目录已重新锚定：%s" % target)
    except OSError as exc:
        _log("重新锚定工作目录失败（可能影响更新收尾）：%r" % (exc,))


def _heal_cwd():
    """修复 fork 出的新进程继承到的失效 cwd（更新换树所致）。

    gui.py 的 EnableReload 重启循环是 **fork**：子进程继承父进程 cwd，而父进程
    的 cwd 永远钉在最初那棵源码树的 inode 上（换树后已不可用）。sitecustomize
    不会在 fork 子进程里重跑，只能靠 import hook：uvicorn / updater 首次导入时
    锚回 $PKGVAR/alas——这发生在 webui 读写任何相对路径文件之前。"""
    var = os.environ.get("ALAS_FNOS_PKGVAR")
    if not var:
        return
    target = os.path.join(var, "alas")
    if not os.path.isdir(target):
        return
    try:
        current = os.getcwd()
    except OSError:
        current = None
    if current is not None and os.path.realpath(current) == os.path.realpath(target):
        return
    try:
        os.chdir(target)
        _log("进程 cwd 已失效，重新锚定：%s" % target)
    except OSError as exc:
        _log("cwd 修复失败：%r" % (exc,))


def _cwd_holders(path, proc_dir=None):
    """返回 cwd 位于 path 之内（含自身）的进程 pid 列表（Linux /proc）。"""
    real = os.path.realpath(path)
    if not real.endswith(os.sep):
        real += os.sep
    holders = []
    try:
        names = os.listdir(proc_dir or _PROC_DIR)
    except OSError:
        return holders
    for name in names:
        if not name.isdigit():
            continue
        try:
            cwd = os.readlink(os.path.join(proc_dir or _PROC_DIR, name, "cwd"))
        except OSError:
            continue
        cwd = cwd.split(" (deleted)")[0].rstrip(os.sep)
        if not cwd:
            continue
        # 两侧都归一化：/proc 链接原文可能是未解析的路径（macOS 测试/软链环境）
        cwd = os.path.realpath(cwd)
        if not cwd.endswith(os.sep):
            cwd += os.sep
        if cwd == real or cwd.startswith(real):
            holders.append(name)
    return holders


def _prune(var, keep):
    """只保留最近一份源码树，避免数据目录被临时目录撑满（每份约 150 MB）。"""
    prefixes = (".alas-prev-", ".alas-staging-", ".alas-download")
    keep = os.path.abspath(keep)
    try:
        names = os.listdir(var)
    except OSError:
        return

    for name in names:
        if not name.startswith(prefixes):
            continue
        path = os.path.join(var, name)
        if os.path.abspath(path) == keep:
            continue
        # gui.py 父进程的 cwd 永远钉在最初那棵树的 inode（即最老的 .alas-prev-*），
        # rmtree 它会让 fork 出的新进程继承到失效 cwd——凡是仍被占用的目录跳过。
        holders = []
        try:
            holders = _cwd_holders(path)
        except Exception as exc:
            _log("检测 %s 的 cwd 占用失败，保守跳过：%r" % (name, exc))
            continue
        if holders:
            _log(
                "跳过清理 %s：仍有进程以其为工作目录（pid=%s）"
                % (name, ",".join(holders[:5]))
            )
            continue
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                os.remove(path)
        except Exception:
            pass


def _tree_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


# --------------------------------------------------------------------------- #
# 装配（import hook / uvicorn 补丁 / 缓存预热）
# --------------------------------------------------------------------------- #


class _LoaderProxy(object):
    """包一层 loader，在原模块执行完成后立刻打补丁。"""

    def __init__(self, inner):
        self._inner = inner

    def create_module(self, spec):
        create = getattr(self._inner, "create_module", None)
        return create(spec) if create else None

    def exec_module(self, module):
        self._inner.exec_module(module)
        try:
            _patch_updater(module)
        except Exception as exc:
            _log("替换更新方法失败：%r" % (exc,))

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _UpdaterFinder(object):
    """在 ``module.webui.updater`` 被加载时接管它的 loader（只用一次）。"""

    def find_spec(self, fullname, path=None, target=None):
        if fullname != _UPDATER_MODULE:
            return None
        try:
            sys.meta_path.remove(self)
        except ValueError:
            pass

        for finder in list(sys.meta_path):
            find_spec = getattr(finder, "find_spec", None)
            if find_spec is None:
                continue
            spec = find_spec(fullname, path, target)
            if spec is not None:
                if spec.loader is not None:
                    spec.loader = _LoaderProxy(spec.loader)
                return spec
        return None


def _patch_updater(module):
    updater_class = getattr(module, "Updater", None)
    if updater_class is None:
        _log("未找到 Updater 类，跳过接管")
        return
    if getattr(updater_class, "_alas_fnos_patched", False):
        return

    updater_class.get_commit = get_commit
    updater_class._check_update = check_update
    updater_class.git_install = git_install
    updater_class._alas_fnos_patched = True
    _log("已接管更新面板：get_commit / _check_update / git_install")


def _patch_uvicorn():
    """上游 gui.py 直接调 ``uvicorn.run``，这里补回我们需要的 WebSocket 上限。"""
    try:
        import uvicorn
    except Exception:
        return

    original = uvicorn.run
    if getattr(original, "_alas_fnos_patched", False):
        return

    def run(*args, **kwargs):
        kwargs.setdefault("ws_max_size", 64 * 1024 * 1024)
        return original(*args, **kwargs)

    run._alas_fnos_patched = True
    uvicorn.run = run


def _warmup_remote_cache():
    """后台预热上游版本缓存，避免首次渲染更新面板时等待网络。"""

    def worker():
        time.sleep(6)
        try:
            fetch_remote(force=True)
        except Exception:
            pass

    thread = threading.Thread(target=worker, name="alas-fnos-warmup")
    thread.daemon = True
    thread.start()


class _CwdHealFinder(object):
    """在 ``uvicorn`` / ``module.webui.updater`` 首次导入前执行一次 cwd 自愈。

    选 ``uvicorn`` 是因为它是 fork 出的新 webui 进程最先导入的第三方模块，
    早于 webui 的一切文件 IO。"""

    def find_spec(self, fullname, path=None, target=None):
        if fullname not in ("uvicorn", _UPDATER_MODULE):
            return None
        try:
            sys.meta_path.remove(self)
        except ValueError:
            pass
        try:
            _heal_cwd()
        except Exception as exc:
            _log("cwd 自愈异常：%r" % (exc,))
        return None


def install():
    """注册 import hook、补丁与缓存预热（同一进程内幂等）。"""
    _patch_uvicorn()

    if not any(isinstance(finder, _CwdHealFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _CwdHealFinder())

    if not any(isinstance(finder, _UpdaterFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _UpdaterFinder())
        _warmup_remote_cache()
