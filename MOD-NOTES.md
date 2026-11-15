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
