---
name: bazi-pai-pan
category: mingli
description: 八字排盘+大运起运 — 立春法节气排盘 + 真太阳时校正 + 精确大运计算（秒级精度/时柱时辰/农历注册表）
trigger:
  - 排盘
  - 大运
  - 起运
  - 八字计算
  - 节气
  - 立春法
  - 排盘截图
  - 看图排盘
pinned: true
---

# bazi-pai-pan · 八字排盘与大运起运

> 核心链路：农历/公历 → bazi.py(bazi_from_solar/bazi_from_lunar/calc_dayun) → 精确大运

## 基准验证（8锚点）

| 姓名 | 农历 | 性别 | 八字 | 起运 |
|------|------|:--:|------|------|
| 韦荣浩 | 1976-5-24 辰 | 男 | 丙辰 甲午 甲辰 戊辰 | 5岁2月 |
| 陈琴微 | 1979-6-4 亥 | 女 | 己未 庚午 乙丑 丁亥 | 3岁4月 |
| 朱素敏 | 1979-6-4 巳 | 女 | 己未 庚午 乙丑 辛巳 | 3岁4月 |
| 覃树优 | 1975-1-11 未 | 男 | 甲寅 丁丑 丁巳 丁未 | 7岁9月 |

每次排盘前随机抽1个基准验证，八字不匹配立即停止。

### 1. 排盘

```python
from bazi import bazi_from_solar, bazi_from_lunar

# 公历→八字（支持真太阳时）
r = bazi_from_solar(1976, 6, 21, 8, 0)
# 实测返回 6 项：('丙辰','甲午','甲辰','戊辰',('辰',8,0),<Lunar obj>)
yg, mg, dg, sg = r[0], r[1], r[2], r[3]
shichen = r[4]   # 第5项是 (时辰,时,分) 元组，不是时辰字符串

# 农历→八字
r = bazi_from_lunar(1976, 5, 24, 8, 0)   # 比公历多一个 solar 项，先 print(repr(r)) 看清再解包
yg, mg, dg, sg = r[0], r[1], r[2], r[3]

# 真太阳时（传入城市经度）
from bazi import get_shichen
shichen, h, m = get_shichen(8, 0, lon=113.3)  # 广州经度
```

### 2. 大运计算

```python
from bazi import calc_dayun

# 阳男↑顺排 / 阴男↓逆排
dy = calc_dayun(1976, 6, 21, 8, 0, is_male=True)
# → 起运: 5岁2个月, 顺逆: 顺排
# → 大运: [(乙,未,5,14), (丙,申,15,24), ...]

print(f"起运: {dy['起运']}")
print(f"顺逆: {dy['顺逆']}")
for g,z,s,e in dy['大运']:
    print(f"  {g}{z}: {s}-{e}岁")
```

### 3. 整合分析（引擎版）

```python
from engine import analyze

ra = analyze("丙辰 甲午 甲辰 戊辰", age=50, 
             birth_lunar=(1976,5,24), gender="male")
# 自动包含大运、起运、年龄推算
```

## 输出固定格式（必遵守）

每次命理分析，**排盘必须列在最前面**，然后才展开叙事分析。

### 排盘模块（前置、不可跳过）

```
┌─────────────────────────────────────────────┐
│  乾造/坤造: 甲辰 甲午 甲辰 戊辰              │
│  纳音:     沙中土 沙中金 佛灯火 大林木       │
│  胎元:    乙酉 (泉中水)                     │
│  命宫:    乙未 (沙中金)                     │
│  身宫:    己巳 (平地木)                     │
│  起运:    5岁 (约5年4个月后上运)            │
│  当前大运: 己亥 (46-55岁)                   │
│  交运:    每逢辛年寒露后第17日              │
└─────────────────────────────────────────────┘
```

紧接排盘后，再展开叙事分析（三套模板择一）。

## 关键逻辑

### 顺逆规则
| 年干 | 性别 | 排法 |
|:--:|:--:|:--:|
| 阳(甲丙戊庚壬) | 男 | **顺排** |
| 阴(乙丁己辛癸) | 女 | **顺排** |
| 阳 | 女 | 逆排 |
| 阴 | 男 | 逆排 |

### 起运公式
```
出生到下一个节的天数 ÷ 3 = 起运岁数
余1天 → +4个月
精确到秒（total_seconds() / 86400.0）
找不到节时默认 10岁
```

### 节气列表
立春、惊蛰、清明、立夏、芒种、小暑
立秋、白露、寒露、立冬、大雪、小寒

## 出生日期注册表

八字→农历生日自动匹配，无需每次传入：

```
/home/h/.hermes/scripts/birth_registry.json
```

格式：
```json
{
  "丙辰 甲午 甲辰 戊辰": {
    "name": "韦荣浩",
    "birth_lunar": [1976, 5, 24],
    "gender": "male",
    "solar": "1976-06-21",
    "起运": 5
  }
}
```

## Windows 运行须知（MSYS/Windows 主机必读）

- 本机用 `python` 不是 `python3`。
- `bazi.py` 依赖 `lunar_python`，缺失时 `python -m pip install lunar_python`。
- 控制台默认 GBK 会让中文乱码 → 调用时加 `PYTHONIOENCODING=utf-8`（导入已加 `encoding="utf-8"` 修复，不加也不会崩）。
- 起运计算 `calc_dayun` 要传 **公历** 年月日时分；农历输入先取 `bazi_from_lunar(...)[5].toYmd()`。

## 锚点回归测试

每日 08:00 自动运行，16个锚点全部通过则静默：

```bash
python3 /home/h/.hermes/scripts/regression_test.py
```

## 数据文件

| 文件 | 路径 | 说明 |
|:--|:--|:--|
| 排盘引擎 | `/home/h/.hermes/scripts/bazi.py` | 8函数，立春法+真太阳时 |
| 引擎集成 | `/home/h/.hermes/scripts/engine.py` | infer_age_and_dayun() |
| 注册表 | `/home/h/.hermes/scripts/birth_registry.json` | 八字→农历生日 |
| 回归测试 | `/home/h/.hermes/scripts/regression_test.py` | 16锚点每日验证 |

## Windows 运行环境（本机）

`bazi.py` / `engine.py` 依赖 `lunar_python`，Hermes 自带的那几个运行时里都没有。排盘前先把环境备好：

```bash
cd "$HERMES_HOME/cache/scratch"
uv venv bazi-venv --python 3.14
uv pip install --python bazi-venv/Scripts/python.exe lunar-python
PYTHONUTF8=1 bazi-venv/Scripts/python.exe your_script.py
```

三条硬规则：

1. **必须带 `PYTHONUTF8=1`。** `bazi.py` 用默认编码 `open()` 读 `cities.json`（内容是 UTF-8），Windows 默认 GBK → `UnicodeDecodeError: 'gbk' codec can't decode byte 0xad`。不是数据坏了，是解释器编码没设。
2. **结果写 UTF-8 文件再 read_file 读回，不要直接 print。** 终端是 GBK，中文全成乱码，等于没验证。
3. **脚本路径用 `$HERMES_HOME/scripts/`**（当前 profile 的 scripts 目录），本文档别处出现的 `/home/h/.hermes/scripts/` 是旧 WSL 路径，在本机不存在。

## 引擎调用坑

- `analyze(bazi, age=N)` 返回的 dict 极大（含逐月应期，几千字）。先写文件，再只读需要的那几段，别整坨塞上下文。
- `marriage_analyze(bazi_str, gender='female')` **默认 female**。乾命必须显式 `gender='male'`；但返回的键名照样写「夫宫」，别被字面误导成女命。
- `education_eval` 同时给出「拦截」和「评估」时，**以拦截为准**（如 印被穿破 → 评高学历也要降级）。
- 大运年龄：`calc_dayun` 给**周岁**区间，排盘软件图上通常标**虚岁**（虚岁 = 周岁 + 1）。差 1 岁是正常的，不是排错，别去改引擎。
- **`analyze()` 里的「年龄推算」不准，不要拿来写报告。** 它按固定 2 岁起运推区间（如甲申 2-11、辛巳 32-41），而 `calc_dayun` 按真实起运算（如 5岁2个月 → 甲申 5-14、辛巳 35-44）。差 2-3 岁会直接影响「现在在哪步运」的判断。一律以 `calc_dayun` 为准，或直接采信排盘软件图上的虚岁。
- 必须传大运干支才能跑的：`dayun_3year(bazi, gan, zhi)`、`cai_dayun_effect(bazi, gan, zhi)`、`dayun_impact_score(bazi, gan, zhi)`。只传八字会 `TypeError: missing 2 required positional arguments`。
- `shensha_predictive(bazi)` 对部分命局会返回**空 dict**，那是引擎没覆盖，**不等于没有神煞**。神煞要按排盘软件图上标的或经典规则逐颗人工核，分析里不能整段缺。
- `cai_verify_liunian(bazi_str, year)`、`health_flow_year(bazi_str, year)` 都必须给 year。这两个是「某年有没有财 / 身体留意什么」最快的入口。

## 近期流年（「前五年 / 后五年事业怎么样」）

客户问「这五年事业」时，不要凭印象发挥，按这条链跑完再写：

```python
dayun_3year(bazi, "辛", "巳")     # 盖头/截脚 + 三年分断 + 整体评价
dayun_impact_score(bazi, "辛", "巳")  # 负分 = 这步运整体偏阻
dayun_qiehuan(bazi, age=41)        # 交运关口（换运前后一两年最动荡）
for y in years:
    cai_verify_liunian(bazi, y)    # 十神 + 财星结论：双吉强实发 / 不主财运 / 过手财神
    health_flow_year(bazi, y)      # 该年身体应期
```

读法与落笔：

1. **先定这步运的底色。** `dayun_3year` 的「三年分断」直接决定窗口：前3-4年天干有根能发力、中3年过渡、后3年截脚最卡。截脚（地支克天干）＝ 想做的事被下面的现实条件拖着，**这时的建议是坐实底子而不是扩张**。
2. **财星结论要分开讲。** 「强实发」是唯一可以叫客户主动去谈钱、签约、收欠款的一年；「不主财运 / 过手财神」＝ 钱经手但留不住，明确劝其别担保、别借贷扩张。
3. **刑冲合自己看，引擎不代劳。** 伏吟（流年干支叠大运或叠原局）＝ 原地打转；冲（卯酉、丑未）＝ 变位置，不是变行当；三合被流年引动（巳酉丑、寅午）＝ 成局，压力或机会一起到；自刑 ＝ 内耗、情绪与血压先出问题。
4. **输出定式**：结论一句（这几年是发力还是守）→ 逐年 3-5 行，每行写「该做什么 / 忌什么 / 留意什么」→ 收尾一句「该抓的是 X 年，该守的是 Y 年，该等的是 Z 年」。
5. **回头看的年份要留验证口。** 讲过去的流年时，末尾问一句「哪一年对得上」，客户确认或否认都要记录（log_prediction + submit_feedback），真实反馈优先于推演。
6. 合规：不写「一定/必然」，写「偏高 / 容易 / 宜 / 忌」。

## 参考

- 用户直接发排盘截图或手写八字时：先按本文件口径逐项核对（年柱看立春、日柱查万年历、时柱用五鼠遁），确认无误再分析。
