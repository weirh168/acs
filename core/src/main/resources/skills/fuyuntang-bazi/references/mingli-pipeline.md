---
name: mingli-pipeline
category: mingli
description: 命理分析18步总纲 — 完整预测流水线，含30个引擎函数映射与调用规则
trigger:
  - 八字分析
  - 命理预测
  - 排盘
  - 算八字
  - 看命
  - 批命
pinned: false
---

# 命理分析18步总纲

## 流水线概览

```
命理分析请求
  → 加载核心Skill（mingli-pipeline / sushi-faze / mangpai-jinghua / guji-jinghua / fuyuntang-mingli）（mingli-pipeline / mangpai-duanming / bazi-analysis-format / mingli-rules / sushi-faze / mingli-marketing-system / bazi-analysis-template）
  → bazi.py 排盘
  → 素水/盲派优先 → 子平辅助 → 交叉验证（engine.py 114函数）
  → 11,524例库对照（case_index.json）
  → 四层叙事结构输出断语
```

## 18步流程 + 引擎函数映射

### 第一阶段：排盘定局（步骤1-3）

| 步骤 | 操作 | 引擎函数 | 说明 |
|:--:|------|----------|------|
| 1 | 真太阳时校正 | bazi.py `get_shichen()` | 城市经度±4分钟/度 |
| 2 | 八字排盘 | bazi.py `bazi_from_solar()` / `bazi_from_lunar()` | 年柱→月柱→日柱→时柱 |
| 3 | 纳音五行 | `nayan(gz)` | 每组干支纳音 |

### 第二阶段：十神与格局（步骤4-6）

| 步骤 | 操作 | 引擎函数 | 说明 |
|:--:|------|----------|------|
| 4 | 十神标注 | `get_shishen(day_master, gan)` | 天干+地支藏干十神 |
| 5 | 日主强弱 | `is_shenwang(bazi_str)` | 得令/得地/得势判定 |
| 6 | 格局定取 | `rate_mingju(bazi_str)` + `check_qingzhuo()` | 六维评分+清浊鉴定 |

### 第三阶段：从格与调候（步骤7-9）

| 步骤 | 操作 | 引擎函数 | 说明 |
|:--:|------|----------|------|
| 7 | 从格检测 | `is_cong_ge(bazi_str)` | 从强/从弱/假从判定 |
| 8 | 调候检查 | `check_tiaohou(bazi_str)` | 寒暖燥湿补正 |
| 9 | 日主喜忌 | `gan_xiji(dm)` | 十干喜忌口诀 |

### 第四阶段：原局分析（步骤10-12）

| 步骤 | 操作 | 引擎函数 | 说明 |
|:--:|------|----------|------|
| 10 | 财官分析 | `cai_tag(bazi_str)` + `cai_check_muku()` | 财星/官星状态与墓库 |
| 11 | 宫位神煞 | `gong_shen(bazi_str)` | 四柱宫位神煞 |
| 12 | 干支五合 | `tian_gan_wuhe(bazi_str)` | 天干合化分析 |

### 第五阶段：大运流年（步骤13-16）

| 步骤 | 操作 | 引擎函数 | 说明 |
|:--:|------|----------|------|
| 13 | 大运排盘 | bazi.py `calc_dayun()` | 顺逆排定，起运年龄 |
| 14 | 大运断事 | `cai_dayun_effect()` + `gaitou_jiejiao()` | 盖头截脚判断 |
| 15 | 流年应期 | `yingqi_analysis()` + `yingqi_refined()` | 合冲刑害应期 |
| 16 | 三年断 | `dayun_3year(bazi_str, dy_gan, dy_zhi)` | 大运天干5年+地支5年分段 |

### 第六阶段：多维验证（步骤17-18）

| 步骤 | 操作 | 引擎函数 | 说明 |
|:--:|------|----------|------|
| 17 | 案例匹配 | `find_similar(bazi_str, top_n=3)` | 1281例库相似命例检索 |
| 18 | 盲派验证 | `sushi_jialiwai()` + `sushi_zuogong()` | 家里家外+做功路线 |

## 函数调用顺序规则

```python
# 标准分析调用链
from engine import *
from bazi import *

# 步骤1-3: 排盘
yg, mg, dg, sg, sc, l = bazi_from_solar(year, month, day, hour, minute)
bazi_str = f"{yg} {mg} {dg} {sg}"

# 步骤4-6: 十神格局
for pillar in parse_bazi(bazi_str):
    get_shishen(dg[0], pillar[0])  # 十神
is_shenwang(bazi_str)               # 强弱
rate_mingju(bazi_str)               # 六维评分

# 步骤7-9: 从格调候
is_cong_ge(bazi_str)
check_tiaohou(bazi_str)
gan_xiji(dg[0])

# 步骤10-12: 原局
cai_tag(bazi_str)
gong_shen(bazi_str)
tian_gan_wuhe(bazi_str)

# 步骤13-16: 大运流年
dy = calc_dayun(year, month, day, hour, minute, is_male)
yingqi_analysis(bazi_str)
yingqi_refined(bazi_str, year)

# 步骤17-18: 验证
find_similar(bazi_str, top_n=3)
sushi_zuogong(bazi_str)
```

## 触发条件

当用户发送以下内容时，自动触发18步流程：
→ 三套叙事结构输出断语（一生/婚姻/性格）

```

## 输出结构（唯一格式）

最终输出**必须严格按 bazi-analysis-format 中的三套模板之一**输出：

| 分析类型 | 模板 | 叙事链 |
|---------|------|--------|
| 一生分析 | 模板A | 定调 → 三层结构 → 人群位置 → 未来走向 |
| 婚姻分析 | 模板B | 正妻定位 → 感情模式 → 她承受的消耗 → 未来走向 |
| 性格分析 | 模板C | 定调 → 三层结构 → 人群位置 → 优缺点 → 后来变化 |

使用四层叙事结构模板（v4.4）：一生/婚姻/性格各四层
