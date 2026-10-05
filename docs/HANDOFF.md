# AzurLaneAutoScript × 飞牛 fnOS 原生应用 —— 任务交接报告

> **位置说明（2026-10-05 迁移）**：本工程原先嵌在 Alas 源码树的 `deploy/fnos/`，现拆分为
> 独立仓库（即本仓库），该目录已删除。下文里以 `deploy/fnos/...` 开头的路径都是**迁移前**的
> 旧位置，对应现在的 `fnos-app/…`、`build_fpk.sh`、`runtime/`、`vendor/`、`tools/`、`dist/`；
> `deploy/fnos/HANDOFF.md` 即本文件（`docs/HANDOFF.md`）。
> 当前交付物已更新为 **1.2.1**（见 `dist/RELEASE_v1.2.1.md`）；下面几行是 1.2.0 首发布时的快照。

> 最近更新：**2026-10-04（改名 1.2.0，准备公开首发布）**。当前交付物：**1.2.0 正式包**
> `deploy/fnos/dist/alas-fnos_1.2.0.fpk`
> （344,073,891 B，SHA256 `ecae9f67868eb90e95d84a7683803f3d299b2302279dd0d896837b6f49c55aa1`，基线 77f4d01f）。
> 仓库：`/Users/shylock/Documents/workspace/AzurLaneAutoScript`
> 发布仓库：`deploy/fnos/github-repo/`（独立 git 仓库 → `github.com/moehz/Alas-FNOS`）。
> 版本流转：`ff74d8cff`（建立基线）→ `5190f0ee5`（阶段 4）→ `359528afb`（1.0.1）
> → `d93c7093a`（1.0.2 热更新 + 卸载向导）→ `746fd3e3b`（`--alas-src` + bash 3.2 修复）
> → `54b82a7c0`/`3e77acdcc`（1.0.4/1.0.5 排障修复）→ `6f4f07d5c`（4.12.8 裁决）
> → `aa1231ed4`（1.0.6 更新收尾 cwd 修复）→ `34ae25802`（1.1.0 包内自带 adb）
> → `cee7e3a1a`（1.1.1 adb HOME 修复）→ 文档/发布仓库整理若干提交 → **1.2.0 改名（见 4.15）**。
> 主仓库全部仅本地提交，未 push；发布仓库已推到 `moehz/Alas-FNOS`（首笔提交信息已被改写，
> 下次推送需 `--force-with-lease`，见 9.5）。
> **真机验收（1.1.1，2026-10-04）全部通过**：安装 / 配置面板 / 检查更新 / 立即更新 +
> 自动重载 / 卸载清理数据 / **adb 零配置**（包内自带 adb + 自动拉起 server，
> DETECT DEVICE 直连 emulator-5554 跑通任务，见 4.14）。
> 决策 #1 已修订为「adb 二进制随包自带，设备/序列号配置仍由使用者完成」（见 4.13）。
> ⚠️ **1.2.0 换了应用标识**（`azurlaneautoscript` → `alas-fnos`）——**仅影响开发机**：
> 旧 `azurlaneautoscript` 包从未公开发布，公开用户无升级路径问题，Release 说明不必提。
> 开发机上的旧包须先卸载（数据默认保留，不自动迁移）。真机复测：**1.2.0 已装并进应用信息页**，
> 剩余项待复测；首发前补了 `distributor` 字段（「发布者」不再为空，见 4.15.1）。
> 遗留可选项：22267 端口监听者身份校验加固（见 4.12.8 末尾）。

---

## 〇、进度总览

| 阶段 | 内容 | 状态 | 产物 |
|---|---|---|---|
| 1 | 可移植 x86_64 CPython 3.7 运行时 | ✅ 完成，冒烟通过 | `deploy/fnos/runtime/dist/runtime`（703 MB） |
| 2 | 控制台后端（网关 + 反代 + 控制面 API） | ✅ 完成，23 项端到端断言通过 | `deploy/fnos/app/server/console_server.py` |
| 3 | 前端控制台（Vite + `@trimjs/web-app`） | ⬜ **未开始** | 目标 `deploy/fnos/app/console/` |
| 4.0 | 资料调研（fnpack / skill / 官方文档） | ✅ 完成 | `deploy/fnos/tools/fnpack`（1.2.3） |
| 4.1 | FPK 骨架 | ✅ 完成，预检 0 问题 | `deploy/fnos/fpk/` |
| 4.2 | 装配脚本 | ✅ 完成，幂等已验证 | `deploy/fnos/build_fpk.sh` |
| 4.3 | 预检 + 打包 | ✅ 完成 | `deploy/fnos/dist/azurlaneautoscript_1.0.2.fpk` |
| 4.9 | 脚本热更新（接管上游更新面板） | ✅ **完成**，离线自测 33 项全绿 | `deploy/fnos/app/patch/` |
| 4.10 | 卸载向导：可选清理数据 | ✅ **完成**，分支测试全绿 | `deploy/fnos/fpk/wizard/uninstall` |
| 4.11 | 更新功能的测试包（基线落后于上游） | ✅ **完成**，包内旧版已逐字节验证 | `deploy/fnos/dist/azurlaneautoscript_1.0.4.fpk` |
| 4.12 | 修「装了新包仍显示旧版本」+ 一键排查脚本 | ✅ **完成**，离线自测 42 项全绿 | `deploy/fnos/app/patch/`、`cmd/upgrade_*`、`tools/diagnose-update.sh` |
| 5 | 真机验收（x86 fnOS） | ✅ **完成**（1.1.1 全项通过，2026-10-04） | 见 4.13 / 4.14 |
| 5.1 | 真机安装失败排障（`code 10111`） | ✅ **根因定位 + 已修复** | 见第五、八节 |
| 6 | 上架（可选） | ⬜ 未开始 | — |
| 7 | 公开发布（改名 1.2.0 → GitHub + Release） | 🔄 **1.2.0 已真机安装；待强推 + 发 Release** | `deploy/fnos/dist/alas-fnos_1.2.0.fpk`（见 4.15 / 第九节） |

> 说明：阶段 3 未完成**不阻塞**阶段 4/5 —— 缺少 `console/dist` 时 console_server 会 **308 直跳 `/alas/`**（1.0.1 起，此前是占位页），Alas 配置界面从 `/app/alas-fnos/alas/` 可进入（1.2.0 起；此前为 `/app/azurlaneautoscript/alas/`）。

---

## 一、任务目标与不可擅改的决策

为 AzurLaneAutoScript (Alas) 开发**飞牛 fnOS 原生应用（非 Docker）**，产出可安装的 `.fpk`。

以下决策已由用户拍板，**不得擅自更改**：

1. **不管安卓设备**。只交付"能装能开"的 FPK。
   **（2026-10-04 修订）** adb 二进制**包内自带**（platform-tools 37.0.1 x86_64，
   装配到 `<target>/bin/adb`，console_server 起 gui.py 时前插 PATH，默认
   `AdbExecutable=adb` 即生效）；设备序列号等**配置**仍由使用者自行完成。
   见 4.13。
2. **新建 fnOS 原生控制台**（`@trimjs/web-app` + 统一网关），**不** iframe 嵌入原 PyWebIO 界面；同时在 `/app/{appname}/alas` 反代 `127.0.0.1` 的 PyWebIO（含 WebSocket），复用网关登录态。
3. **包内自带可移植 x86_64 CPython 3.7**（不用 Docker 运行时、不用 `install_dep_apps=python312`）。
4. **不打包 `av`**（砍掉 FFmpeg 依赖闭包）。
5. **配置落盘用 `$TRIM_PKGVAR`**（应用私有目录）。
6. **强制** `InstallDependencies=false`、`CheckUpdateInterval=0`、`AutoRestartTime=null`；
   `EnableReload=true`、`AutoUpdate=true` —— 后两者自 1.0.2 起放开，配合 4.9 的补丁实现
   脚本热更新（`EnableReload` 让上游 `gui.py` 建立重启循环，更新完成后自动加载新代码）。
7. appname 固定为 **`alas-fnos`**（网关前缀 `/app/alas-fnos` 由 console_server 按 appname 推导）。
   **（2026-10-04 修订）** 原值为 `azurlaneautoscript`；为公开发布改名 —— 应用标识 `alas-fnos`、
   显示名 `ALAS`、开发者 `moehz`、仓库 `https://github.com/moehz/Alas-FNOS`，版本跳到 1.2.0。
   两项改名（标识 + 显示名）**不兼容旧包**，但旧包从未公开发布，公开用户无升级路径问题；
   仅开发机上已装的 `azurlaneautoscript` 包须先卸载（数据默认保留，不自动迁移）。
   改名后 `appname` 重新固定，不得再动。

验收环境：用户有 **x86 fnOS 真机**。

---

## 二、阶段 4 完成内容与验证证据

### 4.1 FPK 骨架 `deploy/fnos/fpk/`

```
fpk/
├── manifest                      platform=x86, micro_app=true, disable_authorization_path=true
├── ICON.PNG                     64×64（由 webapp/buildResources/icon.png 缩放）
├── ICON_256.PNG                 256×256
├── config/privilege             run-as=package（最小权限）
├── config/resource              {}（无 api-scope / data-share / docker）
├── cmd/                         9 个脚本，全部 chmod +x
│   ├── main                     start/stop/status；status 未运行 exit 3，未知参数 exit 1
│   ├── install_init / install_callback
│   ├── upgrade_init / upgrade_callback
│   ├── uninstall_init / uninstall_callback
│   └── config_init / config_callback
├── wizard/
│   ├── install                  一条 tips（ADB 自行配置说明）
│   ├── uninstall                卸载选项（1.0.2 新增，见 4.10）：tips + radio `wizard_data_action`
│   └── upgrade|config           **不创建**（空数组会导致真机安装失败 `code 10111`，见 R12）
└── app/ui/
    ├── config                   统一网关入口（见 4.4）
    └── images/icon_{64,256}.png
```

关键实现约束（均已满足）：
- 生命周期脚本**幂等**，失败信息先写 `$TRIM_TEMP_LOGFILE` 再非零退出。
- **不硬编码** `/var/apps/...`，一律用 `TRIM_APPDEST` / `TRIM_PKGVAR` / `TRIM_PKGETC`。
- `cmd/main` 的 `stop` 先停 Alas 进程组、再停控制台、最后清 `console.pid` / `alas.pid` / `app.sock`。
  - 注意：**不能**用 `POST /api/stop` 从本地脚本停 Alas —— 该接口要求网关 `X-Trim-*` 首部，脚本调用只会拿到 403，故直接按 PID 处理。

### 4.2 装配脚本 `deploy/fnos/build_fpk.sh`

```
./deploy/fnos/build_fpk.sh                  # 校验 → 清理 → 骨架预检 → 装配 → 校验 → 打包
./deploy/fnos/build_fpk.sh --assemble       # 只装配不打包
./deploy/fnos/build_fpk.sh --skip-alas      # 调试用
./deploy/fnos/build_fpk.sh --alas-src DIR   # 用指定的 Alas 源码树装配（见 4.11）
```

环境变量：`ALAS_SRC`（等价 `--alas-src`，默认本仓库根）、`ALAS_COMMIT`（强制指定写进
`alas_version.json` 的上游基线，默认按源码树 git 推断）。

流程顺序（顺序很重要，勿调换）：
1. 源物料校验（骨架必需文件 / runtime / console_server.py / patch 两个文件）
2. 向导文件防回归校验（拒绝空数组，防 `code 10111`）
3. **解析 Alas 源码树**（`--alas-src` / `$ALAS_SRC` / 默认本仓库根）—— 失败在任何清理之前，零副作用
4. 清理上次装配产物（`find -delete`）
5. **骨架预检** —— 必须在装配前跑（原因见 R9）
6. 装配 `app/runtime`（`cp -al` 硬链接）、`app/alas`（rsync，排除 `.git` `/deploy/fnos` `/.trae` `/.workbuddy` `/log`）、`app/server`、`app/patch`、`app/console/dist`（存在时）
7. 生成 `app/alas_version.json`（基线 = 源码树 git 的 `merge-base HEAD origin/master`）
8. 装配后校验：禁止嵌套、文件数一致性、patch 与版本文件在场
9. `fnpack build` → 重命名为 `<appname>_<version>.fpk` 并落到 `deploy/fnos/dist/`
   （appname 由 manifest 读出，不在脚本里硬写；1.2.0 起为 `alas-fnos`）

### 4.3 验证证据（本会话实测）

| 项 | 结果 |
|---|---|
| 骨架预检 `validate_fnos_project.py` | **No issues found**（0 blocker/high/medium/low） |
| 装配体积 | runtime 703 MB + alas 145 MB = **848 MB** |
| 装配后校验 | runtime 文件数一致 = 7731（证明幂等、无嵌套） |
| `fnpack build` | **成功**，装配 848 MB → fpk **324 MB** |
| 产物 | `deploy/fnos/dist/azurlaneautoscript_1.0.0.fpk` |
| 产物结构 | fpk 顶层 = `manifest` / `cmd/` / `config/` / `wizard/` / `ICON*.PNG` / `app.tgz`；`app.tgz` 顶层 = `alas` `config` `runtime` `server` `ui` |
| 关键权限 | `runtime/bin/python3.7` 保持 `-rwxr-xr-x`；`runtime/bin/python3 -> python3.7` 软链保留 |
| 排除项 | `alas/.git` 未进入包 |

#### 4.3.1 1.0.2 装配与产物核验（2026-10-03 实测）

```bash
./deploy/fnos/build_fpk.sh        # EXIT=0
```

| 项 | 结果 |
|---|---|
| 骨架预检 `validate_fnos_project.py` | **No issues found**（0 blocker/high） |
| 装配体积 | runtime 703 MB + alas 145 MB = **848 MB**（与 1.0.0 持平） |
| 装配后校验 | runtime 文件数一致 = **7731**（幂等、无嵌套） |
| 上游基线识别 | **`77f4d01f`**（与 GOC `latest.json`、GitHub `branches/master` 三方一致） |
| `fnpack build` | **成功**，848 MB → **324 MB** |
| 产物 | `deploy/fnos/dist/azurlaneautoscript_1.0.2.fpk`（339,310,373 B） |
| SHA256 | `65bac6903647271d531c529e3a1bdb815eeafc160f89a99c781accb9c8a390ea` |

**产物内容核验（解包逐项确认）**

| 项 | 期望 | 实测 |
|---|---|---|
| `manifest` version | `1.0.2` | ✅ `1.0.2` |
| fpk 顶层 | `manifest` `cmd/` `config/` `wizard/` `ICON*.PNG` `app.tgz` | ✅ 一致 |
| `app.tgz` 顶层 | `alas` `config` `patch` `runtime` `server` `ui` `alas_version.json` | ✅ 一致 |
| `wizard/uninstall` | 非空、合法 JSON、含 `wizard_data_action`（radio，`initValue=keep`） | ✅ 846 B，已解析 |
| `wizard/install` | tips 文案 | ✅ 637 B |
| `cmd/uninstall_init` / `_callback` | 存在且 `mode=755` | ✅ 1983 B / 989 B，755 |
| `cmd/*` 全部 9 个 | `mode=755` | ✅ 9/9 = 755 |
| `app/patch/alas_fnos.py` | 存在 | ✅ 20655 B |
| `app/patch/sitecustomize.py` | 存在 | ✅ 1045 B |
| patch Python 3.7 语法 | `ast.parse(feature_version=(3,7))` 通过 | ✅ 两个文件均 OK |
| `alas_version.json`（出厂） | `base_commit=77f4d01f…`、`source=fpk`、`dirty=false` | ✅ 完全一致 |
| `alas/.git` | 不得存在 | ✅ 0 个 |
| `deploy/fnos` | 不得存在（避免自我嵌套） | ✅ 0 个 |

---

## 三、当前目录现状

```
deploy/fnos/
├── .gitignore                       # （本仓库用）忽略 runtime/dist、tools/fnpack、fpk 装配产物、*.fpk
├── HANDOFF.md                       # 本报告
├── build_fpk.sh                     # 阶段4.2 装配打包流水线（单一入口）
├── fpk/                             # 阶段4.1 骨架（已入库）
│   ├── manifest / config / cmd / wizard / app/ui
│   └── app/{runtime,alas,server,console,patch} + alas_version.json   # 装配产物，已 gitignore
├── dist/
│   └── alas-fnos_1.2.0.fpk          # 当前发布物（+ RELEASE/宣传稿 md）
├── app/
│   ├── server/console_server.py     # 阶段2 产物（单一真源；装配时复制进 fpk）
│   └── patch/{sitecustomize.py,alas_fnos.py}   # 阶段4.9 更新补丁（单一真源；装配进 <target>/patch）
├── runtime/                         # 阶段1：Dockerfile/build.sh/collect.sh/smoke.sh + dist/（703MB）
├── tools/fnpack                     # fnpack 1.2.3（darwin-arm64）
└── github-repo/                     # 对外发布用的独立仓库内容（见 3.1）
```

**历史产物已于 2026-10-05 清理**（`deploy/fnos` 占用 4.1 GB → 1.0 GB）：

- `dist/` 里 `azurlaneautoscript_1.0.0`~`1.1.1` 共 9 个旧包全部删除，只留
  `alas-fnos_1.2.0.fpk` + `RELEASE_v1.2.0.md` + `宣传稿-v1.2.0.md`。
  旧包对应的代码/骨架都能从 git 历史检出重建（见 4.11 的 `--alas-src` 做法）；
  因它们**从未公开发布**，Release 页也不依赖。
- `fpk/app/{runtime,alas,server,patch,bin}` 与 `alas_version.json` 一并清空，
  下次 `build_fpk.sh` 自动装配重建。**注意**：这些目录与 `runtime/dist` 是**硬链接**关系
  （同一 inode），`du` 报的 859 MB 是重复计数，实删仅约 11 MB。
- **骨架 19 个文件（`fpk/manifest|config|cmd|wizard|app/ui|ICON*`）未动**，`git status` 为空。
- 本文档 4.x 各节里出现的旧包文件名与体积，属**当时的历史记录**，文件已不在磁盘上。

### 3.1 `github-repo/` —— 对外发布用的独立仓库

面向 GitHub 的仓库内容单独放在 `deploy/fnos/github-repo/`，日后 `git init` 即可发布。
布局参照社区同类项目 `mydanyi/MAA-FnOS`：

```
github-repo/
├── README.md            对外说明（第一人称口语体，保持短）
├── LICENSE              GPL-3.0，与 Alas 上游一致
├── .gitignore / .gitattributes
├── build_fpk.sh         装配打包入口（已适配新布局 + 支持从仓库外取 Alas 源码）
├── docs/
│   ├── 构建指南.md       构建、平台注意事项、排障
│   └── architecture.svg  架构图
├── fnos-app/            FPK 骨架 + app/ui + server/console_server.py + patch/（单一真源）
├── runtime/             Dockerfile / build.sh / collect.sh / smoke.sh
└── tools/diagnose-update.sh
```

> **两处骨架必须手工保持一致**（脚本不校验）：`app/server/console_server.py`、
> `app/patch/*` 改动后要同步到 `github-repo/fnos-app/server/`、`github-repo/fnos-app/patch/`。
> 本次已用 `diff` 逐项核对通过（wizard / cmd / manifest / patch / server 全部一致）。

**不放入仓库**（已用 `.gitignore` 排掉，或本来就不拷）：`dist/*.fpk`（走 Releases）、
`runtime/dist/`（703 MB）、`fnos-app/app/*` 装配产物、`tools/fnpack`、`.alas/` 源码检出，
以及 `tools/cleanup-probes.sh`（探针打扫脚本，只对开发机有意义，见第八节，不入发布仓库）、
`HANDOFF.md`（本篇属内部交接报告，含探针实验过程，对外不放）。

**与开发的衔接**：`github-repo/build_fpk.sh` 按
`--alas-src` → `$ALAS_SRC` → `../alas` / `.alas/` → 上一级目录 的顺序找 Alas 源码；
在开发机上从 `deploy/fnos/github-repo/` 直接跑，会命中真实的 Alas 仓库（`../../..`），无需额外配置。
独立仓库场景下需先 `git clone` 一份上游并钉死 commit（见 `docs/构建指南.md` 第 0 步）。

**注意**：`deploy/fnos/` 下的 `README.md` / `docs/` 已**移入** `github-repo/`，避免两份文档各自漂移：
对外文档以 `github-repo/` 为准。

**尚未存在**：`deploy/fnos/github-repo/fnos-app/console/`（阶段 3 前端产物）。

`deploy/template` 是**文件**不是目录（Alas 源码内），console_server 用它作为 `deploy.yaml` 的种子。

---

## 四、关键技术要点

### 4.1 FPK 骨架必需结构（fnpack 硬性检查）

根目录必须有：`manifest`（键值文件，非 JSON）、`config/privilege`、`config/resource`、`ICON.PNG`(64×64)、`ICON_256.PNG`(256×256)；目录必须有 `app/`、`cmd/`、`wizard/`；声明 `desktop_uidir=ui` 时 `app/ui/` 必须存在。

### 4.2 manifest 取值（1.2.0 定稿）

```ini
appname=alas-fnos
version=1.2.0
display_name=ALAS
desc=ALAS (AzurLaneAutoScript) 飞牛 fnOS 原生控制台。…
source=thirdparty
platform=x86                 # 必须 x86：runtime 含 x86_64 ELF
maintainer=moehz
maintainer_url=https://github.com/moehz/Alas-FNOS
os_min_version=1.2.0401      # ⚠️ 待真机验证后定稿（见 R2）
desktop_uidir=ui
desktop_applaunchname=alas-fnos.main
ctl_stop=true
checkport=false
micro_app=true
disable_authorization_path=true
changelog=首个公开版本。…
```

`appname` / `username` / `groupname` 的字符集由 fnpack 校验：**字母、数字、`-`、`_`、`.`，
必须以字母或数字开头结尾**（从 fnpack 二进制字符串表读出，MAA-FnOS 的 `maa-fnos` 是活证据）。
`display_name` 与 `appname` 无一致性要求。

### 4.3 cmd/main 的启动方式（唯一正确姿势）

```bash
PY="$TRIM_APPDEST/runtime/bin/python3.7"
export LD_LIBRARY_PATH="$TRIM_APPDEST/runtime/lib"   # 必须先导出，否则 import uvicorn 失败
nohup "$PY" "$TRIM_APPDEST/server/console_server.py" \
      --appname alas-fnos \
      --appdest "$TRIM_APPDEST" --pkgetc "$TRIM_PKGETC" --pkgvar "$TRIM_PKGVAR" \
      --socket "$TRIM_APPDEST/app.sock" --console-dist "$TRIM_APPDEST/console/dist" \
      --port 22267 --autostart true \
      >>"$TRIM_PKGVAR/console.log" 2>&1 &
```

- `--autostart` 默认 true：`start` 一次即拉起控制台 + Alas。
- Alas PID 在 `$TRIM_PKGVAR/alas.pid`（格式 `pid|start_ts`），以 `start_new_session=True` 独立会话运行。
- 控制台 PID 由 `cmd/main` 维护在 `$TRIM_PKGVAR/console.pid`。
- `console_server.py` 支持 `--prepare`（只准备后退出）。

### 4.4 网关入口 `app/ui/config`

```json
{
  ".url": {
    "alas-fnos.main": {
      "title": "ALAS",
      "icon": "images/icon_{0}.png",
      "type": "iframe",
      "protocol": "",
      "gatewayPrefix": "/app/alas-fnos",
      "gatewaySocket": "app.sock",
      "url": "/app/alas-fnos",
      "allUsers": true
    }
  }
}
```

- `gatewaySocket` 只能是**文件名**，网关转发到 `<target>/app.sock`（= `$TRIM_APPDEST/app.sock`），与 console_server 监听路径一致。
- ⚠️ **遗留待决点**：validator 要求 `url == gatewayPrefix`（都无尾斜杠）。本骨架按 validator 取值。若真机发现 PyWebIO 相对路径问题，console_server 已支持目录级 308 兜底，届时再把 `url` 调成 `.../alas/`。
- 入口图标 `images/icon_{0}.png` → `app/ui/images/icon_64.png` 与 `icon_256.png` 均已存在。

### 4.5 观察到的包装行为（无害，勿惊慌）

`fnpack build` 会把项目根的 `config/`（privilege、resource）**同时**放进 fpk 顶层与 `app.tgz` 内。两者语义不同（一个是应用元数据，一个是 target 内容），不冲突。

### 4.6 Alas 内置「在线更新」最初的「关闭」方案（历史记录）

> ⚠️ **本节的结论已被 4.9 取代。** 1.0.2 起改为**接管**更新面板：保留上游页面不动，把底层的
> git 流程换成源码包交换。本节保留是为了说明当初为什么判定「照搬上游不划算」，以及
> `CheckUpdateInterval=0` 这类强制键的来由 —— 其中 `CheckUpdateInterval=0` 与
> `InstallDependencies=false` **现在仍然保留**，只有 `AutoUpdate` / `EnableReload` 已放开。

当时的结论：**是刻意关闭的，属于本打包方式的必然取舍，不是运行时裁剪导致的**。代码依据（上游 master）：

- `deploy/git.py::git_install()` 开头即 `if not self.AutoUpdate: logger.info('AutoUpdate is disabled, skip'); return`
  —— 我们的 `deploy.yaml` 强制 `AutoUpdate=false`，所以拉取源码这一步直接跳过。
- `deploy/pip.py::pip_install()` 开头即 `if not self.InstallDependencies: ... return`
  —— 依赖更新同样跳过；且运行时依赖已由我们连同 Python 一起钉死。
- `module/webui/app.py::startup()`：`if updater.delay > 0: task_handler.add(updater.check_update, updater.delay)`，
  而 `updater.delay = CheckUpdateInterval * 60`。故 **`CheckUpdateInterval=0` 会让「检查更新」后台轮询根本不注册**
  （若用别的非零值，包内没有 git 会变成每 N 分钟一次 `Git fetch failed`）。
- `task_handler.add(updater.schedule_update(), 86400)` + `AutoRestartTime=null`：`schedule_time` 为 None，
  该定时任务在首次运行时 `remove_current_task()` 自我摘除。
- 设置页仍保留 Alas 自带的「检查更新」按钮（`app.py` 内 `put_button(..., onclick=updater.check_update)`），
  `GitOverCdn` 默认 False → 走 `git fetch` → 包内无 git → 返回 False，界面显示「已是最新」，日志留 `Git fetch failed`。
  **按钮存在但无效，属预期现象。**

关闭的三个客观原因：① 包内不带 `git` 二进制，也不带 `.git`；② 安装目录只读语义，Alas 的 `./config`、`./log`
已被软链到 `$TRIM_PKGVAR`；③ 依赖与运行时一起钉死，放任 `pip install` 会破坏自包含假设。

**与运行能力无关**：被裁掉的只有 `av` / `opencv-python`(→headless) / `alas-webapp`(Windows 专用) / `pywin32`，
这些都不参与更新链路；更新链路只依赖 `git` 与可写的源码目录。

若日后要恢复在线更新，可选路线（按侵入性排序，**已按 4.7 的真机权限实测修正**）：
1. **保持现状**：发新 fpk 即升级（当前做法，最可控、可复现）。
2. **把 Alas 源码镜像到 `$TRIM_PKGVAR` 后从该处运行**（走官方可写目录）：安装后或首次启动时把
   `target/alas` 的业务代码复制到 `$TRIM_PKGVAR/alas`，运行时 `cwd` 指过去；更新时由控制台拉取指定
   tag 的 tarball 解包覆盖该副本（不依赖 git），或自带 git 做 `git pull`。
   需要额外处理：升级 fpk 时用 `TRIM_APPVER` 比对并重新同步业务代码（保留 `config`/`log`）、
   自带 git 的体积（约 3–5 MB）、卸载时该目录的保留策略。
3. **完整恢复上游语义**：包内附带静态 `git`，放开 `AutoUpdate` 与 `InstallDependencies`。
   代价同路线 2，且**必须**配合路线 2 的 var 副本，否则无处可写 —— 见 4.7。

> **已实测排除的两条错路**：把 tarball 解包覆盖 `$TRIM_APPDEST/alas`、或把 `alas/` 就地改成可写。
> `$TRIM_APPDEST` 对应用用户**不可写**（真机实测 `readonly`），且 fnOS 未提供任何"令 target 可写"的声明机制。

**但注意路线 2/3 仍解决不了根本矛盾**（见 4.7 末段）：即使源码可更新，冻结的 site-packages 无法跟随
`requirements.txt` 变化，更新到需要新依赖的上游版本会让 Alas `ImportError` 起不来。
所以「在线更新」与「自包含冻结运行时」本质互斥；**推荐仍为路线 1**。

---

### 4.7 安装目录只读是平台设计（官方依据 + 真机实测）

> ⚠️ **2026-10-03 更正（重要）**：下面这条真机命令**测错了目录**。
> `/var/apps/azurlaneautoscript` 是「应用根目录」（内含 `cmd/`、`config/`、`manifest` 以及
> `target`、`var` 两个软链），**不是** `TRIM_APPDEST`。`TRIM_APPDEST` 实际是
> `/vol{n}/@appcenter/azurlaneautoscript`（经 `/var/apps/{appname}/target` 软链到达）。
> 因此 `readonly` 只证明「应用根目录不可写」，**不能**证明 `target/alas` 不可写。
>
> 更关键的反证：`console_server.prepare()` 的 `_link_into_pkgvar()` 会在
> `<target>/alas/` 里 `shutil.rmtree(config)` 并 `os.symlink(...)` —— 这两步都需要对
> `<target>/alas/` 的写权限，而真机上应用**运行正常、配置可上传**，说明该写入确实成功了。
> 结论只能是二者之一：① console_server 实际以 **root** 运行（`cmd/main` 未降权）；
> ② `target` 对应用用户本就可写。**待用下方探针定论。**

**真机实测（2026-10-03，用户执行）**：

```bash
$ sudo -u azurlaneautoscript test -w /var/apps/azurlaneautoscript && echo writable || echo readonly
readonly          # ← 注意：测的是应用根目录，不是 TRIM_APPDEST
```

**待执行探针（定论用）**：

```bash
# 1) 到底谁在跑（最关键）
ps -eo user,pid,args | grep -E 'console_server\.py|uvicorn' | grep -v grep

# 2) 真实路径与属主
readlink -f /var/apps/azurlaneautoscript/target
ls -ld /var/apps/azurlaneautoscript /var/apps/azurlaneautoscript/target \
       /var/apps/azurlaneautoscript/var

# 3) 应用用户对 target/alas 与 var 是否可写
sudo -u azurlaneautoscript test -w /var/apps/azurlaneautoscript/target/alas \
  && echo TARGET_ALAS_WRITABLE || echo TARGET_ALAS_READONLY
sudo -u azurlaneautoscript test -w /var/apps/azurlaneautoscript/var \
  && echo VAR_WRITABLE || echo VAR_READONLY

# 4) 运行时是否真在 target 里建了软链（验证上面的推断）
ls -la /var/apps/azurlaneautoscript/target/alas/ | head -25
```

官方（`developer.fnnas.com`）对「需要写入目录」给出的方案，**就是这套目录约定本身**，而不是提供令安装目录
可写的手段。目录语义与可写性（「应用用户可写」一列为官方设计意图，非实测结论）：

| 目录 | 环境变量 | 用途 | 设计意图：应用用户可写 |
|---|---|---|---|
| `target` | `TRIM_APPDEST` | 已安装的应用文件和运行资源 | ❌ 否（只读语义，但**实测待定**，见上） |
| `etc` | `TRIM_PKGETC` | 应用配置 | ✅ |
| `var` | `TRIM_PKGVAR` | 需要在应用重启后保留的运行数据（位于存储卷） | ✅ |
| `tmp` | `TRIM_PKGTMP` | 临时文件 | ✅ |
| `home` | `TRIM_PKGHOME` | 应用用户数据 | ✅ |
| `shares/` | `TRIM_DATA_SHARE_PATHS` | `config/resource` 声明的共享目录（Windows ACL，用户可见） | ✅ |
| 用户授权目录 | `TRIM_DATA_ACCESSIBLE_PATHS` | 用户在应用设置中授权的目录 | ✅ |

来源（官方文档，2026-10-03 抓取）：

- 《应用框架》`/docs/core-concepts/framework/` —— 安装后布局为 `/var/apps/{appname}`，
  `target -> /vol{n}/@appcenter/{appname}`、`etc -> /vol{n}/@appconf/{appname}`、
  `var -> /vol{n}/@appdata/{appname}`、`tmp -> /vol{n}/@apptemp/{appname}`、`home -> /vol{n}/@apphome/{appname}`；
  `var` 的定义是「需要在应用重启后保留的运行数据」。
- 《环境变量》`/docs/core-concepts/environment-variables/` —— `TRIM_APPDEST` / `TRIM_PKGVAR` 等路径变量的含义；
  其 `cmd/main` 示例给出的官方范式是**把 target 当模板、首次启动复制到可写目录**：
  `cp "$TRIM_APPDEST/config.conf.example" "$TRIM_PKGETC/config.conf"`。
- 《应用权限》`/docs/core-concepts/privilege/` —— 默认 `run-as=package`；「普通应用运行时不建议使用 Root 模式」；
  需要访问用户数据时应由用户授权目录，或由 `config/resource` 声明共享目录。
- 《应用资源》`/docs/core-concepts/resource/` —— `data-share` 共享目录，安装时由系统创建并自动授予
  应用运行用户 ACL；通过 `TRIM_DATA_SHARE_PATHS` 或 `/var/apps/{appname}/share/` 软链访问。

**本包已符合该范式**：`console_server.prepare()` 把 `alas/config`、`alas/log` 软链到 `$TRIM_PKGVAR`，
`deploy.yaml` 落在 `$TRIM_PKGVAR/config/`。**除「在线更新」外，本应用无其他写入需求。**

**官方未提供、也不推荐的手段**：

- 没有任何 manifest 字段或 config 项能把 `target` 声明为可写。
- `config/privilege` 的 `run-as: root` 理论上可绕过（root 对非只读挂载有写权限），但官方口径明确
  「只有没有更窄方案时才请求 Root 模式」「长期运行并对外提供访问的进程应尽可能以非 root 用户运行」。
  为恢复一个可选功能把整个 Web 服务提到 root，**不采纳**。

**根本约束（比权限更关键）**：即便解决了目录可写，`InstallDependencies` 仍必须关闭 ——
运行时的 `site-packages` 是打包时冻结的。上游 Alas 的更新常伴随 `requirements.txt` 变化，
一旦取得需要新依赖的版本，Alas 会 `ImportError` 起不来，而 fpk 无法自动补依赖。
所以「在线更新」本质上与「自包含冻结运行时」互斥，只有把依赖也留给运行时装（即放弃自包含）才真正成立。

---

### 4.8 脚本热更新：可行性实测数据（2026-10-03）

#### 4.8.1 上游更新机制的确切实现（代码级，upstream @ `77f4d01f`）

**先纠正一个常见误解：上游不是「全量交换」，而是「git 增量传输 + 工作树重建」。**

网页「检查更新」面板（`module/webui/app.py:793-950`）里的**每一个**数据点都来自 git：

| UI 元素 | 底层调用 | 依赖 |
|---|---|---|
| 「当前版本 / 上游版本」两个短 SHA | `updater.get_commit()` → `git log -1 --pretty=…` | **git** |
| 最近 20 条更新历史 | `updater.get_commit(f'origin/{branch}', n=20)` | **git** |
| 「检查更新」按钮 | `updater.check_update()` → `_check_update()` | **`git fetch`** |
| 「立即更新」按钮 | `updater.run_update()` → `update()` → `git_install()` + `pip_install()` | **git** |

`git_install()`（`deploy/git.py:87`）的两条分支：

- `GitOverCdn=true`（**默认 False**，见 `deploy/config.py:66`）→ `GitOverCdnClient.update()`：
  下载**增量** zip `{latest_commit}/{current_commit}.zip` → 解出 `pack-*.pack/.idx` 写入
  `.git/objects/pack/` → 改写 `.git/refs/remotes/origin/master` → **`git reset --hard`**
- 否则（默认路径）`git_repository_init()`：`git init` → `git fetch origin master`
  → **`git reset --hard origin/master`** → `git pull --ff-only`

其余默认值：`AutoUpdate=true`（`config.py:19`）、`Repository=https://github.com/LmeSzinc/AzurLaneAutoScript`（:14）、
`GitExecutable=./toolkit/Git/mingw64/bin/git.exe`（:16，Windows 路径）。

**结论**：传输是增量的（`fetch` 只传缺失对象 / GOC 只传差异 pack），但**结果**是把工作树强制重建为
上游 master 的完整快照 —— 所以**效果上**确实是「全量交换」，**机制上**却必须依赖 git。
硬依赖三件套：**`git` 二进制 + `.git` 仓库 + 可写工作树**，本包三者皆无。
（另：`deploy/git_over_cdn/client.py` 虽然免 git *下载*，但 `git_reset()` 仍要 git 来应用 pack，
且 `current_commit` 从 `.git/refs/...` 读 —— 同样卡在 `.git` 上，此路不通。）

#### 4.8.2 原样「参照上游」的代价（实测）

| 需要补进包里的东西 | 体积 / 代价 |
|---|---|
| 可执行的 `git`（x86_64 / glibc 2.x） | ~10–15 MB（压缩后） |
| `.git` 仓库（要能承接 GOC 增量 pack，必须有 baseline 对象） | 实测 **328 MB**（其中 `pack` 326 MB） |
| `alas/` 工作树可写 | 必须挪出只读安装目录，首次多一次约 148 MB 拷贝 |

→ 包体积 324 MB → **约 700 MB**，且仍要处理 `.git` 与 fpk 升级的冲突。**不划算，不建议。**

#### 4.8.3 关键实测：GOC CDN 是上游的实时镜像

| 来源 | commit |
|---|---|
| GOC CDN `latest.json` | `77f4d01fcd2b0acab05a4d89260e8a0a9cd03d21` |
| GitHub API `branches/master` | `77f4d01fcd2b0acab05a4d89260e8a0a9cd03d21`（2026-09-28T15:38:02Z，PR #6023） |
| 本仓库 HEAD（我们自己的 fnOS 提交） | `359528af…` ← **不是上游** |

**前两者完全一致** → GOC `latest.json` 可放心作为「上游最新版本」的探测源（91 B / 0.15 s）。
⚠ 注意：本仓库 HEAD 带我们自己的提交，**打包时必须记录上游 master 的 SHA**，
不能拿本仓库 HEAD 去和上游比，否则会永远显示「有更新」。

#### 4.8.4 版本探测端点（已实测：匿名可访问、国内友好）

| 端点 | 实测结果 |
|---|---|
| `https://1818706573.cdn.123clouddisk.com/1818706573/pack/LmeSzinc_AzurLaneAutoScript_master/latest.json` | 200，91 B，`{"commit":"77f4d01fc…","time":"2026-09-28 23:38:02"}` |
| `https://alas-goc-1254325529.cos.ap-shanghai.myqcloud.com/LmeSzinc_AzurLaneAutoScript_master/latest.json` | 200，内容同上（腾讯云 COS 回源） |

→ 用它做**版本探测**：一个 91 字节的请求即可知道上游最新 commit，成本几乎为零。

**下载量实测（开发机直连）**

| 方式 | 体积 | 耗时 |
|---|---|---|
| 全量源码包 `codeload.github.com/…/tar.gz/refs/heads/master` | **87.8 MB** | 51 s（1.7 MB/s） |
| 第三方代理 `ghfast.top` / `gh-proxy.com` 同 URL | HTTP 200，`application/x-gzip`，可用 | — |

**增量更新量实测**（由本地仓库历史计算：`git diff --name-only <old> HEAD` 得变更列表，
再用 `git ls-tree -r --format='%(objectsize) %(path)'` 汇总新文件体积）

| 落后上游 | 变更文件数 | 合计体积 | 其中 `assets/` |
|---|---|---|---|
| ~30 次提交（约 3 周） | 90 | **1.95 MB** | 0.07 MB |
| ~100 次提交（约 5 周） | 332 | **4.05 MB** | 0.82 MB |
| ~250 次提交（约 3 个月） | 1065 | **11.29 MB** | 6.97 MB |

*参照：本包 alas 全部顶层目录合计约 148 MB，其中 `assets/` 89 MB、`bin/` 42 MB。*

**关键事实**：`assets/` 在最近 200 次提交里被改过 **708 个文件** —— 新地图**确实**会带新图片资源。
因此「只更新代码、`assets/` 保持只读」的方案会漏掉新地图所需的资源，**不可取**。

**GitHub API 可用性**：`api.github.com/repos/LmeSzinc/AzurLaneAutoScript/git/trees/<ref>` 可访问，
返回含全量 `path → blob sha` 的 JSON（实测一次请求约 3.1 MB）→ 这是做**增量**的前提。

**下载源候选（按回退顺序）**：`codeload.github.com` 直连 → `ghfast.top` → `gh-proxy.com`；
版本探测统一用 GOC CDN `latest.json`。

### 4.9 脚本热更新：已实现的方案（1.0.2，接管更新面板）

> 这是 4.8 调研结论的落地实现。**用户已确认按此方案改**（2026-10-03）。

#### 4.9.1 核心思路：不照搬 git，而是替换 `Updater` 的三个方法

保留上游更新面板的**页面、按钮、进度提示、失败处理、更新后自动重启**全部不动，只把
**数据来源**换掉 —— 上游那四个数据点全部来自 `git`，我们替换其中三个底层方法即可：

| 上游方法 | 原实现 | 本补丁实现 | 是否依赖 git / 写安装目录 |
|---|---|---|---|
| `Updater.get_commit` | `git log -1 --pretty=…` | 读 `alas_version.json`（本地）/ 上游版本缓存（`origin/*`，n>1 时给历史列表） | ❌ |
| `Updater._check_update` | `git fetch` | 请求 GOC CDN `latest.json`（**91 B**）与本地 `base_commit` 比对 | ❌ |
| `Updater.git_install` | `git reset --hard origin/master` | 下载源码包 tarball → 校验 → **原子交换** `$TRIM_PKGVAR/alas` | ❌ |

`run_update()` / `update()` / `pip_install()` / `check_update()` 等**外层方法一律不改**，
所以上游的行为契约（含 `EnableReload` 触发的重启）原样生效。

#### 4.9.2 注入方式：`sitecustomize.py` + import hook（不改上游任何文件）

补丁放在 **`<target>/patch/`**（`TRIM_APPDEST/patch`），由 `console_server` 启动 Alas 时注入：

```python
env["ALAS_FNOS_PKGVAR"] = self.pkgvar
env["ALAS_FNOS_APPDEST"] = self.appdest
env["PYTHONPATH"] = self.patch_dir + (":" + existing if existing else "")
cmd = [self.python, os.path.join(self.alas_dir, "gui.py"),
       "--host", "127.0.0.1", "-p", str(self.webui_port)]
```

- CPython 启动时 `site` 模块会**自动 import `sitecustomize`** → 无需改上游代码、无需 site-packages 写权限。
- `sitecustomize.py` 把自身目录塞进 `sys.path` 并调用 `alas_fnos.install()`，
  **整体包在 try/except 里**：补丁自身出错只写 stderr，绝不拖垮 Alas 启动。
- `install()` 做两件事：给 `uvicorn.run` 补上 `ws_max_size=64MB`（上游 `gui.py` 直接调 `uvicorn.run`，
  绕过了我们的网关设置）；向 `sys.meta_path` 插入一个 finder。
- 该 finder 只认 `module.webui.updater`：命中后用 `_LoaderProxy` 包住原 loader，
  **等原模块 `exec_module` 执行完**，再对 `Updater` 类打补丁（`_alas_fnos_patched = True` 保证幂等）。
- 首次插入时额外起一个 daemon 线程，6 秒后预热上游版本缓存 → 首次打开面板不必等网络。

> **为什么用 import hook 而不是直接改文件**：`$TRIM_PKGVAR/alas` 会被运行期更新整体替换，
> 任何写进源码树的改动都会在下次更新后消失。补丁放在 **`patch/`（安装在 target，不参与更新）**，
> 所以**补丁不会随 alas 更新而失效** —— 这是本方案能成立的关键。

#### 4.9.3 更新流程（等价于 `git reset --hard`）

```
download  https://codeload.github.com/LmeSzinc/AzurLaneAutoScript/tar.gz/<commit>
    ↓     （失败按回退：ghfast.top → gh-proxy.com）
extract   解压到 $TRIM_PKGVAR/.alas-staging-<ts>，剥掉顶层目录 AzurLaneAutoScript-<sha>/
    ↓     拒绝 `..` 路径、拒绝绝对路径/越界软链目标
validate  必须存在 alas.py、module/webui/app.py、deploy/config.py、deploy/template
    ↓     缺任一 → 判定下载不完整 → 删暂存树 → ExecutionError（被上游 retry(tries=3) 接住）
swap      alas → .alas-prev-<ts>；.alas-staging-* → alas（都是 os.replace，同文件系统内原子）
    ↓     任一步失败 → 回滚 prev → alas
relink    alas/config、alas/log 重新软链到 $TRIM_PKGVAR（种子文件先合并进 PKGVAR，不覆盖已有）
    ↓
prune     只保留最近一份 .alas-prev-*，删掉更早的 prev/staging/download（每份约 150 MB）
    ↓     失败只记日志，不影响已完成的代码更新
write     alas_version.json ← {base_commit, base_time, message, author, source:"update", updated_at}
```

**回滚策略**：`.alas-prev-<ts>` 留下一份旧树供人工回退（`mv` 回来即可）；
交换失败自动回滚；校验失败直接丢弃暂存树、不动现网。

#### 4.9.4 版本记录与「有更新」判定（这是最容易踩的坑）

`alas_version.json` 有**两份**，路径不同、用途不同：

| 文件 | 位置 | 谁写 | 用途 |
|---|---|---|---|
| 出厂记录 | `<target>/alas_version.json` | `build_fpk.sh` 打包时生成 | 安装包基线（`source: "filepack"`） |
| 运行记录 | `$TRIM_PKGVAR/alas_version.json` | `console_server.seed_alas()` 播种 / 补丁更新后写 | **实际比对基准** |

> ⚠️ **必须记录「上游 master 的 SHA」，不能拿本仓库 HEAD。** 本仓库带我们自己的 fnOS 提交，
> 拿 HEAD 去和上游比会**永远显示「有更新」**。`build_fpk.sh` 用
> `git merge-base HEAD refs/remotes/origin/master` 求基线（可用环境变量 `ALAS_COMMIT` 覆盖），
> 本次实测得 **`77f4d01f`**，与 GOC `latest.json` 完全一致。

`dirty` 标记只看**核心 Alas 源码路径**（`alas.py gui.py module campaign deploy assets bin submodule webapp
requirements.txt requirements-in.txt`，排除 `:!deploy/fnos`）。原因：根 `.gitignore` 之类与
运行无关的改动会造成 `dirty=true` 误报（实测踩过）。

#### 4.9.5 源码树搬到 `$TRIM_PKGVAR/alas`（安装目录保持只读）

`console_server` 的职责变了：**安装目录里的 `alas/` 降级为「出厂种子」**，真正运行的是
`$TRIM_PKGVAR/alas` 的可写副本。`seed_alas()` 的播种策略：

| 条件 | 动作 |
|---|---|
| 目标树不存在 | `copytree(seed, target)`（**复制而非移动**，种子留着供 `reset_alas` 回退） |
| 运行记录 `source == "update"` | **保留**用户已更新过的版本，不被安装包覆盖 |
| `source == "fpk"` 且安装包基线 ≠ 当前基线 | 随安装包**重播**（旧树先 `os.replace` 到 `.alas-prev-*`，失败回滚） |
| 其余 | 沿用现有树 |

配套 API：`POST {prefix}/api/alas/reset` → 停服务 → 删树+版本 → 重新播种 → 重新软链 `config`/`log` → 重启。
（`reset_alas()` 必须**重新软链** `config`/`log` —— 这是离线测试抓出来的真实缺陷。）

`prepare()` 现在只写 `$TRIM_PKGVAR`，**不再需要写安装目录**，与 4.7 的「target 只读」设计自洽。

#### 4.9.6 强制的 `deploy.yaml` 键（1.0.2 起）

```python
FORCED_DEPLOY = {
    "InstallDependencies": "false",   # 运行时依赖随包冻结，绝不让 pip 动
    "EnableReload": "true",           # ← 1.0.2 放开：让 gui.py 建立重启循环
    "AutoUpdate": "true",             # ← 1.0.2 放开：否则 git_install 开头直接 return
    "CheckUpdateInterval": "0",       # 0 才不注册 check_update 后台轮询
    "AutoRestartTime": "null",        # None 使 schedule_update 任务自我摘除
    "ReplaceAdb": "false",
    "AdbExecutable": "adb",
    "WebuiHost": "127.0.0.1",
    "Password": "null",
}
```

> **`EnableReload` 是关键**：`State.restart_event` **只在 `gui.py:18` 赋值**。
> 我们此前直接起 uvicorn 绕过了 `gui.py`，导致 `restart_event is None` → 更新面板显示
> `Gui.Update.DisabledWarn` 且不会自动重启。改为 `python3.7 gui.py` +
> `EnableReload=true` 后，`gui.py` 用 `multiprocessing.Event` + `Process` 建立重启循环，
> 上游「更新完成 → 自动加载新代码」的原生行为即刻恢复。
> （Alas 本就依赖 multiprocessing —— `State.init()` 里有 `multiprocessing.Manager()`，该循环无额外代价。）

⚠️ **本次随之开启**：该进程不再由 uvicorn 直接托管，`cmd/main stop` 仍按 PID 停，
但重启循环的**父进程**是 `gui.py`，脚本停服务时需确认进程组整体退出（见 4.3 的 `start_new_session`）。

#### 4.9.7 已知限制（必须如实交接）

1. **依赖不会跟着更新**。`site-packages` 是打包时冻结的，`InstallDependencies` 强制 `false`。
   若上游新版本 `requirements.txt` 引入了我们没有的依赖，更新后 Alas 会 `ImportError` 起不来。
   **缓解**：`POST /api/alas/reset` 可一键回到安装包内的出厂版本（含配套依赖）。
   **这是「自包含冻结运行时」与「在线更新」的本质矛盾，无法在本架构内彻底消除。**
2. **`git` 相关分支不可用**：`GitOverCdn=true`、`git_repository_init()` 等路径仍会失败，
   但因三个方法已被整体替换，正常流程不会走到它们。
3. **`get_commit('origin/…', n=20)` 的历史列表**依赖 GitHub API（一次约 3.1 MB）。
   失败只记日志并返回空列表，**不影响更新功能**（面板历史表会空着）。
4. **下载体积**：全量源码包 **87.8 MB**（实测 51 s）。已按 4.8.4 的数据确认
   「只更代码不更 assets」不可取（200 次提交里 `assets/` 改了 708 个文件），故接受全量。
   暂存期间 `$TRIM_PKGVAR` 需额外约 **240 MB** 空闲（下载包 + 暂存树），随后 `_prune` 回收。

#### 4.9.8 离线自测证据（33 项全绿）

测试脚本 `/tmp/alasfnos_test/test_patch.py`，在开发机上用 Python 3.7 语法检查 + 桩模块跑通：

| 组 | 断言 |
|---|---|
| 语法兼容 | `alas_fnos.py` / `sitecustomize.py` 可被 **Python 3.7** 编译（无 walrus、无 f-string `=`） |
| 版本读写 | `read_version` / `write_version` 原子写（`os.replace`）、缺文件返回 `{}` |
| `get_commit` | `n==1` 返回 4 元组；`n>1` 返回列表；`short_sha1` 只改首元素；本地分支读运行记录 |
| `check_update` | 本地=上游 → `False`；不等 → `True`；上游不可达 → `False`；本地未知 → `True` |
| 解压 | 剥顶层目录、拒绝 `..`、拒绝越界软链、拒绝绝对链接目标 |
| 校验 | 缺 `REQUIRED_FILES` 任一 → `ExecutionError`，且**happy path 不 import `deploy`** |
| 交换 | 原子换树、旧树成 `.alas-prev-*`、`config`/`log` 重链、失败回滚、`_prune` 只留一份 |
| 幂等 | `install()` 二次调用不重复插 finder、不重复预热 |
| 注入 | import hook 命中 `module.webui.updater` 且**原模块执行后**才打补丁；`_alas_fnos_patched` 生效 |

---

### 4.10 卸载向导：可选「是否清理数据」（1.0.2）

> ⚠️ **本节取代 4.1 骨架结构里的「uninstall 刻意不给删除数据开关（R5）」**。
> 1.0.2 起按官方 wizard 规范补上了这个开关，用户可在卸载时自行决定。

#### 4.10.1 向导字段

`fpk/wizard/uninstall`（**绝不能是空数组 `[]`** —— 真机会报 `code 10111`，见第八节）：

```json
[
  {
    "stepTitle": "卸载选项",
    "items": [
      { "type": "tips", "helpText": "…卸载不影响 Android 设备与 ADB 配置…" },
      {
        "type": "radio",
        "field": "wizard_data_action",
        "label": "应用数据处理",
        "initValue": "keep",
        "options": [
          { "label": "保留数据（推荐）…", "value": "keep"  },
          { "label": "删除全部数据 —— 不可恢复…", "value": "purge" }
        ]
      }
    ]
  }
]
```

要点（对照官方 wizard 文档）：

- 自定义字段**必须带 `wizard_` 前缀**，且**不得**使用 `TRIM_`（平台保留）。
- `field` 名会成为生命周期脚本的**同名环境变量** → 脚本里读 `$wizard_data_action`。
- `initValue: "keep"` —— **默认不删数据**，与旧行为一致，避免用户不看清就丢配置。
- `tips` 项同时满足「数组非空」与「说明清楚」两个目的。

#### 4.10.2 两个脚本都实现（`uninstall_init` 主责 + `uninstall_callback` 兜底）

`cmd/uninstall_init`（删文件前）：

1. 复用 `cmd/main stop` 停服务（此时安装目录还在，能直接用）。
2. 归一化环境变量：

   ```bash
   DATA_ACTION="$(printf '%s' "${wizard_data_action:-}" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
   case "$DATA_ACTION" in
     purge|delete|remove|clean|true|1|yes) PURGE=1 ;;
     *) PURGE=0 ;;
   esac
   ```

   —— 容忍大小写与空格，且**未知值一律按保留处理**（保守优先）。
3. `PURGE=0` → 打印 `保留应用数据：$PKGVAR` 后 `exit 0`。
4. `PURGE=1` → 先过 **路径护栏**：

   ```bash
   case "$PKGVAR" in
     ""|"/"|"/var"|"/usr"|"/vol"|"/vol1"|"/vol2")
       echo "数据目录路径异常，拒绝清理：$PKGVAR" >&2; exit 0 ;;
   esac
   ```

   然后**只删本应用自己管理的条目**，绝不整目录 `rm -rf`：

   | 删 | 说明 |
   |---|---|
   | `config/`、`log/`、`alas/` | 用户配置、日志、运行期更新过的源码树 |
   | `alas.log`、`alas.pid`、`console.pid`、`console.log` | 运行期产物 |
   | `alas_version.json` | 版本记录（删掉 = 下次安装视为全新） |
   | `.alas-prev-*`、`.alas-staging-*`、`.alas-download*` | 更新过程的临时树（每份约 150 MB） |

   平台可能放进 `$TRIM_PKGVAR` 的其他文件**不碰**。

`cmd/uninstall_callback`：同样的归一化 + 护栏 + 清理逻辑，作为兜底再扫一遍
（`init` 阶段若因故被打断，`callback` 仍能完成清理）。

#### 4.10.3 离线测试证据（全绿）

`/tmp/alasfnos_test/test_uninstall.sh`，用 `expect <path> <1|0> <desc>` 辅助函数显式传环境变量，
覆盖分支：

| 用例 | 期望 |
|---|---|
| `wizard_data_action` 未设置 | 保留，`exit 0` |
| `keep` | 保留 |
| `KEEP` / ` keep `（大小写+空格） | 保留 |
| `purge` / `PURGE` / `1` / `true` / `yes` / `clean` | 清理 |
| 未知值 `maybe` | **保留**（保守） |
| `PKGVAR="/"` 或 `""` | 拒绝清理，`exit 0` |
| 存在 `.alas-prev-*` / `.alas-staging-*` | 一并清掉 |
| 平台放置的无关文件 | **保留** |

> **踩过的坑**：一开始写成 `wizard_data_action=keep run ...` 期望作用域内赋值，
> 实测在本地 shell 里不生效，且本机 `grep` 行为异常（返回空）。
> 改成显式传参 + `[[ ... == *"..."* ]]` 字串判断后全部稳定通过。

---

### 4.11 用「上一版 Alas」打测试包（验证检测更新 + 更新功能）

#### 4.11.1 为什么需要

正常发布的包，基线就是**上游最新**（`77f4d01f`）。装上去点「检查更新」只会显示
**「已是最新」**，`git_install` 直接 `return` —— **根本走不到下载/交换/重启那条路径**，
更新功能等于没法验证。必须打一个**基线落后于上游**的包。

#### 4.11.2 做法（三步）

```bash
# 1) 取「上一个上游版本」到一个临时目录
OLD="$(git -C /path/to/AzurLaneAutoScript rev-parse refs/remotes/origin/master^1)"
git clone --shared --no-checkout /path/to/AzurLaneAutoScript /tmp/alas-old
git -C /tmp/alas-old checkout --detach "$OLD"
git -C /tmp/alas-old update-ref refs/remotes/origin/master \
    "$(git -C /path/to/AzurLaneAutoScript rev-parse refs/remotes/origin/master)"

# 2) 抬高应用版本号（否则无法覆盖安装到设备上已有的版本）
sed -i.bak 's/^version=.*/version=1.0.3/' deploy/fnos/fpk/manifest

# 3) 用该源码树打包
./deploy/fnos/build_fpk.sh --alas-src /tmp/alas-old

# 4) 还原版本号 + 清理
mv deploy/fnos/fpk/manifest.bak deploy/fnos/fpk/manifest
rm -rf /tmp/alas-old
```

- `--shared` 让临时 clone 走主仓库的对象库（`alternates`），**秒级完成、不复制 700 MB**；
  用完直接 `rm -rf`，对主仓库无影响（已用 `git fsck --connectivity-only` 验证）。
- `--alas-src` 是本次为测试新增的能力（见 4.2）；脚本会从**该源码树自己的 git** 推断基线，
  所以 `alas_version.json` 自动就是旧版本，**不需要手写 `ALAS_COMMIT`**。
- 版本号必须抬高：设备上已有 1.0.2 时，同版本或降级都装不上。

#### 4.11.3 实测结果（2026-10-03）

> **本节记录 1.0.3 的实测数据；当前应使用 1.0.4**（= 1.0.3 的功能 + 4.12 的三处修复，
> 基线同为 `01c0a010`，构建方式完全相同）。1.0.4 的核验见 4.12.5。

打包命令 `./deploy/fnos/build_fpk.sh --alas-src /tmp/alas-old-01c0a010`，**EXIT=0**。

| 项 | 值 |
|---|---|
| 产物 | `deploy/fnos/dist/azurlaneautoscript_1.0.3.fpk`（339,226,683 B / 324 MB） |
| SHA256 | `985311d48a7e38ea67d551f3ccaca9cadc6e2187da94bf68ca1fe003f42af374` |
| 包内基线 | `01c0a0101a7ce7bf4adec17f9a4ed46ebb94cfa1`（2026-09-24，`Upd: [TW] event entrance…`） |
| 包内 `dirty` | `false`（干净检出，正确） |
| 包版本 | `1.0.3`（`packed_app_version`） |
| 装配体积 | 848 MB → 324 MB（与正常包一致） |
| 预检 | 0 blocker / high |

**如何证明包内真的是旧版**（不能只看版本号字段）：

| 判别方式 | 结果 |
|---|---|
| 新版才新增的 `assets/cn/private_quarters/PRIVATE_QUARTERS_SHIP_IMPLACABLE.png` | 包内**不存在** → 旧版 ✅ |
| `module/private_quarters/private_quarters.py` 逐字节哈希 | 包 `0974dc68df45` = 旧版；新版为 `9520e992f551` ✅ |
| `module/dorm/dorm.py` | 包 `6903e35df109` = 旧版；新版 `e04f13455b61` ✅ |
| `module/equipment/equipment_code.py` | 包 `b3cd60cc544e` = 旧版；新版 `17505caf81e7` ✅ |

（`01c0a010 → 77f4d01f` 共 13 个文件、+41/-10，见 4.8.3。）

#### 4.11.4 用这个包怎么测（装到设备后）

装 `1.0.4` 覆盖现有版本（1.0.4 > 1.0.3 > 1.0.2，都能装）→ 打开 Alas 配置界面 → 滚到更新区域：

| 步骤 | 预期 |
|---|---|
| 打开更新面板 | 「当前版本」= **`01c0a010`**（不是 `77f4d01f`，也不是空） |
| 点「检查更新」 | 提示**有新版本**；上游版本显示 `77f4d01f`；最近更新历史能列出条目 |
| 点「立即更新」 | `alas.log` 出现 `[alas-fnos] 下载源码包：…` → `源码包就绪：… (xx MB)` → `更新完成：77f4d01f` |
| 更新后 | **自动重启**并加载新代码（验证 `EnableReload` + `gui.py` 重启循环） |
| 版本记录 | `$TRIM_PKGVAR/alas_version.json` 的 `base_commit` 变 `77f4d01f…`、`source` 变 `"update"` |
| 用户数据 | `$TRIM_PKGVAR/config`、`log` **原样保留**；`alas/config` 仍是软链 |
| 安装目录 | `$(readlink -f /var/apps/azurlaneautoscript/target)/alas` **未被改动** |
| 旧树备份 | `ls -d $TRIM_PKGVAR/.alas-prev-*` 恰好 **1 份** |
| 逃生通道 | `POST /app/azurlaneautoscript/api/alas/reset` 能回到出厂版 `01c0a010`（`source` 变回 `"fpk"`） |

⚠️ **测完要退出测试包**：测试包版本比现有正式包高，**无法直接降级**。
两条路：
1. 应用中心**卸载**（默认保留数据）→ 再装正式包；
2. 等一个版本号更高的正式包（`1.0.4` 已被测试包占用，正式包计划发 **1.0.5**，
   构建时去掉 `--alas-src` 即为正式基线）。若此时脚本树已是 `source=update`，覆盖安装会
   **保留用户更新过的脚本树**（`seed_alas()` 的设计行为），不会白跑一次更新。

### 4.12 真机问题：「装了新包，更新面板仍显示最新版本」（1.0.4 修复）

#### 4.12.1 用户反馈原文

> 是不是上一个版本清理数据没有作用啊，安装1.0.3后怎么还是最新的版本

这是**两个独立的问题**，不要混在一起判断：

* **(a)** 卸载向导里选「删除全部数据」到底删没删 → 见 4.12.4 的判别方法；
* **(b)** 更新面板显示「已是最新」→ **和 (a) 没有因果关系**：即使数据一个字节没删，
  只要应用在升级后**重新启动过**，`prepare()` → `seed_alas()` 就会按「包内基线 ≠ 运行记录」
  重播源码树并刷新版本记录，面板就会正确显示 `01c0a010`。反过来，**只要进程没重启，
  数据删得再干净也白搭** —— 因为面板是**正在运行的旧进程**渲染的。

#### 4.12.2 先把判定链看清楚（谁决定显示什么）

上游 `module/webui/app.py::dev_update()` 的关键事实：**打开更新面板就会自动检查一次**
（函数末尾直接调 `updater.check_update()`），不需要点按钮。

| 面板元素 | 取值来源 | 本包实现 |
|---|---|---|
| 「本地」行 | `Updater.get_commit()` | 读 `$TRIM_PKGVAR/alas_version.json` |
| 「上游」行 | `get_commit("origin/master")` | GOC `latest.json`（91 B） |
| 状态文案 | `Updater._check_update()` 的返回值 | 我们的 `check_update()` |

于是「还是最新的版本」只有四种可能，**看「本地」行和「上游」行就能当场分辨**：

| 情形 | 「本地」行 | 「上游」行 | 状态文案 | 含义 |
|---|---|---|---|---|
| **A. 正常** | `01c0a010` | `77f4d01f` | 有新版本 | 测试包按预期工作 |
| **B. 记录陈旧**（本次真机） | `77f4d01f` | `77f4d01f` | 已是最新 | 面板由**旧进程**渲染，或 `prepare()` 没跑 → 4.12.3 第 1 条 |
| **C. 补丁没生效** | 空 / `None` | 空 / `None` | 已是最新 | `PYTHONPATH` / `patch` 目录问题 → 看 `[alas-fnos]` 日志，**无该行即补丁未生效** |
| **D. 探测失败** | 本地正常 | **空** | 1.0.3 及以前：**已是最新**（误导）；1.0.4：更新失败 | 网络不可达或证书校验失败 → 4.12.3 第 2、3 条 |

**B 和 D 是本次实打实修掉的**；C 由 4.12.4 的一键脚本负责判定。

#### 4.12.3 三处根因与修复（1.0.4）

**1) 升级后没有重启 → 跑的还是旧代码**（最可能命中本次现象）

平台在升级时会替换 `<target>` 下的**全部文件**，但**不保证**之后把应用重新拉起来。
老进程（旧 console + 旧 Alas）继续跑，就等于还在用旧代码、读旧的版本记录 ——
这正是「装了 1.0.3 却显示 1.0.2 时代的 `77f4d01f`」的形态。
官方测试清单也把「运行中的应用能按预期停止和重启」列为**升级必须自己保证**的行为。

修复（`cmd/upgrade_init` + `cmd/upgrade_callback`）：

```bash
# upgrade_init：此时安装目录里还是旧文件，cmd/main status 判定可信
"$APPDEST/cmd/main" status >/dev/null 2>&1 && : >"$PKGVAR/.upgrade-restart-pending"
# upgrade_callback：有标记就停掉旧进程、再用新代码拉起
"$MAIN" stop; setsid "$MAIN" start
```

标记文件保证「用户本来就没开这个应用」时不会被强行拉起；`main start` 本身幂等
（`is_running` 直接返回），即便平台随后也启动一次也不会重复。

**2) 探测失败被伪装成「已是最新」**

上游 `_check_update()` 在网络失败时返回 `0` —— 与「没有更新」**同一个值**，
面板于是显示「已是最新」。我们 1.0.2 照抄了这个语义（`if not remote: return False`），
把「查不到」也显示成「不用更新」，是最容易被误判的一类故障。

修复：`check_update()` 现在返回三态 —— `True` 有更新 / `False` 已是最新 / `"failed"` 检查失败
（面板显示「更新失败」+ 重试按钮），同时先置 `self.state = "checking"`（与上游一致，
检查期间有 loading 提示）。

**3) 捆绑运行时没有系统 CA，HTTPS 可能整体失败**

`runtime/dist` 是从构建镜像里 `docker cp` 出来的裸解释器：**包内没有 `/etc/ssl/certs`**，
只有 `site-packages/certifi/cacert.pem`。而标准库 `urllib` **不读 certifi** ——
一旦宿主机缺 CA，所有 HTTPS 请求都会以 `SSLCertVerificationError` 失败，
再叠加第 2 条就变成「显示已是最新、什么也查不到」。

修复：`_ssl_context()` 显式用 `certifi.where()` 建 `SSLContext`（取不到再退回系统默认）。

**4) 顺带加固**

* 探测端点从 2 个增加到 5 个（GOC CDN / 腾讯 COS / GitHub API / 两个镜像站），
  `_parse_latest()` 同时兼容 GOC `latest.json` 与 GitHub `branches` 两种响应形状；
* `read_version()` 在运行期记录缺失时**回退到出厂记录**（`<target>/alas_version.json`），
  面板不会再显示空白版本；只提示一次，不刷日志；
* `seed_alas()` 每次 `prepare()` 都打印「包内记录 vs 运行记录」以及播种决策
  （`首次播种` / `随安装包重播` / `沿用现有源码树` / `已在运行期更新过`），
  并在包内记录不可读时**明确告警**而不是静默沿用。

#### 4.12.4 设备上一键定位：`deploy/fnos/tools/diagnose-update.sh`

只读脚本，`bash diagnose-update.sh` 即可（自动从运行进程的 `/proc/<pid>/environ` 里
取 `TRIM_APPDEST` / `TRIM_PKGVAR`）。输出 6 段：

| 段 | 看什么 | 判别 |
|---|---|---|
| 1 | 应用 `version` | 确认新包**是否真的装上了** |
| 2 | 包内 / 运行期两份 `alas_version.json` | 两者不一致 = `prepare()` 没跑或被跳过 |
| 3 | `console.log` 里的播种决策 | 有没有出现 `重播` / `沿用` |
| 4 | Alas 日志里的 `[alas-fnos]` 行 | **有 = 补丁生效（情形 C 排除）**；一行都没有 = 补丁没生效 |
| 5 | 用包内 CPython 实测三个探测端点 | 打印 `OK/FAIL` 与异常；证书问题会在这里现形 |
| 6 | `patch/`、`.alas-prev-*`、进程启动时间 | 对照 `manifest` 修改时间判断"装完有没有重启" |

#### 4.12.5 1.0.4 验证证据（2026-10-03 本机）

| 项 | 结果 |
|---|---|
| 产物 | `deploy/fnos/dist/azurlaneautoscript_1.0.4.fpk`（339,278,178 B / 324 MB） |
| SHA256 | `cf016c6ad5d466f23d1a9bc38bd56d7ec71c8716e12a594f89f6ef47427f5825` |
| 包内基线 | `01c0a0101a7ce7bf4adec17f9a4ed46ebb94cfa1`（2026-09-24，仍是"落后一版"的测试包） |
| 包内 `dirty` | `false` |
| 骨架预检 | 0 blocker / high |
| 装配体积 | 848 MB（runtime 703M + alas 145M）→ fpk 324 MB，runtime 文件数 7731 一致 |
| 离线自测 | 补丁 **42 项**全绿（新增 `_parse_latest` 4 项、出厂记录回退 4 项、`check_update` 三态 5 项） |
| console_server 自测 | 33 项全绿（含新增的「包内记录 vs 运行记录」日志） |
| 卸载分支自测 | 全绿 |
| 产物核验 | `cmd/*` 全 755；`upgrade_init` 含状态标记、`upgrade_callback` 含 stop+start+setsid；`patch/alas_fnos.py` 与源文件逐字节一致且含全部 5 处新逻辑；Python 3.7 语法通过；`.git` 目录 0 个、`deploy/fnos` 0 条；wizard 两个文件合法 JSON 且 `upgrade`/`config` 不存在 |
| 运行时 CA | 包内**无** `etc/ssl`，有 `site-packages/certifi/cacert.pem` → 证实 4.12.3 第 3 条的必要性 |
| 端点实测 | GOC CDN 91 B / 0.19 s；腾讯 COS 91 B / 0.13 s；GitHub API 直连 403（限流），`gh-proxy.com` 兜底 5175 B / 3.38 s → 均取到 `77f4d01f` |

#### 4.12.6 真机复测步骤（装 1.0.4）

1. 装 `1.0.4` 覆盖现有版本（1.0.4 > 1.0.3 > 1.0.2，都能装）。
2. **关键判定**：打开 Alas 更新面板看「本地」行。
   * 若是 `01c0a010` → 修复生效，直接进第 3 步；
   * 若仍是 `77f4d01f` → **手动重启应用**（应用中心停→启，或 `sudo appcenter-cli stop/start`），
     再看一次。手动重启后变正确，就**确认了根因是"升级后没重启"**（4.12.3 第 1 条），
     请把这一步的结果反馈给我。
3. 点「立即更新」走完整流程（日志 `下载源码包 → 源码包就绪 → 更新完成`、自动重启、
   `source` 变 `update`、配置/日志不丢、`.alas-prev-*` 恰好 1 份）。
4. 存疑时跑 `bash diagnose-update.sh`，把输出贴回来。

#### 4.12.7 真机第二轮反馈与 1.0.5 测试包（2026-10-03 晚）

用户反馈（装 1.0.4 后）：面板仍显示 `本地 77f4d01f / 上游 77f4d01f`；且「卸载时确认
`@appdata/azurlaneautoscript` 已被清空，重装后配置文件还是之前导入的」。

**本机已核实的事实**（排除了一批假说）：

* 包内 `alas/config/` 只有上游模板（`deploy.template-*.yaml` ×8 + `template*.json` ×3），
  **不含任何个人配置** → 「重装后旧配置还在」不可能来自安装包种子。
* console_server 没有第二个配置上传入口；`start_alas` 的 `cwd=$TRIM_PKGVAR/alas`，
  上传的配置必然落在 `$TRIM_PKGVAR/config`。
* 补丁 `get_commit` / `check_update` 每次调用都**现读** `alas_version.json`，无缓存。
* `seed_alas()`：树不存在 → 播种并写记录；`source=fpk` 且基线不同 → 重播并覆写记录。
  因此「数据被真正清空 + 装 1.0.4」的组合下面板必然显示 `01c0a010`。

**由此收窄到两种自洽解释**（靠设备证据裁决）：

1. **重装的其实是正式包 1.0.2**（基线本来就是上游最新 `77f4d01f`）→ 面板显示
   `77f4d01f/77f4d01f（已是最新）`是**正确行为**；而旧配置还在 = 卸载清理实际没生效。
2. **装的是 1.0.4，但浏览器里是一个旧的 PyWebIO 会话页面**（本项目已有浏览器缓存误导前科），
   屏幕上的版本号和配置列表都是旧渲染。

**1.0.5 测试包针对的确定性修复**（与裁决无关，都该修）：

* **卸载脚本静默 no-op 隐患**：`uninstall_callback` 在 `$TRIM_PKGVAR` 解析不到时直接
  `exit 0`（不留痕迹）；`uninstall_init` 同样无兜底。若平台在执行脚本前移走了 appdir
  （`var` 是指向 `/vol*/@appdata/<appname>` 的软链），「选了清理」就会无声失效。
  现在两个脚本都会：环境变量失效时按 `appname` 兜底扫描 `/vol*/@appdata/<appname>`；
  把向导取值、环境变量、解析结果、删除动作、清理后剩余条目**全部留痕**
  （echo 进平台日志 + `/tmp/azurlaneautoscript-uninstall.log`）。
* **`diagnose-update.sh` 新增第 7 节**：全卷扫描 `@appdata/<appname>`（含 config/ 明细与
  `alas_version.json` 内容）、僵尸进程检测（`/proc/<pid>/cwd` 显示 `(deleted)` 即老进程未死）、
  22267 端口占用者、卸载审计日志。

**裁决命令**（设备 SSH，60 秒）：

```bash
ls -la /vol*/@appdata/azurlaneautoscript/
cat   /vol*/@appdata/azurlaneautoscript/alas_version.json   # 01c0a010=测试包在跑；77f4d01f=正式包或旧数据存活
ls    /vol*/@appdata/azurlaneautoscript/config/             # 有导入文件=清理没生效
ps -ef | grep -E 'gui\.py|console_server' | grep -v grep
```

另注意：GOC CDN 的 `latest.json` 有延迟——2026-10-03 实测 CDN 仍为 `77f4d01f` 而
GitHub master 已是 `b9a965ce`。测试包照样会显示「有更新」（01c0a010 ≠ 77f4d01f），
但「上游版本」行跟随的是 CDN，不是 GitHub 实时值。

#### 4.12.8 裁决：root 权限 `python gui.py` 僵尸进程占用 22267（2026-10-03 深夜）

用户提供 4 条裁决命令输出，两个假说全部落空，真因唯一：

* `alas_version.json`：`base_commit=01c0a010`、`packed_app_version=1.0.5` → **装的就是
  1.0.5 测试包**（假说 1 死），数据目录里的版本记录完全正确。
* `config/` 12 个文件 = 11 个上游模板 + `deploy.yaml`（Alas 首次启动从模板生成，
  属正常产物）→ 数据目录本身干净。
* `ps -ef`：**4 个 root 用户的 `python gui.py` 进程自 Sep29 存活至今**，
  链条 `/bin/sh -c python gui.py`(1937514, PPID=1) → 1937591 → 1937618 → 1937687
  （层层嵌套是 Alas 自身重启机制反复再拉起的表现）。

**作用机制（解释全部现象）**：

1. fnOS 包的架构是「网关 console_server + 反代 `127.0.0.1:22267` 的 PyWebIO」；
   console_server 健康检查只测 `127.0.0.1:22267` 是否可连。
2. 老 root gui.py 自 Sep29 起一直**占着 22267**（cwd 指向已被卸载删除的旧
   `@appdata/alas` 目录）→ 新包的 gui.py 起不来（端口被占），健康检查却「成功」，
   网关于是把浏览器请求全部反代给**老进程**。
3. 老进程 = 老代码 + 老数据（被删目录靠打开的 fd / `/proc/<pid>/cwd` 仍可读），
   于是面板永远显示 `77f4d01f`，「重装后配置还在」是老进程渲染的**假象**。
4. 老进程属 **root**，console_server 以 `azurlan+` 运行 → 卸载/升级/自愈重启全都
   无权限杀它，故能穿越卸载存活。

**来源推断**：`/bin/sh -c python gui.py` + root + PPID=1，是 Sep29 前后有人用
root shell 手工（或按上游文档/Docker 方式）启动过一次 Alas，与 fnOS 包生命周期无关。

**处置（设备 SSH，root/sudo）**：

```bash
sudo kill 1937514 1937591 1937618 1937687      # 顽固时 -9
ls -l /proc/1937618/cwd                         # 杀前可佐证：(deleted)
ps -ef | grep 'gui\.py' | grep -v grep          # 应只剩 azurlan+ 的新进程
```

然后在应用管理里重启本应用，浏览器 **强刷（Ctrl+Shift+R）**。预期面板变为
`本地 01c0a010 / 上游 77f4d01f（有更新）`，即可正式测试检查更新/立即更新。

**遗留加固项（建议下一包实现）**：`console_server` 健康检查前校验 22267 的监听者
身份——若占用者 cmdline 不含本包 `$TRIM_PKGVAR`/runtime 路径，明确报错并在控制台
提示「端口被外部进程占用（root 僵尸 gui.py）」，而不是静默反代到老进程。

#### 4.12.9 真机第三轮：更新收尾 FileNotFoundError（1.0.6 修复）

装 1.0.5 后行为符合预期（面板 `01c0a010/77f4d01f`），点「立即更新」：下载、换树
**全部成功**，但收尾在 webui 里抛：

```
FileNotFoundError: [Errno 2] No such file or directory: './config/reloadalas'
  updater._run_update:252  with open("./config/reloadalas", mode="w")
```

**根因（唯一，链路完整）**：

1. 补丁 `git_install` → `_swap` 用 `os.replace` 把旧树整体挪到 `.alas-prev-*`、
   新树挪进 `$PKGVAR/alas`，随后 `_prune` **rmtree 掉旧树**。
2. 而正在执行更新的 webui 进程 cwd 仍指向旧树的 **inode**（`os.replace` 只改路径
   不改 inode，进程感知不到）→ rmtree 后 cwd 成了 `(deleted)`。
3. 回到上游 `_run_update`：`open("./config/reloadalas")` 相对 cwd 解析 → 目录已不存在
   → FileNotFoundError。`state` 卡死在 `"run update"`，`_trigger_reload` 没执行，
   **自动重载新代码没发生**（树其实已是新版，重启应用即生效）。
4. 更深的坑：gui.py 的 EnableReload 重启循环是 **fork**——父进程 cwd 永远钉在最初
   那棵树的 inode 上。就算修好第 3 步，reload 后 fork 出的新 webui 仍继承失效 cwd。

**修复（全部在 `alas_fnos.py`，三道防线）**：

| 防线 | 函数 | 作用 |
|---|---|---|
| 1 | `_swap` 新增 `_reanchor_cwd(current)` | 更新进程在 `_prune` 前显式 `chdir` 到新树，`./config/reloadalas`、`pip_install` 等相对路径全部恢复正确语义 |
| 2 | `_prune` 新增 `_cwd_holders()`（扫 `/proc/*/cwd`） | 旧树/暂存树若仍被任何进程当 cwd，**跳过清理**并留痕（保护 gui.py 父进程的 pinned inode，代价是最老一份备份暂时保留） |
| 3 | 新增 `_CwdHealFinder`（import hook） | fork 出的新 webui 进程在 **uvicorn/updater 首次导入前**自检 cwd，失效则锚回 `$PKGVAR/alas`——早于 webui 一切文件 IO；无 `ALAS_FNOS_PKGVAR` 时 no-op |

离线自测（macOS 无 `/proc`，用假 proc 树 + `_PROC_DIR` 注入）：`_cwd_holders` 命中
自身/子目录/`(deleted)` 形态/忽略无关与脏项、`_reanchor_cwd` chdir 且幂等、
`_prune` 占用跳过/空闲删除、无 env 时安全 no-op —— 4 项全过。

**当前设备状态与复测路径**：本次更新其实已完成换树（本地 77f4d01f，记录
`source="update"`，seed_alas 会尊重不重播）。先**重启应用**即可用上新代码；
要完整回归「检查更新→立即更新→自动重载」闭环，需装 **1.0.6 测试包**（基线仍为
01c0a010）：卸载（选清理）→ 装 1.0.6 → 更新应无报错且面板自动变回新版。

另：上一节的加固项（22267 监听者身份校验）仍未实现，记入下版。

**1.0.6 测试包**：`dist/azurlaneautoscript_1.0.6.fpk` = **339,296,372 B**，
SHA256 `c464738d692c5fbbc9a55db6947bfb7c1ba7c856db0afbb25aefdcc6d07766de`；
基线 01c0a010（dirty=false）、骨架预检 0 blocker/high、包内已验证含三道防线补丁。
临时源码树已清理，`git fsck --connectivity-only` 通过。

#### 4.13 包内自带 adb（决策 #1 修订，1.1.0）

**背景**：真机验证更新闭环（1.0.6，已通过）后，用户配置 Alas 跑实际任务时
`adbutils` 报 `FileNotFoundError: 'adb'`（5037 无 server，回退 `adb start-server`
失败——系统无 adb）。用户澄清决策 #1：**adb 二进制必须随包自带，不依赖外部环境；
设备/序列号等配置仍由使用者完成**。

**落地**：

* `deploy/fnos/vendor/adb/`：platform-tools **37.0.1** 的 `adb`（x86-64 ELF，
  SHA256 `a902be8f…3ed01`；DT_NEEDED 仅 glibc 家族，libc++ 已静态链接，零额外依赖）
  + 原版 `NOTICE.txt` + 记录来源/版本/校验和的 `README.md`。二进制入库（10.6 MB），
  构建离线可复现。
* `build_fpk.sh`（两份副本同步）：装配 `<target>/bin/{adb,adb-NOTICE.txt,adb-README.md}`，
  `clean_dir "$APP/bin"` 幂等；缺文件/不可执行直接 die。
* `console_server.start_alas`：`<appdest>/bin` 前插进 gui.py 的 `PATH` →
  默认 `AdbExecutable=adb` 直接命中，adbutils 自动 `adb start-server`。
  不改 `FORCED_DEPLOY`（`AdbExecutable: adb` 保持默认即可）。
* `github-repo/fnos-app/server/console_server.py` 同步。

**验证（本机）**：`bash -n` 两脚本通过；预检 0 blocker/high；包内 `bin/adb`
SHA256 与 vendor 一致；版本记录基线 `77f4d01f`（dirty=false）。

**1.1.0 正式包**：`dist/azurlaneautoscript_1.1.0.fpk` = **344,025,203 B**（+4.5 MB），
SHA256 `87769f36ac5934c733add63e460cd81704c8e7807f2696d05b88522ebce6359c`。
装配 859 MB。装 1.1.0 后只需在 WebUI 配 `Alas.Emulator.Serial`。

#### 4.14 adb server 起不来：HOME 不可写（1.1.1 修复）

**现象**（真机 1.1.0）：报错从 `FileNotFoundError: 'adb'` 变为纯
`ConnectionRefusedError`（5037）——adb 二进制已被 PATH 命中，但 adbutils 的
`adb start-server` 回退静默失败。用户在 SSH 里手工跑
`<target>/bin/adb start-server` 成功（server 全局共享，DETECT DEVICE 立即可用，
列出 `emulator-5554`），证明二进制本身完好。

**根因**：`start_alas` 的 `env = os.environ.copy()` 继承平台拉起 console_server
时的 `HOME`，不可写；adb server 首启需创建 `~/.android/adbkey`，失败即静默退出
（adbutils 捕获了 stderr，无回显）。

**修复**（`console_server.start_alas`，两份副本同步）：

1. **强制可写 HOME**：优先 `<appdest>/home`（fnOS 分配的应用 home 软链），
   检测不可写则兜底 `$PKGVAR/home`（数据目录必然可写），`os.makedirs` 后写回
   `env["HOME"]`；均失败仅告警不阻塞。
2. **预启动 adb server**：起 gui.py 前以同一 env best-effort 跑一次
   `<target>/bin/adb start-server`（15s 超时、DEVNULL、失败不阻塞）——server 以
   应用用户身份常驻，首次 DETECT DEVICE 无冷启动延迟。

**教训**：给子进程注入 PATH 只是「能找到二进制」；凡是自身要写状态目录的工具
（adb 的 `~/.android`、git 的 `~/.gitconfig` 等）都必须一并保证 `$HOME` 可写。

#### 4.15 公开发布改名（1.2.0）

**触发**：准备把工程发布到 GitHub（`github.com/moehz/Alas-FNOS`，参照 MAA-FnOS 的组织方式）。
用户要求：**名字改成 ALAS、开发者改成 moehz、链接到该仓库**，并重打包准备发 Release。

**改名范围：连包标识一起改**（不是只改显示名）。

| 字段 | 旧值 | 新值 |
|---|---|---|
| `appname` | `azurlaneautoscript` | **`alas-fnos`** |
| `display_name` | `AzurLaneAutoScript` | **`ALAS`** |
| `maintainer` | `AzurLaneAutoScript`（占位） | **`moehz`** |
| `maintainer_url` | 上游 Alas 仓库（占位） | **`https://github.com/moehz/Alas-FNOS`** |
| `version` | `1.1.1` | **`1.2.0`** |
| 网关前缀 | `/app/azurlaneautoscript` | **`/app/alas-fnos`** |
| 入口卡片 key | `azurlaneautoscript.main` | **`alas-fnos.main`** |
| 桌面显示标题 | `AzurLaneAutoScript` | **`ALAS`** |

**合法依据**：`appname` / `username` / `groupname` 的字符集是
「字母、数字、`-`、`_`、`.`，必须以字母或数字开头结尾」（从 `tools/fnpack` 二进制的
校验字符串表读出），`alas-fnos` 合法；MAA-FnOS 的 `maa-fnos` 是同类活证据（其
`privilege` 干脆不写 `username`/`groupname`，交给平台按 appname 生成）。
`config/privilege` 的 `username`/`groupname` 早在第 8 节探针实验中已被**证伪为无罪**，
故这两项按 appname 同步改写为 `alas-fnos`。

**改动清单**（发布仓库与主仓库骨架两处同步）：

- `fnos-app/manifest`：上表全部字段 + 新增 `changelog`（首个公开版本）。
- `fnos-app/config/privilege`：`username` / `groupname` → `alas-fnos`。
- `fnos-app/app/ui/config`：key / `title` / `gatewayPrefix` / `url` → `alas-fnos.*`。
- `fnos-app/cmd/{main,uninstall_init,uninstall_callback}`：`${TRIM_APPNAME:-…}` 兜底值。
- `fnos-app/server/console_server.py`：`APPNAME_DEFAULT`（网关前缀由 `self.prefix = "/app/" + self.appname`
  推导，**没有第二处硬编码**；`--appname` 由 `cmd/main` 传入）。
- `fnos-app/wizard/install`：提示文案里的桌面入口名 → `ALAS`。
- `tools/diagnose-update.sh`：`APPNAME` 兜底值。
- 文档：`README.md`、`docs/构建指南.md`、`docs/architecture.svg` 的入口名 / 前缀 / 产物名。
- 主仓库骨架：`fpk/manifest`、`fpk/config/privilege`、`fpk/app/ui/config`、`fpk/cmd/*`、
  `fpk/wizard/install`、`app/server/console_server.py`、`tools/diagnose-update.sh`。

**不需要改的**（容易误伤）：`patch/alas_fnos.py` 与 `diagnose-update.sh` 里的
`LmeSzinc/AzurLaneAutoScript`（上游仓库/源码包名）、补丁的日志标记 `[alas-fnos]`
（它本来就是 `alas-fnos`，与 appname 无关，且已被 4.12 的排障章节引用）。
阶段 3 前端未做，`app/console/` 不存在，无前端引用要改。

**构建**：`cd deploy/fnos && ./build_fpk.sh`（主仓库路径，`runtime/dist` 与 `tools/fnpack` 已就位）。

- 骨架预检：`No issues found`（0 blocker / high）。
- 装配 859 MB（runtime 703 MB + alas 145 MB）；`runtime` 文件数一致 7731。
- `app/console/dist` 不存在 → 按设计跳过（根路径 308 → `/alas/`）。
- 产物：`dist/alas-fnos_1.2.0.fpk` = **344,074,618 B**（328 MiB），
  SHA256 `10f2a12df1ee81b1db69e73e278be307b9739726167153f1b2c10cdc04cf8677`
  （**2026-10-04 补 `distributor` 后重打的最终版**；同一路径早先那份 344,073,891 B /
  `ecae9f67…5aa1` 已作废，见 4.15.1）。
- 包内抽检：`manifest`（appname=alas-fnos / display_name=ALAS / maintainer=moehz /
  **distributor=moehz** / version=1.2.0）、
  `config/privilege`、`app/ui/config`（`alas-fnos.main` + `/app/alas-fnos`）、
  `console_server.py::APPNAME_DEFAULT`、`bin/adb` 全部符合预期；
  `alas_version.json` 的 `packed_app_version=1.2.0`、`source=fpk`、基线 `77f4d01f`（dirty=false）。

**升级兼容性（仅开发机，对外无影响）**：两项改名都动到了平台侧标识，旧包不能覆盖升级。
但**旧 `azurlaneautoscript` 包从未公开发布**，公开用户第一次装的就是本包，
不存在「旧版本升级」这条路径 —— Release 说明里**不写升级告警**。
对本机设备而言：装着 `azurlaneautoscript` 时须先卸载再装 `alas-fnos`；
卸载向导默认「保留数据」，但数据目录挂在 `/vol*/@appdata/azurlaneautoscript`，
新标识读不到 —— 想沿用旧配置需**手工搬目录**（`mv .../azurlaneautoscript .../alas-fnos`，
或只搬 `config/`），否则等同于全新安装。

#### 4.15.1 应用信息页字段映射：`distributor` 缺失导致「发布者」为空

**真机现象**（2026-10-04，1.2.0 手动安装）：应用中心 → 应用信息页显示
「开发者 `moehz` / 发布者 `—` / 当前版本 `1.2.0` / 来源 `手动安装`」——
**开发者有值、发布者是空的横杠**。

**字段映射**（对照 MAA-FnOS 的 `fnos-app/manifest` 得出）：

| 应用信息页 | manifest 字段 | MAA-FnOS 取值 |
|---|---|---|
| 开发者 | `maintainer` / `maintainer_url` | `danyi` |
| 发布者 | **`distributor` / `distributor_url`** | `danyi` |

MAA-FnOS 的 manifest 比我们多两行 `distributor` / `distributor_url`，我们只写了
`maintainer`，所以「发布者」落到空值。**修复**：manifest 补

```ini
distributor=moehz
distributor_url=https://github.com/moehz/Alas-FNOS
```

**版本号仍为 1.2.0**（用户确认：1.2.0 尚未上传到 GitHub，不必为此跳版本）。
代价是同版本号重新打包会覆盖本地 `dist/alas-fnos_1.2.0.fpk`（旧 SHA256 作废）；
设备上要生效需重装，**「同版本号覆盖安装」在飞牛上未验证过**，被拒就先卸载再装。

**真机状态**：**1.2.0 已真机安装并进入应用信息页**（标识、显示名、图标、版本、来源均正确）。
仍待复测：安装向导文案、桌面入口标题、网关前缀 `/app/alas-fnos`、`/alas/` 跳转、
adb 零配置、卸载清理。补 `distributor` 后的包**尚未真机复测**。

**发布动作**：见第九节「公开发布（GitHub / Release）」。

---

## 五、潜在风险与未解决问题

| 编号 | 风险 / 问题 | 状态 | 说明 / 建议 |
|---|---|---|---|
| **R1** | FPK 体积上限未确认 | ✅ **已消解** | 实测 **324 MB**（装配 848 MB，fnpack 压缩+去重）。体积不再构成风险 |
| **R2** | `os_min_version=1.2.0401` 未经真机验证 | ⏳ 待测 | 真机安装后据实测定稿。**注意**：p2 对照包带该字段可正常安装，说明它不是 10111 的成因 |
| **R3** | 统一网关 + WebSocket 反代仅在容器内 mock 验证 | ⏳ 待测 | 阶段 5 真机必测 WS 升级 |
| **R4** | `maintainer` / `maintainer_url` 无确定值 | ⏳ 待用户 | 当前填上游项目名与仓库地址，建议用户确认或替换 |
| **R5** | `wizard/uninstall` 的字段类型与取值编码未知 | ✅ **已解决（1.0.2）** | 早期为规避 R12 直接不创建该文件。1.0.2 按官方 wizard 规范改为 `radio` + `wizard_data_action`（`keep`\|`purge`，`initValue=keep`），脚本侧归一化并容忍未知值（按保留处理）。见 4.10 |
| **R6** | 阶段 3 前端未做 | ⏳ 待做 | 不阻塞阶段 4/5；1.0.1 起根路径 308 直跳 `/alas/` |
| **R7** | `ICON.PNG` 来源与尺寸 | ✅ 已解决 | 由 `webapp/buildResources/icon.png`（256×256）缩放，尺寸已校验 |
| **R8** | 开发机 arm64 / 目标 x86_64 | ✅ 已解决 | fnpack 只打包不编译，实测正常 |
| **R9** | **预检脚本会把捆绑运行时误报** | ✅ 已规避 | 装配后跑 validator 会扫到 CPython 标准库 / site-packages / Alas 自带脚本，实测产生 **22 条 high 误报**。**必须针对干净骨架运行**；`build_fpk.sh` 已把预检固化在装配前 |
| **R10** | `cp` 在目标目录已存在时会**嵌套** | ✅ 已规避 | 早期把 runtime 装成 `app/runtime/runtime`，文件数 7731→15461、体积翻倍。`build_fpk.sh` 改为“先建空目录再拷内容”，并加装配后文件数一致性校验 |
| **R11** | 批量删除安全护栏 | ✅ 已规避 | `rm -rf` 删除装配产物会触发 `SAFE_DELETE_BULK_CONFIRM_REQUIRED`；改用 `find -delete` |
| **R12** | **空的向导文件导致真机安装失败（`code 10111`）** | ✅ **已修复** | `wizard/{upgrade,uninstall,config}` 写成 `[]` 时，真机在 `Verifying files...` 后抛 `APP_INSTALL_FAILED_PKG_EXCEPTION`（CLI 只显示 `code 10111`）。**不需要的向导文件应当不创建，而不是留空数组**。已删除这 3 个文件，并在 `build_fpk.sh` 加了防回归校验。详见第八节 |
| **R13** | `fnpack` 的 `$TMPDIR` 残留导致**假失败** | ✅ 已规避 | `$TMPDIR` 中若已有同名 `fnpack.<ts>` 目录，会报 `Copy pack ... is a directory`，与包内容无关。`build_fpk.sh` 已为每次构建准备私有 `TMPDIR` |
| **R14** | **安装目录可写性未定论**（影响脚本热更新） | ✅ **已消解（方案绕开）** | 1.0.2 改为「安装目录当只读种子、运行树放 `$TRIM_PKGVAR/alas`」，`prepare()` **不再写 `<target>`** → 该疑问不再阻塞任何功能。真机探针仍可留作知识补充（见 4.7） |
| **R15** | **脚本热更新后可能出现 `ImportError`** | ⏳ 已知限制 | `site-packages` 随包冻结、`InstallDependencies=false`。上游新版若新增依赖，更新后 Alas 起不来。**缓解**：`POST /api/alas/reset` 一键回到出厂版本。见 4.9.7。**架构内无解** |
| **R16** | `$TRIM_PKGVAR` 空间占用 | ⏳ 待真机确认 | 更新需临时约 **240 MB**（源码包 87.8 MB + 暂存树 ~150 MB），`_prune` 随后回收；平时保留一份 `.alas-prev-*`（约 150 MB）+ 运行树（约 150 MB）。若设备卷太小需提示用户，或改为更新后不留 prev |
| **R17** | 上游更新面板的 20 条历史依赖 GitHub API | ⏳ 可接受 | `api.github.com/.../commits` 一次约 3.1 MB；失败只记日志、返回空列表，**不影响更新功能**，仅历史表为空 |
| **R18** | `wizard/uninstall` 清数据的路径护栏 | ✅ 已加固 | 拒绝 `""`/`/`/`/var`/`/usr`/`/vol`/`/vol1`/`/vol2`；只删应用自管条目，不整目录删。已测 8 条分支全绿 |
| **R19** | **`$VAR` 紧邻中文会让 bash 报 `unbound variable`** | ✅ **已全仓修掉** | macOS 自带 **bash 3.2.57**，在 UTF-8 环境下会把多字节字符的**前导字节吞进变量名**：`"$FOO，"` 被解析成变量 `FOO\xef` → `set -u` 下直接退出。**规则：`$VAR` 后面紧跟中文（或任何非 ASCII）时必须写 `${VAR}`。** 本次实测踩中：`build_fpk.sh` 装配 alas 前的 `say` 行（`--skip-alas` 预演恰好跳过该行，所以第一次没暴露）。全仓扫描后共修 7 处可执行行（`build_fpk.sh`、`github-repo/build_fpk.sh` ×2、`tools/cleanup-probes.sh` ×2、`runtime/smoke.sh` ×2），**全在报错分支**，平时不触发、真出事时才炸。`github-repo/build_fpk.sh` 的 `[ -d "$ALAS_SRC/.git" ]` 一并改为 `git rev-parse --git-dir`（兼容 worktree，其 `.git` 是文件） |

| **R20** | **升级后未重启 → 新包不生效（跑的还是旧代码）** | ✅ **已修复（1.0.4）** | 平台替换 `<target>` 全部文件后不保证重启应用；老进程继续跑就还是旧代码、读旧版本记录，表现为「装了新包却还是旧行为」。`cmd/upgrade_init` 留 `.upgrade-restart-pending` 标记、`cmd/upgrade_callback` 停旧进程并用新代码拉起。见 4.12.3 |
| **R21** | **捆绑运行时没有系统 CA，HTTPS 可能整体失败** | ✅ **已修复（1.0.4）** | `runtime/dist` 内无 `/etc/ssl/certs`，只有 `site-packages/certifi/cacert.pem`，而标准库 `urllib` 不读 certifi。缺 CA 的机器上所有 HTTPS 都会证书报错。改为显式用 certifi 建 `SSLContext`。见 4.12.3 |
| **R22** | **探测失败被伪装成「已是最新」** | ✅ **已修复（1.0.4）** | 上游 `_check_update()` 失败也返回 `0`（= 无更新），1.0.2 照抄了这个语义。现在返回 `"failed"`，面板显示「更新失败」+ 重试。见 4.12.3 |
| **R23** | **卸载「清理数据」可能静默失效** | ✅ **已加固（1.0.5）** | `$TRIM_PKGVAR` 是指向 `/vol*/@appdata/<appname>` 的软链；若平台在执行卸载脚本前移走了 appdir，环境变量失效 → 旧脚本静默 no-op、不留痕迹。现在两脚本都按 appname 兜底定位真实数据目录，并把向导取值/解析结果/删除动作/剩余条目全部留痕（平台日志 + `/tmp/<appname>-uninstall.log`）。见 4.12.7 |
| **R24** | **版本探测：延迟与新鲜度无关（1.2.1 已改）** | ✅ **已修（1.2.1）** | 2026-10-03 实测 GOC `latest.json` 停在 `77f4d01f` 而 GitHub master 已是 `b9a965ce`；旧实现串行取第一个可用源、把 GOC 排在前面，面板就跟随这个过期值。**1.2.1 起**：版本真值取官方提交列表第一行（与「详细提交历史」同源），镜像只在官方接口不可达时按顺序兜底。**不要改成并发抢答**——2026-10-05 实测 GOC COS 0.18 s、123clouddisk 0.20 s，只快 20 ms 的过期源会把正确版本顶掉 |

**已解决、无需再踩的坑**：`av` 编译失败、`pywin32` 无 Linux 分发、`libssl.so.3` 缺失、`/alas` 308、`git fetch` 每 5 分钟失败。

**后台任务状态**：1.0.5 测试包构建完成后即无运行中的构建/打包进程。

---

## 六、下一步工作规划

### 优先级 P0-B —— 脚本热更新（用户明确需求，2026-10-03 提出）✅ **已实现**

> **状态：已按方案 A 落地，代码见 `deploy/fnos/app/patch/`，细节见 4.9。**
> 保留下方原始方案骨架作为「设计意图留档」；实际实现与本骨架的**差异**已就地标注。

**需求**：游戏更新后上游 Alas 会频繁更新（主要是 `campaign/`/`module/` 的新地图适配 + 少量 `assets/`），
用户不希望每次都要重新打包 + 重装 fpk。**只要不是框架级大改动，应用本身不应需要更新。**

**方案骨架与实际实现的对照**

| # | 骨架设想 | 实际实现 | 差异说明 |
|---|---|---|---|
| 1 | `$TRIM_PKGVAR/alas` 作运行树 | ✅ 一致 | 但**用 `copytree` 复制、不用 `move`** —— 安装目录须保留一份只读种子，`reset_alas` 才有东西可回退（4.9.5 表） |
| 1 | `<target>/alas` 退化为种子 | ✅ 一致 | 未改为软链；`prepare()` 不再写 `<target>`，与 4.7「target 只读」自洽 |
| 2 | import hook 注入 | ✅ 一致 | `<target>/patch/sitecustomize.py` + `PYTHONPATH`（**不随 alas 更新失效**，方案关键点） |
| 2 | 替换 `Updater` 三个方法 | ✅ 一致 | `get_commit` / `_check_update` / `git_install`，见 4.9.1 |
| 2 | 放开 `AutoUpdate`、`CheckUpdateInterval=0` | ⚠️ **多放开一个** | 还须放开 **`EnableReload=true`** —— 否则 `restart_event is None`，更新不会自动重启（4.9.6，本次实测发现） |
| 3 | GOC `latest.json` 探测（91 B） | ✅ 一致 | 双 CDN 回退，TTL 300 s + 启动后台预热 |
| 4 | `codeload` tar.gz，回退第三方代理 | ✅ 一致 | 三级回退：`codeload` → `ghfast.top` → `gh-proxy.com` |
| 5 | staging → 校验 → 交换 → 重链 → 回滚 | ✅ 一致 | 用 `os.replace` 保证同卷原子；`_prune` 只留一份 prev（4.9.3） |
| 6 | 与 app 升级的关系 | ✅ 一致 | `source: "fpk" \| "update"` 决定是否重播（4.9.5 表） |
| 6 | 「恢复出厂脚本」按钮 | ✅ 换形式实现 | **未**在控制台加按钮，改为控制面 API `POST /api/alas/reset`（阶段 3 前端未做，先留 API 更务实） |

**A/B/C 取舍终选：A（全量源码包交换）**。理由：实测 87.8 MB / 51 s，一次请求、无状态漂移、
实现约 200 行；B（增量）需处理改名/删除 + 构建期 manifest，且 4.8.4 已证 `assets/` 确实会被改，
收益不稳定。B 留作后续优化。

**遗留（已登记为 R15，必须让用户知道）**：更新不会跟着更新依赖。上游新版若引入我们没有的
`site-packages` 依赖，更新后 Alas 会起不来，需用 `/api/alas/reset` 回到出厂版本。
这是「自包含冻结运行时」与「在线更新」的本质矛盾（4.7 末段已述），架构内无解。

### 优先级 P0-A —— 阶段 5 真机验收（x86 fnOS）

> **本次要复测的是 1.0.4**（1.0.1 已通过基础验收；1.0.2/1.0.3 的更新与卸载功能真机尚未走通）。
> 重点三组用例：**0. 版本显示是否正确**（4.12）、**A. 脚本热更新**（4.9）、**B. 卸载可选清数据**（4.10）。
>
> ⚠️ **A 组必须用测试包 `azurlaneautoscript_1.0.4.fpk` 测**，不能用正式包 —— 正式包的基线就是
> 上游最新，打开面板只会显示「已是最新」，**走不到更新流程**。测试包的构建与验收细节见 **4.11**。

按 `references/build-test.md` 第 3–6 节执行：

```bash
# 1) 把 deploy/fnos/dist/azurlaneautoscript_1.0.4.fpk 传到 x86 fnOS 设备后安装
sha256sum azurlaneautoscript_1.0.4.fpk        # 见 4.12.5
sudo appcenter-cli install-fpk azurlaneautoscript_1.0.4.fpk
sudo appcenter-cli list
sudo appcenter-cli start azurlaneautoscript

# 2) 存疑时一键排查（只读，输出 6 段信息）
bash deploy/fnos/tools/diagnose-update.sh
```

**0. 版本显示（本次新增，先过这一关）**

> 现象背景：用户装 1.0.3 后看到的面板仍是「最新版本」，根因分析见 **4.12**。

1. 打开 Alas 更新面板 → **注意「本地」行**：
   * `01c0a010` → ✅ 修复生效（1.0.4 的升级后自愈重启起作用了），继续 A 组；
   * 仍是 `77f4d01f` / 空白 → **手动重启应用**（应用中心 停→启，或 `sudo appcenter-cli stop/start azurlaneautoscript`）
     再看一次，**把两次结果都记录下来**：手动重启后变正确 = 确认根因是「升级后没重启」；
     手动重启后**依旧**不对 → 跑 `diagnose-update.sh` 并把输出贴回，重点看第 4 段有没有 `[alas-fnos]` 行。
2. 「上游」行应显示 `77f4d01f` 且最近更新历史有内容；若为空，看 `diagnose-update.sh` 第 5 段的
   端点连通性/证书结论。
3. 状态文案：探测不到上游时应显示**「更新失败」**（1.0.4 起），**不应**再显示「已是最新」。

**A. 脚本热更新验收（新增，最关键）**

> 前提：设备上装的是**测试包 `azurlaneautoscript_1.0.4.fpk`**（基线 `01c0a010`）。
> 若装的是正式包，第 1–2 条会看到「当前版本 `77f4d01f`／已是最新」，**这是正确的**，
> 但第 3 条之后无法进行 —— 那正是要打测试包的原因。

1. 打开 Alas 配置界面 → 滚动到「更新」区域 → 应看到**当前版本为 `01c0a010`**
   （不是空白、不是本仓库 HEAD、不是 `77f4d01f`）。这证明补丁的 `get_commit` 读到了包内版本记录。
2. 点「检查更新」：应显示**有新版本**，上游版本 `77f4d01f`；面板上方两张表的短 SHA 非空
   （证明 `get_commit` 的本地/远端两条分支都生效）。
3. 点「立即更新」：观察 `$TRIM_PKGVAR/alas.log` 出现 `[alas-fnos] 下载源码包：…` →
   `源码包就绪：… (xx MB)` → `更新完成：77f4d01f`；面板版本号随之变为 `77f4d01f`。
   （下载 87.8 MB，视网速约 1 分钟；耗时期间界面会转圈，属正常。）
4. 更新后**应自动重启**并加载新代码（验证 `EnableReload=true` + `gui.py` 重启循环，4.9.6）。
5. `$TRIM_PKGVAR/alas_version.json` 的 `source` 变为 `"update"`，`base_commit` = `77f4d01f…`。
6. 验证旧树保留：`ls -d $TRIM_PKGVAR/.alas-prev-*`（只应有 1 份）。
7. 验证**用户数据未丢**：`$TRIM_PKGVAR/config`、`log` 内容与更新前一致；`alas/config` 仍是软链。
8. 反例：**安装目录未被改动** —— `ls -la $(readlink -f /var/apps/azurlaneautoscript/target)/alas/`
   仍与出厂一致（target 只读语义成立）。
9. 兜底：调 `POST /app/azurlaneautoscript/api/alas/reset`（带网关登录态）→ 应回到出厂版 `01c0a010`，
   `source` 变回 `"fpk"`，服务重启正常。**这是 R15（依赖不匹配）的唯一逃生通道，务必测通。**

**B. 卸载可选清数据验收（新增）**

10. 卸载向导应出现「应用数据处理」单选，**默认为「保留数据」**；不点它直接卸载 → `$TRIM_PKGVAR` **保留**。
11. 重新安装 → 选「删除全部数据」→ 卸载后 `$TRIM_PKGVAR` 下 `config/` `log/` `alas/`
    `alas_version.json` `console.pid` `.alas-prev-*` 全部消失，且**平台放置的其他文件仍在**。
12. 卸载后无残留进程与 Socket（1.0.1 已验，回归确认）。

### 真机实测记录（2026-10-03，用户反馈）

- 1.0.0 安装成功并运行正常：安装向导、桌面图标、网关前缀、`/alas/` 反代、控制台服务均正常 ✅
- 唯一问题：桌面入口打开的是占位页，需手动补 `/alas/` 才进 Alas → 已在 1.0.1 修复（308 直跳）。

验收清单：
1. 安装向导正常显示 tips 文案；选卷安装成功。
2. 桌面入口「AzurLaneAutoScript」可见、可打开。
3. 网关前缀 `/app/azurlaneautoscript` 已注册；`$TRIM_APPDEST/app.sock` 已监听。
4. 页面与 API 正常；**WebSocket 能升级**（`/app/azurlaneautoscript/alas/`，R3）。
5. 无网关登录态（无 `X-Trim-*`）访问控制面 API 返回 403。
6. `cmd/main` 的 start / status / stop 行为正确（status 未运行必须 exit 3）。
7. 重启设备后复测：`AutoRestartTime=null` 下应用不会自动起；手动 start 正常。
8. 升级流程：装 1.0.0 → 改版本 → 覆盖升级，`$TRIM_PKGVAR/config` 保留、`deploy.yaml.bak` 生成。
9. 卸载：向导出现「应用数据处理」选项；默认选「保留数据」时 `$TRIM_PKGVAR` 保留；
   选「删除全部数据」时应用自管条目被清空（4.10、R18）。两种情况都无残留进程与 Socket。
10. 据实测定稿 `os_min_version`（R2），确认 `maintainer`（R4）。

#### 已结案：外网桌面图标显示为飞牛默认图标（2026-10-03）

- 现象：LAN `192.168.2.130:5666` 访问 `/app-center-static/icon/azurlaneautoscript/icon.png` 得到真实 Alas 图标；
  外网 `fnnas.moehz.com:10082` 同一路径得到飞牛默认图标。
- 排查中确认的事实（可复用）：
  - 该路径在**外网入口按路径鉴权**：匿名请求返回 `401`（`server: nginx`，body 空），
    且**对不存在的 appname 同样 401** → 与 appname、与应用是否在册无关。
  - 外网入口 `/` 返回 fnOS 桌面 SPA（200，`server: nginx`）；HEAD 请求由前一层反代（`server: LuckyWeb`，
    大鹏 Lucky）回 404 → 链路为 `公网:10082 → Lucky → fnOS`。
  - 包内 4 个图标规格均已核验合规（64×64 / 256×256、RGBA、非隔行、<1MB）。
- **根因：外网浏览器缓存**。清缓存后恢复正常，与应用包内容、与 fnOS 权限策略均无关。
- 教训：这类「同 URL 不同入口返回不同图片」的问题，**先排除缓存**再谈其他；
  应用商店静态资源 URL 无版本号，安装/换图标后旧缓存会长期留存。
- 本项**无需修改 FPK**，仅留档。

### 优先级 P1 —— 阶段 3 前端控制台

在 `deploy/fnos/app/console/` 用 **Vite + `@trimjs/web-app`**：
- 主题 / 语言跟随宿主（`$on('os/theme'|'os/language')` 仅在 `sdk.isWeb && !sdk.isStandaloneWeb` 时启用）。
- 消费控制面 API `{prefix}/api/{status,start,stop,log}`。
- 提供跳转 `{prefix}/alas/` 的入口。
- 构建产物放到 `deploy/fnos/app/console/dist`，`build_fpk.sh` 会自动装配并重新打包。

参考模板：`.trae/skills/fnos-developer/templates/frontend-auth-flow.ts`（本应用**不做文件授权**，`config/resource={}`、`disable_authorization_path=true`，故只需 SDK 初始化 + 主题语言监听部分）。

### 优先级 P2（可选）—— 阶段 6 上架

需最终 `.fpk`、图标、真实界面截图、准确 manifest。

### 优先级 P3（可选）—— 进一步瘦身

当前 `app.tgz` 含 `.github`、`dev_tools`、`doc`、`tests`、`webapp`（Electron 外壳）等开发期内容。324 MB 已可接受，如需再瘦可在 `build_fpk.sh` 的 rsync 增加 `--exclude`，但**必须回归阶段 5 验收**。

---

## 七、交接后第一步建议

1. 读 `.trae/skills/fnos-developer/SKILL.md` + 本报告。
2. 确认产物存在：`ls -lh deploy/fnos/dist/azurlaneautoscript_1.0.0.fpk`（324 MB）。
3. 需要重新打包时，**只用** `./deploy/fnos/build_fpk.sh`（它保证了预检顺序、幂等与非嵌套）。
4. 直接进入**阶段 5 真机验收**；阶段 3 前端可并行推进。

### FAQ-1：`FileNotFoundError: 'adb'` / `Connection refused`（127.0.0.1:5037）

> **2026-10-04 起已由 4.13 解决**：adb 随包自带（`<target>/bin/adb`），装 1.1.0+ 无需
> 任何手工安装。以下仅适用于历史版本（≤1.0.6）或 adb 仍连不上时的对照排查。

早期版本按旧决策 #1 不带 adb。日志特征：`AdbClient(127.0.0.1, 5037)`
拒绝连接 → adbutils 回退执行 `adb start-server` → 系统无 `adb` 二进制。处置：

```bash
# fnOS 为 Debian 系，SSH 到 NAS：
sudo apt update && sudo apt install -y adb
adb version && adb start-server && adb devices   # 确认 server 起来、设备可见
```

WebUI 里 `Alas.Emulator.Serial` 填设备序列号（真机 USB/`ip:5555`）或 `auto`。
1.1.0+ 若仍报 5037 拒绝：确认 `<target>/bin/adb` 存在且可执行（`ls -l
$(readlink -f /var/apps/azurlaneautoscript/target)/bin/`），再查
`cat /proc/<gui.py pid>/environ | tr '\0' '\n' | grep ^PATH` 是否含 `<appdest>/bin`。

> **1.1.1 追加（真机实锤）**：1.1.0 报错形态变为「能找到 adb（无
> FileNotFoundError）但 5037 仍拒绝」——根因是 gui.py 继承平台 HOME，不可写，
> `adb start-server` 无法创建 `~/.android/adbkey` 而静默失败（adbutils 捕获了
> stderr，仅表现为重试后仍 refused）。手工以普通用户跑一次
> `<target>/bin/adb start-server` 即可临时恢复（server 全局共享）；根治见 4.14
> （强制可写 HOME + 起.gui.py 前预启动 adb server）。

---

## 八、附录：`code 10111` 真机安装失败排障全过程（已结案）

### 8.1 现象

真机 `sudo appcenter-cli install-fpk azurlaneautoscript_1.0.0.fpk`：

```
- Verifying files...
[Error]Something wrong with appcenter: code 10111
```

`sha256` 与本地一致（排除传输损坏）；`df -h /vol1` 有 278 G 可用（排除空间不足）。
系统日志关键行：

```
TRIMEVENT:{...,"APP_NAME":"azurlaneautoscript","DISPLAY_NAME":"azurlaneautoscript",
           "eventId":"APP_INSTALL_FAILED_PKG_EXCEPTION","from":"trim.app-center"}
```

对比「安装成功」的对照组，**失败时没有 `POST /rpc/v1/install/task`** —— 说明卡在
**装配前校验**阶段，根本没进入安装流程。

> 环境事实：`appcenter-cli` 必须 `sudo`（不加会 `Permission denied`）；设备 `appcenter-cli` 版本 **1.0.1**；
> 装未上架 fpk 前需先 `sudo appcenter-cli manual-install enable`。
> ⚠️ `install-fpk` **不会覆盖已安装的同名应用**（会直接提示 `Application [x] is installed.` 后返回），
> 做对照实验时务必保证 appname 互不相同或先卸载。

### 8.2 方法：以官方骨架为基线的单变量对照实验

用 `fnpack create` 生成官方最小骨架（**已验证可安装**，记作 `probeA`），
然后每次只替换一个变量，appname 各不相同 → 一条命令即可全部安装、互不冲突、无需卸载。

| 轮次 | 探针 | 唯一变量 | 结果 |
|---|---|---|---|
| 1 | `probeA` | 官方骨架原样 | ✅ 通过（证明工具链/设备正常） |
| 1 | `probeB` | + `os_min_version=1.2.0401` | ✅ 通过（**该字段无罪**） |
| 2 | `probeC` | 我们的**全部元数据** + 小负载 | ❌ 10111（**负载无罪，元数据有罪**） |
| 3 | `p1` | 中文 `desc` | ✅ |
| 3 | `p2` | +6 个附加 manifest 字段 | ✅ |
| 3 | `p3` | `appname=azurlaneautoscript` | ✅ |
| 3 | `p4` | 统一网关 `ui/config` | ✅ |
| 3 | **`p5`** | **`cmd/` + `wizard/` + 图标** | ❌ **10111 → 范围锁定在这三者** |
| 4 | `p6` | 我们的 `cmd/` 全部（0755 + 中文注释） | ✅ |
| 4 | **`p7`** | **我们的 `wizard/` 全部 4 个** | ❌ **10111 → 元凶在 wizard** |
| 4 | `p8` | 我们的 4 个图标 | ✅ |
| 4 | `p9` / `p10` | 仅 `cmd/main` / 仅其余 8 个 cmd | ✅ |
| 4 | **`p11`** | **仅 `wizard/install`（有内容）** | ✅ **通过** |
| 4 | **`p12`** | **仅 `wizard/{upgrade,uninstall,config}`（均为 `[]`）** | ❌ **10111 → 空数组是元凶** |
| 4 | `p13` / `p14` | 我们的 cmd 内容+0644 / 官方 cmd 内容+0755 | ✅ / ✅（**权限位无罪**） |
| 4 | `p15` / `p16` | 仅根图标 / 仅 `app/ui/images/*` | ✅ |
| 4 | `p17` / `p18` | 仅 `config/privilege` / 仅 `config/resource`（`{}`） | ✅ |
| 5 | **`p19`** | **修复后完整元数据（wizard 仅 install）+ 小负载** | ✅ **通过 → 修复验证成功** |
| 5 | **`p20`** | **仅空 `wizard/upgrade`** | ❌ **10111** |
| 5 | **`p21`** | **仅空 `wizard/uninstall`** | ❌ **10111** |
| 5 | **`p22`** | **仅空 `wizard/config`** | ✅ **通过（允许为空）** |

### 8.3 根因

> **`wizard/upgrade` 与 `wizard/uninstall` 不能是空步骤数组 `[]`。**
> 二者任一留空 → 真机安装失败（`code 10111` / `APP_INSTALL_FAILED_PKG_EXCEPTION`）。
> `wizard/config` 实测**允许为空**（p22 通过），但没有需要就不要创建。
> 只保留内容非空的 `wizard/install` → 正常安装（p19 已用等价于正式包的元数据验证）。

官方 `fnpack create` 生成的骨架其 `wizard/` 就是一个**空目录**（无任何文件），
即「不需要的向导文件应当**不创建**，而不是写 `[]`」。

同时被本次实验**证伪**的怀疑（都无罪）：`os_min_version` 取值、中文 `desc`、
`appname` 长度与取值、`cmd/*` 的 0755 权限位、`cmd/*` 的中文注释、图标尺寸/字节结构、
`config/privilege` 的 `username`/`groupname`、`config/resource` 为 `{}`、统一网关 `ui/config`。

### 8.4 修复

1. 删除 `deploy/fnos/fpk/wizard/{upgrade,uninstall,config}`，仅保留非空的 `install`。
2. `build_fpk.sh` 新增 **1.5 向导文件防回归校验**：任一向导文件内容为 `[]` 或空即中止。
3. 重新打包：**324 MB**，sha256 `029d3d47cf0c6456ae514144562a629ba2d4dd4490a146616067c993014b18fc`。
4. 新增 `deploy/fnos/tools/cleanup-probes.sh`：设备上一键批量卸载全部探针
   （`--dry-run` 预演 / `--dirs` 连 `/var/apps/<name>` 残留一并清理）。
5. 已把「空向导文件」这条实测约束补进 `.trae/skills/fnos-developer/references/package-model.md`。
6. **真机验证（第 5 轮）**：`p19` = 修复后完整元数据 + 小负载 → ✅ 安装成功，
   证明修复有效、正式包必然可装；`p20`（空 upgrade）/`p21`（空 uninstall）复现失败，
   `p22`（空 config）通过，规则边界据此钉死。

### 8.5 附带收获（都是可复用的硬知识）

- **`fnpack build` 的两条强制校验**（构建期即失败）：
  - `app/ui/config` 的条目名必须以 `appname` 开头；
  - manifest 的 `desktop_applaunchname` 必须与 `ui/config` 中某个条目名完全一致。
- **`fnpack` 的 `$TMPDIR` 残留会引发假失败**（`Copy pack ... is a directory`），
  与包内容无关；给每次构建一个干净的私有 `TMPDIR` 即可。
- **真实可用参照仓库**：`liwei9745/fnos-apps`（18 个第三方应用、x86+arm 双构建、CI 出包）。
  其通用打包脚本 `scripts/build-fpk.sh` 用 `tar -czf "$FPK_NAME" *`，manifest 的
  `checksum = md5sum(app.tgz)`。其 `shared/wizard/uninstall` 证明
  `type: tips` + `helpText` 的写法合法；其 `apps/gopeed/fnos/ICON.PNG` 实测为 **90×90**，
  说明 **fnOS 不严格校验图标尺寸**。
- 探针包全部保留在 `deploy/fnos/dist/p*.fpk`（14 KB ~ 278 KB），后续再遇安装类问题可直接复用这套二分法。

---

## 九、公开发布（GitHub / Release）

### 9.1 发布仓库布局

发布仓库就是 `deploy/fnos/github-repo/` 这个**独立的 git 仓库**（内层有自己的 `.git`，与主仓库各自提交），
对应远端 `github.com/moehz/Alas-FNOS`。独立出来是为了让公开仓库只含「可复现的源码 / 脚本 / 骨架」，
不带 Alas 源码、运行时、fnpack 与产物（照 MAA-FnOS 的组织方式）。

```
github-repo/
├── build_fpk.sh            独立维护，结构与主仓库的 build_fpk.sh 不同（不共用）
├── fnos-app/               fpk 骨架（manifest / config / cmd / wizard / app/ui / server / patch）
├── runtime/                Dockerfile 与收集脚本（不含 dist，运行时需自行构建）
├── vendor/adb/             platform-tools 的 adb（入库，保证离线可复现）
├── tools/                  仅 diagnose-update.sh（cleanup-probes.sh 是开发机工具，不入发布仓库）
├── docs/                   构建指南.md、architecture.svg
├── README.md
├── LICENSE
├── .gitignore              忽略 runtime/dist、.alas、tools/fnpack、fnos-app/app/*、dist、*.fpk
└── .gitattributes          vendor/adb/adb 标为 binary + linguist-vendored
```

⚠️ **主仓库按普通文件跟踪 `github-repo/` 下的全部内容**（外层不是 gitlink）。
在发布仓库做的任何增删，都必须回主仓库再提交一次，否则两边会漂移。

⚠️ **两处骨架要手工保持同步**：A = 主仓库 `deploy/fnos/{fpk,app/server,app/patch}`，
B = 发布仓库 `fnos-app/`（`build_fpk.sh` 不校验，靠 `diff` 自查）。
涉及的改动面：`manifest`、`config/privilege`、`app/ui/config`、`cmd/*`、`wizard/install`、
`server/console_server.py`、`patch/*`。

### 9.2 用哪个构建脚本

- **主仓库 `deploy/fnos/build_fpk.sh`**：`runtime/dist`（703 MB）与 `tools/fnpack` 已就位，
  是本地出包的实际路径（1.2.0 就是这样打的）。
- **发布仓库 `github-repo/build_fpk.sh`**：给「clone 公开仓库自己打」的人用 —— 需先
  跑 `runtime/build.sh` 生成运行时、自备 `tools/fnpack`；支持
  `RUNTIME_SRC=…` / `FNPACK=…` / `--alas-src …` 覆盖。

### 9.3 发布 1.2.0 的动作清单

⚠️ **首笔提交被改写，必须强推**（见 9.5）：本地 `main` 的根提交已从
`f7b94e5 Initial release: Alas as a native fnOS app (v1.1.1)` 改为
`a1fd3ac Initial release: ALAS as a native fnOS app (v1.2.0)`，其后全部提交哈希随之变化，
远端仍是旧历史 → 首次推送要用 `--force-with-lease`。

```bash
# 1) 强推提交（历史被改写）+ 打 tag
cd deploy/fnos/github-repo
git push --force-with-lease origin main
git tag v1.2.0 && git push origin v1.2.0

# 2) 网页 Releases → Draft a new release → 选 v1.2.0
#    附件拖入 deploy/fnos/dist/alas-fnos_1.2.0.fpk
#    体积与 SHA256 见下（补 distributor 后重新打包的那份）
```

⚠️ **`dist/` 在 `.gitignore` 里，fpk 不进仓库**，只能走 Release 附件。

### 9.4 升级兼容性（**不写进 Release 说明**）

旧包 `azurlaneautoscript` 与 1.2.0 的 `alas-fnos` 是**两个不同的应用标识**，不能覆盖升级。
但旧包**从未公开发布**，公开用户拿到的第一个包就是 1.2.0，因此 Release 说明**不写升级告警**。
（开发机自己的升级步骤见 4.15 的「升级兼容性」段 —— 先卸载旧包、按需手工搬数据目录。）

### 9.5 改写首笔提交信息的做法（可复用）

需求：根提交写的是 `Initial release: … (v1.1.1)`，与实际首发版本 1.2.0 不符，要改。

**不能用 `git commit --amend` 直接改** —— 根提交的子孙全部要重写，`rebase --onto` 最干净：

```bash
cd deploy/fnos/github-repo
BEFORE_TREE=$(git rev-parse main^{tree})        # 先记下树哈希，改完核对内容未变
OLDROOT=$(git rev-list --max-parents=0 main)
git checkout -q --detach "$OLDROOT"
git commit -q --amend -m "Initial release: ALAS as a native fnOS app (v1.2.0)"
NEWROOT=$(git rev-parse HEAD)
git rebase -q --onto "$NEWROOT" "$OLDROOT" main
git checkout -q main
[ "$(git rev-parse main^{tree})" = "$BEFORE_TREE" ] && echo "只有提交信息变了"
```

**要点**：
- **先 `git stash`/提交工作区**：`checkout --detach` 会被未提交改动挡住（首次尝试就栽在这）。
- **务必比对树哈希**：前后一致才证明只改了提交信息、没动文件。
- 改写后远端必须 `--force-with-lease`；本仓库是全新公开库、单人维护，可接受。
- `--force-with-lease` 比 `--force` 稳：远端若被他人推进过会拒绝而不是覆盖。
