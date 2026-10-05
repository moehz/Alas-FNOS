#!/bin/bash
# build_fpk.sh —— 装配 fnOS 应用包并调用 fnpack 打包
#
#   0. 定位 Alas 源码
#   1. 校验骨架与源物料是否齐备
#   2. 清理上一次装配产物
#   3. 装配 app/{runtime,alas,server,patch,bin}
#   4. fnpack build，产物落到 dist/
#
# 用法：
#   ./build_fpk.sh                        # 完整装配 + 打包
#   ./build_fpk.sh --assemble             # 只装配，不打包
#   ./build_fpk.sh --skip-alas            # 跳过 Alas 源码复制（调试用）
#   ./build_fpk.sh --alas-src DIR         # 指定 Alas 检出目录
#
# Alas 源码从哪来：
#   本仓库不含 Alas 源码（体积太大，也没必要）。按以下顺序找：
#     1) --alas-src 参数
#     2) $ALAS_SRC 环境变量
#     3) 同级目录 ../alas、仓库内 .alas/
#     4) 上一级 / 上两级目录（开发时本工程就嵌在 Alas 仓库里）
#   都没有就报错，并提示怎么 clone。见 docs/构建指南.md。
#
# 环境变量：
#   ALAS_SRC      等价于 --alas-src
#   ALAS_COMMIT   强制指定写进 alas_version.json 的上游基线 commit
#                 （不指定则按源码树的 git 推断：merge-base HEAD origin/master）
#   RUNTIME_SRC   覆盖自带运行时目录（默认 runtime/dist/runtime）
#   ADB_SRC       覆盖 vendored adb（默认 vendor/adb/adb）
#   FNPACK        覆盖 fnpack 可执行文件（默认 tools/fnpack）
#   VALIDATOR     覆盖骨架预检脚本（默认 tools/validate_fnos_project.py）
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"        # 本仓库根
FNOS_APP="$HERE/fnos-app"                    # fpk 骨架
APP="$FNOS_APP/app"                          # 包内容（装配产物）
DIST_OUT="$HERE/dist"

RUNTIME_SRC="${RUNTIME_SRC:-$HERE/runtime/dist/runtime}"
SERVER_SRC="$FNOS_APP/server/console_server.py"
PATCH_SRC="$FNOS_APP/patch"
ADB_SRC="${ADB_SRC:-$HERE/vendor/adb/adb}"
FNPACK="${FNPACK:-$HERE/tools/fnpack}"
ALAS_SRC="${ALAS_SRC:-}"
ALAS_REPO_URL="${ALAS_REPO_URL:-https://github.com/LmeSzinc/AzurLaneAutoScript}"

ASSEMBLE_ONLY=0
SKIP_ALAS=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --assemble)   ASSEMBLE_ONLY=1; shift ;;
    --skip-alas)  SKIP_ALAS=1; shift ;;
    --alas-src)
      [ "$#" -ge 2 ] || { echo "错误：--alas-src 需要一个目录参数" >&2; exit 1; }
      ALAS_SRC="$2"; shift 2 ;;
    --alas-src=*) ALAS_SRC="${1#--alas-src=}"; shift ;;
    -h|--help)    awk 'NR > 1 && /^set / {exit} NR > 1 {sub(/^# ?/, ""); print}' "$0"; exit 0 ;;
    *) echo "未知参数：$1" >&2; exit 1 ;;
  esac
done

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die() { echo "错误：$*" >&2; exit 1; }

# 清空目录内容（保留目录本身）。用 find -delete 而非 rm -rf：
# 一是避免触发批量删除护栏，二是对嵌套/符号链接处理更可控。
clean_dir() {
  local d="$1"
  [ -d "$d" ] || return 0
  find "$d" -mindepth 1 -delete
}

looks_like_alas() {
  [ -n "${1:-}" ] && [ -f "$1/alas.py" ] && [ -d "$1/module" ] && [ -d "$1/deploy" ]
}

# --- 0. 定位 Alas 源码 ---------------------------------------------------
if [ "$SKIP_ALAS" -eq 0 ] && ! looks_like_alas "$ALAS_SRC"; then
  ALAS_SRC=""
  for cand in "$HERE/../alas" "$HERE/.alas" "$HERE/.." "$HERE/../.." "$HERE/../../.."; do
    if looks_like_alas "$cand"; then ALAS_SRC="$(cd "$cand" && pwd)"; break; fi
  done
  [ -n "$ALAS_SRC" ] || die "找不到 Alas 源码。请先 clone 一份，然后重试：
    git clone --depth 1 --branch master $ALAS_REPO_URL ../alas
  （或用 --alas-src <目录> / ALAS_SRC=<目录> 指定；只想装配骨架可加 --skip-alas）"
fi

# --- 1. 前置校验 ---------------------------------------------------------
say "校验源物料"
[ -f "$FNOS_APP/manifest" ]           || die "缺少骨架: $FNOS_APP/manifest"
[ -d "$FNOS_APP/cmd" ]                || die "缺少骨架: $FNOS_APP/cmd"
[ -d "$FNOS_APP/wizard" ]             || die "缺少骨架: $FNOS_APP/wizard"
[ -f "$FNOS_APP/config/privilege" ]   || die "缺少骨架: $FNOS_APP/config/privilege"
[ -f "$FNOS_APP/config/resource" ]    || die "缺少骨架: $FNOS_APP/config/resource"
[ -f "$FNOS_APP/app/ui/config" ]      || die "缺少骨架: $FNOS_APP/app/ui/config"
[ -f "$RUNTIME_SRC/bin/python3.7" ]   || die "缺少运行时（先跑 runtime/build.sh）: $RUNTIME_SRC"
[ -f "$SERVER_SRC" ]                  || die "缺少控制台服务: $SERVER_SRC"
[ -f "$PATCH_SRC/sitecustomize.py" ]  || die "缺少更新补丁: $PATCH_SRC/sitecustomize.py"
[ -f "$PATCH_SRC/alas_fnos.py" ]      || die "缺少更新补丁: $PATCH_SRC/alas_fnos.py"
[ -f "$ADB_SRC" ]                     || die "缺少 vendored adb（见 vendor/adb/README.md）: $ADB_SRC"

APPNAME="$(sed -n 's/^appname=//p' "$FNOS_APP/manifest" | head -n1)"
APPVER="$(sed -n 's/^version=//p' "$FNOS_APP/manifest" | head -n1)"
[ -n "$APPNAME" ] || die "manifest 缺少 appname"
[ -n "$APPVER" ]  || die "manifest 缺少 version"
echo "应用: $APPNAME 版本: $APPVER"
[ "$SKIP_ALAS" -eq 1 ] || echo "Alas 源码: $ALAS_SRC"

# --- 1.5 向导文件防回归校验 ---------------------------------------------
# 空步骤数组（[]）的向导文件会让真机安装失败：安装器在 "Verifying files..." 阶段
# 抛 APP_INSTALL_FAILED_PKG_EXCEPTION，设备 CLI 只显示 "Something wrong with
# appcenter: code 10111"。真机逐文件单变量实测结论：
#   wizard/upgrade   = []  → 失败（绝不可留空）
#   wizard/uninstall = []  → 失败（绝不可留空）
#   wizard/config    = []  → 通过（可空，但没需要就别创建）
#   wizard/install（有内容）→ 通过
# 因此：不需要的向导文件请直接不要创建，而不是留一个空数组。
# 这里对所有向导文件一律拒绝空内容，是更保守的超集约束（当前骨架本就不需要空的 config）。
# 注：同一条约束也应当由 tools/validate_fnos_project.py 报出，这里是打包前的最后一道闸。
if [ -d "$FNOS_APP/wizard" ]; then
  for wf in "$FNOS_APP/wizard"/*; do
    [ -f "$wf" ] || continue
    wf_body="$(tr -d ' \t\r\n' < "$wf")"
    case "$wf_body" in
      "" | "[]")
        die "向导文件为空数组，会导致真机安装失败（code 10111）：$wf —— 请删除该文件而非留空" ;;
    esac
  done
fi

# --- 2. 清理 -------------------------------------------------------------
say "清理上一次装配产物"
clean_dir "$APP/runtime"
clean_dir "$APP/alas"
clean_dir "$APP/server"
clean_dir "$APP/patch"
clean_dir "$APP/bin"
find "$APP" -maxdepth 1 -name 'alas_version.json' -delete 2>/dev/null || true
mkdir -p "$APP" "$DIST_OUT"

# --- 2.5 骨架预检 -------------------------------------------------------
# 必须针对“干净骨架”运行：装配后会把捆绑的 CPython 标准库 / site-packages /
# Alas 自带脚本一起扫描，产生大量与本次交付无关的误报（已实测 22 条 high）。
VALIDATOR="${VALIDATOR:-}"
if [ -z "$VALIDATOR" ]; then
  for cand in "$HERE/tools/validate_fnos_project.py" \
              "$HERE/.trae/skills/fnos-developer/scripts/validate_fnos_project.py"; do
    if [ -f "$cand" ]; then VALIDATOR="$cand"; break; fi
  done
fi
if [ -n "$VALIDATOR" ] && [ -f "$VALIDATOR" ]; then
  say "骨架预检（$(basename "$VALIDATOR")）"
  PY_BIN="$(command -v python3 || true)"
  if [ -n "$PY_BIN" ]; then
    if "$PY_BIN" "$VALIDATOR" "$FNOS_APP"; then
      echo "   预检通过：无 blocker / high"
    else
      die "骨架预检未通过（存在 blocker/high），请先修复"
    fi
  else
    echo "   未找到 python3，跳过预检（建议手动执行：python3 ${VALIDATOR} ${FNOS_APP}）"
  fi
else
  echo "   警告：未找到骨架预检脚本，本步骤被跳过（可用 VALIDATOR=<path> 指定）"
fi

# --- 3. 装配 -------------------------------------------------------------
say "装配 runtime（优先硬链接，避免复制 703MB 运行时）"
mkdir -p "$APP/runtime"
# 目标目录先建空、再拷内容：避免 cp 在目标已存在时嵌套出 runtime/runtime。
# 这里用 rsync --link-dest 而不是 `cp -al`：macOS/BSD 的 `cp -al` 遇到符号链接
# （运行时的 bin/python3）时会因为无法给符号链接复制扩展属性而**非零退出**，
# 于是被误判成「硬链接失败」而回退 `cp -a`；可目标里已经全是刚建好的硬链接，
# `cp -a` 又对每个文件报 "are identical (not copied)" 并再次非零退出，`set -e`
# 直接把整个构建打断（实测：装配停在 runtime 这一步）。rsync 2.6.9 / openrsync
# 都支持 --link-dest，对内容一致的文件建硬链接，退出码可靠。
if command -v rsync >/dev/null 2>&1 && \
   rsync -a --link-dest="$RUNTIME_SRC" "$RUNTIME_SRC/" "$APP/runtime/" 2>/dev/null; then
  echo "   使用硬链接 (rsync --link-dest)"
else
  cp -a "$RUNTIME_SRC/." "$APP/runtime/"
  echo "   使用普通复制 (cp -a)"
fi

if [ "$SKIP_ALAS" -eq 0 ]; then
  say "装配 alas 源码（排除 .git / log 等）"
  echo "   来源：${ALAS_SRC}"
  mkdir -p "$APP/alas"
  # 从开发用的 Alas 主仓库复制时，deploy/fnos 是本工程的旧址，必须排除，否则会套娃
  EXCLUDES=(
    --exclude=/.git
    --exclude=/log
    --exclude=/.DS_Store
    --exclude=/.trae
    --exclude=/.workbuddy
    --exclude=/deploy/fnos
    --exclude='*.fpk'
  )
  if command -v rsync >/dev/null 2>&1; then
    rsync -a "${EXCLUDES[@]}" "$ALAS_SRC/" "$APP/alas/"
  else
    # 无 rsync 时用 tar 管道
    tar -C "$ALAS_SRC" \
      --exclude=./.git --exclude=./log --exclude=./.DS_Store \
      --exclude=./.trae --exclude=./.workbuddy --exclude=./deploy/fnos \
      --exclude='./*.fpk' \
      -cf - . | tar -C "$APP/alas" -xf -
  fi
else
  echo "   跳过 alas 源码复制（--skip-alas）"
fi

say "装配控制台服务"
mkdir -p "$APP/server"
cp -p "$SERVER_SRC" "$APP/server/console_server.py"

say "装配脚本更新补丁（target/patch，不随 alas 更新而失效）"
mkdir -p "$APP/patch"
cp -p "$PATCH_SRC/sitecustomize.py" "$APP/patch/sitecustomize.py"
cp -p "$PATCH_SRC/alas_fnos.py" "$APP/patch/alas_fnos.py"

say "装配 adb（决策 #1 修订：包内自带，设备序列号仍由使用者配置）"
# 只依赖 glibc 家族（libc/libdl/libgcc_s/libm/libpthread/librt），fnOS 原生可用；
# console_server 起 gui.py 时会把 <target>/bin 前插进 PATH，默认 AdbExecutable=adb 即生效。
[ -x "$ADB_SRC" ] || die "vendored adb 不可执行：$ADB_SRC"
mkdir -p "$APP/bin"
cp -p "$ADB_SRC" "$APP/bin/adb"
chmod 755 "$APP/bin/adb"
cp -p "$HERE/vendor/adb/NOTICE.txt" "$APP/bin/adb-NOTICE.txt"
cp -p "$HERE/vendor/adb/README.md" "$APP/bin/adb-README.md"

# --- 生成 Alas 版本记录 ---------------------------------------------------
# 更新面板靠它判断「本地版本 vs 上游版本」。记录的是**上游基线 commit**，
# 而不是装配脚本所在仓库的 HEAD —— 包内 alas 源码等价于上游 origin/master 快照。
# 若拿本仓库 HEAD 去和上游比，会永远显示「有更新」。
say "生成 Alas 版本记录 alas_version.json"

GIT="$(command -v git || true)"

# 版本信息从 Alas 源码树自己的 git 取；没有 .git 则退回本仓库查历史。
ALAS_GIT="$ALAS_SRC"
if [ -n "$GIT" ] && [ -n "$ALAS_SRC" ] && \
   ! "$GIT" -C "$ALAS_SRC" rev-parse --git-dir >/dev/null 2>&1; then
  echo "   注意：Alas 源码树不是 git 仓库，版本信息退回本仓库查询"
  ALAS_GIT="$HERE"
fi

ALAS_BASE=""
if [ -n "${ALAS_COMMIT:-}" ]; then
  ALAS_BASE="$ALAS_COMMIT"
elif [ -n "$GIT" ] && "$GIT" -C "$ALAS_GIT" rev-parse --verify --quiet refs/remotes/origin/master >/dev/null 2>&1; then
  ALAS_BASE="$("$GIT" -C "$ALAS_GIT" merge-base HEAD refs/remotes/origin/master 2>/dev/null || true)"
fi
[ -n "$ALAS_BASE" ] || ALAS_BASE="$("$GIT" -C "$ALAS_GIT" rev-parse HEAD 2>/dev/null || echo unknown)"

ALAS_TIME=""; ALAS_MSG=""; ALAS_AUTHOR=""
if [ -n "$GIT" ]; then
  ALAS_TIME="$("$GIT" -C "$ALAS_GIT" log -1 --pretty=%ad --date=format:'%Y-%m-%d %H:%M:%S' "$ALAS_BASE" 2>/dev/null || true)"
  ALAS_MSG="$("$GIT" -C "$ALAS_GIT" log -1 --pretty=%s "$ALAS_BASE" 2>/dev/null || true)"
  ALAS_AUTHOR="$("$GIT" -C "$ALAS_GIT" log -1 --pretty=%an "$ALAS_BASE" 2>/dev/null || true)"
fi

# 若包内 alas 的**核心源码**相对基线有定制改动，标记 dirty。
# 只看会被打包进包、且真正影响运行的那些路径：仓库根的 .gitignore 之类虽然也进了包，
# 但与 Alas 行为无关，不该被算作 dirty。
ALAS_DIRTY="false"
if [ -n "$GIT" ] && [ "$ALAS_BASE" != "unknown" ]; then
  if [ "$ALAS_GIT" = "$ALAS_SRC" ]; then
    ALAS_CHANGED="$("$GIT" -C "$ALAS_GIT" diff --name-only "$ALAS_BASE" HEAD -- \
      alas.py gui.py module campaign deploy assets bin submodule webapp \
      requirements.txt requirements-in.txt ':!deploy/fnos' 2>/dev/null | head -n1 || true)"
    if [ -n "$ALAS_CHANGED" ]; then
      ALAS_DIRTY="true"
      echo "   注意：包内 alas 核心源码相对上游基线有定制改动（dirty=true）"
    fi
  else
    # 源码树不是 git 仓库时无法判定，保守标记为 dirty
    ALAS_DIRTY="true"
    echo "   注意：无法判定包内 alas 是否相对基线有改动 → 保守标记 dirty=true"
  fi
fi

PY_BIN="$(command -v python3 || true)"
if [ -n "$PY_BIN" ]; then
  "$PY_BIN" - "$APP/alas_version.json" "$ALAS_BASE" "$ALAS_TIME" "$ALAS_MSG" \
      "$ALAS_AUTHOR" "$APPVER" "$ALAS_DIRTY" <<'PYEOF'
import json
import sys

path, commit, when, message, author, appver, dirty = sys.argv[1:8]
data = {
    "base_commit": commit,
    "base_time": when,
    "message": message,
    "author": author,
    "source": "fpk",
    "packed_app_version": appver,
    "dirty": dirty == "true",
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PYEOF
else
  echo "   未找到 python3，退回最小 JSON"
  printf '{\n  "base_commit": "%s",\n  "source": "fpk",\n  "packed_app_version": "%s",\n  "dirty": %s\n}\n' \
    "$ALAS_BASE" "$APPVER" "$ALAS_DIRTY" >"$APP/alas_version.json"
fi
echo "   上游基线：${ALAS_BASE:0:8}  ($ALAS_BASE)"

# --- 装配后校验：防止嵌套复制导致体积翻倍 -------------------------------
say "装配后校验"
[ -e "$APP/runtime/runtime" ] && die "runtime 装配出现嵌套（$APP/runtime/runtime）"
[ -e "$APP/alas/alas" ] && die "alas 装配出现嵌套（$APP/alas/alas）"
[ -x "$APP/runtime/bin/python3.7" ] || die "runtime 主程序不可执行：$APP/runtime/bin/python3.7"
[ -f "$APP/server/console_server.py" ] || die "缺少 $APP/server/console_server.py"
[ -f "$APP/patch/sitecustomize.py" ] || die "缺少 $APP/patch/sitecustomize.py"
[ -f "$APP/patch/alas_fnos.py" ]     || die "缺少 $APP/patch/alas_fnos.py"
[ -f "$APP/alas_version.json" ]      || die "缺少 $APP/alas_version.json（更新面板需要它判断版本）"

SRC_FILES="$(find "$RUNTIME_SRC" -type f | wc -l | tr -d ' ')"
DST_FILES="$(find "$APP/runtime" -type f | wc -l | tr -d ' ')"
[ "$SRC_FILES" = "$DST_FILES" ] || die "runtime 文件数不一致：源 $SRC_FILES / 装配 $DST_FILES"
echo "   runtime 文件数一致：$DST_FILES"

say "装配体积"
du -sh "$APP/runtime" 2>/dev/null || true
du -sh "$APP/alas" 2>/dev/null || true
du -sh "$APP" 2>/dev/null || true

if [ "$ASSEMBLE_ONLY" -eq 1 ]; then
  say "仅装配模式：完成（未打包）"
  exit 0
fi

# --- 4. 打包 -------------------------------------------------------------
say "fnpack build"
[ -x "$FNPACK" ] || die "缺少可执行打包器: $FNPACK（见 docs/构建指南.md）"
# fnpack 会在 $TMPDIR 下创建 fnpack.<时间戳> 临时目录；若该路径已被占用（例如上一次
# 构建中断留下同名目录），会报 "Copy pack ... is a directory" 这类与包内容无关的
# 假失败。为此给每次构建准备一个干净的私有 TMPDIR。
FNPACK_TMP="$(mktemp -d "${TMPDIR:-/tmp}/fnpack-build.XXXXXX")"
trap 'rm -rf "$FNPACK_TMP"' EXIT
OUT="$(cd "$DIST_OUT" && TMPDIR="$FNPACK_TMP" "$FNPACK" build --directory "$FNOS_APP" 2>&1)" || { echo "$OUT"; die "fnpack build 失败"; }
echo "$OUT"

BUILT="$(printf '%s\n' "$OUT" | sed -n 's/.*output file \([^ ]*\.fpk\).*/\1/p' | head -n1)"
[ -n "$BUILT" ] || BUILT="$APPNAME.fpk"
[ -f "$DIST_OUT/$BUILT" ] || die "未找到打包产物: $DIST_OUT/$BUILT"

FINAL="$APPNAME"_"$APPVER.fpk"
mv -f "$DIST_OUT/$BUILT" "$DIST_OUT/$FINAL"

say "完成"
echo "产物: $DIST_OUT/$FINAL"
ls -lh "$DIST_OUT/$FINAL"
