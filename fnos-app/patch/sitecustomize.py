# -*- coding: utf-8 -*-
"""Alas fnOS 补丁注入的引导脚本（Python 的 sitecustomize 约定入口）。

console_server 启动 Alas 时会带上 ``PYTHONPATH=<target>/patch``，CPython 初始化
site 模块时会自动导入本文件。这里只做最小的事：

  1. 把补丁目录本身放进 ``sys.path``，使 ``alas_fnos`` 可被导入；
  2. 调用 ``alas_fnos.install()`` 注册 import hook，等 ``module.webui.updater``
     真正被加载后再替换它的方法。

设计约束：
  - **绝不能因为补丁出错而让 Alas 起不来**，任何异常只写到 stderr；
  - 尽量轻量：本文件会在该解释器的每个子进程启动时被执行一次。
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    import alas_fnos

    alas_fnos.install()
except Exception as exc:  # noqa: BLE001 - 补丁失败不得影响 Alas 启动
    sys.stderr.write("[alas-fnos] bootstrap failed: %r\n" % (exc,))
    sys.stderr.flush()
