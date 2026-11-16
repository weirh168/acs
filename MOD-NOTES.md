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
