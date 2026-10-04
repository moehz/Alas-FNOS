#!/bin/bash
# deploy/fnos/tools/cleanup-probes.sh —— 批量卸载排查期间安装的探针应用
#
# 在【飞牛设备】上以 root 执行：
#     sudo bash cleanup-probes.sh            # 卸载全部探针（含 azurlaneautoscript 探针）
#     sudo bash cleanup-probes.sh --dry-run  # 只列出将要卸载的名字，不动手
#     sudo bash cleanup-probes.sh --dirs     # 卸载后额外清理残留的 /var/apps/<name>
#
# 背景：为定位 FPK 安装失败（code 10111）问题，先后装了若干 14KB~278KB 的探针包。
# 这些包都是空应用（cmd 不做任何事），卸载不会影响 Alas 真正的配置与数据。
set -u

CLI="${APPCENTER_CLI:-appcenter-cli}"
DRY_RUN=0
CLEAN_DIRS=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --dirs)    CLEAN_DIRS=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "未知参数：$arg" >&2; exit 1 ;;
  esac
done

if [ "$(id -u)" -ne 0 ] && [ "$DRY_RUN" -eq 0 ]; then
  echo "请用 sudo 执行：sudo bash $0" >&2
  exit 1
fi

# 排查期间用过的全部 appname（未安装的会被自动跳过）
NAMES="probeapp probe1 probe2 probe3 probe4 probe5 probe6 probe7 probe8 probe9 probe10 \
probe11 probe12 probe13 probe14 probe15 probe16 probe17 probe18 probe19 probe20 probe21 probe22 \
azurlaneautoscript"

echo "=== 当前已安装应用 ==="
"$CLI" list || true
echo

if [ "$DRY_RUN" -eq 1 ]; then
  echo "=== --dry-run：将要尝试卸载以下应用 ==="
  for n in $NAMES; do echo "  $n"; done
  exit 0
fi

echo "=== 开始卸载 ==="
removed=0
skipped=0
for n in $NAMES; do
  if out=$("$CLI" uninstall "$n" 2>&1); then
    echo "  已卸载   $n"
    removed=$((removed + 1))
  else
    echo "  跳过     ${n}（未安装 / 已卸载）"
    skipped=$((skipped + 1))
  fi
done

echo
echo "卸载完成：成功 $removed 个，跳过 $skipped 个。"

if [ "$CLEAN_DIRS" -eq 1 ]; then
  echo
  echo "=== 清理残留目录 /var/apps/<name> ==="
  for n in $NAMES; do
    d="/var/apps/$n"
    if [ -d "$d" ]; then
      rm -rf "$d" && echo "  已删除 $d"
    fi
  done
fi

echo
echo "=== 卸载后已安装列表 ==="
"$CLI" list || true
