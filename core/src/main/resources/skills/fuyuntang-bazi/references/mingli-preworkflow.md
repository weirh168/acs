---
name: mingli-preworkflow
category: mingli
description: 命理预测预流程全景 — 数据层·引擎层·输出层·内容管线·安全保障·辅助模块。钉选备份，备恢复使用。
pinned: true
trigger:
  - 预流程
  - 系统全景
  - 恢复
  - 重建
  - 备份
---

# 🏯 命理预流程全景 · v3.0（钉选备份）

> 此技能为 mingli 命理智能体完整预流程的系统快照。用于恢复重建、排查断点、重新搭建时参考。

---

## 一、数据层（输入）

### 案例库
```
路径: /home/h/.hermes/scripts/case_index.json
总量: 10,843条真实命例（非AI虚构）
来源: 古籍/论坛/民国/港台/公众人物/帝王名人 9类
去重: MD5哈希锁，零重复
```

### 知识库
```
/mnt/e/课程/命理知识库/ — 48篇（含福运法则）
├── 02_八字命理/理论精读/         — 子平派8篇（~31K字）
├── 02_八字命理/理论精读2_盲派/   — 盲派6篇（~25K字）
└── 福运命理法则.md
知识库另有:
├── /mnt/e/课程/福运堂知识库/02_八字命理/（修正闭环+历代命例库+BlindSchool）
├── /mnt/e/姓名/（周姓名学+全息姓名学）
└── /mnt/e/课程/知识库/05_图片素材/
```

### 注册命例
```
路径: /home/h/.hermes/scripts/birth_registry.json
总量: 4人
  韦荣浩  = 用户本人（广西/酸菜生意）1976-06-21辰时，5岁起运，身弱不从，喜水木
  韦鉴霖  = 2017-06-25亥时，财多身弱
  梁秀玉  = 丙辰 辛卯 庚午 丁亥
  韦浚森  = 乙酉 丙戌 甲戌 乙亥
```

---

## 二、引擎层（分析）

### 核心引擎
```
路径: /home/h/.hermes/scripts/engine.py
体积: 190KB / 84个函数
权限: 444（只读锁定）
```

### 6维评分体系
```
格局 45% | 调候 25% | 清纯 20% | 流通 10% | 胎元 5%
等级: 上品≥4.0 / 中上品≥3.3 / 中品≥2.8 / 中下品≥2.3 / 下品
准确率: 87.2%（经3轮调优 + 10,843条正反推验证）
```

### 双派交叉验证（盲派 × 子平）
```
子平 → 六维评分 + 用神 + 大运流年
盲派 → sushi_zuogong（做功类型：比劫制财/食伤生财/食伤制杀/化杀生印/财官双美/做功不明显）
      + sushi_jialiwai（家里家外：自己做/打工型/混合型/无明确财官）
      + 天干五合 + 墓库检查
矛盾率: 仅6% → 输出标注 ⚠️/ℹ️ 差异备注
```

### 特殊格局
```
从格/假从/魁罡+0.3/天元一气+0.4/专旺+0.3
从格判定: 弱根+月令极旺→假从格
身弱判定: 藏干根+比劫≥1→中/偏弱
官杀混杂: 有印时不扣分（"带杀为权"）
```

### 调候参考
```
引用《穷通宝鉴》按月查五行优先级
夏生先看水、冬生先看火
```

### 回归测试
```
路径: /home/h/.hermes/scripts/regression_test.py
锚点: 27个
频率: 每日08:00 cron → run_regression_test.sh
状态: 27/27 ✅ 全部通过
```

---

## 三、输出层（格式）

### 钉选技能（3个主技能 + 1个辅助）

| 技能 | 钉选 | 作用 |
|:----|:----:|:-----|
| mingli-think-framework | ✅ | 五大思维模型（整体辩证·取象比类·五行生克·格局用神·岁运流转） |
| mingli-life-narrative | ✅ | 一生分析叙事模板（排盘→格局→七运→关键领域→收尾） |
| mingli-output-format | ✅ | 输出格式公约（pro脑袋flash嘴·文学化叙事·禁用加粗/表格） |
| i-have-adhd | ❌ | 按需激活的技术操作模式（不用于命理分析） |

### 输出模板

**简析（性格/婚姻/感情）：**
```
排盘 → 分点解读 → 一句话总结
格式: 引用>收束每小点，序号❶❷❸❹❺，禁用加粗/表格
```

**一生详批：**
```
排盘盒（代码块）→ 五行格局总览（力量表）→ 八运拆解
每运: 十神组合 → 核心事件 → 性格表现 → 实证反推（>引用）
关键领域: 婚姻❤️ 事业💼 健康🏥
一句话收尾（有画面·有共情·不煽情）
```

### 写作守则
```
- 推理用 pro 深度（午亥暗合/三辰自刑/巳亥冲—一步不跳）
- 输出用 flash 式文学化叙事（不列公式、不翻术语、用人话讲故事）
- 口语化但不油滑，像老师在跟学生讲
- 禁止 ❌ 免责声明/模棱两可/"可能""也许"
- 风格: 运道堂风格
```

---

## 四、内容生产管线（cron）

### 每日流水线（mingli profile）

| 时间 | 产出 | 脚本/命令 |
|:----|:-----|:----------|
| 07:00 | 案例采集·古籍典籍 | collector_v2.py |
| 08:00 | 命理文章收集 | mingli-wechat-collect.sh |
| 08:00 | 预测回测·逾期检查 | prediction_reminder.py |
| 08:00 | 大运回归测试 | run_regression_test.sh |
| 08:00 | 每日状态汇总 | daily_status.py |
| 08:30 | 安全巡检 | upgrade_safety.py --check |
| 09:00 | 案例采集·特殊命格1 | batch_case_special_1.sh |
| 09:30 | **国学内容日更** | guoxue_content.py |
| 10:00 | 案例采集·普通百姓1 | batch_case_normal_1.sh |
| 10:30 | 案例采集·公众反馈 | collector_v2.py |
| 12:00 | **命理朋友圈每日案例** | mingli-social-poster.py |
| 14:00 | **命理短视频日更** | mingli-video-cron.py |
| 14:00 | 案例采集·企业家2 | batch_case_enterprise_2.sh |
| 14:10 | **命理视频自动发布** | mingli-video-publish.py |
| 15:00 | 案例采集·文体明星2 | batch_case_celebrity_2.sh |
| 16:00 | 案例采集·港澳台海外2 | batch_case_hkmo_2.sh |
| 16:00 | 命理内容生成（一三五） | mingli-article-production |
| 17:00 | 案例采集·特殊命格2 | batch_case_special_2.sh |
| 17:00 | 命理案例采集·补充轮 | collector_v2.py |
| 18:00 | 案例采集·普通百姓2 | batch_case_normal_2.sh |
| 19:00 | **命理知识日报** | LLM prompt |
| */10 | clawbot-watchdog | clawbot-launcher.sh |
| */2h | 高频巡检 | watchdog_hourly.py |
| */3h | 知识库变更监控 | kb_watch.py |

### 输出路径
```
E:\课程\每日内容\{date}/
├── 国学日更_{topic}.md  + .docx
├── 命理视频_{title}.mp4
└── 朋友圈案例_{name}.txt
```

---

## 五、安全与保障层

### 安全巡检（3层）

| 机制 | cron | 脚本 |
|:----|:-----|:-----|
| config-guard | 每30分钟 | config-guard.py |
| key_guard | 每30分钟 | key_guard.py check |
| 升级防护 | 每小时 | post-upgrade-guard.py |
| 高频巡检 | 每2小时 | watchdog_hourly.py |

### 审批配置（已固化）
```
mode: off, cron_mode: off, subagent_auto_approve: true
config.yaml 双配置 + 444权限锁定
```

### 关键文件权限
```
engine.py, config.yaml, .env → 444
所有钉选技能 → 不可删除不可降级
```

---

## 六、辅助模块

| 模块 | 用途 |
|:-----|:------|
| **bazi.py** | 八字排盘（真太阳时+藏干+纳音+胎元+命宫） |
| **xingming_analyze.py** | 姓名学分析（全息五格+周易卦象+外格对拆+天干盈虚） |
| **mingli-title-factory.py** | 标题工厂（8大公式） |
| **mingli-social-poster.py** | 朋友圈案例（案例卡片+互动钩子） |
| **mingli-video-publish.py** | Playwright自动发布到视频号+抖音 |
| **mingli-theory-collect.py** | 子平派古籍精读采集 |
| **mingli-mangpai-collect.py** | 盲派/素水理论采集 |
| **mingli-cross-validate-v2.py** | 盲派×子平交叉验证数据统计 |
| **mingli-deep-analyze.py** | 六维区分度/十神组合排行/冲刑合影响分析 |
| **collector_v2.py** | DeepSeek API真实命例采集 |
| **case_pipeline.py** | 案例索引扫描→合并→备份 |
| **batch_verify.py** | 引擎批量验证 |
| **guoxue_content.py** | 国学命理日更文章（含SEO关键词） |
| **i-have-adhd**（外装） | 按需激活技术操作/排错模式 |

---

## 七、API密钥体系

| API | 用途 |
|:----|:------|
| DeepSeek（gateway） | 主模型 + 案例采集 |
| DashScope | Vision校验（qwen-vl-plus） |
| Agnes | AI生图（agnes-image-2.1-flash） |
| 通义万相 | 生图备用（wan2.7-image） |

### 密钥保护
```
唯一源: .hermes/.env（444锁）
巡检: 每30分钟双脚本守护
```

---

## 八、恢复重建速查

### 钉选技能恢复
```bash
hermes skills pin mingli/mingli-think-framework
hermes skills pin mingli/mingli-life-narrative
hermes skills pin mingli/mingli-output-format
hermes skills pin mingli/mingli-preworkflow
```

### 审批配置恢复
```yaml
approvals:
  mode: off
  cron_mode: off
subagent_auto_approve: true
```

### 关键路径
```
脚本目录:     /home/h/.hermes/scripts/
案例索引:     /home/h/.hermes/scripts/case_index.json
注册命例:     /home/h/.hermes/scripts/birth_registry.json
知识库:       /mnt/e/课程/命理知识库/
内容输出:     /mnt/e/课程/每日内容/{date}/
视频输出:     /mnt/e/课程/视频输出/{date}/
备份:         /home/h/.hermes/backups/
```

---

> 最后更新: 2026-07-22 · 此技能为mingli系统预流程的完整快照，供恢复重建时参考。
