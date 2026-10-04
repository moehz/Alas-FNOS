#!/bin/bash
# diagnose-update.sh —— 在 fnOS 设备上排查 Alas「更新面板」的问题
#
# 用法（在设备上执行，只读，不改任何东西）：
#   bash diagnose-update.sh
#
# 它会依次打印：
#   1. 应用安装目录 / 数据目录 / 正在跑的进程与启动时间
#   2. 包内版本记录 vs 运行期版本记录（更新面板「本地版本」的来源）
#   3. console.log 里 seed_alas() 的播种决策（重播？沿用？）
#   4. Alas 日志里补丁留下的 [alas-fnos] 行（补丁是否生效的铁证）
#   5. 用包内 CPython 实测版本探测端点的连通性与证书
#   6. 补丁文件、旧源码树、后台回滚点是否就位
#
# 判断口径见 deploy/fnos/HANDOFF.md 4.12。
set -u

APPNAME="${TRIM_APPNAME:-azurlaneautoscript}"

line() { printf '\n=== %s ===\n' "$1"; }
getenv() { tr '\0' '\n' <"/proc/$1/environ" 2>/dev/null | sed -n "s/^$2=//p" | head -n1; }

CONSOLE_PID="$(pgrep -f 'server/console_server.py' 2>/dev/null | head -n1 || true)"
ALAS_PID="$(pgrep -f "/alas/gui.py" 2>/dev/null | head -n1 || true)"

APPDEST=""; PKGVAR=""
if [ -n "$CONSOLE_PID" ]; then
  APPDEST="$(getenv "$CONSOLE_PID" TRIM_APPDEST)"
  PKGVAR="$(getenv "$CONSOLE_PID" TRIM_PKGVAR)"
fi
[ -n "$PKGVAR" ] || PKGVAR="$(getenv "$ALAS_PID" ALAS_FNOS_PKGVAR)"
[ -n "$APPDEST" ] || APPDEST="$(getenv "$ALAS_PID" ALAS_FNOS_APPDEST)"

if [ -z "$PKGVAR" ]; then
  for p in /vol*/@appdata/"$APPNAME" /vol*/@appcenter/"$APPNAME"/var /var/apps/"$APPNAME"/var; do
    [ -d "$p" ] && PKGVAR="$p" && break
  done
fi
if [ -z "$APPDEST" ]; then
  for p in /vol*/@appcenter/"$APPNAME"/target /var/apps/"$APPNAME"/target; do
    [ -d "$p" ] && APPDEST="$p" && break
  done
fi

line "0) 基本定位"
echo "  console pid : ${CONSOLE_PID:-（未运行）}"
echo "  alas    pid : ${ALAS_PID:-（未运行）}"
echo "  APPDEST     : ${APPDEST:-（未定位到）}"
echo "  PKGVAR      : ${PKGVAR:-（未定位到）}"
for pid in "$CONSOLE_PID" "$ALAS_PID"; do
  [ -n "$pid" ] && echo "  pid $pid 启动于 : $(ps -o lstart= -p "$pid" 2>/dev/null | sed 's/^ *//')"
done
[ -n "$APPDEST" ] && [ -e "$APPDEST/manifest" ] && \
  echo "  manifest    : $(stat -c '%y  %s B' "$APPDEST/manifest" 2>/dev/null)"

if [ -n "$APPDEST" ]; then
  line "1) 应用版本（应用中心里显示的）"
  sed -n 's/^version[[:space:]]*=[[:space:]]*/  version = /p' "$APPDEST/manifest" 2>/dev/null || echo "  读不到 manifest"
fi

line "2) 版本记录对比（更新面板「本地版本」的来源）"
if [ -n "$APPDEST" ]; then
  echo "  包内  $APPDEST/alas_version.json:"
  cat "$APPDEST/alas_version.json" 2>/dev/null | sed 's/^/    /' || echo "    （缺失）"
fi
if [ -n "$PKGVAR" ]; then
  echo "  运行  $PKGVAR/alas_version.json:"
  cat "$PKGVAR/alas_version.json" 2>/dev/null | sed 's/^/    /' || echo "    （缺失）"
fi

line "3) console.log 里的播种决策（最近 20 行相关记录）"
if [ -n "$PKGVAR" ] && [ -f "$PKGVAR/console.log" ]; then
  grep -n "alas " "$PKGVAR/console.log" 2>/dev/null | tail -n 20 | sed 's/^/  /'
  echo "  --- 启动 Alas 用的命令 ---"
  grep -n "start alas:" "$PKGVAR/console.log" 2>/dev/null | tail -n 2 | sed 's/^/  /'
else
  echo "  （无 $PKGVAR/console.log）"
fi

line "4) 补丁是否生效（Alas 日志里的 [alas-fnos] 行）"
FOUND=0
if [ -n "$PKGVAR" ]; then
  for f in $(ls -t "$PKGVAR"/log/*.txt "$PKGVAR"/log/*.log "$PKGVAR"/alas.log 2>/dev/null | head -n 5); do
    if grep -q "alas-fnos" "$f" 2>/dev/null; then
      echo "  $f:"
      grep -a "alas-fnos" "$f" | tail -n 8 | sed 's/^/    /'
      FOUND=1
    fi
  done
fi
if [ "$FOUND" -eq 0 ]; then
  echo "  ⚠ 没有找到任何 [alas-fnos] 行 —— 说明补丁没生效（PYTHONPATH / patch 目录问题），"
  echo "    或者面板打开后还没触发过检查。请先在 Alas 界面上打开「更新」面板再重跑本脚本。"
fi

line "5) 版本探测联通性（用包内 CPython 实测）"
if [ -n "$APPDEST" ] && [ -x "$APPDEST/runtime/bin/python3.7" ]; then
  LD_LIBRARY_PATH="$APPDEST/runtime/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    "$APPDEST/runtime/bin/python3.7" - <<'PY' 2>&1 | sed 's/^/  /'
import json, ssl, time, urllib.request
print("默认 CA:", ssl.get_default_verify_paths())
try:
    import certifi
    print("certifi :", certifi.where())
except Exception as exc:
    print("certifi : 不可用 %r" % (exc,))
urls = (
    "https://1818706573.cdn.123clouddisk.com/1818706573/pack/LmeSzinc_AzurLaneAutoScript_master/latest.json",
    "https://alas-goc-1254325529.cos.ap-shanghai.myqcloud.com/LmeSzinc_AzurLaneAutoScript_master/latest.json",
    "https://api.github.com/repos/LmeSzinc/AzurLaneAutoScript/branches/master",
)
for url in urls:
    start = time.time()
    try:
        raw = urllib.request.urlopen(url, timeout=15).read()
        commit = ""
        try:
            data = json.loads(raw.decode("utf-8"))
            c = data.get("commit")
            commit = c if isinstance(c, str) else (c or {}).get("sha", "")
        except Exception:
            pass
        print("OK   %5.2fs %s  %s" % (time.time() - start, (commit or raw[:40])[:40], url[:60]))
    except Exception as exc:
        print("FAIL %5.2fs %r  %s" % (time.time() - start, exc, url[:60]))
PY
else
  echo "  （找不到 $APPDEST/runtime/bin/python3.7）"
fi

line "6) 补丁文件 / 旧源码树 / 临时目录"
if [ -n "$APPDEST" ]; then
  ls -l "$APPDEST/patch/" 2>/dev/null | sed 's/^/  /' || echo "  缺少 $APPDEST/patch/"
fi
if [ -n "$PKGVAR" ]; then
  for d in "$PKGVAR"/alas "$PKGVAR"/.alas-prev-* "$PKGVAR"/.alas-staging-* "$PKGVAR"/.upgrade-restart-pending; do
    [ -e "$d" ] && echo "  $(stat -c '%y  %n' "$d" 2>/dev/null)"
  done
  echo "  --- PKGVAR 根目录 ---"
  ls -la "$PKGVAR" 2>/dev/null | sed 's/^/  /'
fi

line "7) 卸载/重装疑点（@appdata 全卷扫描 / 僵尸进程 / 端口占用）"
echo "  --- 所有卷上的 @appdata/$APPNAME ---"
FOUND_DATA=0
for d in /vol*/@appdata/"$APPNAME"; do
  [ -e "$d" ] || continue
  FOUND_DATA=1
  echo "  [$d]"
  ls -la "$d" 2>/dev/null | sed 's/^/    /'
  if [ -f "$d/alas_version.json" ]; then
    echo "    alas_version.json:"
    sed 's/^/      /' "$d/alas_version.json"
  fi
  if [ -d "$d/config" ]; then
    echo "    config/ 内容（有没有你导入的文件，看这里）："
    ls -la "$d/config" 2>/dev/null | tail -n +2 | sed 's/^/      /'
  fi
done
[ "$FOUND_DATA" -eq 0 ] && echo "  （没有任何卷上存在 @appdata/$APPNAME —— 数据目录确已被清空）"
echo "  --- 僵尸进程检测（cwd 一栏出现 (deleted) = 老进程没死、还在服务面板）---"
for pid in "$ALAS_PID" "$CONSOLE_PID"; do
  [ -n "$pid" ] || continue
  echo "  pid $pid cwd : $(readlink /proc/$pid/cwd 2>/dev/null || echo '读不到')"
  echo "  pid $pid 启动 : $(ps -o lstart= -p "$pid" 2>/dev/null | sed 's/^ *//')"
done
echo "  --- 22267 端口占用者（谁在服务你看到的页面）---"
if command -v ss >/dev/null 2>&1; then
  ss -tlnp 2>/dev/null | grep 22267 | sed 's/^/  /' || echo "  （未监听）"
elif command -v netstat >/dev/null 2>&1; then
  netstat -tlnp 2>/dev/null | grep 22267 | sed 's/^/  /' || echo "  （未监听）"
fi
echo "  --- 卸载审计日志（上次卸载到底删了什么）---"
[ -f "/tmp/$APPNAME-uninstall.log" ] && sed 's/^/  /' "/tmp/$APPNAME-uninstall.log" || echo "  （无 /tmp/$APPNAME-uninstall.log —— 旧版卸载脚本没有留痕）"

printf '\n=== 完 ===\n'
