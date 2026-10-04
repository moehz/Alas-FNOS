# vendored adb（随包分发，决策 #1 修订版）

- 来源：https://dl.google.com/android/repository/platform-tools-latest-linux.zip
- 版本：platform-tools **37.0.1**（source.properties: `Pkg.Revision=37.0.1`）
- 下载日期：2026-10-04
- 只取 `platform-tools/adb`（x86-64 ELF，动态链接，DT_NEEDED 仅 glibc 家族：
  `libc.so.6 / libdl.so.2 / libgcc_s.so.1 / libm.so.6 / libpthread.so.0 / librt.so.1`，
  均为 Debian/fnOS 自带；libc++ 已静态链接，无需 `lib64/libc++.so`）
- `NOTICE.txt` 为 Android platform-tools 原版许可声明，随包分发（`<target>/bin/adb-NOTICE.txt`）

## 校验和（SHA256）

```
a902be8f45c6c62e76c9efaf6947a0fa747c9cabd89a2ac8e0d16ecb30b3ed01  adb
d230f13842f60f782a8645f9c813f8f845bf36089ea7289f28c48f17979313f1  platform-tools-latest-linux.zip（下载时快照）
```

## 装配与运行

- `build_fpk.sh` 将本目录的 `adb` 装配到 `<target>/bin/adb`（含 NOTICE/README）。
- `console_server.start_alas` 把 `<appdest>/bin` 前插进 gui.py 的 `PATH`，
  默认配置 `AdbExecutable=adb` 直接命中；`adb start-server`（127.0.0.1:5037）
  由 adbutils 自动拉起。
- 设备序列号（`Alas.Emulator.Serial`）等仍由使用者在 WebUI 自行配置。
- 升级方法：替换本目录 `adb` 并更新本文件的版本与校验和，重打包即可。
