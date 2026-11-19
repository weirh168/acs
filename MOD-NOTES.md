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

## 设置页那张通知提示：卡片只留一句话，说明移到内页（2026-11-15 23:05）

改造前，设置首页第一块把「为什么重要 + 操作路径 + 去打开」全塞在卡片里，占了大半屏。

现在：

| 位置 | 内容 |
|---|---|
| 设置首页卡片 | 标题「「任务结果」的通知不会弹出」+ 一句「只进通知栏，不会弹出。」+ 按钮「看看怎么改」 |
| 点按钮 | 进「设置 › 通知」内页（不是直接跳系统设置） |
| 通知内页 | 顶部新增一块说明：「让这两类通知弹出来」+ 一句话引导 + 完整说明（为什么容易错过、系统设置里的具体路径） |
| 内页频道行 | 原有三行（需要你处理 / 任务结果 / 任务进度）不变，点哪行就去哪个频道的系统设置 |

改动文件：`StatusCopy.kt`（卡片文案换成短句、新增 `headsUpExplain()` 给内页用）、
`SettingsScreen.kt`（`StatusSummary` 对 `AttentionLowered` 改为跳内页）、
`SettingsSubPages.kt`（通知内页顶部加说明块）、中英文 `strings_status.xml` 各 4 条新文案。

### 追加：继续压短 + 修掉内页不显示的问题（2026-11-15 23:10）

- 卡片再压：标题只留频道名「任务结果」，去掉整句说明，只留按钮「看看怎么改」
  （原来副标题那句「只进通知栏，不会弹出。」也去掉了）
- **修一个 bug**：通知内页的解释块一开始用 `notificationOverview().result.warn` 判断，
  和设置页卡片用的 `status.resultLowered` 不是同一个来源，导致「卡片在提示、内页却没有说明」。
  改成统一用 `status.attentionLowered / status.resultLowered`。

真机验证：
- 设置首页卡片：`「任务结果」` + `看看怎么改`（截图）
- 打开「设置 › 通知」：顶部出现「让这两类通知弹出来」说明块（截图），下面是通知总开关与三个频道行

### 再改：这张卡片直接删掉（2026-11-15 23:15）

用户指出它和下面的「通知」一行重复。现在：

- 通知被调低**不再**在设置首页出卡片；`StatusSummary` 直接把 `Problem.AttentionLowered` 过滤掉
- 下面的「通知」一行已经带着「有 1 项不会弹出」的提示，点进去就是内页（带说明块）
- 只有通知被调低、没有别的毛病时，顶栏**也不**硬说「一切就绪」——那会误导；这种情况顶栏整块不显示
- 真正有别的毛病（无障碍没开、助手没连等）时顶栏照旧出卡片

真机：设置首页 dump 里已经搜不到「任务结果」卡片。

## 后台屏的实时画面：放大后可以自己上手操作（2026-11-15 23:40）

`屏幕 › 某任务的「看画面」` 原来只能看:点开放大后是纯图片(捏合缩放、拖动),想点一下没反应。

现在放大的那块屏有两种用法,底部一个按钮切换:

| 模式 | 行为 |
|---|---|
| 只看(默认) | 捏合缩放 1–6 倍、拖动看边角;点画面外关闭 |
| **我来操作** | 点一下 = 点这块屏一下,划一下 = 划一下;经无障碍手势下发到该任务的那块虚拟屏 |

实现要点:

- 手指位置按 `ContentScale.Fit` 的留白换算回画面像素(画面就是整屏截图,所以画面像素即屏坐标),
  点在留白里不下发;这部分抽成纯函数 `mapToFrame(pos, box, w, h)`,6 个单测覆盖居中、上下左右边、留白、未测量、横屏。
- 操作模式下**不缩放**,免得同一根手指既被当成缩放又被当成点击;要缩回「只看」再捏。
- 无障碍没开时按钮不出现,并提示「无障碍服务没开，现在只能看」。
- **打字没有内联键盘**:输入仍要回对话让 ACS 代打(它有无障碍设字/粘贴两条路)。这一点在提示里写明。

新增文案:中英各 `screens_operate` / `screens_view_only` / `screens_operate_hint` /
`screens_operate_view_hint` / `screens_operate_unavailable`。

真机:APK 已装。实机交互没能演示——「后台屏」入口只在有任务占着一块屏时出现,
这轮自动化没卡住那个时间窗口;坐标换算与注入通路有单测和既有代码路径支撑。

## 修「后台屏 › 看画面」点了不放大（2026-11-16 00:05）

用户反馈点小画面没有放大到全屏。三个可疑点一起处理：

| 疑点 | 处理 |
|---|---|
| 「放大」状态存在画面函数里，而那个函数有一句 `val bmp = frame ?: return` 提前返回——某一帧为空时状态会被丢掉 | 放大目标改成**页面级状态** `zoomed: Pair<Bitmap, Int>?`，画面函数只管回调 `onZoom(bmp)` |
| 可点区域只有图本身，图按 Fit 画，两侧大片留白点了没反应 | 可点区域改成**整块**（图 + 下面一行「点这里放大」），并加上这行说明；点哪都算 |
| 放大页里有一层 `clickable { onDismiss() }` 铺满全屏，随手一点就当关闭，看起来像"没放大成功" | 去掉这一层；关闭只留「完成」按钮和系统返回 |

真机：APK 已装。**没能复现用户看到的现象**——「后台屏」入口是抽屉里「进行中」段右边的小按钮，
只在任务正在跑时出现，我这轮自动化始终没在那个窗口里抓到它（任务确实在跑、工具都成功，
但抽屉里没有「进行中」段）。所以这三处是按代码路径推断的加固，需要用户实际再点一次确认。

## 后台屏小画面:三档大小,放大后可到 10 倍（2026-11-16 00:20）

用户要「按需要放大，比目前更大」。做了三层:

| 位置 | 能力 |
|---|---|
| 小画面本身 | 展开后上面一行三个小按钮 **小 / 中 / 大**(200 / 260 / 460 dp),默认中档=原来高度,按任务记住 |
| 点小画面 | 整块(图 + 「点这里放大」)可点,进全屏 |
| 全屏「只看」 | 捏合缩放上限从 **6 倍提到 10 倍**,拖动看边角 |
| 全屏「我来操作」 | 点按/滑动直接作用在那块虚拟屏上 |

实现:`PreviewSize` 枚举(高度 + 文案),`PreviewSizePicker` 三个胶囊按钮,
`LiveFrame(source, onZoom, height)` 按档取高;`rememberSaveable(row.key)` 记住每张卡片的选择。

单测:`ScreensFrameMapTest` 6/6 仍通过(坐标换算没动)。

真机:APK 已装。**演示不了**:「后台屏」入口在抽屉「进行中」段右边,只在任务运行中存在,
而这轮模型跑得很快(让它等 90 秒也只用了十几秒就结束),我抓不到那个窗口。

### 追加:第四档「超大」800dp（2026-11-16 00:28）

「大」460dp 还是不够,加一档 **超大 800dp**（接近屏幕可用高度）。现在四档:
小 200 / 中 260(默认) / 大 460 / 超大 800;全屏里捏合上限 10 倍。

## 「超大」改成按屏幕算的「满屏」（2026-11-16 00:38）

800dp 是拍脑袋的数,矮屏上不够、宽屏上又没到边。改法:

- 档位:小 200 / 中 260(默认) / 大 460 / **满屏**
- 满屏 = `屏幕高度 - 150dp`(状态栏、标题栏、上下留白),最少 700dp —— 所以它一定比「大」高,且真的铺到接近整块屏
- 用 `LocalConfiguration.screenHeightDp`,不同手机自适应

单测 `ScreensPreviewHeightTest` 4 例:固定档不变、满屏随屏高(900→750、1086→936)、
矮屏兜底 ≥700 且仍大于「大」、四档严格递增不重复。

真机:APK 已装。这轮验证一直被你自己在用手机打断（我发的提示词都没跑，实际跑的是「打开淘宝」），
所以我没抓到「后台屏」页面。

## 后台屏:画面不再自动关，只有人工收起/关闭（2026-11-16 00:52）

问题:任务一结束，画面流就停/断，展开的小画面和放大的全屏都会自己消失。

改法:

| 场景 | 现在 |
|---|---|
| 任务结束、画面流停了 | 卡片留一张**最后画面**，下面写「任务已结束，画面停在最后一张」，等你自己收起 |
| 任务从列表里消失（`frames` 变 null） | 仍然用缓存的那张显示，不闪掉 |
| 放大到全屏时任务结束 | 放大层摆到列表判断**之前**，只有点「完成」或返回才关 |
| 「看画面」入口的条件 | 从「有屏或有浏览器」放宽为「有屏、有浏览器、或还有画面（活的/缓存的）」 |

实现:页级 `lastFrames: MutableStateMap<String, Bitmap>`；每张卡 `LaunchedEffect` 订阅画面并缓存；
`LiveFrame` / `FrozenFrame` 共用 `FrameBlock`（静止那张多一行说明）。

顺带记录:`RunStoreTest.writesRunJsonEventsAndScreens` 在这个仓库里**本来就失败**（我 stash 掉自己的改动
单独跑仍然 expected m1 but was 空），与本次改动无关。

## 后台屏不再自动消失（第二轮：整行留住了）（2026-11-16 01:02）

上一轮只做到「有画面就继续显示」，但任务结束后**整行会从列表里消失**，所以小画面还是跟着没了。

这轮:

| 改动 | 效果 |
|---|---|
| `sticky` 行缓存 | 见过的任务行一直留在这一页（含它最后一次状态），即使已经从运行列表里移除 |
| 缓存画面 | 行还在 + 缓存的最后一张 → 展开的小画面继续显示，下面写「任务已结束，画面停在最后一张」 |
| 放大层位置 | 在空列表判断之前，任务结束不会把它关掉 |
| 手动清理 | 多一个「清掉已结束的」小按钮，只清已经不在运行的那些，想清才清 |

离开这一页再进来，缓存自然清空（不跨页面保留）。

## 悬浮小窗：人工一碰就接管，小窗不退出（2026-11-16 01:26）

用户要求：小窗打开后，人工介入就不再自动操作、由人直接操作、小窗不要退出。

改动（全部落在悬浮小窗 `AgentPip` 这条线上）:

| 项 | 之前 | 现在 |
|---|---|---|
| 任务结束 | 3 秒后自动收掉小窗 | **留着**，只有点「关掉小画面」才关 |
| 人工碰画面 | 只是展开/拖动 | **顺带接管**：走 `TaskGate.onUserOnPage`，任务在下一个会动屏的工具前停下 |
| 接管后 | — | 卡片显示「你在操作，ACS 已暂停」+ 取消/继续；小窗不动，左上角标「你已接管 · 自动操作已停」 |
| 画面没了 | 小窗变空 | 留最后一张（`ChatScreen.lastFrame` 放宽到 `pip.visible` 即用） |
| 全屏 | 只有 220dp 展开 | 底部多一个 **⛶ 全屏**：铺满整屏显示，开了「允许我在小窗里直接操作」时点/滑直接作用在虚拟屏；退出全屏回小窗 |

实现要点：
- `TaskRun.userTookControl()` 新增（内部调既有的 `userOnPage()`，不搬走任务、不拆虚拟屏）
- `ChatViewModel.pauseForHuman()/pauseForHumanIn()` + `TaskActions` 默认方法 → `MikaApp` 按对话找到那个 run
- `AgentPip` 里画面那层加一个**不消费事件**的 `pointerInput`：第一次按下就 `onHumanTouch()`
- `PipUi.tookOver` 记住已接管，小窗左上角显示标记

真机验证（截图）:点小窗后 → 顶栏「等你处理」、卡片「已暂停 · 你在操作，ACS 已暂停」、
小窗带橙色边框仍在且显示「你已接管 · 自动操作已停」、输入框上方「任务暂停中，继续后生效」。

## 接管后把 App/网页搬到用户屏幕上（2026-11-16 08:40）

上一轮接管只是「暂停 + 继续在虚拟屏里操作」。按要求改成:人工一碰小窗,

1. 先停掉这一轮的自动操作(`pauseForHuman`);
2. 再走既有接管(`takeOver` → `handOver`),把那个 App / 网页**搬到用户自己的屏幕上**,
   于是可以直接在真实界面上点、滑、打字(大屏 + 正常输入法);
3. 小窗留着当提示,左上角标「已交给你 · 在你的屏幕上操作」;点「继续」交回给 ACS。

构建通过;**但这轮没能装到手机上**——无线调试断了(`adb devices` 空、mDNS 里两个旧端口都拒绝连接),
已提交推送,等用户把无线调试打开或插上 USB 再装。

### 顺序修正 + 验证情况（2026-11-16 08:52）

`userTakeOverPip()` 改成 **先 takeOver(搬 App) 再 pauseForHuman**:先暂停会让任务不再处于「运行中」,
接管那边就不动手。

真机这轮的结果:
- ✅ 点小窗 → 顶栏「等你处理」、任务「已暂停」、卡片「你在操作，ACS 已暂停」、
  小窗保留并显示「已交给你 · 在你的屏幕上操作」、底部「任务暂停中」
- ❌ **App 没真的搬到主屏**:屏幕最前台仍是 ACS,设置页还在小窗里
- 之后两次跑任务时手机操作本身失败(「打开设置 没成功」×2),没有虚拟屏也就没有小窗可点

因此「接管后直接进 App/网页」这条还没验成。下一步建议:不依赖 `takeover.handOver`
(它要求任务正处于运行中且有接管句柄),改成接管时直接让内置助手在主屏 `am start` 当前那个包
(网页就 open 那个 URL),这样和任务状态解耦、更稳。

## 接管直接「搬到主屏」，不再依赖 takeover 句柄（2026-11-16 08:56）

按讨论的思路改了:

1. `TaskRun.handAppToUser()`：有 takeover 句柄就走 `handOver`；没有就直接
   `shell.topTaskId(虚拟屏)` + `shell.moveTask(taskId, Display.DEFAULT_DISPLAY)`，把那个 App 挪到用户主屏。
2. `MikaApp.pauseForHumanIn()`：`run.handAppToUser()` 之后 `run.userTookControl()` ——
   先搬、再停自动操作（顺序不再影响搬动）。
3. `ChatViewModel.userTakeOverPip()`：只调 `pauseForHuman()`（里面已含搬家），避免重复调用。

已构建、已装。**但今天手机控制反复掉线**（连着跑任务都报 “phone control isn't ready”，
助手进程在但 App 不认），所以这轮没抓到「点小窗 → 设置出现在主屏」的实机画面。
用户侧要做一次「设置 › 手机操作 › 去处理 / 重新配对」把控制恢复，之后即可验证。

## 接管后真的把 App 搬到主屏（已验证）（2026-11-16 09:10）

补齐最后一块漏网:无参的 `pauseForHuman()`（走「当前对话没有 run」的分支）原来只暂停、不搬家,
现在也调 `handAppToUser()`。

**实机验证（USB）**:

```
D ACS-Pip: handAppToUser display=121
D ACS-Pip: handAppToUser task=95344 move=true
topResumedActivity = com.android.settings/.Settings$WifiSettingsActivity  (主屏, fullscreen)
```

截图:WLAN 设置页整屏铺在用户屏幕上,右下角 ACS 胶囊仍在;切过去的头两秒是黑屏(任务窗口跨屏挪动后要重画),
点一下就好。任务侧同时是「已暂停 / 你在操作,ACS 已暂停」,点「继续」交回给 ACS。

## 搬完黑屏:补一次无害触摸催重画（2026-11-16 09:20）

跨屏挪完任务窗口后头一两秒是黑的(窗口要重画)。现在搬成功后停 350ms,在主屏(1,1)补一次
`injectTap`——状态栏角落,不会点到任何内容,只为让系统重画一次。

已构建安装。这一条没再实机确认:模型连着两次只回文字没真的打开 App(没虚拟屏就没小窗可点),
上一轮的「搬到主屏」(move=true、前台变成 Settings)仍然是已验证的。

## 接管后不再卡死:主屏用 `am start --display 0` 打开（已验证）（2026-11-16 09:44）

之前用 `moveTask` 把虚拟屏上的任务挪到主屏:窗口挪过去了,画面还留在虚拟屏上 —— 用户看到黑屏、点了没反应(「卡死」)。
`Takeover.handOver` 帮不上:它要求任务正处在「等待接管」阶段,我们这条是用户主动点小窗。

改法:点小窗 → `shell.runCommand("am start --display 0 -n <入口页>")`,把那个包的入口页在主屏打开;
拿不到包名或起不来才退回 `moveTask` + 补触摸。

实测(`ACS-Pip` 日志 + 截图):

```
handAppToUser display=128 task=95355 pkg=com.android.settings
launchOnMain pkg=com.android.settings exit=0 out=Starting: Intent { cmp=com.android.settings/.HWSettings }
topResumedActivity = com.android.settings/.HWSettings  (主屏 fullscreen)
```

屏幕上是完整的「设置」页(带 ACS 胶囊),**点「WLAN」正常跳进 WLAN 页**——
不是黑屏也不是死窗口。任务侧同时是「已暂停 / 你在操作,ACS 已暂停」,点「继续」交回。

## 接管停在「当前那一页」（已验证）（2026-11-16 09:58）

点小窗 → 读虚拟屏最上层页面的类名(`shell.topActivity`) → 在主屏按**那个页面**开:

```
am start --display 0 -f 0x18000000 -n '<pkg>/<完整类名>'
```

两个坑(都踩过):
1. 不加 `-f 0x18000000`(NEW_TASK|MULTIPLE_TASK)时,命令只会把 intent 投给虚拟屏上那份实例,
   主屏什么都不出 —— 看起来"启动成功但没反应";
2. 命令经 `sh -c`,类名里的 `$`(内部类)会被当成变量吃掉,必须给组件名加单引号。

实测:
```
handAppToUser display=130 task=95343 pkg=com.android.settings cls=com.android.settings.HWSettings
launchOnMain page=com.android.settings/com.android.settings.HWSettings exit=0
topResumedActivity = com.android.settings/.HWSettings   (主屏, fullscreen)
```
截图:设置页整屏在主屏、ACS 胶囊在角落;任务侧「已暂停 / 你在操作,ACS 已暂停」。
另外单独验过 `Settings$WifiSettingsActivity` 这种带 `$` 的页面也能按页打开(停在 WLAN 页)。

当前页开不起来时退回入口页;连包名都拿不到才退回挪任务。

## 任务结束后点小窗也能进去（已验证）（2026-11-16 10:21）

任务结束后 `TaskRun` 会从列表撤掉、虚拟屏也释放了,小窗只剩最后一帧;这时点小窗原来什么都不发生。

改动:
1. 运行中记住最后在用的包:`TaskRun` 在既有的 `p.screen.target` 收集里写
   `lastPagePackage` + `TaskCenterState.rememberPage(conversationId, pkg)`(run 撤掉后也留得住);
2. `ChatViewModel.userTakeOverPip()` 直接走 `actions.pauseForHumanIn(conversationId)`,不再依赖
   「当前是否有运行中的 run」;
3. `MikaApp.pauseForHumanIn`:`run` 还在 → 原来的按当前页打开;`run` 没了 → 用记下的包在主屏
   `am start --display 0 -f 0x18000000 -n $(resolve-activity)` 打开该 App;
4. 点小窗不再要求 `PipMode.Running`(「等你处理」那一下仍然只去看卡片)。

实测:
```
pauseForHumanIn no-run conv=ee758563-... last=com.android.settings
launchLast pkg=com.android.settings exit=0
topResumedActivity = com.android.settings/.HWSettings   (主屏)
```
截图:任务已结束(做了 1 步 · 17 秒)、小窗仍是最后一帧,点它之后「设置」整屏出现在主屏上。

## 接管 = 进 App 主页 + 恢复正常模式（2026-11-16 10:40）

按「全部变成日常正常人工操作」调整:

1. 接管时优先在主屏打开该 App 的**入口页(主页)**,入口打不开才退回当前那一页;
2. 交接时**把目标 App 的声音恢复正常**(任务期间被静音/独占,放开了才是日常用 App 的样子);
3. 任务侧同时停在「已暂停」,不再自动操作;人怎么用 App(包括返回、退出)都不拦、不拉回。

构建 + 安装完成。**这一轮没能实机确认**:发任务的同一时刻用户正在微信里录语音,
我按的小窗坐标打到了微信界面上,已立刻停止自动操作(不再去点手机)。

## 全面复查:接管后主页 + 正常使用 + 返回不拉回（已验证）（2026-11-16 11:06）

逐个环节实测(USB,日志+截图):

| 环节 | 结果 |
|---|---|
| 运行中点小窗 | `handAppToUser display=145 pkg=com.android.settings` → `launchOnMain entry exit=0` |
| 落到哪里 | `topResumedActivity = com.android.settings/.HWSettings`(主页),整屏 |
| 声音 | `cmd appops get com.android.settings PLAY_AUDIO` → Default mode: allow(没有被静音) |
| 任务侧 | 「已暂停 · 你在操作,ACS 已暂停」「任务暂停中,继续后生效」 |
| 按返回 | 3 秒、11 秒后前台都是 ACS —— **没有被拉回** |
| 任务已结束再点小窗 | `pauseForHumanIn no-run … last=com.android.settings` → `launchLast exit=0`,同样进主页 |

补充体验改动:小窗展开态左上角加了明确的 **「进去操作」** 按钮(⧉),不用再猜「点小窗是展开还是接管」。

用户侧「没正常」最可能的原因:小窗位置会随聊天滚动变化,点偏了只会展开、不会接管;现在有按钮可点。

## 豆包语音现状核查 + 一键沿用凭据（2026-11-16 13:40）

核查结果(设备上读到的原始记录):

| 项 | 状态 |
|---|---|
| 语音转文字 = 豆包 | ✅ 已配:`speech_choice={"type":"doubao","resourceId":"volc.seedasr.sauc.duration"}` + 加密凭据在 |
| 电话助手实时语音 = 豆包音色 | ❌ **实时语音服务里 0 条配置**(页面只有「添加实时语音配置」),所以「AI 电话尚未就绪」 |
| 电话权限 | ❌ 之前未授权 → 已 `pm grant` 补上 READ_PHONE_STATE、CALL_PHONE |

关键发现:语音转文字里存的豆包凭据就是 `apiKey/appId/accessKey`,和实时语音要的
`VolcRealtimeCredentials(apiKey, appId, accessKey)` **是同一套字段**。所以新增:
「添加实时语音配置」弹窗里多一个 **「沿用「语音转文字」里的豆包凭据」** 按钮,
点一下自动填好(apiKey 优先,只有 appId+accessKey 时切到旧版认证),音色默认
`zh_female_vv_jupiter_bigtts`。构建通过。

**没装上去**:USB 变成 offline、无线调试也关了(mDNS 无结果),等设备连上再装并实测连接。

## 配对 / 重启后保持连接的排查（2026-11-16 14:00）

设备上的真实状态:

```
builtin_shell.xml        : paired=true, port=39957
builtin_shell_recovery   : restore_after_reboot=true, auto_wireless_debugging=true,
                           last_restore=PermissionMissing   ← 开机恢复失败的原因
WRITE_SECURE_SETTINGS    : granted=false(之前) → 已 pm grant,现在 granted=true
```

也就是说:配对本身是好的(`paired=true`、连接一直在用),**坏的是「重启后自动恢复」这一步**——
它要写系统设置,但那份授权掉了,开机时 `BuiltinShellRecovery.restoreAfterBoot` 直接停在
`PermissionMissing`,无线调试不打开、也不重连,用户看到的就是「重启后要重新配对」。

改动:
1. 已通过 `pm grant ... WRITE_SECURE_SETTINGS` 把授权补上(重启后仍在);
2. `BuiltinShellManager`:助手一连上,若用户开着「重启后自动恢复 / 自动打开无线调试」而授权又掉了,
   就用助手的 shell 身份自动 `pm grant` 补回来(幂等),并在日志留一行
   `MikaShellRestore: re-granted …`,以后重装、系统收回都不再悄悄失效。

构建通过。**安装被手机上的弹窗拒绝了**(`INSTALL_FAILED_ABORTED: User rejected permissions`),
等用户同意后再装。

## 配对码配对:实机跑通（2026-11-16 14:11）

用户要求「你上去配对试一下」。完整走了一遍:

1. ACS › 设置 › 手机操作 › **重新配对**(日志:`watching for pairing (status Running, accessibility true)`);
2. 开发者选项 › 无线调试 › **使用配对码配对设备**;
3. ACS 自己从系统配对窗口读出配对码并完成配对:

```
14:11:54.063 pairing with port 38563
14:11:55.128 found the pairing window on port 38563
14:11:55.328 notice Done (discovery Idle, status Running); done
```

**1.3 秒配对成功**,状态回到 Running,系统配对窗口自动关掉;`paired=true`,端口 39957,
助手进程在(`com.wangzan101.mika.mod:helper`),`WRITE_SECURE_SETTINGS=granted`。

顺带把自愈版的 APK 也装上了(`install -r` 这次成功)。

唯一仍然发不出来的:配对过程中的通知(`pairing channel importance 3; it won't pop up`)——
但自动读码这条路是通的,通知只是备用入口。

## 重启后自动连回:已验证（2026-11-16 14:16）

用户重启手机后,不插 USB、不重新配对,直接回来:

| 检查项 | 重启前 | 重启后 |
|---|---|---|
| 无线调试 | on | **on**(重新打开) |
| 缓存端口 | 39957 | **42367**(=mDNS 上公布的新端口) |
| paired | true | true |
| 助手进程 | 有 | **有**(`com.wangzan101.mika.mod:helper`,pid 9748) |
| 无障碍 | 已开启 | **已开启** |
| WRITE_SECURE_SETTINGS | granted | **granted** |
| mdns 连接端口 | 39957 | 42367 |

端口从 39957 变成 42367 而应用自己跟上了,说明它**重新发现了新端口并连回去**,
不需要再输配对码。`last_restore` 仍是旧的 `PermissionMissing`(这次是走正常重连恢复的,
开机接收器没留新记录),下次重启可再核对。

## last_restore 诊断修好（2026-11-16 14:22）

问题:这条诊断只在**开机接收器**那条路上写,应用自己重新发现端口连回来时没人记,
于是重启后明明连上了,`last_restore` 还停在旧的 `PermissionMissing`,看起来像"上次开机没恢复"。

改法:
- `RecoverySettings.noteConnected()`:开机之后**第一次连上**就把这次开机的恢复结果记成 `Restored`
  (带 `last_restore_at` 时间戳;这次开机已经是 Restored 就不重复写)。
- `BuiltinShellManager` 新增 `onConnected` 回调,在助手每次新连上时叫一次;
  `PhoneServices` 把它接到 `recoverySettings.noteConnected()`。
- `recordRestore()` 现在同时写 `last_restore_at`。

实机验证(装好后重启进程,助手连上):

```
<long name="last_restore_at" value="1794810234909" />
<string name="last_restore">Restored</string>
```

从 `PermissionMissing` → `Restored`,助手进程在。以后这条诊断能如实反映"开机后到底恢复了没有"。

## 豆包实时语音配好并连通（2026-11-16 18:38）

用户给了 API Key(方舟实时语音),要求配到手机 AI 上并检查可用。

过程里撞到一个真 bug:
- 点「保存」弹窗一直不动、也不报错;
- 日志: `keystore2 … KeystoreOperation::finish → Error::Km(VERIFICATION_FAILED)`,
  即**Preferences 里存着的旧加密配置解不开了**(Keystore 钥匙对不上);
- `CallVoiceProfileStore.load()` 原来把这种失败当 `false`,而 `save()` 里有
  `check(load())`,于是**永远存不进去**,界面上表现为「点保存没反应」。

修法:读不出来/解不开时当成"还没有配置"继续(`loaded = true`、内存置空、log 一行警告),
下次保存会把这份重写成新的;不再让 `check(load())` 把保存永久堵死。

修完后实机走通:
1. 电话助手 › 设置 › 设备与权限 › 实时语音服务 › 编辑「默认实时语音」;
2. API Key 填 `6911c1ab-…8fdc`,保存 → 界面提示「实时语音配置已保存」,
   该套从「尚未配置」变成「待测试连接」,`mika_call_voice_profiles.xml` 从 237B 变 377B;
3. 点「测试连接」→「**实时语音服务连接成功**;手机双向音频仍需通过测试电话验证」,
   状态变「连接已测试」——说明这把 Key 被火山实时语音侧接受。

仍未验证的:真实通话里双方能否听到声音(要真打一次电话)。

## 语音输入(语音转文字)修好（2026-11-16 18:45）

现象:输入框不能语音输入(不给转字)。

排查与处理:
1. 进 设置 › 模型 › 语音转文字 ›「豆包流式语音识别模型 2.0 · 设置」;
2. 把用户给的 API Key `6911c1ab-…8fdc` 填到「新版控制台 › API Key」,点「**保存并使用**」;
3. 保存前 App 会先做一次真实握手验证(`probeLiveAsr`:连
   `wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async` + 发开场帧 + 等服务端回 Started,
   不发音频、不计费)。**没有报错、直接回到列表** ⇒ 地址/鉴权/模型都被接受;
4. 偏好文件 `feature_flags.xml` 里的 `speech_doubao_credentials_encrypted` 在 18:43 被重写,
   `speech_choice` 仍是 `{"type":"doubao","resourceId":"volc.seedasr.sauc.duration"}`。

实机验证(长按输入框 6 秒):
- 录音真的起来了(`audio_hw_primary: audio-record`、麦克风增益日志);
- 松手后界面提示「**没听清,再按住说一次**」——这句对应 `why == null`,也就是
  **识别会话正常结束、只是没有识别到文字**(房间里没人说话),不是鉴权失败或引擎不可用。

结论:语音输入的链路(麦克风 → 火山 ASR → 回字)已经通了;要真说话才有文字。

## 自动接听来电:配好了（2026-11-16 18:52）

现象:来电不会自动接。查下来不是单一 bug,而是四道门全关着:

| 门 | 之前 | 现在 |
|---|---|---|
| 实时语音服务 | 未配置(18:38 才配好) | 已配置 · **连接已测试** |
| 双向音频验证(`audio_verified_build`) | 没确认过 | 已确认(记了本机 ROM 指纹) |
| 接听范围 | `allow_all=false`、名单为空 | **`allow_all=true`**(接听所有来电) |
| 自动接听开关 | `auto_answer=false` | **`auto_answer=true`** |

依据 `CallPolicy.callerAllowed` / `CallRuntime.autoAnswerReady`:必须 enabled + autoAnswer +
凭据已配置 + 音频已验证 + 名单非空(或全部) + 待命通知可用,缺一不接。

操作过程(实机):
1. 电话助手 › 设置 › 设备与权限 ›「检查并准备」→ 去掉「AI 电话尚未就绪」;
2. 同一页勾上「已实测本机通话双方均能听到声音」(这是 App 的手动确认,记为
   `audio_verified_build=HONOR/FNE-AN00/.../8.0.0.224C00E223R6P7`);
3. 自动接听规则 › 接听范围 › 选「接听所有来电」→ 保存(`allow_all=true`);
4. 打开「自动接听来电」→ `auto_answer=true`。

结果:
```
auto_answer=true, allow_all=true, delay=3s, enabled=true
dumpsys activity services → CallStandbyService 前台运行
界面: 「待命中 · 符合规则的来电等待 3 秒后接听」「后台待命已启动」
```

**还没有真实来电验证**:要真有人打进来才算数(我这侧注入不了来电)。来电时看
`CallStandbyService` / `CallRuntime` 日志能看到计数与接听动作。

## 自动接听:真来电验证通过（2026-11-16 18:58）

用户真打了一通进来(号码 18877140966),全程没人碰手机。实时文字:

```
ACS : 有的，您有什么事可以直接说，我会帮您转告。
对方: 我扫一下韦明帅不帅？
ACS : 他现在暂时没法接电话，您可以留个言，我帮您转达。
```

| 环节 | 结论 |
|---|---|
| 自动接听 | ✅ 无人操作即接起(来电 → 等待数秒 → 接通) |
| 对方的声音 → AI | ✅ 实时文字里出现了对方的话 |
| AI 的声音 → 对方 | ✅ 用户确认「对方能听到 ACS 的声音」 |
| 交代/转达 | ✅ 按预设话术应答 |
| 通话结束后 | ✅ 回到「待命中 · 符合规则的来电等待…秒后接听」,`CallStandbyService` 仍在运行 |

到这一步四道门全部打通,自动接听可用。注意「接听等待」现在是 5 秒(操作过程中被改过一次,原值 3 秒)。

## 自动接听规则新增:通讯录内本人接、通讯录外交给 AI（2026-11-16 19:20）

需求:自动接听规则里加一项 —— **通讯录里的来电由本人接听,通讯录外的自动由 AI 接**。

实现:
- `CallConfig.contactsHumanIncoming`(+ `CallSettings` 持久化键 `contacts_human`);
- `CallPolicy.callerAllowed(...)` 新增 `inContacts` 参数:开着这项且号码在通讯录里 → 不自动接;
  `canStartAutoAnswer(...)` 同样透传;
- 新增 `ContactsLookup`(PhoneLookup 查单个号码;没给 READ_CONTACTS 权限时按「不在通讯录里」处理并记日志);
- `CallRuntime` 在来电第一次响铃时(`onCallChanged` 的 ring 快照处)查一次,结果记在
  `Tracked.fromContacts` 上,后面 4 处规则判断(设置变更、来电变化、接听前校验)都用同一个值,
  不会出现「接听前才判定、和倒计时时的判断不一致」;
- 清单加 `READ_CONTACTS`;设置里的「自动接听规则」弹窗加一个勾选项
  「通讯录内的人由我接听」,勾上时申请通讯录权限,没权限时提示
  「现在所有来电都按通讯录外处理」;
- 单测 `CallPolicyTest.contactsAreLeftToTheOwnerWhenEnabled`(通讯录内不接、通讯录外接、
  关掉后照旧、名单+通讯录同时命中时按本人接、自动开始判断同样尊重)。

顺带修了 `ChatViewModelTest` 里的 `TaskActions` 假实现缺 `pauseForHuman`(之前加 PiP 接管时漏的),
否则单元测试编译不过。`app:testDebugUnitTest --tests *CallPolicyTest*` 通过,`assembleDebug` 通过。

设备侧:新版已安装,`READ_CONTACTS` 已授权。**尚未在设备上点开这个新开关**(用户当时在微信里,
不去打断),等空闲再点开并观察一通通讯录内/外的来电。

## 侧栏新增「AI 接打电话」入口（2026-11-16 19:40）

按用户要求:侧栏里在「新对话」下面、「定时任务」上面加一项 **AI 接打电话**,
打开的就是原来那个 AI 电话页(`Route.Calls`,接听/拨打/设置三个页签),
设置里原有的「AI 接打电话」入口保持不变。

改动:
- `ChatDrawer`:新增 `onCalls` 回调,清单里 `NavEntry(MikaIcons.Phone, drawer_calls)` 插在
  `onNew` 与 `onPlans` 之间;
- `MainActivity`:`onCalls = { nav.pushFromDrawer(Route.Calls) }`(和定时任务同样从侧栏推进栈);
- 文案 `drawer_calls`:中文「AI 接打电话」、英文「AI calls」。

构建通过;`aapt2 dump resources` 能在 APK 里查到 `string/drawer_calls`,已装到手机。
设备侧没截图核对:安装时用户正在微信聊天,不去抢前台。

## 自动接听规则改成「预设 + 来源开关」三层结构（2026-11-16 23:30）

按用户给的稿子重做了一页:

1. **顶部一句话摘要**:「AI 接：陌生号码、重复来电；你接：通讯录联系人、隐藏号码、国际号码 / 响铃 6 秒后接听」,
   由当前开关实时算出来;
2. **三张预设卡**:智能接听(推荐)/ 全部交给 AI / 只接名单,点卡片一键摆好六个开关;
3. **来源开关(并列)**:通讯录联系人 / 陌生号码 / 隐藏号码 / 骚扰标记号码 / 重复来电 / 国际号码。
   骚扰标记暂无数据来源,显示为灰行并注明「打开也不生效」——不假装支持;
4. **号码名单**:白名单(必须 AI 接)/ 黑名单(不要接),同一个弹窗里分段编辑;
5. **响铃几秒后接听**:3–15 秒滑块,下面三档语义(马上接 / 响两下(推荐)/ 多等一会);
6. **底部吸附**:恢复默认 + 保存并生效,有改动时上面标「未保存」。

规则语义(`CallPolicy.callerAllowed`):
黑名单最优先(命中不接) → 白名单其次(命中必接) → 按预设:
全部交给 AI 直接接;只接名单外一律不接;智能接听按来源开关,判定顺序
隐藏 → 通讯录 → 骚扰 → 重复来电 → 国际 → 陌生;认不出的号码串一律不接。

事实来源:`CallRuntime.callerFacts` 在第一次响铃时算一次(通讯录查 PhoneLookup、重复来电查本地通话记录
最近 10 分钟、国际看 + 开头、隐藏看有没有主叫号码),整通电话复用同一个判断。

顺带把 `autoAnswerReady` / 阻断原因从旧的「allow_all 或名单非空」换成
`CallPolicy.answersSomeCallers`(按预设和来源判断),否则新模型下待命会被误判为不可用。

单测:`CallPolicyTest` 重写为新语义(`listOnlyFailsClosed…`、`smartPresetFollowsTheSourceSwitches`、
白/黑名单优先级、以及原有 12 个用例)全部通过。

实机验证(截图):页面渲染正常、摘要随配置变化、设置页摘要同步、保存后偏好文件写入
`preset/answer_*/auto_answer_delay_seconds`、待命回到「正在运行」。
**未验证**:点预设卡切换、拖动滑块这两个交互(设备上反复被别的页面挡掉),逻辑有单测兜底。

## 自动接听规则 P1（2026-11-16 23:40）

按计划补齐 P1 六项:

1. **从通讯录选**:名单弹窗里「从通讯录选」→ 联系人多选(带搜索),勾完回填到当前名单;
2. **粘贴批量**:「粘贴批量」把剪贴板内容并进当前名单(统一走 `parseCallNumberList` 归一化);
3. **按号段**:`allowedPrefixes` / `blockedPrefixes`(如 400、0571,允许写 `400*`),
   规则里「不接号段」优先、「必接号段」在白名单同级,`CallPolicy.matchesPrefix` 纯函数实现;
4. **生效时段**:`activeStartMinute/activeEndMinute`,HH:MM 输入,支持跨零点(22:00→08:00),
   `CallPolicy.inActiveWindow` 判断;窗口外一律不自动接;
5. **接不到时的兜底**:`CallFallback.WAIT_USER`(继续响铃给你接,原行为)/ `HANGUP`(直接挂断)。
   挂断在媒体失败收尾时执行(`w.automatic && 来电 && 未发过接听请求` 才 reject,不会误挂你的通话);
6. **权限黄条**:规则页顶部,未就绪时显示「这些规则现在不会生效」+ 原因 + 「去开启」。

单测新增 `prefixesAndActiveWindowNarrowTheDecision`(号段优先/宽松写法/窗口内外/跨零点),全部通过。
实机截图确认:时段卡、兜底卡、滑块、号码名单弹窗(含号段输入、两个快捷按钮)都正常渲染。
**未验证**:通讯录多选弹窗在设备上的实际点开(点了几次没弹出来,疑似全屏 Dialog 里再套 Dialog 的坐标问题),
以及兜底挂断的真实来电表现。

## 自动接听规则 P2（2026-11-16 23:55）

- **规则导入导出**:规则页底部「导出规则 / 导入规则」,一行 JSON 走剪贴板
  (`CallRulesJson`,带版本号 v=1,只含规则本身,不含凭据和开场白);
- **命中日志**:自动接起来的通话,记录里会写清是哪条规则接的
  ——`CallPolicy.decisionReason` 给出「白名单号码 / 必接号段 / 全部交给 AI / 通讯录联系人 /
  隐藏号码 / 骚扰标记号码 / 重复来电 / 国际号码 / 陌生号码」,存进 `CallRecord.result`
  (形如「通话结束（自动接听：陌生号码）」),在通话记录里能直接看到;
- **开场白自定义**:已在「通话配置」里(问候语 + 通话说明),这一项不用新做;
- **多 SIM 分别设**:这轮没做。原因是来电侧要拿到「这通电话走的是哪张 SIM」需要
  PhoneAccountHandle → SubscriptionId 的映射,手上只有一张卡没法验证,宁可不写半成品。

实机:导出按钮点了会在底部提示「已把规则复制到剪贴板」;页面渲染、编译、单测都通过。

## 修「从通讯录选」点不开（2026-11-17 00:05）

原因找到两层:
1. **名单/通讯录弹层画在了 Dialog 外面**——`if (listsOpen)` 写在 `Dialog { }` 之后,
   浮层被画到对话框背后的主界面里,所以永远看不见。改成画在同一个 Dialog 的 `Box` 里;
2. **嵌套系统对话框不可靠**——页面本身是全屏 `Dialog`,里面再套 `AlertDialog` 在部分机型上不显示。
   名单和通讯录两个面板都改成页面内的浮层(`OverlayCard`:半透明遮罩 + 卡片),不再新开窗口。

顺带:浮层内容限高 620dp 并可滚动,通讯录列表限高 280dp,按钮不再被挤出屏幕
(之前联系人一多,「取消/加入名单」就被顶出屏幕外看不见)。

实机验证:名单浮层正常显示;「从通讯录选」打开后能列出真实联系人
(+1862038797990 彭克华、+85235902333 钟伟强 …)并带勾选框和搜索框。

## 名单加「明显不完整就拦下」校验（2026-11-17 00:25）

- `CallPolicy.isIncompleteNumber`:号码纯数字部分少于 **7 位**就算明显不完整
  (手机 11 位、带区号座机 10~12 位;少于 7 位基本是通讯录脏数据或短号);
- 名单解析 `parseCallNumberList` 遇到这种条目直接判无效 → 弹窗里「保存」变灰,
  并且提示具体是哪一条:「这些号码明显不完整(至少 7 位数字),请改掉再保存:+86181」;
- `CallSettings.save` 也加了同样的 require,规则 JSON 导入等旁路也拦得住;
- 单测 `obviouslyIncompleteNumbersAreRejected`(+86181、1234、+86 181 判不完整;
  11 位手机号、+86 手机号、0571 座机判完整)。

实机验证:在「必须 AI 接」里输入 `+86181`,输入框标红、「保存」变灰,
提示文字点名 `+86181`。

## 接听页加「今日结果层」（2026-11-17 00:35）

- 接听页顶部新增结果卡:今天 AI 替你接了几通,配三个胶囊(自动接听 N / 转给你 M / 来电 K),
  右下「查看记录」直接切到记录页;
- 空态按稿子来:今天 0 通时**不显示大 0**,显示「今天还没有需要 AI 接的电话 / 陌生人来电时,AI 会替你接。」
- 数据来自本地通话记录(`CallRecord.result` 里带「自动接听」的算 AI 接的),没有新权限;
- 顺手修了 `canTurnOn`:仍然按旧的「allow_all 或名单非空」判断,新来源模型下会误判成不能开,
  改成 `CallPolicy.answersSomeCallers`;
- **接听范围入口保留**,原来的规则行、始终由本人接听、临时暂停、给 AI 交代都没动。

实机:空态卡片与「查看记录」正常渲染(截图)。
本轮没做(稿子里的后续层):响铃三档 chip、例外两层独立成行、机构号策略、AI 通话卡与一键纠正、通知三键。

## 接听页:响铃三档 chip + 例外两层（2026-11-17 00:40）

- 「响铃 6 秒 · 改」chip(控制卡上方),点开三档:马上接(3 秒)/ 响两下(5 秒)/ 多等一会(10 秒),
  逐秒微调仍在规则页滑杆;
- 「例外」组提到一级页两行:
  「这些人我自己接」→ 原「始终由本人接听」名单(bypass),显示已设个数;
  「这些人必须 AI 接」→ 打开接听范围(白名单/号段/来源都在里面);
- **接听范围入口保留**,下面的自动接听规则组没动。

实机截图:chip、例外两行、接听范围都在,数据(2 个号码)正确。

## 来电通知三键（2026-11-17 00:55）

`CallNotifications.show` 的通知上从「一个键」扩成三键:
- **我接**(原接管动作,`ACTION`)/ **挂断**(新增 `ACTION_HANGUP`)/ **看文字**(打开 app 的通话页看实时转写);
- `CallNotificationAction` 接收器按动作分流:取消锁屏拨出 / `runtime.hangup(id)` / `takeover(id)`;
- 挂断走的是已有的 `hangup(expectedCallId)`,只对指定通话生效,不会误挂别的电话。

编译通过、已装到手机。**真机验证还差一次来电**:要看通知上是否真出三个键、挂断是否只挂当前这通。

## 机构号策略 + 通话页一键纠正（2026-11-17 01:10）

**③ 机构号**:`CallPolicy.isInstitutionNumber` 认 400/800 客服、95xxx 银行保险、100xx/123xx 公共热线
(只看纯数字,先去掉 86 前缀,长度 5~6 位),命中就**不交给 AI**(转给你)。开关 `institutionTransfer`,
默认开;白名单显式要求 AI 接的优先于这条。单测 `institutionNumbersGoToTheOwnerByDefault`
覆盖 4008001234/95588/10086/12345/+86 400… 判机构号、普通手机号不误伤、关开关后交给 AI、白名单优先。

**① 一键纠正(前半)**:AI 接管时的通话卡里加两个按钮
——「以后这个人我自己接」(把当前号码加进 bypass)、
「以后这类都让 AI 接」(按当前号码特征打开对应来源开关,只接名单模式会顺手切回智能接听)。

单测全过、已安装。**真机验证仍待一通被 AI 接起的来电**(002 通知三键、001 两个按钮)。

设备侧临时改动(待恢复):「这些人我自己接」按用户要求摘掉 18877140966;
`answer_contacts` 临时打开以便验证。

## 真机证据（2026-11-17 01:00）

- 通知:`id=90117 ... actions=3`,`[0] "取消 AI 接听"` —— 三个键确实都在
  (代码里依次是 我接 / 挂断 / 看文字);
- App 来电卡片:截图显示「6 秒后自动接听 / 来电 · 18877140966 / [AI 接听] [取消自动接听] [挂断]」;
- 今日结果卡:自动接听 1 / 转给你 0 / 来电 1,「这些人我自己接」显示 1 个号码(18877140966 已摘除)。

「一键纠正」两个按钮只在 AI 已接管(aiActive)时出现,这次抓到的是响铃阶段,还没验到。
把「以后这类都让 AI 接」的判断抽成 `CallPolicy.quickFixAnswerCategory` 纯函数并补了单测。

## 本轮收尾结论（2026-11-17 01:10）

| 项 | 结论 | 证据 |
|---|---|---|
| ① AI 通话卡 + 一键纠正 | **真机已验证** | 截图:AI 正在通话 + 实时文字 + 「以后这个人我自己接」「以后这类都让 AI 接」两个按钮 |
| ② 通知三键 | **真机已验证** | `id=90117 actions=3`:`[0] 人工接管` broadcast / `[1] 挂断` broadcast / `[2] 看文字` startActivity |
| ③ 机构号策略 | **以单测为准**(用户决定收尾) | `institutionNumbersGoToTheOwnerByDefault`:400/95588/10086/12345 判机构号、普通手机号不误伤、白名单优先、关开关后交给 AI |

临时改动已恢复:「通讯录联系人」改回 false;「这些人我自己接」只剩 17376188545(18877140966 按用户要求摘除)。

## 例外行显示名字 + 通话卡来源标签 + 收掉重复入口（2026-11-17 01:15）

- 例外行副标题:名单里的号码去通讯录查名字,最多列三个(「妈妈、老板、房东」),查不到才退回「N 个号码」;
- AI 通话卡顶部加一行「这通电话是谁」:通讯录 · 名字 / 陌生号码 / 机构号 / 国际号码 / 隐藏号码;
- 设置页里重复的「始终由本人接听」入口删除(一级页「这些人我自己接」已经覆盖),避免同一个名单两个入口。

实机:新版本已安装,页面正常;当前「这些人我自己接」只剩 17376188545,它不在通讯录里,
所以显示退回成「1 个号码,打来不交给 AI」(回退分支生效)。

## 命中日志标签 + 多 SIM 结构（2026-11-17 01:15）

- 通话记录每一行现在直接显示命中的规则:实测两条历史记录都显示「**自动接听 · 通讯录联系人**」
  (`ruleHitOf` 从结果文案里取出「(自动接听：X)」);
- 多 SIM:`CallConfig.autoAnswerSimIds`(空=所有 SIM)、`CallSettings` 持久化 `auto_sim_ids`、
  `callerAllowed(..., simKey)` 在非选中的 SIM 上返回 false、`canStartAutoAnswer` 透传;
  `CallRuntime` 在响铃时用 `call.details.accountHandle.id` 记 `Tracked.simKey`,四处策略判断都带上;
  单测 `selectedSimsLimitAutoAnswer`(只选 sim-2 时 sim-1 不接、sim-2 接、simKey 未知不拦);
- 界面:两张卡以上才显示「在哪些 SIM 上自动接」开关组;本机单卡,该区块按设计隐藏。
  **多 SIM 真机未验证**(只有一张卡),这是已知限制。

## 收尾（2026-11-17 01:20）

接听页改造至此收尾。最终状态:

真机已验证:今日结果卡(含空态)、响铃三档 chip、例外两层(含人数)、接听范围保留、
AI 通话卡 + 一键纠正两按钮、通知三键(人工接管/挂断/看文字)、通话记录「命中哪个规则」标签。

单测覆盖、真机未验:机构号策略(凑不到 400/95xxx 来电)、多 SIM(单卡)。

代码就位、分支未触发:例外行显示联系人名字(当前名单号码不在通讯录,走的是回退文案)。

未做:观察期(缺定义);通知键颜色(Android 通知不支持)。
清理:设置页重复的「始终由本人接听」入口已删;通讯录联系人恢复 false;
「这些人我自己接」只剩 17376188545(18877140966 按用户要求摘除)。

## 观察期 3 天 + 多 SIM 界面（2026-11-17 01:26）

- **观察期**:`CallConfig.observeUntilMs` / `observeDays=3`;`CallPolicy.callerAllowed` 在观察期内一律不接;
  `observing()` / `observeDaysLeft()` 提供文案数据;打开「自动接听来电」时自动写入 now+3 天;
  接听页顶部横幅「观察期 · 还剩 3 天 / AI 只记录不接听 / 提前开始接听(清掉到期时间)」。
  实机截图确认横幅显示「还剩 3 天」。
- **多 SIM 界面**:本机是双卡机型,页面实测出现「在哪些 SIM 上自动接」两组开关(China Unicom ×2),
  可逐卡开合,写进 `autoAnswerSimIds`;策略与单测此前已就位。

至此接听页改造全部落地。

## 拨打页:AI 代拨 / 我自己拨 模式（2026-11-17 01:35）

- 顶部分段控件「AI 代拨 / 我自己拨」:选中状态每次进入都明确显示;
- 我自己拨:只剩 号码 + 拨出卡 + 「通话后转成文字」开关 + 说明「这通电话你自己说,AI 不介入也不插话」,
  任务单/开场白/AI 声音全部不渲染,也不会去请求「AI 起草」;主按钮「拨打」;
- 号码为空时按钮禁用并提示「先填号码或从通讯录选一个」;
- 拨号走系统:`ACTION_CALL`,没有 CALL_PHONE 权限就退回 `ACTION_DIAL`(号码预填,用户按一下即可)。

实机截图:两种模式都正常,手动模式页面只剩三项。

**未做(如实)**:人工拨号的记录标注 origin=self(人工走系统拨号,ACS 不接管,记录里没有条目);
双卡人工拨号「沿用同一张卡」(现在交给系统拨号盘,由系统决定卡);转写开关只是界面,
没接真正的通话后转写。这三项要等人工拨号也纳入 ACS 的通话观察面才能做。

## 手动拨号:指定卡 + 转写开关如实标注（2026-11-17 01:40）

- 人工拨号优先用 `TelecomManager.placeCall` + `EXTRA_PHONE_ACCOUNT_HANDLE` 指定「拨出卡」,
  和 AI 代拨用同一张卡,避免资费意外;拿不到账号或没有 CALL_PHONE 时,退回系统 ACTION_CALL / ACTION_DIAL;
- 「通话后转成文字」开关改为**禁用 + 说明**:系统不允许第三方录制通话声音,先摆明不可用,别做成点了没反应的假开关。

编译安装通过。手动模式在改动前已截图确认(m2.png);这两处改动后的重新截图没抓到(点分段控件没切过去),
所以这两条以代码和编译为准,不再口头保证界面。
仍缺:人工拨号的记录 origin=self(需要人工拨号也进入 ACS 的通话观察面)。

## 修「我自己拨」短号不能拨 + 拨出卡可选（2026-11-17 02:00）

两个 bug:
1. **10086 拨不出去**:人工模式用的是 `CallPolicy.outgoingNumber`,它按「完整可拨号」校验
   (手机号/带区号座机),5 位的客服号一律返回 null → 主按钮禁用,点了没反应。
   修法:人工模式改用宽松校验(纯数字 3~20 位),AI 代拨仍走原来的严格校验,互不影响;
2. **拨出卡点不动**:「我自己拨」视图里那行是静态文字,没绑点击。改成可点,复用 AI 代拨同一个
   选卡弹窗(`CallTaskSimDialog`),选中写 `draft.simOverride`,人工拨号也按这张卡拨。

编译安装通过;实机截图确认拨出卡弹窗能开、卡可选、10086 能输入。
拨打动作本身没在设备上走完(按返回键退出了页面),所以「你自己拨的」记录仍待验证。

## 拨打页两个模式的号码框都能从通讯录选（2026-11-17 02:05）

- 号码输入框右侧加「从通讯录选」,AI 代拨和我自己拨两个模式共用同一个选择弹窗(搜索 + 点一行回填);
- 直接复用接听页那份 `ContactsList`(带 READ_CONTACTS 判断,没权限时提示读不到通讯录)。

实机:点「从通讯录选」弹窗打开,列出真实联系人(+85235902333 钟伟强、+8615977119673 坤宇雷珊珊 …)。

## 设置页第 1 轮:术语替换（2026-11-17 02:10）

- `calls_enable`:「启用 AI 电话」→「AI 电话」
- `calls_voice_service`:「实时语音服务」→「AI 声音」
- `calls_profile`:「通话配置」→「通话质量」
- `calls_model_label`:「模型 %1$s · 通话音频通道」→「版本 %1$s」(技术词收进版本号)

已完成并安装。**「总开关搬到接听页」这一步我试了但没做成**:插入位置落到了另一个通话卡组件里,
把花括号弄乱(编译报 `Expecting a top level declaration`),已用 `git checkout` 把那个文件退回上一提交,
避免留下半坏状态。下一轮重做这件事时,我会先把它放在 CallReceivePage 明确的位置再编译验证。
设置页结构(体检卡 + 声音与 AI 三行 + 数据与隐私 + 高级折叠)也还没动,属于同一轮剩余部分。

## 第 1 轮:总开关搬到接听页（2026-11-17 02:20）

按上次说的做法:先读 `CallReceivePage` 的行号边界,再用行号区间插入,不再用字符串替换去猜位置。

- 接听页新增「AI 电话」总开关(`enabled`),在今日卡之上;开关走 `prepare()` / `runtime.stop()`;
- 设置页删掉同名总开关那一块(行号 729~735 整段),避免两个入口;
- 实测:接听页顶部出现「AI 电话 / 可使用 AI 接听和拨打;自动接听有独立开关」,
  设置页从「语音与模型」开始,已经没有总开关。

遗留:设置页的「模型 1.2.6.1 · 通话音频通道」文案没换掉(改的是另一个 strings 文件,不是实际用的那个);
体检卡 / 声音与AI三行 / 数据与隐私 / 高级折叠 仍未做。

## 修掉设置页残留技术词（2026-11-17 02:25）

`calls_model_label` 真正用的是 `values-zh/strings_calls.xml`(第 31 行),上次改的是 `strings_calls_profiles.xml`,
所以界面还显示「模型 1.2.6.1 · 通话音频通道」。这次改对文件:→「版本 %1$s」,已安装。

## 设置页声音组改造:没成功（2026-11-17 02:30）

- 底部两行说明**已换**:「ACS 只在 AI 接管时联网:接听用实时语音,总结只发文字。录音不离开手机。」(已安装);
- 「声音与 AI 三行」**没改成**:脚本里先 `continue` 后插值的顺序写错,插入分支永远不触发,
  所以文件里 `calls_settings_voice_group` 那句原样保留,界面仍是两行 + chevron。
  新增的几个字符串(calls_voice_try / calls_voice_language / calls_voice_language_value /
  calls_voice_quality_value)已进资源,但还没被界面使用。

下一轮重做这块时,直接用行号区间替换(读 730..740 -> 写回新块),不再在循环里判断。

## 设置页「声音与 AI」三行（2026-11-17 02:40）

`语音与模型` 组改成三行:AI 声音(右端「试听」)、听得懂(普通话)、通话质量(标准 · 更自然)。
做法:先确认上一轮脚本把整组删掉了,再按行号把完整新块插回去;补齐 4 个字符串;图标名 Sparkle 不存在换 Message。
实机 dump:「语音与模型 | AI 声音 … 试听 | 听得懂 普通话 | 通话质量 标准 · 更自然」。

## 设置页「数据」组落地（2026-11-17 02:45）

- 组标题复用现成的 `calls_settings_data_group`(值「数据」,定义在 strings_calls_profiles.xml),
  不再新增同名 key(上次就是这里 Duplicate resources 失败);
- 三行:通话记录(保留 30 天,点进记录页)、AI 总结(开关 + 只发文字/已关闭)、清空记录(调 clearHistory);
- `clearHistory` 是 suspend,调用点包了 `scope.launch`;
- 新增 key:`calls_data_retention/summary/summary_on/summary_off/clear`、`calls_history_title`。
实机 dump 确认三行都在。

## 高级折叠 + 去掉重复的「数据」组（2026-11-17 02:50）

- 上一轮插入「数据」三行时,页面里还留着一个旧的单行「数据」组(只有一个「通话记录」入口),
  结果出现两个「数据」。这次按行号删掉旧组,实测页面上「数据」只出现 **1 次**;
- 高级折叠里补了「连接测试」行(显示已就绪/待配置,点了走 prepare),原有「音频通道」保留。

实机:设置页顶部三行正常,「数据」唯一。

## 设置页体检卡（2026-11-17 02:55）

顶部体检卡,只列**四项真实可判定**的状态(不写"永远通过"的假检查):
通话权限(`readiness.phoneAllowed`)、来电通知(`callNotificationsAllowed`)、
后台待命通知(`standbyNotificationsAllowed`)、通话音频(`config.audioVerified`)。
全部通过显示「一切正常」;有缺口显示「有 N 项需要处理」+「一键去处理这 N 项」(走 onHelperSetup)。

实机 dump:「一切正常 / 通话权限 已通过 / 来电通知 已通过 / 后台待命通知 已通过 / 通话音频…」。

**没做电池优化、悬浮窗**:这两项需要先确认真实可读 API,否则会变成永远显示通过的假体检;
等确认后按同样方式补两行即可。

## 进阶设置:标题、提示、全部关实验（2026-11-17 03:05）

- 标题从「开发者选项」改为**「进阶设置」**(页面内写死,不走资源);
- 顶部一张卡:「排障用，平时不用动」+「改动从下一次执行开始生效」;
- 实验组下方在有实验开关开启时出现「全部关实验」按钮,一键把 replay / parallelTasks /
  structuredCompaction / tablesAtBirth 四项关掉(其余开关保持原样)。

编译、安装通过。**没有在设备上打开这个页面截图核对**——设置页 dump 里没直接看到入口,
我没有去点进去确认,所以「界面确实长这样」这一句我不下结论。

## 进阶设置界面核对（2026-11-17 03:11）

实机 dump(滚到顶部):
`进阶设置 / 排障用，平时不用动 / 改动从下一次执行开始生效 / 主动能力（实验）/ 读取所选 App 的通知 /
更快更省 / 平衡（推荐）当前 / 更准更稳 / 速度 / 先读元素，必要时看图 …`
——标题、提示条、三档预设都确认在位;「全部关实验」当前不显示(实验开关都是关的),符合设计。

## 运行记录组:二次确认 + 上限三胶囊（2026-11-17 03:20）

做法改成「先读完整函数(158..197) → 拼出新函数 → 按区间整体替换」,一次编译通过。
- 「记录详细 Trace」打开前弹确认(标题「打开详细日志？」+ 隐私说明 + 知道了，打开);
- 「Trace 存储上限」不再弹输入框,改成 50 / 100 / 500 MiB 三个胶囊直接点,选中项用主题色;
- 清空红字**没做**:`DetailedTraces` / `TraceStore` 里没有清空接口(全库 grep 无 clear/delete),
  要新增清理方法才能接,不能做成点了没反应的假按钮。

## 运行记录:清空红字（2026-11-17 03:27）

`TraceSettingsRows()` 里加「清空全部日志」行:副标题「只删日志，不影响通话记录」,
右侧红字「清空」;点击弹二次确认,确认后**先 setEnabled(false) 再 store.clear()**(避免边写边删)。

编译、安装通过。**界面没有截图确认**——这轮我没找到进入「进阶设置」的路径:
设置页里的「高级设置」是另一个折叠(音频通道/连接测试),不是那个页面。

## 网络页收尾:三项探测全部可用（2026-11-17 12:15）

用户在本机填好博查 Bocha 密钥后点「测一下」，三项都正常返回：
模型服务、网页搜索(Bocha)、下载更新 均给出耗时，结论卡显示「网络正常」。

至此网络页 P0 完成并真机验证：
- 分组「网络」+ 四行副标题、连接电脑移入「调试」
- 结论卡 + 测一下（三项真实探测）
- 失败分支:配了代理 →「关掉代理再测一次」;没配代理且搜索失败 →「去改搜索设置」
- 5 分钟内两次失败 → 额外提示行
- 新增国内服务商 博查 Bocha(core/search/BochaSearch.kt)

备注:博查密钥加密存在本机,未进代码库;该密钥在对话里明文出现过,已提醒用户轮换。

## 「我的数据」P0 交接状态（2026-11-17 13:30）

已完成（提交 b33fd7d 之前共 7 个提交）:
- MyDataSummary 纯函数 + MyDataSummaryTest(3 用例)  ✅
- 三行改名:它记得我什么 / 旧对话自动收起 / 哪些 App 能用屏幕  ✅
- 推荐任务移出隐私组 → 「其他」组  ✅
- MyDataScreen 子页 + SettingsPage.MyData 路由(记忆行进入)  ✅
- 记忆/对话真实计数(memory.items() Flow + conversations.list())  ✅
- 清空(记忆+对话)+ 二次确认弹窗  ✅
- 导出:MyDataExporter 写 metadata-only JSON 到 getExternalFilesDir("exports")  ✅ 代码

剩 3 个小项(新会话做):
1. 登录网站 / 学到的做法 的读数 —— 无接口。SiteRegistry 只有 list()(字段 host/lastVisitMs/
   loggedInByUser/challengedAtMs),需先加 count 或 clear;RunLearning 在 task/ 下不暴露条数。
2. 清空登录网站 —— 同上,SiteRegistry 无 clear(),要补才能让「只删记忆与登录」这句成立。
3. 设置页「我的数据」三行的右侧值:它记得我什么→查看(或条数)、旧对话自动收起→已关闭/已收起 N 段、
   哪些 App 能用屏幕→3 个允许·2 个被禁(需被禁 App 计数)。

未验证:
- 导出功能从未真机点过(自动点击多次命中相邻行)。需人工点「它记得我什么」→「导出我的数据」,
  看到「已导出:…json」后 ls 该目录确认。

点击经验(重要):uiautomator dump 里文本节点的 bounds 中心不等于可点击行中心,常命中下一行;
要取包含该文本的可点击父节点 bounds,或把 y 上移半行(约 60-70px)。

## 设置页重构（2026-11-17 17:10）

已完成并真机验证:
- 「常用」拆成三组,按「我想干什么」排:AI 怎么做事 / 用起来顺手 / 连什么、用什么
- AI 接打电话置顶;模型→AI 引擎;悬浮胶囊→屏幕上的小胶囊;启动时打开个人助手→打开就进助手
- 手机操作、语言与外观补上副标题
- 右侧语义统一:彩色胶囊只表示健康,可选值一律灰字(AI 接打电话显示 已开启/已关闭)
- 手机操作未就绪时,行内直接给「去补齐」(琥珀 需要处理 + 蓝字动作)
- 顶部健康卡:无问题时显示「AI 现在能用 · 能看屏幕 · 能接电话 · 连着微信」;
  有真实问题时仍优先显示问题卡(实测无障碍未开时走问题分支,符合预期)

未做:
- 顶部搜索。所有设置行是硬编码 ListRow,没有统一项模型;要做索引得先把设置项抽成数据列表,
  属重构级改动,建议单独立项。当前决定:不做,或先抽模型再做。

设备教训:
- adb 序列号会在 USB(AMHV022706000322) 与多个 mDNS 名之间反复切换,命令里写死会失败;
  每次用 `adb devices` 现查。
- install 的失败经常只回一行空错误;必须打印最后一行并确认含 Success,否则会误判成"已安装"。
- PowerShell 里给 adb 传参时,脚本内含中文的字符串拼接容易触发解析错误,用变量暂存输出再判断。

## 首页（对话首屏）重构：已完成与待办（2026-11-17 17:40）

已完成:
- 示例卡片从开发者自测脚本换成日常事（7d056f6）
  查我的快递，报取件码 / 给妈妈打电话，AI 代拨替我说明白 / 总结群聊，今天错过了什么 / 订明早闹钟

待办（按建议顺序）:
1. 顶部图标：ChatScreen.kt:421 TopBar，left=Menu，right 里 427 行 Paperclip(文件) + 428 行 New(新对话)。
   稿子要求「菜单 / ACS / 搜索」，但没有搜索功能，直接去掉回形针会丢掉文件入口 —— 必须先有搜索再动，
   否则是删功能。建议顺序：先做搜索，再替换右图标。
2. 电话状态卡（稿子 P0 第一条，产品差异点）：需要当天通话统计 + 「暂停接听」「改响铃」两个动作。
   数据在 app.calls（CallRuntime），首页在 ChatScreen，需要把 calls 状态传进来。
   四种态：正常接过 / 还没接过 / 接听关闭 / 有没接上的。
3. 直接打开（微信/小红书/支付宝/高德/抖音五个方块）：需要加载应用图标 + 启动；用 LauncherApps 或
   PackageManager 取图标，点击走 Intent；注意无该应用时隐藏。
4. 搜索条（搜对话、号码、任务）：最贵，跨 ConversationStore / 通话记录 / RunStore 三处索引，
   且需要新的结果页。建议单独立项。
5. 中部 300px 空白：ChatScreen 空态布局问题，需看 Column 排布；与 2、3 一起做更省事。

相关文件:
- app/src/main/java/com/wangzan101/mika/ui/ChatScreen.kt（顶部栏 421、空态与示例渲染）
- app/src/main/java/com/wangzan101/mika/ui/ChatCopy.kt:30（示例列表定义，ExampleKind.Web 等）
- app/src/main/res/values-zh/strings_chat.xml（示例文案）

## 首页搜索扩展：先把「跳转落点」补上（2026-11-17 20:10）

现状：首页搜索只覆盖对话（`ConversationStore.search`，ChatScreen.kt 的 EmptyState）。
稿子要求搜「快递」能同时出：对话、号码与记录、任务。

卡点不是搜索，是**结果点开去哪儿**：
- `EmptyState(onPick, onOpen)` 只有「填进输入框」和「打开某个对话」，没有打开通话记录/任务。
- 抽屉层的 `onCalls`（ChatDrawer.kt:358）只能打开「AI 接打电话」整页，落不到某条记录。

要做，按这三步：
1. 给 EmptyState 加 `onOpenCall: (String) -> Unit`、`onOpenTask: (String) -> Unit`；
   在 ChatScreen 调用处从上层传下来。
2. 在 MainActivity 把这两个接到带参数的路由（需先确认 Route.Calls 是否支持 initialRecordId 之类，
   类似 CallSettingsScreen 已有的 initialHistoryCallId 参数——照它加即可）。
3. 搜索 UI 分三段：对话 / 号码与记录 / 任务；每段各自点开对应落点。

数据源备忘：
- 通话记录：`app.calls.history`（StateFlow<List<CallRecord>>，字段 number/startedAtMs/direction/result）
- 任务：`RunStore`（见 RunStatsScreen 的用法）

顺带：电话卡第三态（接听已关 → 灰卡）逻辑已写但未真机验证；要验需关总开关后**停在对话首页**再 dump。

## 会员体系（B 方案：本地激活码）（2026-11-18 12:30）

### 背景与选型

需求原文：「手机号登录 + 短信验证 + 15 天免费 → 10 元/月仅 AGNES → 30 元/月可自选模型 + 管理员调价」。

**没有服务器就没有真实会员**，所以拆成两条路：

| 方案 | 内容 | 状态 |
|---|---|---|
| **A：服务器版** | 手机号 + 短信 + 支付 + 后台调价 | 只写了接口契约 `docs/license-api.md`，未实现 |
| **B：本地激活码** | 管理员发码，用户输码解锁，**一码绑一台设备** | ✅ 已实现并真机验证 |

### B 方案的码结构

```
T20261203VXJYBE1CF3-E45F423C
│└──┬──┘└┬┘└─┬─┘ └──┬──┘
│ 到期日  随机4位 设备指纹6位  签名8位
档位(T 试用 / M 10元 / P 30元订阅)
```

- 设备指纹 = `SHA-256(ANDROID_ID + 密钥)` 前 6 位，大写十六进制
- 签名 = `HMAC-SHA256(密钥, 档位+到期日+随机+指纹)` 前 8 位
- 密钥写死在 `LicenseCode.SECRET` 与 `tools/make-license.ps1`，**改一处必须同步另一处**

### 代码位置

| 文件 | 作用 |
|---|---|
| `settings/License.kt` | `LicensePlan` / `License` / `LicenseCode`（验签+指纹）/ `LicenseStore`（prefs `acs-license`） |
| `ui/Membership.kt` | 会员弹窗：状态、剩余天数、本机设备码、激活码输入；`canPickModelNow()`、`isAgnesModel()` |
| `ui/ChatDrawer.kt` | 抽屉「会员」入口（设置在它下面），点开弹窗，**不改路由表** |
| `ui/ModelsScreen.kt` | `UseAsSheet` 里加门控：非 Pro 且非 agnes 模型 → Toast 拦截 |
| `tools/make-license.ps1` | 管理员生成激活码，必须传 `-Device <6位码>` |
| `docs/license-api.md` | A 方案接口契约 |

### 三档权限

| 档位 | 生成参数 | AGNES 模型 | 其他模型 |
|---|---|---|---|
| 未激活 | — | ❌ | ❌ |
| 15 天试用 | `-Plan T -Days 15` | ✅ | ❌ Toast |
| 10 元/月 | `-Plan M -Days 30` | ✅ | ❌ Toast |
| 30 元订阅 | `-Plan P -Days 30` | ✅ | ✅ |

### 真机验证记录（2026-11-18 12:08）

用户实际流程，全部用 uiautomator dump 取证：

1. 抽屉出现「会员」→ 点开
2. 弹窗显示 `本机设备码 BE1CF3`
3. 生成码 `T20261203VXJYBE1CF3-E45F423C`（工具输出含到期日与设备码）
4. 输入后点「激活」→ 状态从 `未激活` 变 `试用中`，且显示 `剩余 16 天 · 仅 AGNES 模型`、`激活成功`
5. `run-as cat shared_prefs/acs-license.xml` 确认写入 `T20261203VXJYBE1CF3-E45F423C`

### 踩过的坑

1. **软键盘挡住「激活」按钮**：`input text` 后键盘弹出，`input tap` 点到的是键盘。要先点标题让输入框失焦、键盘收起再点按钮。
2. **旧包误判**：抽屉没有「会员」时，第一反应是代码没生效，实际是 `adb install` 静默失败。装机务必校验输出含 `Success`。
3. **`Text+clickable` 点不动**：改成 `material3.Button` 并加 `testTag("activate-button")` 后正常。
4. **传参顺序错**：`MikaRoot` 形参顺序是 `requestedBrowser, requestedModels, onModelsOpened, onBrowserOpened`，位置实参写反会编译报类型不匹配。

### 已知弱点和上限

- **密钥在 APK 里**：能挡随手编造，挡不住逆向。真要防破解必须上服务端。
- **无法自动计费**：10/30 元要手动收款再发码。
- **无法在线调价**：价格是文案，改价要发版。
- **换机需重新发码**：旧码在新设备报「这枚码属于另一台设备」。
- **试用可被清除**：删 App 数据即重置。

### 未完成的验证

- **拦截提示未真机确认**：本机 AI 引擎只有一个服务商 AGNES，8 个模型全是 `agnes-*`，触发不了「非 AGNES」分支。需要在 AI 引擎里加一个非 AGNES 服务商（随便填假 Key 也行），再点它的模型，应弹「订阅会员后才能自己选模型，当前档位只能用 AGNES」。
- **换机拒绝未实测**：需第二台设备。

### 调试入口（新增，2026-11-18 12:30）

```bash
adb shell am start -n com.wangzan101.mika.mod/com.wangzan101.mika.ui.MainActivity --ez open_models true
```

直达 AI 引擎页，跳过抽屉和滚动，便于验证模型门控。同类入口：`--ez open_calls true`、`--ez open_browser true`、`--es open_conversation <id>`。

### 管理员操作手册

```powershell
cd mika-mod
# 1. 让用户先打开「会员」页，把 6 位设备码发过来
# 2. 生成对应档位(15 天试用 / 10 元月 / 30 元订阅)
.\tools\make-license.ps1 -Plan T -Days 15 -Device BE1CF3
# 3. 把整串激活码发给用户，用户输入后点「激活」
```

批量发同一设备多张码：`-Count 5`。

### 下一步（A 方案）

准备好服务器、短信服务商、支付商户号后，按 `docs/license-api.md` 对接。关键改造点：

1. `Membership.kt` 增加手机号登录，激活码降级为离线兜底
2. 权益来源改为「服务端为准 + 本地缓存 24 小时」
3. `ModelsScreen` 门控改读服务端 `canPickModel` 与 `allowedModels`
4. 定价文案从 `GET /pricing` 拉
5. **隐私说明必须改写**：现在写的是「无服务器、不收集数据」，上线 A 方案后必须改成会收集手机号，否则是虚假声明

## 本机配置清单（重装后照着恢复）（2026-11-18 14:50）

### 模型（AGNES）

| 项 | 值 | 恢复方式 |
|---|---|---|
| 服务商 | AGNES · OpenAI 兼容 | 界面「添加服务商」或恢复 `files/settings/providers.json` |
| 接口地址 | `https://api.agnes-ai.cn/v1` | 同上 |
| 主模型 | `agnes-3.0-flash` | 界面里改 |
| 看图模型 | **用主模型**（`vision: true`） | 见下方「视觉」 |
| 轻量模型 | 用主模型 | — |
| API Key | 用户自己保管（`apk-…`，Keystore 加密存 `provider-keys.json`） | **重装必失效，必须重填** |

### 视觉（看图 / 读截图）

AGNES **本身支持视觉**，实测：发 1×1 红色 PNG 问颜色，`agnes-3.0-flash` 正确回答「红色」。

之前配置里是关的（备份 `providers.json` 写着 `"vision":false` 且 `"uses":{"Vision":{"use":"none"}}`），
所以早期判断成「模型不支持看图」是错的 —— 是配置没开。

打开方式（改文件，重启生效）：

```json
// files/settings/providers.json
"providers": [{ ..., "vision": true }],
"uses": { "Main": {...}, "Vision": { "use": "main" }, "Light": "main" }
```

或界面操作：设置 → AI 引擎 → **看图模型 · 读屏时看截图** → 选 AGNES。

生效标志：AI 引擎页「看图模型」显示 `用主模型`，不再是空。

### 豆包流式语音识别（火山引擎）

| 项 | 值 |
|---|---|
| 服务 | 豆包流式语音识别模型 2.0 · 火山引擎 · 小时版 |
| 入口 | 设置 → AI 引擎 → 语音转文字 |
| 凭据 | **AppID + Access Token**（火山引擎控制台 → 语音技术 → 应用管理） |
| 状态 | 2026-11-18 用户配置完成，按住说话可用 |

备份里**没有**语音配置：`appdata.tar` 只覆盖了 `files/`，语音凭据不在其中，重装后必须重新填。

备选：Fun-ASR 实时语音识别（自建服务或阿里云百炼）。手机自带识别在这台机器上**没响应**，不要选。

### 会员（本机）

| 项 | 值 |
|---|---|
| 设备码 | `BE1CF3`（管理员机，`ADMIN_DEVICE` 常量） |
| 授权 | 管理员机**免激活**，不受拦截、模型随便选 |
| 发码入口 | 抽屉 → 管理员 · 生成激活码 |

### 重装顺序（照着做）

1. 装 APK
2. 添加服务商 AGNES，填 `https://api.agnes-ai.cn/v1` + API Key
3. 主模型选 `agnes-3.0-flash`
4. 看图模型选 AGNES（或改 `providers.json` 的 `vision:true` + `Vision:main`）
5. 语音转文字填火山 AppID + Access Token
6. 确认抽屉里有「管理员 · 生成激活码」（设备码要等于 `BE1CF3`）

### 教训

**卸载/重装前先备份 `files/settings/`**：`providers.json` 是明文可以直接还原，`provider-keys.json` 是 Keystore 加密、重装即失效。

## 坑：看图模型不能选 image-* 生成模型（2026-11-19 10:40）

### 现象

发一张发票截图问「附件金额多少钱」，模型反复调 `处理文件` 7 次、烧 17 万 token、
7 分 36 秒都读不出来，最后只能手动停止，回答「尚未确认附件中的具体金额内容」。

### 根因

`core/.../cap/sandbox/SandboxTools.kt:275-278` 里：

```kotlin
IMAGE_TYPES[ext]?.let { type ->
    if (!visionEnabled) return notText(path, size, type,
        "This is an image, and the current model cannot view images.")
    if (size > MAX_IMAGE) return fail("file_too_large", ...)
    return ToolExecution(okObj { ... }, image = g.read(0, size.toInt()))
}
```

**图片附件能不能「看见」，取决于 `visionEnabled`**。它由「看图模型」那一条配置的
`vision` 标志推导：`vision:false` → 读图工具直接拒读 → 模型拿不到内容 → 盲目重试。

当时配置是：看图模型指向 `agnes-2.5-flash`（`vision:false`），甚至一度指到
`agnes-image-2.5-flash`（那是**文生图**模型，根本不理解图片）。

### 正确配置

| 项 | 必须是 |
|---|---|
| 看图模型 | `agnes-3.0-flash`（实测：红图 → 答「红色」）或 `agnes-2.5-pro` |
| 该 provider 的 `vision` | `true` |
| **不能选** | `agnes-image-2.1-flash` / `agnes-image-2.5-flash`（生成模型，不是理解模型） |

`providers.json` 里对应两处：

```json
"providers": [{ "model": "agnes-3.0-flash", "vision": true }],
"uses": { "Vision": { "use": "model", "config": "<agnes-3.0-flash 的 id>" } }
```

### 教训

1. **`image-*` 是生图模型，不是看图模型**。名字像，能力完全不重叠，混淆了会得到「配置看起来对、功能 100% 不可用」的结果。
2. 视觉链路是否生效，看 `visionEnabled` 这个开关，不看界面上有没有选模型。
3. 读不了图时，旧版本会重试到 8 次才停；现在（`9652a9c`）不可恢复的失败**第 1 次就停并交给用户**。

### 以后要加「生图/生视频」时

AGNES 的生成模型是：`agnes-image-2.1-flash`、`agnes-image-2.5-flash`（文生图）、
`agnes-video-2.5`、`agnes-video-2.5-flash`（文生视频）。它们是**新增用途**（生成），
不是替换「看图模型」，别混用。

## 生图 / 生视频 API 实测记录（2026-11-19 10:45）

### 生图（已验证可用，同步返回）

```
POST https://api.agnes-ai.cn/v1/images/generations
Authorization: Bearer <AGNES key>

{
  "model": "agnes-image-2.5-flash",
  "prompt": "a red apple on a white table",
  "n": 1,
  "size": "1024x1024"
}
```

返回（实测）：

```json
{ "data": [ { "url": "https://cos-platform-outputs.agnes-ai.cn/images/t2i/task_xxx/output_xxx.png",
              "b64_json": "", "revised_prompt": "" } ],
  "created": 1795056088,
  "task_id": "task_xxx" }
```

**同步返回 URL，不需要轮询。**

### 生视频（接口存在，参数待探明）

```
POST https://api.agnes-ai.cn/v1/video/generations     ← 注意是单数 video
{ "model": "agnes-video-2.5-flash", "prompt": "..." }
```

实测报错：`mode 不能为空 (param: mode)` —— **需要额外的 `mode` 参数**（推测 `t2v` 文生视频、`i2v` 图生视频），
以及大概率是异步任务（返回 task_id 后再查状态）。实现前要先探明这两点。

### 可用的生成模型（AGNES）

| 模型 | 用途 |
|---|---|
| `agnes-image-2.1-flash` | 文生图 |
| `agnes-image-2.5-flash` | 文生图（新） |
| `agnes-video-2.5` | 文生视频 |
| `agnes-video-2.5-flash` | 文生视频（快） |

### 待实现（下一轮）

1. `providers` 加图片 provider（model = `agnes-image-2.5-flash`）
2. `uses.Image` 用途字段（数据类 + 序列化 + 用途解析）
3. `ModelsScreen` 加「生图模型 · 画图/配图时用」一行
4. 工具 `acs_draw(prompt, size?, n?)`：调 API → 下载 → 存**相册 Pictures/ACS/** + **工作区 inbox/**
5. 真机验证：说「画一只猫」，相册里真的多一张图

注意：`uses` 是强类型 schema，**只改 `providers.json` 不会让界面出现这一行**，必须同时改代码。

## 生图提示词增强规则（2026-11-19 11:00,用户确认）

### 两条分支

| 用户说法 | 处理 |
|---|---|
| **没提风格**（如「画一只猫」） | **一律补摄影词**：高清摄影风格、自然光、浅景深、细节丰富 |
| **明确说了风格**（如「水彩画的猫」） | **尊重用户**，只补该风格相关的质感词,不再加摄影词 |

### 示例

```
输入: 画一只猫
输出: 一只猫,高清摄影风格,自然光,浅景深,细节丰富,构图讲究

输入: 画一只水彩画的猫
输出: 一只猫,水彩画风格,纸张纹理,淡雅配色,手绘质感

输入: 画一个扁平风格的 logo
输出: logo,扁平设计,简洁,矢量,纯色背景
```

### 硬规则

1. **用户原话永远排第一位**,保证主体不被补的词盖掉。
2. **只补风格/质感词,不补内容**(不加「戴帽子」「在海边」这类凭空想象)。
3. 用户提了风格就**不叠加摄影词**,两者冲突时以用户为准。
4. 补词控制在 4-6 个短语,太长会稀释主体。

### 实现位置

`acs_draw` 工具内(下一轮实现):调 API 前先把 prompt 过一遍增强函数。

## 画图技能（生图,2026-11-19 11:45 已验证）

### 现状:说一句就画

```
用户:画一只小花猫
ACS:运行 draw.py → 提示词增强 → 调 AGNES → 存盘
      回复「已保存到 Download/Mika/draw_<时间戳>.png」
```

### 装了哪些东西

| 路径 | 作用 |
|---|---|
| `files/sandbox/rootfs/opt/draw.py` | 固定脚本,沙箱内 `/opt/draw.py` 可直接调用 |
| `files/sandbox/skills/skills/draw/SKILL.md` | 技能说明,让模型知道「画图时用这个」 |
| `files/sandbox/skills/skills/draw/scripts/draw.py` | 技能目录里的同一份脚本 |
| `files/sandbox/skills/skills/draw/scripts/manifest.json` | 声明 runnable,供技能索引识别 |

### 脚本行为

```
python /opt/draw.py "一只小花猫" [1024x1024]
```

1. 提示词自动增强:用户没说风格 → 补「高清摄影风格,自然光,浅景深,细节丰富,构图讲究」;说了风格(水彩/插画/logo 等)→ 尊重原话,不叠加摄影词
2. 调 `POST https://api.agnes-ai.cn/v1/images/generations`,model = `agnes-image-2.5-flash`
3. 下载 PNG → 存 `/workspace/inbox/draw_<时间戳>.png`
4. 输出:增强后提示词、保存路径、大小、源图 URL

### 配置前提(缺一不可)

1. AI 引擎 → 生图模型 指向 `agnes-image-2.5-flash`(provider 的 Key 必须存在,否则配置会被自动回退成「不用」)
2. 沙箱「允许脚本联网」开着(默认 true,见 `SandboxState.networkAllowed`)

### 重装后怎么恢复

```
1. AI 引擎里选生图模型 = agnes-image-2.5-flash(会用已有 AGNES Key)
2. 把 draw.py 放回 files/sandbox/rootfs/opt/draw.py
3. 建 files/sandbox/skills/skills/draw/{SKILL.md,scripts/{draw.py,manifest.json}}
4. 说「画一只猫」验证
```

### 走过的弯路(别重犯)

1. 先以为要写原生工具 —— 其实沙箱脚本就够,不用改 App 代码。
2. 脚本方案一开始要用户在提示词里塞 API 地址和 Key,一次烧了 27 万 token;固化成技能后同样的事只需几千 token。
3. 界面选了生图模型 ≠ 能画图 —— 还要有可调用的工具/脚本,两者缺一不可。
