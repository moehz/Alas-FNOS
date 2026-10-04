#!/usr/bin/env bash
# 构建并导出 Alas 的 x86_64 自带运行时。
#
#   ./build.sh [输出目录]      默认 deploy/fnos/runtime/dist/runtime
#
# 首次构建需完整拉取依赖（数百 MB），耗时较长；后续构建复用 Docker 层缓存。
# 依赖清单的裁剪规则见 Dockerfile 顶部注释。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
DEST="${1:-$HERE/dist/runtime}"
IMAGE=alas-py37-runtime:build

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "==> 准备构建上下文"
cp "$HERE/Dockerfile" "$HERE/collect.sh" "$STAGE/"
cp "$REPO/requirements.txt" "$STAGE/requirements.txt"

echo "==> 构建 amd64 运行时镜像"
docker build --platform linux/amd64 -t "$IMAGE" "$STAGE"

echo "==> 导出运行时到 $DEST"
rm -rf "$DEST"
mkdir -p "$DEST"
cid="$(docker create --platform linux/amd64 "$IMAGE")"
docker cp "$cid:/runtime/." "$DEST/"
docker rm "$cid" >/dev/null

echo "==> 磁盘占用"
du -sh "$DEST"
du -sh "$DEST"/* 2>/dev/null | sort -h | tail -n 5