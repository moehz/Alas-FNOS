#!/usr/bin/env bash
# 把 /usr/local 下的 CPython 3.7 前缀整理成可重定位、自包含的运行时树。
#
# 产出结构：
#   $OUT/bin/python3.7
#   $OUT/lib/python3.7/{stdlib,lib-dynload,site-packages}
#   $OUT/lib/libpython3.7m.so.1.0
#   $OUT/lib/*.so*             <- libgomp、libssl 等非基线依赖闭包
#
# 运行时通过 LD_LIBRARY_PATH=$OUT/lib 启动，因此不需要 patchelf，
# 也不依赖 fnOS 提供这些库。
set -euo pipefail

OUT="${1:?用法: collect.sh <输出目录>}"
PYROOT=/usr/local
PYVER=3.7

# fnOS 是 Debian 系，这些由系统提供，不打进包内
BASELINE=(
  ld-linux-x86-64.so.2
  libc.so.6 libm.so.6 libdl.so.2 libpthread.so.0 librt.so.1
  libgcc_s.so.1 libstdc++.so.6
  libresolv.so.2 libutil.so.1 libnsl.so.1 libnss_dns.so.2 libnss_files.so.2
)

is_baseline() {
  local n="$1" b
  for b in "${BASELINE[@]}"; do
    [[ "$n" == "$b" ]] && return 0
  done
  return 1
}

echo "==> [1/5] 复制 CPython 前缀"
rm -rf "$OUT"
mkdir -p "$OUT/bin" "$OUT/lib"
cp -a "$PYROOT/lib/python${PYVER}" "$OUT/lib/python${PYVER}"
cp -a "$PYROOT/lib/libpython${PYVER}m.so.1.0" "$OUT/lib/"
cp -a "$PYROOT/bin/python${PYVER}" "$OUT/bin/"
ln -sf "python${PYVER}" "$OUT/bin/python3"

echo "==> [2/5] 清理测试、构建产物与用不到的标准库"
SP="$OUT/lib/python${PYVER}"
# Alas 运行时不使用 Tk，且 _tkinter 会引入 X11 依赖，直接剔除
rm -rf "$SP/tkinter" "$SP/idlelib" "$SP/lib2to3" "$SP/turtledemo" "$SP/test" "$SP/ensurepip"
rm -f "$SP"/lib-dynload/_tkinter*.so
rm -rf "$SP/config-${PYVER}m-x86_64-linux-gnu"
find "$SP" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "$SP" -type f \( -name '*.pyc' -o -name '*.pyx' -o -name '*.pxd' \) -delete 2>/dev/null || true
# 只在编译期需要的头文件（numpy 的 include 目录较大）
find "$SP/site-packages" -type d -name include -prune -exec rm -rf {} + 2>/dev/null || true

echo "==> [3/5] 收集动态库闭包"
QUEUE="$(mktemp)"
DONE="$(mktemp)"
trap 'rm -f "$QUEUE" "$DONE"' EXIT

printf '%s\n' "$OUT/bin/python${PYVER}" "$OUT/lib/libpython${PYVER}m.so.1.0" >> "$QUEUE"
find "$OUT/lib/python${PYVER}" -type f -name '*.so' >> "$QUEUE"

while read -r f; do
  [[ -z "$f" || ! -f "$f" ]] && continue
  grep -qxF "$f" "$DONE" && continue
  printf '%s\n' "$f" >> "$DONE"
  while read -r p; do
    [[ -z "$p" || ! -f "$p" ]] && continue
    n="$(basename "$p")"
    is_baseline "$n" && continue
    # 位于 CPython 树内的库（auditwheel 的 site-packages/*.libs/、lib-dynload 等）
    # 已随 [1/5] 的整树复制一并搬走，运行时靠 RUNPATH=$ORIGIN 相对定位，
    # 再复制一份到 $OUT/lib 纯属重复。这里只遍历它的依赖，不复制。
    # 两种前缀都要判：同一个文件，ldd 对树内的引用方会报源前缀路径
    # （/usr/local/...），对已复制的引用方会报目标树路径（$OUT/...）。
    case "$p" in
      "$PYROOT"/lib/python*/*|"$OUT"/lib/python*/*)
        printf '%s\n' "$p" >> "$QUEUE"
        continue
        ;;
    esac
    if [[ ! -e "$OUT/lib/$n" ]]; then
      cp -Lf "$p" "$OUT/lib/$n"
      printf '%s\n' "$p" >> "$QUEUE"
    fi
  done < <(ldd "$f" 2>/dev/null | awk '$2 == "=>" && $3 ~ /^\// {print $3} $1 ~ /^\// {print $1}')
done < "$QUEUE"

echo "==> [4/5] 校验收集结果"
# 不变式：$OUT/lib 内的库不应与 CPython 树内的库内容重复。按 md5 判定，
# 避免把"同名不同内容"（如系统 libquadmath 与 mxnet 自带的那份）误判为重复。
TREE_MD5="$(find "$SP" -type f -name '*.so*' -exec md5sum {} + 2>/dev/null | cut -d' ' -f1)"
dups=0
for f in "$OUT"/lib/*.so*; do
  [[ -e "$f" ]] || continue
  h="$(md5sum "$f" | cut -d' ' -f1)"
  if printf '%s\n' "$TREE_MD5" | grep -qx "$h"; then
    echo "   重复: $(basename "$f")" >&2
    dups=$((dups + 1))
  fi
done
if (( dups > 0 )); then
  echo "错误：$OUT/lib 有 $dups 个库与 CPython 树内的库内容相同" >&2
  exit 1
fi
echo "   lib/ 独有库 $(find "$OUT/lib" -maxdepth 1 -name '*.so*' | wc -l | tr -d ' ') 个，无重复"

echo "==> [5/5] 运行时自检"
LD_LIBRARY_PATH="$OUT/lib" "$OUT/bin/python${PYVER}" - <<'PY'
import platform, sys
assert platform.machine() == 'x86_64', platform.machine()
print('   interpreter:', sys.version.split()[0], platform.machine())
for mod in ('numpy', 'cv2', 'mxnet'):
    __import__(mod)
    print('   ok:', mod)
PY

echo "==> 完成，动态库数量: $(find "$OUT/lib" -maxdepth 1 -name '*.so*' | wc -l | tr -d ' ')"