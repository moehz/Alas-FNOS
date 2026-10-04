#!/usr/bin/env bash
# 可重定位冒烟测试。
#
# 关键点：把运行时挂载到 /opt/alas-rt —— 与构建时的 /usr/local 完全不同，
# 且宿主用干净的 debian:bookworm-slim（不含 FFmpeg / libgomp），
# 以此证明运行时自包含且不依赖构建路径。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RT="${1:-$HERE/dist/runtime}"

[[ -d "$RT/bin" ]] || { echo "运行时不存在: ${RT}，请先执行 build.sh" >&2; exit 1; }

docker run --rm --platform linux/amd64 \
  -v "$RT":/opt/alas-rt:ro \
  debian:bookworm-slim \
  env LD_LIBRARY_PATH=/opt/alas-rt/lib \
  /opt/alas-rt/bin/python3.7 -c "
import platform, sys
print('exe     =', sys.executable)
print('prefix  =', sys.prefix)
print('machine =', platform.machine())
assert platform.machine() == 'x86_64'
assert sys.prefix == '/opt/alas-rt', sys.prefix

import numpy, cv2, mxnet, scipy, matplotlib, PIL
import lz4, msgpack, zmq, gevent, cffi, yaml, psutil
print('numpy   =', numpy.__version__)
print('cv2     =', cv2.__version__)
print('mxnet   =', mxnet.__version__)

# 本包按设计不含 av（scrcpy 截图路径不可达），此处确保没有被意外引入
try:
    import av
except ImportError:
    print('av      = (intentionally absent)')
else:
    raise AssertionError('av should not be bundled')

print('ALL IMPORTS OK')
"