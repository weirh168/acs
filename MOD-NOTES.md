# Mika Mod —— 本仓库说明

这是 [wangzan101/mika](https://github.com/wangzan101/mika) 的修改版（Apache-2.0，保留原 `LICENSE`、`NOTICE` 与版权声明）。
仓库历史里第一个提交是**原样导入的上游源码包 0.1.42**，之后的提交都是本仓库的改动，
所以「和上游差了什么」用一条命令就能看：

```bash
git diff 05b59da..HEAD --stat        # 改动的文件与行数
git log --oneline                    # 提交历史
```

## 与上游的差异

| 类别 | 内容 |
|---|---|
| 新工具（6 个） | `web_read_all`、`web_auth`、`usage_stats`、`phone_tap_ocr`、`phone_read_chat`、`phone_long_screenshot` |
| 新参数 | `phone_observe.includeOcr`、`phone_tap_ocr/read_chat.region`（0–999 区域裁剪）、`phone_long_screenshot.direction` |
| 降级模式 | 内置助手连不上时，用无障碍读/操作**用户主屏**（开关在 设置 › 任务运行，默认关） |
| 诊断 | 窗口读不到时给 `reason`：`protected_frame` / `no_window_here` / `empty_tree` |
| 工程 | 长截图对齐逻辑抽到 `core/visual/LongShotMath.kt`（JVM 单测）；恢复意图闸门（调试包与正式包行为一致）；`ci.sh`；发布签名与版本号 |

## 构建

Windows 上需要把工作区映射成 ASCII 盘符再构建（中文路径会让 AGP/protoc/aidl 崩）：

```bash
subst X: <本仓库父目录>
X:\\Mika-main\\build-mika.sh            # 调试包
X:\\Mika-main\\build-mika.sh :app:assembleRelease   # 发布包（需要 keystore.properties）
```

`build-mika.sh`、`keystore.properties`、`*.jks` 都**不在仓库里**：前者是本机的构建脚本，
后两者是发布签名材料，进 `.gitignore`。没有 `keystore.properties` 时 release 包未签名，行为与上游一致。

## 同步上游更新

```bash
git remote add upstream https://github.com/wangzan101/mika.git
git fetch upstream
git rebase upstream/main        # 或 git merge upstream/main
```

冲突大概率集中在：`app/build.gradle.kts`（签名/版本）、`core/uistate/ScreenPort.kt`（端口新方法）、
`core/uistate/AppAccessScreenPort.kt`（新端口方法必须在这里显式转发）、`prompts/tools/`（提示词）。

## 注意

- 仓库里带着 `app/src/main/assets/runtime/rootfs.tar.xz`（56 MB，沙盒运行环境）；GitHub 单文件上限 100 MB 够用，
  但克隆会慢。想瘦身可以转 Git LFS 或改用「首次使用下载」（见 `架构差异-优化建议.md` 里 P1-3 的计划）。
- 本仓库的发布签名是**自签名**，与官方 Mika 不同，不能覆盖安装官方包，可以并存（包名 `com.wangzan101.mika.mod`）。

## 名称与图标

这个分支对外叫 **ACS**：应用显示名、应用内标志、顶栏标题都是 ACS，图标取自 ACS 官方的自适应图标（深色底 + 蓝色光球轨道，矢量 + 渐变，见
`app/src/main/res/drawable/acs_ic_*.xml`、`acs_mark.xml` 与 `mipmap-anydpi-v26/ic_launcher.xml`）。

包名仍是 `com.wangzan101.mika.mod`：这样可以直接覆盖安装，不丢已有的模型 Key、配对和任务记录，也能和手机上的 ACS 0.2.0 并存。
如果将来要改成独立的 ACS 包名，改 `app/build.gradle.kts` 的 `applicationId` 与 `namespace` 即可（需要卸载重装）。

## 本次改动：三个手机工具的参数增强

给 `phone_read_chat`、`phone_tap_ocr`、`phone_long_screenshot` 各补了实战里最缺的参数，
**原有行为完全不变**（不传新参数时与改前一致）。全部有单元测试；关键路径在真机上跑通。

### `phone_read_chat`

| 参数 | 作用 |
|---|---|
| `direction` | `down`（默认）/ `up`：往上读旧内容。聊天与通知都锚在最新一条，往上滚才是历史；`up` 时屏序自动倒置，`lines` 仍是阅读顺序（最旧在前） |
| `settleMs` | 每滚一屏后等多久再读（100–3000，默认 500），原来是硬编码 |
| `until` | 读到含该文字的那一行就停，并包含该行；返回 `stoppedBy: "until"`。用来读回到某个已知地标，不必猜 `maxScreens` |
| `match` | 滚完、去重之后只保留含该文字的行（不区分大小写），回报 `matched` / `dropped`。长群里只取一个人的发言或某个关键词，省 token |

### `phone_tap_ocr`

| 参数 | 作用 |
|---|---|
| `index` | 0 起，同名文字出现多次时点第 N 个（原来只能点第一个）；越界报 `ocr_index_out_of_range` 并给出真实数量，不会乱点 |
| `waitMs` | 界面还在动时每 250ms 重读，直到命中或超时（0–5000，默认 0＝只读一次）；命中后结果带 `waitedMs` |

排序规则也写清楚了：整行相等 > 更短 > 更靠上，因此 `index` 的语义是确定的。

### `phone_long_screenshot`

| 参数 | 作用 |
|---|---|
| `startFrom` | `current`（默认）/ `top` / `bottom`：拍之前先把页面滚到那一端（滚到「这一下界面没变化」为止）。中途被翻过的列表也能完整截出来；返回 `preScrolls` / `atEdge` |
| `settleMs` | 定位后、第一帧前等多久（0–3000，默认 400） |

### 调试探针（仅调试包）

`PhoneDebug.allowForceWait` 由 `MikaApp` 在 `BuildConfig.DEBUG` 时打开；打开后
`phone_tap_ocr` 可以先故意忽略第一次读到的结果（参数 `_forceWaitMs`，或 App 私有目录存在
`debug-force-wait` 文件），把 `waitedMs` 逼出来，用于验证等待循环本身。
**release 包里这个开关恒为 false，两条触发都不生效。**

### 测试

- `CompositeToolsTest`：**32 例全过**（新增 16 例，覆盖上面每个参数的正常路径与边界）
- `prompt-surface` 金样同步更新（模型看到的 schema 与工具说明已含新参数）

## 降级模式：让模型知道自己在你自己的屏幕上（2026-11-15 21:55）

降级模式（`FeatureFlags.degradedScreen()`，内置助手没连上时读用户主屏）能力其实很全：
`MainScreenPort` 有读屏、截图、点击、滚动、长截图（还带手势滚不动时退回无障碍滚动的兜底）。
缺的是**模型不知道自己在用户眼前操作**——它会按"后台虚拟屏可以随便折腾"的习惯做事。

### 改动

| 位置 | 内容 |
|---|---|
| `ScreenPort` | 新增 `val degradedScreen: Boolean get() = false`，注释说明这个端口操作的是用户主屏 |
| `MainScreenPort` | `override val degradedScreen = true`（它就是降级模式本身） |
| `LazyPhoneScreen` | `port?.degradedScreen == true`：接上之后才知道走的是哪块屏 |
| `AppAccessScreenPort` | 显式转发（该类约定每个成员都手写，不靠 `by`） |
| `ScreenSession.observe` | 结果里加 `"degraded": true`，并把一句说明并进 `note`（和「读的时候屏在变」那条并存，不互相覆盖） |
| `prompts/feedback/tools.md` | 新增 `degraded_screen` 说明：截图至少隔一秒、手势更钝、长截图每帧好几秒；少滚动、不做没被要求的长截图、用户可能同时也在动这块屏，并在回答里说明正在操作他的屏幕 |
| `phone_read_chat` / `phone_long_screenshot` | 结果带 `"degraded": true`（这两个要翻屏/连拍，最费时间） |

### 测试

- 新增 `DegradedScreenTest` 3 例：降级读屏带标记与说明、正常屏不带、和「屏在变」的 note 并存
- `CompositeToolsTest` 加 3 例：读聊天/长截图在降级下带标记、正常端口不带（共 **35 例**）
- `AppAccessScreenPortTest` 的「每个成员都被显式转发/检查」清单加上 `getDegradedScreen`
- 受影响的老测试（`UnreadableReasonTest` 等）全过

### 真机

正常路径（内置助手连着、走虚拟屏）跑了一次 `phone_observe`：结果里**没有** `degraded` 字段，
说明标记不会误报。降级路径本身需要断开内置助手才能触发，会牵动刚配好的连接，
这一轮没有在真机上强行制造，属单测覆盖。
