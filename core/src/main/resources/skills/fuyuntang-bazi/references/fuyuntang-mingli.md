---
name: fuyuntang-mingli
description: 福运堂命理专用知识库 — 八字分析、日课择吉、姓名学完整知识体系
triggers:
  - 排盘
  - 八字
  - 大运
  - 流年
  - 十神
  - 择日
  - 起名
  - 命理
  - 运程
---

# 福运堂命理知识库

> 路径：`E:\课程\福运堂命理知识库\`（WSL: `/mnt/e/课程/福运堂命理知识库/`）

## 📂 结构

| 目录 | 内容 |
|------|------|
| `00_` 配置档案 | 输出格式公约、智能体配置 |
| `01_文案素材/` | 合规规则、去AI化铁律 |
| `02_八字命理/` `03_八字命理/` | 八字理论 |
| `04_择日日课/` | 日课择吉 |
| `05_姓名学/` | 起名改名（65文件） |
| `06_外部收集/` | 外部资料 |

## 🔑 必读文件

- `福运命理法则.md` — 25函数+9层法则+986命例
- `命理模型速查手册.md` — 日主五行、十神人格化、月令旺衰
- `00_输出格式公约.md` — 输出规范
- 文学叙事风格公约见 `本目录下的《00-输出格式公约.md》`（禁加粗、禁表格、排盘盒用代码块）
- `01_文案素材/八平台审核规则深度研究.md` — 合规444锁定
- `01_文案素材/去AI化写作铁律.md` — 去AI化444锁定

## ⚙️ 引擎函数（25个）

排盘：parse_bazi, get_shishen, bazi_from_solar, calc_dayun
强弱：is_shenwang, rate_mingju, is_cong_ge, check_qingzhuo
调候：check_tiaohou, gan_xiji, tian_gan_wuhe
财运：cai_tag, cai_dayun_effect, cai_verify_liunian, cai_check_muku
盲派：sushi_jialiwai, sushi_zuogong, gong_shen
应期：yingqi_refined, yingqi_analysis, dayun_3year, gaitou_jiejiao
辅助：koujue_18(24条口诀), find_similar(986命例)

## 📐 分析顺序

①死活→②强弱→③调候→④格局→⑤做功→⑥根基→⑦体用→⑧应期→⑨匹配

## 📝 输出规范

允许：```排盘盒、>引用、❶❷❸序号、🔸💰标注、叙事段落
禁止：**加粗**、__加粗__、|表格|、正文公式

## 🔒 合规

- 各平台禁用词不同，见审核规则
- 禁止确定性断言、恐吓引导
- 话术替换：八字→出生时间与性格，财运→事业方向

## 🛠 可用 Skills（7个）

| Skill | 用途 |
|-------|------|
| `bazi-pai-pan` | 八字排盘 |
| `mingli-think-framework` | 命理思维框架 |
| `mingli-preworkflow` | 命理分析工作流 |
| `mingli-life-narrative` | 人生叙事化输出 |
| `mingli-output-format` | 输出格式规范 |
| `config-guard` | 配置防窜改 |
| `fuyuntang-mingli` | 本知识库索引 |

## 🐍 核心脚本

| 脚本 | 用途 |
|------|------|
| `scripts/bazi.py` | 八字排盘引擎 |
| `scripts/backtest_engine.py` | 回测引擎 |
| `scripts/case_collector.py` | 案例采集 |
| `scripts/predict_record.py` | 预测记录 |

## 🎯 使用流程

1. 打开知识库 → `read_file /mnt/e/课程/福运堂命理知识库/`
2. 载入必读 → 法则 + 速查手册 + 格式公约
3. 加载 skill → `skill_view('bazi-pai-pan')`
4. 执行排盘 → `python3 scripts/bazi.py`
5. 叙事输出 → 遵循格式公约
6. 合规自查 → 审核规则 + 去AI化铁律