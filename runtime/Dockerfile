# 构建 Alas 在 fnOS 上运行所需的自带 CPython 3.7 运行时（x86_64）
#
# fnOS 只跑 x86_64，而开发机多是 arm64。本镜像全程以 --platform linux/amd64 构建，
# 产出的解释器、扩展模块和动态库都是 x86_64，与目标设备架构一致。

FROM python:3.7-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# build-essential 仅为兜底编译可能出现的 sdist，不会进入最终运行时。
# 不再安装 libav*-dev：见下方 av 的处理。
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential pkg-config \
      libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# requirements.txt 是 pip-compile 在 Windows 上生成的平铺清单，构建期做四处 Linux 适配，
# 与项目自带的 deploy/docker/requirements_generator.py 保持同一口径：
#   1. pywin32==301 在 Linux 上没有任何分发，会中断安装 -> 补平台标记
#   2. alas-webapp 是 Windows 专用的 Electron 外壳（内置 24MB app.asar），
#      上游各 Linux 生成器均显式剔除 -> 移除
#   3. av==10.0.0 在 PyPI 上只有 sdist（PyAV 从未发布 cp37 的 Linux 轮子），
#      而它只在 scrcpy 截图路径中被懒加载。scrcpy 不在 Emulator_ScreenshotMethod
#      的选项里，auto 基准测试也不包含它，故本包直接移除 av，从而不必连同
#      FFmpeg 依赖闭包一起分发。项目作者亦确认不使用 scrcpy 时可忽略 pyav。
#   4. opencv-python -> opencv-python-headless，去掉 libGL / libX11 / libgtk 依赖；
#      已确认没有任何包声明依赖 opencv-python，不会被拉回。
#
# 必须使用旧解析器：该清单由 pip-compile 用旧解析器生成，本身不自洽——
# requests==2.18.4 与 mxnet 1.6.0 要求的 requests>=2.20.0 矛盾，只是当年未校验。
# 清单已完整钉死所有传递依赖，无需再解析，旧解析器按原样安装即可。
COPY requirements.txt /tmp/requirements.txt
RUN sed -E \
      -e 's/^(pywin32==[^ ]+).*$/\1 ; sys_platform == "win32"/' \
      -e '/^alas-webapp==/d' \
      -e '/^av==/d' \
      -e 's/^opencv-python==/opencv-python-headless==/' \
      /tmp/requirements.txt > /tmp/requirements-linux.txt \
 && pip install Cython==0.29.37 wheel \
 && pip install --no-build-isolation --use-deprecated=legacy-resolver \
      -r /tmp/requirements-linux.txt \
 && rm -f /tmp/requirements.txt /tmp/requirements-linux.txt

COPY collect.sh /tmp/collect.sh
RUN bash /tmp/collect.sh /runtime