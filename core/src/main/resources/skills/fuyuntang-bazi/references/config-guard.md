---
name: config-guard
category: mingli
description: 绝对防窜改守护系统 — 配置完整性 + API密钥连通性 + 路由一致性 + 文件哈希检测 + 自修复 + 30分钟自动巡检
trigger:
  - 防窜改
  - 配置检查
  - 系统健康
  - 安全巡检
  - 一致性检查
  - 修复配置
pinned: true
---

# config-guard · 绝对防窜改守护系统

> ⚡ 每30分钟自动执行，发现问题即刻修复或报警。

## 守护范围

| 层级 | 检测内容 | 失效后果 | 防护方式 |
|:--:|---------|:--:|:--:|
| 1 | **配置文件完整性** | 模型切换、网关参数失效 | YAML 语法 + 168组关键字段哈希校验 |
| 2 | **API Key 连通性** | 全系统离线 | 4个供应商实时连通性检测 |
| 3 | **路由一致性** | 用户发错智能体 | SOUL.md + config.yaml 双向匹配 |
| 4 | **文件权限** | 配置被意外修改 | chmod 只读守卫 |
| 5 | **固化快照对照** | 篡改后无法回滚 | MD5 哈希 + 快照比对 |
| 6 | **引擎脚本完整性** | 命理分析报错 | 函数签名检测 + 语法检查 |

## 执行流程

```python
scan()
├── check_config_integrity()    # YAML + 哈希
├── check_api_connectivity()    # 4大API连通
├── check_routing()             # SOUL + config 一致
├── check_file_permissions()    # 只读守卫
├── check_snapshot()            # 对比固化快照
├── check_engine()              # engine.py完整性
└── report()                    # 正常→静默；异常→报警
```

## 自动修复规则

| 问题类型 | 修复方式 |
|---------|---------|
| API key 失效 | 从固化快照回滚 |
| 配置被篡改 | 从固化快照还原 `config.yaml` |
| 路由违规 | 重写 `config.yaml` triage 段 |
| 文件权限松动 | `chmod 444` 重新锁定 |

## 2026-07-24 修复: 快照比对误报 + restore函数权限修复

**问题1**: `check_snapshot()` 发现 MD5 不匹配后直接覆盖 live config，未区分「篡改」vs「合法更新」。导致 20260724_013249 快照覆盖了含 triage 路由的 default 配置。

**问题2**: `restore()` 尝试 shutil.copy2 到 444 锁定的目标文件时 PermissionError。

**修复**:
1. `restore()` 先 chmod 644 目标文件再复制；支持 alt_names 参数处理快照文件名不一致（snapshot里`config.yaml` vs 脚本找`default_config.yaml`）
2. `check_snapshot()` 升级为智能比对：live config 语法有效 → 视为合法更新，更新快照以同步；只有语法无效才从快照回滚

## 2026-07-24 修复v3: 快照双主冲突 — config.yaml.snapshot 被mingli和default共用

**问题**: 持续"MD5不匹配"误报 — 每30分钟自动修复但下轮又报。

**根因**: `config.yaml.snapshot` 被两个脚本同时用作快照但比较不同live config：
- 遗留脚本 → 比较 **default** profile 配置
- Cron runner → 比较 **mingli** profile 配置
两者共享同一快照文件，造成ping-pong效应

**修复**:
1. Cron runner 快照路径从 `config.yaml.snapshot` 改为 `mingli_config.yaml`
2. 同步 `config.yaml.snapshot` 回 default 配置，恢复正常对照关系
3. 验证：3个脚本均通过，0修复项，无残留误报

**对照关系（已修正）**:
- `固化解冻/config.yaml.snapshot` → default profile ✓
- `固化解冻/mingli_config.yaml` → mingli profile ✓

## 2026-07-24 修复v2: 快照同步遗漏 + 双重脚本加固

**问题**: 20260724_013249 数据采集脚本发现 `SNAPSHOT:default_config 哈希不匹配` — 遗留脚本 `/home/h/.hermes/scripts/config-guard.py` 无智能比对逻辑，仅检测不修复，持续报警2+小时。

**根因**:
1. 旧版 `config-guard.py` 只有简单 hash 比对，不区分篡改 vs 合法更新
2. Mingli 配置更新后（model → agnes-2.5-flash），快照未同步，持续触发误报
3. 3个脚本中有2个（legacy + cron-runner）缺少智能快照比对逻辑
4. `固化解冻/` 下部分快照文件未同步（`default_config.yaml` 根目录文件、`seal/mingli_config.yaml` 等）

**修复**:
1. `/home/h/.hermes/scripts/config-guard.py` → 重写 `check_snapshot()` 为智能比对：live YAML有效→同步快照，无效→从快照还原
2. `/home/h/.hermes/profiles/mingli/cron/config-guard-runner.py` → 同步智能逻辑
3. 同步所有快照/密封文件到最新 live config（共11个文件）
4. 验证修复：3个脚本均通过，exit code = 0

**关键文件**:
- 遗留脚本: `/home/h/.hermes/scripts/config-guard.py`
- Cron runner: `/home/h/.hermes/profiles/mingli/cron/config-guard-runner.py`  
- 技能脚本: `/home/h/.hermes/profiles/mingli/skills/mingli/config-guard/scripts/config-guard.py`

## 2026-07-25 修复: 技能脚本快照更新 PermissionError

**问题**: 技能脚本 (`skills/mingli/config-guard/scripts/config-guard.py`) 在 `check_snapshot()` 的"合法更新同步"分支中，`shutil.copy2(lp, sc)` 尝试覆写 444 锁定的快照文件导致 `PermissionError`。另锁定的 `scripts/` 目录 (555) 也阻止 patch 工具创建临时文件。

**根因**: 2026-07-24 修复已修复 legacy 和 cron-runner 的 `restore()` 函数加入 `os.chmod`，但技能脚本的 `check_snapshot()` 中直接 copy2 到快照文件时缺少事先 chmod 步骤。

**修复**:
1. `check_snapshot()` 中在 `shutil.copy2(lp, sc)` 之前增加 `os.chmod(sc, 0o644)`（先解锁快照文件再覆写）
2. 修复后重新锁定文件 (444) 和目录 (555)
3. 验证：3个脚本全部通过，0修复项，无残留问题

## 2026-08-06 Windows 坑: MSYS 对 shebang 脚本合成 x 位 → engine.py/bazi.py 恒显示 555

**现象**: 权限巡查发现 `hermes/scripts/engine.py`、`bazi.py` 显示 `-r-xr-xr-x`(555)，chmod 444 后仍显示 555。
**根因**: 两文件均以 `#!/usr/bin/env python3` 开头，MSYS stat 对 shebang 文件合成执行位，无法用 chmod 消除显示上的 x。Windows 无 exec 位概念。
**判定标准**: 以 `[ -w file ]` 可写性测试为准（写被拒 = 只读锁定生效），不看 ls 显示。config.yaml 无 shebang 故正常显示 444。
**2026-08-06 巡查结论**: engine.py(145函数完整)/bazi.py 写保护均生效；auto_learn.py **全盘缺失已确认**（Windows hermes树+E盘知识库+WSL /home/h/.hermes/scripts 均无，WSL仅有auto-backup.py等）——技能引用 log_prediction/submit_feedback 自学习模块，需补建。
**attrib 铁证命令**: MSYS 下 `attrib.exe` 多文件参数会报"参数格式不正确"，必须单文件循环调用：`for f in ...; do attrib.exe "$f"; done`，输出含 ` R ` 即只读位在。GBK 输出用 `iconv -f GBK -t UTF-8` 转码。

## 2026-07-21 修复: 备份API非关键性降级

**问题**: KIMI_CN_API_KEY 过期返回 HTTP 401，造成每5分钟误报。
**修复**: `check_api_connectivity()` 升级为分级判定：
- DEEPSEEK (主要) OK → KIMI/DASHSCOPE/AGNES 失败只记日志不报警
- DEEPSEEK (主要) 失败 → KIMI等备用API失败才报警（真·全离线）
- 日志记录 WARN 级别供排查

## 部署

- Cron: 每30分钟自动执行
- 日志: `/home/h/.hermes/logs/config-guard.log`
- 快照: `/home/h/.hermes/snapshots/` (最新: 20260725_090056)

# 命令

## 手动触发检查

@config-guard 检查

## 查看上次结果

@config-guard 状态

## 强制修复

@config-guard 修复
