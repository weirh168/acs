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
