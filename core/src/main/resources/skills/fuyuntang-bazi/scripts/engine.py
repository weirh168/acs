#!/usr/bin/env python3
"""命理分析引擎 — 格局评分 + 案例匹配 + 多维验证 + 预测回测"""
import json, re, os, sys
from pathlib import Path
from lunar_python import Solar, Lunar

# ===== 预测回测系统 =====
PREDICT_PATH = os.path.join(os.path.dirname(__file__), "predict_record.py")
sys.path.insert(0, os.path.dirname(__file__))
try:
    from predict_record import add_prediction, verify_prediction, get_stats, get_overdue
    PREDICT_AVAILABLE = True
except Exception:
    PREDICT_AVAILABLE = False

# ===== 加载外部资源 =====
BASE = os.path.dirname(__file__)
SHISHEN_TABLE = {}
SS_PATH = os.path.join(BASE, "shishen.json")
if os.path.exists(SS_PATH):
    with open(SS_PATH, encoding="utf-8") as f:
        SHISHEN_TABLE = json.load(f)

CITIES_PATH = os.path.join(BASE, "cities.json")
CITY_LON = {}
if os.path.exists(CITIES_PATH):
    with open(CITIES_PATH, encoding="utf-8") as f:
        CITY_LON = json.load(f)

CASE_PATH = os.path.join(BASE, "case_index.json")
CASE_DB = []
if os.path.exists(CASE_PATH):
    with open(CASE_PATH, encoding="utf-8") as f:
        CASE_DB = json.load(f)

REVIEW_PATH = os.path.join(BASE, "review_log.json")
REVIEW_LOG = []
if os.path.exists(REVIEW_PATH):
    with open(REVIEW_PATH, encoding="utf-8") as f:
        REVIEW_LOG = json.load(f)

# 婚姻参数v2
MARRIAGE_PARAMS_PATH = os.path.join(BASE, "marriage_params_v2.json")
MARRIAGE_PARAMS = {}
if os.path.exists(MARRIAGE_PARAMS_PATH):
    with open(MARRIAGE_PARAMS_PATH, encoding="utf-8") as f:
        MARRIAGE_PARAMS = json.load(f)

# ===== 一、原局清浊评分（六维） =====
YANG = {"甲","丙","戊","庚","壬"}
YIN = {"乙","丁","己","辛","癸"}
GAN_WX = {"甲":"木","乙":"木","丙":"火","丁":"火","戊":"土","己":"土","庚":"金","辛":"金","壬":"水","癸":"水"}
ZHI_WX = {"子":"水","丑":"土","寅":"木","卯":"木","辰":"土","巳":"火","午":"火","未":"土","申":"金","酉":"金","戌":"土","亥":"水"}
SHENG = {"木":"火","火":"土","土":"金","金":"水","水":"木"}

# 十天干/十二地支顺序（胎元/大运推算）
GAN_ORDER = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
ZHI_ORDER = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]

def gan_step(gan, n):
    """天干顺推n位"""
    return GAN_ORDER[(GAN_ORDER.index(gan) + n) % 10]

def zhi_step(zhi, n):
    """地支顺推n位"""
    return ZHI_ORDER[(ZHI_ORDER.index(zhi) + n) % 12]

def calc_taiyuan(month_gan, month_zhi):
    """胎元 = 月干+1, 月支+3"""
    return f"{gan_step(month_gan, 1)}{zhi_step(month_zhi, 3)}"

def rate_taiyuan(taiyuan_gz, bazi_str):
    """胎元评分：生扶喜用神→4分，生扶忌神→2分，中性→3分"""
    try:
        xy = calc_xiyong(bazi_str)
        xs = set(xy.get("喜神", []) + xy.get("用神", []))
        js = set(xy.get("忌神", []))
        tw = GAN_WX[taiyuan_gz[0]]
        if not xs: return 3
        if tw in xs: return 4
        if tw in js: return 2
        return 3
    except: return 3

def dayun_impact_score(bazi_str, dayun_gan="", dayun_zhi=""):
    """大运影响因子：-0.5~+0.5"""
    if not dayun_gan or not dayun_zhi: return 0
    try:
        xy = calc_xiyong(bazi_str)
        xs = set(xy.get("喜神", []) + xy.get("用神", []))
        js = set(xy.get("忌神", []))
        if not xs and not js: return 0
        zwx = {"子":"水","丑":"土","寅":"木","卯":"木","辰":"土","巳":"火",
               "午":"火","未":"土","申":"金","酉":"金","戌":"土","亥":"水"}
        imp = 0
        gw = GAN_WX[dayun_gan]; zw = zwx[dayun_zhi]
        if gw in xs: imp += 0.2
        elif gw in js: imp -= 0.2
        if zw in xs: imp += 0.15
        elif zw in js: imp -= 0.15
        b = parse_bazi(bazi_str)
        if b:
            ch = {("子","午"),("卯","酉"),("寅","申"),("巳","亥"),("辰","戌"),("丑","未")}
            for z in [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]:
                if (dayun_zhi,z) in ch or (z,dayun_zhi) in ch:
                    imp -= 0.15; break
        return round(max(-0.5, min(0.5, imp)), 2)
    except: return 0

def get_shishen(day_master, gan):
    """获取十神（正偏全）"""
    dm_wx = GAN_WX[day_master]
    g_wx = GAN_WX[gan]
    dm_yang = day_master in YANG
    
    # 同我
    if dm_wx == g_wx:
        return "比肩" if dm_yang == (gan in YANG) else "劫财"
    # 生我
    if {"木":"水","火":"木","土":"火","金":"土","水":"金"}[dm_wx] == g_wx:
        return "正印" if dm_yang != (gan in YANG) else "偏印"
    # 我生
    if SHENG[dm_wx] == g_wx:
        return "伤官" if dm_yang != (gan in YANG) else "食神"
    # 克我
    if {"木":"金","火":"水","土":"木","金":"火","水":"土"}[dm_wx] == g_wx:
        return "正官" if dm_yang != (gan in YANG) else "七杀"
    # 我克
    if {"木":"土","火":"金","土":"水","金":"木","水":"火"}[dm_wx] == g_wx:
        return "正财" if dm_yang != (gan in YANG) else "偏财"
    return "?"

def parse_bazi(bazi_str):
    """将八字字符串转为结构化数据"""
    if not bazi_str or not isinstance(bazi_str, str):
        return None
    parts = bazi_str.strip().split()
    if len(parts) != 4:
        return None
    for p in parts:
        if len(p) != 2:
            return None
    return {
        "year": parts[0], "month": parts[1], "day": parts[2], "hour": parts[3],
        "year_gan": parts[0][0], "month_gan": parts[1][0], "day_gan": parts[2][0], "hour_gan": parts[3][0],
        "year_zhi": parts[0][1], "month_zhi": parts[1][1], "day_zhi": parts[2][1], "hour_zhi": parts[3][1],
        "天干": [parts[0][0], parts[1][0], parts[2][0], parts[3][0]],
        "地支": [parts[0][1], parts[1][1], parts[2][1], parts[3][1]],
    }

def is_cong_ge(bazi_str):
    """检测是否为从格/化格/专旺格
    返回: {"从格": True/False, "类型": "从X格"/"专X格"/"非从格", "原因": "..."}
    """
    b = parse_bazi(bazi_str)
    if not b:
        return {"从格": False, "类型": "非从格", "原因": "排盘失败"}
    dm = b["day_gan"]
    dm_wx = GAN_WX[dm]
    gans = [b["year_gan"], b["month_gan"], b["hour_gan"]]
    zhis = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
    
    # 过滤无效干支（如"时缺"）
    gans = [g for g in gans if g in GAN_WX]
    zhis = [z for z in zhis if z in ZHI_WX]
    if len(gans) < 2 or len(zhis) < 3:
        return {"从格": False, "类型": "非从格", "原因": "干支数据不全"}
    
    zhi_canggan = {
        "子":"癸", "丑":"己癸辛", "寅":"甲丙戊", "卯":"乙",
        "辰":"戊乙癸", "巳":"丙庚戊", "午":"丁己", "未":"己丁乙",
        "申":"庚壬戊", "酉":"辛", "戌":"戊辛丁", "亥":"壬甲"
    }
    # 检查地支中是否藏有日主的同类五行
    has_root = False
    for z in zhis:
        cangs = zhi_canggan.get(z, "")
        for cg in cangs:
            if GAN_WX.get(cg) == dm_wx:
                has_root = True
                break
    
    # 天干同类占比
    same_count = sum(1 for g in gans if GAN_WX[g] == dm_wx)
    # 地支同类占比
    zhi_same = sum(1 for z in zhis if ZHI_WX[z] == dm_wx)
    
    # 从格判断：日主同类≤1且月令非同类
    if same_count <= 1 and zhi_same <= 1:
        month_wx = ZHI_WX[b["month_zhi"]]
        month_strong = sum(1 for z in zhis if ZHI_WX[z] == month_wx) >= 2
        month_strong_same = sum(1 for g in gans if GAN_WX[g] == month_wx) >= 2
        if (month_strong or month_strong_same):
            if not has_root:
                return {"从格": True, "类型": f"从{month_wx}格", "原因": f"月令{month_wx}强旺，日主无根"}
            # 有弱根但月令极旺，仍判从格（假从）
            if month_strong and month_strong_same:
                return {"从格": True, "类型": f"假从{month_wx}格", "原因": f"月令{month_wx}极旺，虽有微根仍从"}

    # 专旺格：日主同类≥3
    if same_count >= 3 and zhi_same >= 3:
        return {"从格": True, "类型": f"专{dm_wx}格", "原因": f"满盘{dm_wx}，一气专旺"}
    
    # 天元一气专旺格：四柱天干相同 + 印比一片 → 视为从格（优先于has_root检查）
    all_gans_v2 = [b["year_gan"], b["month_gan"], b["day_gan"], b["hour_gan"]]
    if len(set(all_gans_v2)) == 1 and all_gans_v2[0] == dm:
        WX_SHENG_MAP2 = {'木':'水','火':'木','土':'火','金':'土','水':'金'}
        dm_wx_v2 = GAN_WX.get(dm, dm)
        zhis_v2 = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
        ty_yin2 = any(ZHI_WX.get(z,'') == WX_SHENG_MAP2.get(dm_wx_v2,'') for z in zhis_v2)
        ty_root2 = any(ZHI_WX[z] == dm_wx_v2 for z in zhis_v2)
        if ty_yin2 or ty_root2:
            return {"从格": True, "类型": f"专旺{dm_wx_v2}格", "原因": f"天元一气{'印星坐实' if ty_yin2 else '有根'}"}
    if has_root:
        return {"从格": False, "类型": "非从格", "原因": f"地支藏{dm_wx}根气，按正格论"}
    return {"从格": False, "类型": "非从格", "原因": f"日主同类{same_count}天干{zhi_same}地支，不足以从"}


def rate_mingju(bazi_str, age=None):
    """六维评分（增强版：先判从格，支持胎元实算+岁运调整）
    参数:
        bazi_str: 八字字符串
        age: 当前年龄（可选）。传入则计算大运影响因子
    """
    b = parse_bazi(bazi_str)
    if not b:
        return None
    
    # 先判从格 — 从格评分带区分度
    cong = is_cong_ge(bazi_str)
    if cong.get("从格", False):
        # 从格评分根据纯度
        sw = is_shenwang(bazi_str)
        root = sw.get("根类型", "")
        if "无根" in root:
            cong_score = 4.3
        elif "弱根" in root:
            cong_score = 3.8
        else:
            cong_score = 3.5
        # 从格也计算胎元
        ty_gz = calc_taiyuan(b["month_gan"], b["month_zhi"])
        return {"score": cong_score, "level": "上品（从格）",
                "details": [f"从格:纯度评分={cong_score}", f"胎元:{ty_gz}"],
                "dayun_adjust": 0}
    
    dm = b["day_gan"]
    dm_wx = GAN_WX[dm]
    sw = is_shenwang(bazi_str)
    score = 0
    details = []
    
    # 1. 格局成败 (35%)
    tian_gan = [b["year_gan"], b["month_gan"], b["hour_gan"]]
    di_zhi = [b["year_zhi"], b["month_zhi"], b["hour_zhi"]]
    has_guan = any(s in ["正官","七杀"] for s in [get_shishen(dm, g) for g in tian_gan])
    has_yin = any(s in ["正印","偏印"] for s in [get_shishen(dm, g) for g in tian_gan])
    has_shi = any(s in ["食神","伤官"] for s in [get_shishen(dm, g) for g in tian_gan])
    has_cai = any(s in ["正财","偏财"] for s in [get_shishen(dm, g) for g in tian_gan])
    
    pattern_score = 3  # 基础分
    if has_guan and has_yin: pattern_score += 2  # 官印相生
    if has_shi and has_cai: pattern_score += 1.5  # 食伤生财
    if has_guan and has_cai: pattern_score += 0.5  # 财官相生
    if tian_gan.count(dm) >= 2: pattern_score -= 0.5  # 比劫多（比劫多可带杀）
    # 身旺加分：身旺且不从格的命局，格局根基好
    qiangruo = sw.get("强弱", "")
    if "身旺" in qiangruo:
        pattern_score += 0.5
    # 官杀混杂扣分
    has_guan_s = any(s == "正官" for s in [get_shishen(dm, g) for g in tian_gan])
    has_sha_s = any(s == "七杀" for s in [get_shishen(dm, g) for g in tian_gan])
    if has_guan_s and has_sha_s:
        # 官杀混杂：无印则扣分，有印则带杀为权（朱元璋/蒋介石类）
        if not has_yin:
            pattern_score -= 1
    pattern_score = max(0, min(6, pattern_score))  # 范围0-6
    details.append(f"格局:{pattern_score}/6")
    score += pattern_score * 0.40  # 反推优化:v2.1 0.45→0.40
    
    # 2. 调候有力 (30%) — 反推优化:v2.1 25%→30%
    tiaohou_score = 3
    # 夏月(巳午未)见水为调候
    summer = b["month_zhi"] in "巳午未"
    winter = b["month_zhi"] in "亥子丑"
    # 不敏感日主：丙丁火（冬生才重要）、壬癸水（夏生才重要）
    insensitive = (dm in "丙丁" and not winter) or (dm in "壬癸" and not summer)
    if insensitive:
        tiaohou_score = 2  # 降低基础分
    all_zhis = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
    has_water = any(GAN_WX[g] == "水" for g in tian_gan) or any(ZHI_WX[z] == "水" for z in all_zhis)
    has_fire   = any(GAN_WX[g] == "火" for g in tian_gan) or any(ZHI_WX[z] == "火" for z in all_zhis)
    if summer and has_water: tiaohou_score += 2
    if winter and has_fire:   tiaohou_score += 2
    details.append(f"调候:{tiaohou_score}/5")
    score += tiaohou_score * 0.30  # 反推优化:v2.1 0.25→0.30
    
    # 3. 清纯无杂 (20%) — 精读修正：权重从10%→20%
    clean_score = 3
    ss_list = [get_shishen(dm, g) for g in tian_gan]
    if has_guan_s and has_sha_s: clean_score -= 1  # 官杀混杂
    if "食神" in ss_list and "伤官" in ss_list: clean_score -= 1  # 食伤混杂
    # 正官一位为清
    if ss_list.count("正官") == 1: clean_score += 0.5
    details.append(f"清纯:{clean_score}/5")
    score += clean_score * 0.20
    
    # 4. 流通有情 (10%) — 精读修正：权重从15%→10%
    flow_score = 3
    # 简单判断：看天干五行是否连续相生
    gans = [b["year_gan"], b["month_gan"], b["day_gan"], b["hour_gan"]]
    flow_count = 0
    for i in range(3):
        w1 = GAN_WX[gans[i]]
        w2 = GAN_WX[gans[i+1]]
        if SHENG.get(w1) == w2:
            flow_count += 1
    flow_score += flow_count * 0.5
    # 流通好：连续相生2次以上
    if flow_count >= 2:
        flow_score += 0.5
    details.append(f"流通:{flow_score:.1f}/5")
    score += flow_score * 0.10
    
    # 5. 胎元实算（5%权重）
    taiyuan_gz = calc_taiyuan(b["month_gan"], b["month_zhi"])
    taiyuan_score = rate_taiyuan(taiyuan_gz, bazi_str)
    details.append(f"胎元:{taiyuan_score}/5({taiyuan_gz})")
    score += taiyuan_score * 0.05  # 保留5%权重实算
    
    # 7. 特殊格局加分
    special_bonus = 0
    
    # 魁罡格
    ri_zhi = b["day_zhi"]
    ri_gan = b["day_gan"]
    kui_gang = (ri_gan == "庚" and ri_zhi in ("戌","辰")) or \
               (ri_gan == "壬" and ri_zhi == "辰") or \
               (ri_gan == "戊" and ri_zhi == "戌")
    if kui_gang:
        special_bonus += 0.3
        details.append("特殊格局:魁罡格+0.3")
    
    # 天元一气（四柱天干相同）— v3.1修正：地支配合 + 印星坐实
    all_gans = [b["year_gan"], b["month_gan"], b["day_gan"], b["hour_gan"]]
    if len(set(all_gans)) == 1 and all_gans[0] == dm:
        ty_root = any(ZHI_WX[z] == dm_wx for z in [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]])
        WX_SHENG_MAP = {'木':'水','火':'木','土':'火','金':'土','水':'金'}
        dm_wx_val = GAN_WX.get(dm, dm)
        ty_yin = any(ZHI_WX.get(z,'') == WX_SHENG_MAP.get(dm_wx_val,'') for z in [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]])
        if ty_root:
            special_bonus += 0.3
            details.append("特殊格局:天元一气(有根)+0.3")
        elif ty_yin:
            special_bonus += 1.0
            details.append("特殊格局:天元一气(印星坐实)+1.0")
        else:
            details.append("特殊格局:天元一气(无根)不加分")
    
    # 独象格（四柱同一五行）
    all_zhi = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
    all_wx = [GAN_WX[g] for g in all_gans] + [ZHI_WX[z] for z in all_zhi]
    most_common_wx = max(set(all_wx), key=all_wx.count)
    if all_wx.count(most_common_wx) >= 6:  # 8个中有6个以上同一五行
        special_bonus += 0.3
        details.append(f"特殊格局:专{most_common_wx}格+0.3")
    
    total = round(score + special_bonus, 1)
    
    # 清浊修正范围扩大：反推优化v2.1 2.5-4.0→2.3-4.3
    if 2.3 <= total < 4.3:
        qz = check_qingzhuo(bazi_str)
        if qz[0] == "浊": total -= 0.3
        elif qz[0] == "清": total += 0.2
        total = round(total, 1)
    
    if total >= 4.0: level = "上品"
    elif total >= 3.3: level = "中上品"
    elif total >= 2.8: level = "中品"
    elif total >= 2.3: level = "中下品"
    else: level = "下品"
    
    # 8. 岁运影响因子（可选，需传入age）
    dayun_adjust = 0
    if age is not None:
        try:
            dy = calc_dayun_from_bazi(bazi_str, age=age)
            if dy and dy.get("当前大运"):
                cur_dy = dy["当前大运"]
                if len(cur_dy) >= 2:
                    dayun_adjust = dayun_impact_score(bazi_str, cur_dy[0], cur_dy[1])
                    details.append(f"岁运:当前{cur_dy} 调整{dayun_adjust:+.2f}")
        except Exception:
            pass
    
    total = round(total + dayun_adjust, 1)
    
    # 岁运调整后等级可能变化
    if total >= 4.0: level = "上品"
    elif total >= 3.3: level = "中上品"
    elif total >= 2.8: level = "中品"
    elif total >= 2.3: level = "中下品"
    else: level = "下品"
    
    return {"score": total, "level": level, "details": details, "dayun_adjust": dayun_adjust}

# ===== 二、相似案例匹配 =====
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_SCRIPT_DIR, "case_index.json"), encoding="utf-8") as f:
    case_db = json.load(f)

def check_qingzhuo(bazi_str):
    """清浊专项判定 — 看天干是否混杂、用神是否被坏"""
    b = parse_bazi(bazi_str)
    if not b:
        return "未知", 0
    
    dm = b["day_gan"]
    dm_wx = GAN_WX[dm]
    tian_gan = [b["year_gan"], b["month_gan"], b["hour_gan"]]
    zhijiao = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
    
    ss_list = [get_shishen(dm, g) for g in tian_gan]
    
    # 浊的信号
    zhuo_score = 0
    # 官杀混杂
    if "正官" in ss_list and "七杀" in ss_list: zhuo_score += 2
    # 食伤混杂
    if "食神" in ss_list and "伤官" in ss_list: zhuo_score += 1
    # 比劫多
    if sum(1 for s in ss_list if s in ["比肩","劫财"]) >= 2: zhuo_score += 1
    # 财印打架（正财+正印同时透干）
    if "正财" in ss_list and "正印" in ss_list: zhuo_score += 2
    # 杀印互碍
    if "七杀" in ss_list and "偏印" in ss_list: zhuo_score += 1
    
    # 地支三刑/自刑/四冲
    for z in zhijiao:
        if zhijiao.count(z) >= 2: zhuo_score += 1  # 伏吟/自刑
    
    # 地支四冲（子午冲、卯酉冲、寅申冲、巳亥冲、辰戌冲、丑未冲）
    chong_map = {"子":"午","午":"子","卯":"酉","酉":"卯","寅":"申","申":"寅","巳":"亥","亥":"巳","辰":"戌","戌":"辰","丑":"未","未":"丑"}
    for zi, zo in chong_map.items():
        if zi in zhijiao and zo in zhijiao:
            zhuo_score += 2  # 每有一对冲加2分
            break  # 最多加一次
    
    if zhuo_score >= 4:
        return "浊", zhuo_score
    elif zhuo_score >= 2:
        return "中", zhuo_score
    else:
        return "清", zhuo_score


def _bazi_structure(bazi_str):
    '''Extract bazi structural features for matching'''
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b['day_gan']
    gans = [b['year_gan'],b['month_gan'],b['hour_gan']]
    zhis = [b['year_zhi'],b['month_zhi'],b['day_zhi'],b['hour_zhi']]
    return {
        '日主': dm,
        '日主五行': GAN_WX.get(dm,''),
        '格局': rate_mingju(bazi_str).get('level',''),
        '十神': [get_shishen(dm,g) for g in gans],
        '月令': b['month_zhi'],
        '官杀数': sum(1 for g in gans if get_shishen(dm,g) in ['正官','七杀']),
        '财星数': sum(1 for g in gans if get_shishen(dm,g) in ['正财','偏财']),
        '日支': b['day_zhi'],
    }

def find_similar(bazi_str, top_n=3):
    """在案例库中找最相似的命例（增强版）"""
    b = parse_bazi(bazi_str)
    if not b:
        return []
    
    dm = b["day_gan"]
    dm_wx = GAN_WX[dm]
    my_gans = [b["year_gan"], b["month_gan"], b["hour_gan"]]
    my_ss = [get_shishen(dm, g) for g in my_gans]
    my_zhi = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
    
    scored = []
    for c in case_db:
        bazi = c.get("bazi", "")
        if not bazi or "时缺" in bazi or "时" == bazi.strip():
            continue
        sim = 0
        cb = parse_bazi(bazi)
        if not cb:
            continue
        
        cb_gans = [cb["year_gan"], cb["month_gan"], cb["hour_gan"]]
        cb_ss = [get_shishen(dm, g) for g in cb_gans]
        cb_zhi = [cb["year_zhi"], cb["month_zhi"], cb["day_zhi"], cb["hour_zhi"]]
        
        # 1. 日主相同 +30%
        if cb["day_gan"] == b["day_gan"]: sim += 30
        
        # 2. 月令相同 +20%
        if cb["month_zhi"] == b["month_zhi"]: sim += 20
        
        # 3. 十神配置一致 +20%（逐位比较）
        ss_match = sum(1 for a, bz in zip(my_ss, cb_ss) if a == bz)
        sim += ss_match * 7
        
        # 4. 地支结构相似 +15%（冲刑合害模式）
        for z in ["子","午","卯","酉","寅","申","巳","亥","辰","戌","丑","未"]:
            if (z in my_zhi) == (z in cb_zhi):
                sim += 2  # 每有一个相同地支
        
        # 5. 清浊同级别 +15%
        q1 = check_qingzhuo(bazi_str)
        q2 = check_qingzhuo(c["bazi"])
        if q1[0] == q2[0]: sim += 15
        
        # 6. 纳音同类型 +5% - 年天干五行相同
        cb_year = c["bazi"].split()[0][0] if c["bazi"] else ""
        my_year = b["year_gan"]
        if cb_year and GAN_WX.get(cb_year) == GAN_WX.get(my_year): sim += 5
        
        scored.append((sim, c))
    
    scored.sort(key=lambda x: -x[0])
    # 封顶100%
    if scored:
        max_score = scored[0][0]
        scored = [(min(s, 100), c) for s, c in scored]
    # 转为字典格式(兼容性)
    result = []
    for s, case in scored[:top_n]:
        entry = dict(case)
        entry["score"] = s
        result.append(entry)
    return result


def verify_prediction(bazi_str, year, liu_nian_gan, liu_nian_zhi, event_type=""):
    """多维交叉验证 — 至少2条线索才断'实发'"""
    b = parse_bazi(bazi_str)
    if not b:
        return 0, []
    
    clues = []
    count = 0
    
    # 线索1：天干应事（十神）
    dm = b["day_gan"]
    ss = get_shishen(dm, liu_nian_gan)
    if ss:
        count += 1
        clues.append(f"天干:{ss}")
    
    # 线索2：地支动应（冲合会刑穿）
    dong = []
    liu_chong = {"子":"午","丑":"未","寅":"申","卯":"酉","辰":"戌","巳":"亥","午":"子","未":"丑","申":"寅","酉":"卯","戌":"辰","亥":"巳"}
    liu_he = {"子":"丑","寅":"亥","卯":"戌","辰":"酉","巳":"申","午":"未","未":"午","申":"巳","酉":"辰","戌":"卯","亥":"寅"}
    
    zhi_list = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
    
    if liu_nian_zhi in zhi_list:
        dong.append("伏吟")
    if liu_chong.get(liu_nian_zhi) in zhi_list:
        dong.append("冲")
    if liu_he.get(liu_nian_zhi) in zhi_list:
        dong.append("合")
    
    if dong:
        count += 1
        clues.append(f"地支:{','.join(dong)}")
    
    # 线索3：空亡
    # 年柱旬空（简化）
    xun_kong = {
        "甲子":"戌亥","甲戌":"申酉","甲申":"午未","甲午":"辰巳","甲辰":"寅卯","甲寅":"子丑"
    }
    year_gan_zhi = b["year_gan"] + b["year_zhi"]
    for xun_start, kong in xun_kong.items():
        # 判断年柱所在的旬
        gan_idx = "甲乙丙丁戊己庚辛壬癸".index(b["year_gan"])
        zhi_idx = "子丑寅卯辰巳午未申酉戌亥".index(b["year_zhi"])
        idx = gan_idx % 10
        start_zhi = (zhi_idx - gan_idx) % 12
        # 简化处理
        break
    
    return count, clues

# ===== 四、应期推演 =====
# 财星状态评估系统
ZHI_CANGGAN = {
    "子":"癸", "丑":"己癸辛", "寅":"甲丙戊", "卯":"乙",
    "辰":"戊乙癸", "巳":"丙庚戊", "午":"丁己", "未":"己丁乙",
    "申":"庚壬戊", "酉":"辛", "戌":"戊辛丁", "亥":"壬甲"
}

def is_shenwang(bazi_str):
    """快速判断身旺/身弱 + 根类型
    返回: {"强弱": "身旺/中偏弱/身弱", "根类型": "强根(寅卯)/余气(辰戌丑未)/无根", "比劫数": N}
    """
    b = parse_bazi(bazi_str)
    if not b: return {"强弱": "未知", "根类型": "未知", "比劫数": 0}
    dm = b["day_gan"]
    dm_wx = GAN_WX[dm]
    gans = [b["year_gan"], b["month_gan"], b["hour_gan"]]
    zhis = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
    # 天干比劫
    same_count = sum(1 for g in gans if GAN_WX[g] == dm_wx)
    # 地支强根（寅卯巳午申酉亥子中与日主同五行）
    qianggen = [z for z in zhis if ZHI_WX[z] == dm_wx and z in "寅卯巳午申酉亥子"]
    # 地支余气根（辰戌丑未）
    yugen = [z for z in zhis if ZHI_WX[z] == dm_wx and z in "辰戌丑未"]
    # 藏干根
    has_cang = False
    for z in zhis:
        for cg in ZHI_CANGGAN.get(z, ""):
            if GAN_WX.get(cg) == dm_wx:
                has_cang = True
    
    # 根类型判定
    if qianggen:
        root_type = f"强根({','.join(qianggen)})"
        strength = "身旺"
    elif yugen:
        root_type = f"余气({','.join(yugen)})"
        strength = "中/偏弱" if same_count >= 1 else "身弱"
    elif has_cang:
        root_type = "藏干弱根"
        strength = "中/偏弱" if same_count >= 1 else "身弱"
    else:
        root_type = "无根"
        strength = "身弱"
    
    # 月令加权
    month_zhi = b["month_zhi"]
    month_wx = ZHI_WX[month_zhi]
    sheng_wx = {"木":"水","火":"木","土":"火","金":"土","水":"金"}.get(dm_wx,'')
    if month_wx == dm_wx or month_wx == sheng_wx:
        # 月令支持（得令/得生）→ 升级
        if strength == "中/偏弱": strength = "身旺"
        elif strength == "身弱": strength = "中/偏弱"
    else:
        # 月令不支持（克/泄/耗）→ 降级
        if strength == "身旺": strength = "中/偏弱"
        elif strength == "中/偏弱": strength = "身弱"
    
    return {"强弱": strength, "根类型": root_type, "比劫数": same_count}

def cai_tag(bazi_str):
    """第一步：原局财星可使用性评估"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    dm_wx = GAN_WX[dm]
    sw = is_shenwang(bazi_str)
    gans = [b["year_gan"], b["month_gan"], b["hour_gan"]]
    zhis = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
    
    # 定位正财和偏财
    zhengcai_gan = [g for g in gans if get_shishen(dm, g) == "正财"]
    piancai_gan = [g for g in gans if get_shishen(dm, g) == "偏财"]
    zhengcai_zhi = [z for z in zhis for cg in ZHI_CANGGAN.get(z,"") if get_shishen(dm, cg) == "正财"]
    piancai_zhi = [z for z in zhis for cg in ZHI_CANGGAN.get(z,"") if get_shishen(dm, cg) == "偏财"]
    
    # 财星有没有根
    zc_yougen = len(zhengcai_gan) > 0 and len(zhengcai_zhi) > 0
    pc_yougen = len(piancai_gan) > 0 and len(piancai_zhi) > 0
    
    # 财星是否被比劫克
    bijie_near = sum(1 for g in gans if get_shishen(dm, g) in ["比肩","劫财"])
    zc_beike = bijie_near >= 2 and len(zhengcai_gan) > 0
    pc_beike = bijie_near >= 2 and len(piancai_gan) > 0
    
    # 财星源头：是否有食伤生财
    has_shiyang = any(get_shishen(dm, g) in ["食神","伤官"] for g in gans)
    cai_yuanyou = has_shiyang  # 食伤生财为上佳
    
    # 财入墓库检查
    cai_kucang_check = False
    cai_wx = {"木":"土","火":"金","土":"水","金":"木","水":"火"}.get(dm_wx, "")
    for z in zhis:
        if z in "辰戌丑未" and ZHI_WX.get(z) == cai_wx:
            cai_kucang_check = True  # 财坐墓库
    
    # 禄当财看：原局无财无官时，看禄（含藏干）
    lu_dang_cai = ""
    lu_map = {"甲":"寅","乙":"卯","丙":"巳","丁":"午","戊":"巳","己":"午","庚":"申","辛":"酉","壬":"亥","癸":"子"}
    day_lu = lu_map.get(dm, "")
    
    # 查藏干中是否有财和官杀
    has_cang_cai = False
    has_cang_guan = False
    for z in zhis:
        for cg in ZHI_CANGGAN.get(z, ""):
            ss = get_shishen(dm, cg)
            if ss in ["正财","偏财"]:
                has_cang_cai = True
            if ss in ["正官","七杀"]:
                has_cang_guan = True
    
    has_ming_cai = len(zhengcai_gan) > 0 or len(piancai_gan) > 0
    has_ming_guan = any(get_shishen(dm, g) in ["正官","七杀"] for g in gans)
    
    if not has_ming_cai and not has_cang_cai:
        # 真的无财（天干地支都无财）
        if has_ming_guan or has_cang_guan:
            lu_dang_cai = "官当财看（以名得财）"
        elif day_lu in zhis:
            lu_dang_cai = f"禄当财看（{day_lu}为日主之禄）"
        else:
            lu_dang_cai = "无财无官无禄→看纳音质地"
    
    result = {}
    result["禄当财"] = lu_dang_cai
    result["财坐墓"] = cai_kucang_check
    result["财有源"] = cai_yuanyou
    result["身旺"] = sw["强弱"]
    result["比劫数"] = bijie_near
    # 正财评定
    if len(zhengcai_gan) > 0:
        if zc_yougen and not zc_beike and "身旺" in sw["强弱"]:
            result["正财"] = "可用吉财"
        elif zc_yougen and not zc_beike and "身弱" in sw["强弱"]:
            result["正财"] = "为财所累"
        elif zc_beike:
            result["正财"] = "受损之财"
        else:
            result["正财"] = "虚花之财"
    else:
        result["正财"] = "无明财"
    
    # 偏财评定
    if len(piancai_gan) > 0 or len(piancai_zhi) > 0:
        if pc_yougen and not pc_beike and "身旺" in sw["强弱"]:
            result["偏财"] = "可用吉财"
        elif pc_beike:
            result["偏财"] = "受损之财"
        elif "身旺" in sw["强弱"]:
            result["偏财"] = "虚花之财"
        elif "身弱" in sw["强弱"]:
            result["偏财"] = "为财所累"
        else:
            result["偏财"] = "待用潜财"
    else:
        result["偏财"] = "原局无偏财"
    
    return result

def cai_dayun_effect(bazi_str, dayun_gan, dayun_zhi):
    """第二步：大运对财星状态的影响"""
    b = parse_bazi(bazi_str)
    if not b: return ""
    dm = b["day_gan"]
    # 大运干支对财星是生扶还是克制
    dayun_ss = get_shishen(dm, dayun_gan)
    dm_wx = GAN_WX[dm]
    dayun_zhi_wx = ZHI_WX.get(dayun_zhi, "")
    
    is_wealth_friendly = False
    is_wealth_hostile = False
    
    # 食伤运生财 → 财源好
    if dayun_ss in ["食神","伤官"]:
        is_wealth_friendly = True
    # 比劫运夺财
    if dayun_ss in ["比肩","劫财"]:
        is_wealth_hostile = True
    # 财运直接生扶财星
    if dayun_ss in ["正财","偏财"]:
        is_wealth_friendly = True
    
    return {"食伤生财": is_wealth_friendly, "比劫夺财": is_wealth_hostile}

def cai_verify_liunian(bazi_str, year):
    """第三步+第四步：流年双象验证"""
    b = parse_bazi(bazi_str)
    if not b: return ""
    dm = b["day_gan"]
    liu_gan = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"][(year-4) % 10]
    liu_zhi = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"][(year-4) % 12]
    
    cai_tag_result = cai_tag(bazi_str)
    sw = cai_tag_result["身旺"]
    
    # 天干信号
    gan_ss = get_shishen(dm, liu_gan)
    is_cai_year = gan_ss in ["正财","偏财"]
    
    # 地支生扶（含藏干）
    zhi_wx = ZHI_WX.get(liu_zhi, "")
    dm_wx = GAN_WX[dm]
    cai_wx = {"木":"土","火":"金","土":"水","金":"木","水":"火"}.get(dm_wx, "")
    
    # 检查藏干中是否含财五行
    canggan_has_cai = False
    for cg in ZHI_CANGGAN.get(liu_zhi, ""):
        if GAN_WX.get(cg) == cai_wx:
            canggan_has_cai = True
    
    if zhi_wx == cai_wx or canggan_has_cai:
        zhi_shengfu = "生扶"
    elif zhi_wx == dm_wx:
        zhi_shengfu = "克泄"
    else:
        zhi_shengfu = "中性"
    
    # 双象判定
    signals = {"天干": gan_ss, "地支": zhi_shengfu, "十神": gan_ss}
    
    # 获取原局财星标签
    cai_tag_result_local = cai_tag(bazi_str)
    piancai_tag = cai_tag_result_local.get("偏财", "")
    zhengcai_tag = cai_tag_result_local.get("正财", "")
    
    if is_cai_year and zhi_shengfu == "生扶":
        # 原局标签修正
        if piancai_tag in ["受损之财","虚花之财"] or zhengcai_tag in ["受损之财","虚花之财"]:
            signals["结论"] = "天干地支皆动，但原局财星不可用 → 看似机会实则虚浮"
            signals["强度"] = "虚象"
        else:
            signals["结论"] = "双吉 → 有实发之财"
            signals["强度"] = "强实发"
    elif is_cai_year and zhi_shengfu == "克泄":
        signals["结论"] = "天干见财但根被伤 → 有迹象但留不住"
        signals["强度"] = "弱虚象"
    elif not is_cai_year and zhi_shengfu == "生扶":
        signals["结论"] = "财根动但未透 → 暗中准备，尚未落袋"
        signals["强度"] = "待用"
    else:
        signals["结论"] = "不主财运"
        signals["强度"] = "无"
    
    # 偏财特殊：被合入日时柱才断落袋
    if gan_ss == "偏财":
        # 是否合入我宫
        he_map = {"甲":"己","乙":"庚","丙":"辛","丁":"壬","戊":"癸","己":"甲","庚":"乙","辛":"丙","壬":"丁","癸":"戊"}
        if he_map.get(liu_gan) == dm:
            signals["偏财落袋"] = "合入日主 → 偏财有望落袋"
        else:
            signals["偏财落袋"] = "未合入身 → 过手财神"
    
    return signals
NAYIN_MAP = {
    "甲子":"金","乙丑":"金","丙寅":"火","丁卯":"火","戊辰":"木","己巳":"木","庚午":"土","辛未":"土","壬申":"金","癸酉":"金",
    "甲戌":"火","乙亥":"火","丙子":"水","丁丑":"水","戊寅":"土","己卯":"土","庚辰":"金","辛巳":"金","壬午":"木","癸未":"木",
    "甲申":"水","乙酉":"水","丙戌":"土","丁亥":"土","戊子":"火","己丑":"火","庚寅":"木","辛卯":"木","壬辰":"水","癸巳":"水",
    "甲午":"金","乙未":"金","丙申":"火","丁酉":"火","戊戌":"木","己亥":"木","庚子":"土","辛丑":"土","壬寅":"金","癸卯":"金",
    "甲辰":"火","乙巳":"火","丙午":"水","丁未":"水","戊申":"土","己酉":"土","庚戌":"金","辛亥":"金","壬子":"木","癸丑":"木",
    "甲寅":"水","乙卯":"水","丙辰":"土","丁巳":"土","戊午":"火","己未":"火","庚申":"木","辛酉":"木","壬戌":"水","癸亥":"水",
}

def nayan(gz):
    return NAYIN_MAP.get(gz, "")

def yingqi_analysis(bazi_str, start_year=2025, end_year=2035):
    """大运流年应期推演"""
    b = parse_bazi(bazi_str)
    if not b:
        return []
    
    dm = b["day_gan"]
    results = []
    
    for year in range(start_year, end_year + 1):
        clues = []
        score = 0
        liu_gan = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"][(year-4) % 10]
        liu_zhi = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"][(year-4) % 12]
        
        # 线索1：十神
        ss = get_shishen(dm, liu_gan)
        if ss in ["偏财","正财"]:
            score += 1; clues.append(f"财年({ss})")
        elif ss in ["七杀","正官"]:
            score += 1; clues.append(f"官杀年({ss})")
        elif ss in ["食神","伤官"]:
            score += 1; clues.append(f"食伤年({ss})")
        elif ss in ["正印","偏印"]:
            score += 1; clues.append(f"印年({ss})")
        elif ss in ["比肩","劫财"]:
            score += 1; clues.append(f"比劫年({ss})")
        
        # 线索2：地支动应
        zhi_list = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
        chong_map = {"子":"午","午":"子","卯":"酉","酉":"卯","寅":"申","申":"寅","巳":"亥","亥":"巳","辰":"戌","戌":"辰","丑":"未","未":"丑"}
        he_map = {"子":"丑","丑":"子","寅":"亥","亥":"寅","卯":"戌","戌":"卯","辰":"酉","酉":"辰","巳":"申","申":"巳","午":"未","未":"午"}
        
        if liu_zhi in zhi_list:
            score += 1; clues.append(f"地支伏吟({liu_zhi})")
        if chong_map.get(liu_zhi) in zhi_list:
            score += 1; clues.append(f"地支冲({liu_zhi})")
        if he_map.get(liu_zhi) in zhi_list:
            score += 1; clues.append(f"地支合({liu_zhi})")
        
        # 线索3：纳音
        year_nayan = nayan(liu_gan + liu_zhi)
        day_nayan = nayan(b["day_gan"] + b["day_zhi"])
        if year_nayan and day_nayan:
            ke_map = {"金":"木","木":"土","土":"水","水":"火","火":"金"}
            if ke_map.get(year_nayan) == day_nayan:
                score += 1; clues.append(f"纳音克日({year_nayan}克{day_nayan})")
        
        if score >= 2:
            # 判断吉凶倾向
            good_ss = ss in ["正财","偏财","食神","正印"]
            if good_ss and "冲" not in str(clues):
                trend = "吉"
            elif not good_ss and "合" in str(clues):
                trend = "平转吉"
            else:
                trend = "平/需细断"
            
            results.append({
                "year": year, "gan": liu_gan, "zhi": liu_zhi,
                "十神": ss, "线索": clues, "分数": score, "趋势": trend
            })
    
    return results

# ===== 五、评分拆细 =====
def rate_refined(score, qingzhuo_level, qingzhuo_score):
    """中品评分拆细：加清浊权重"""
    if "中品" not in str(score):
        return score
    if qingzhuo_level == "浊":
        return round(score - 0.3, 1)
    elif qingzhuo_level == "清":
        return round(score + 0.2, 1)
    return score

# ===== 九、调候检查 =====
TIAOHOU_MONTHS = {"夏":["巳","午","未"], "冬":["亥","子","丑"]}

def check_tiaohou(bazi_str):
    """调候规则：按日主敏感度分级"""
    b = parse_bazi(bazi_str)
    if not b: return {"调候": "未知", "降级": False}
    mzhi = b["month_zhi"]
    dm = b["day_gan"]
    gans = [b["year_gan"], b["month_gan"], b["hour_gan"]]
    zhis = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
    
    # 调候敏感度分级（调候正解原文）
    # 甲木、乙木：最敏感 → 夏生无水、冬生无火都降级
    # 庚金、辛金：次敏感 → 冬生无火（金寒水冷）降级
    # 丙丁壬癸戊己：不敏感 → 不做调候降级
    sensitive = {"甲","乙","庚","辛"}
    
    if dm not in sensitive:
        return {"调候": f"{dm}日主不敏感不需调候", "降级": False}
    
    # 夏生（巳午未月）—— 甲乙木要水
    if mzhi in "巳午未" and dm in {"甲","乙"}:
        has_water = any(GAN_WX[g] == "水" for g in gans)
        has_water_zhi = any(ZHI_WX[z] == "水" for z in zhis)
        if not has_water and not has_water_zhi:
            return {"调候": "甲乙木夏生无水", "降级": True}
        return {"调候": "夏生有水", "降级": False}
    
    # 冬生（亥子丑月）—— 甲乙木要火，庚辛金要火
    if mzhi in "亥子丑" and dm in {"甲","乙","庚","辛"}:
        has_fire = any(GAN_WX[g] == "火" for g in gans)
        has_fire_zhi = any(ZHI_WX[z] == "火" for z in zhis)
        # 查藏干余气（如寅中丙、巳中丙）
        has_fire_cang = False
        if not has_fire and not has_fire_zhi:
            for z in zhis:
                for cg in ZHI_CANGGAN.get(z, ""):
                    if GAN_WX.get(cg) == "火":
                        has_fire_cang = True
                        break
            if not has_fire_cang:
                tag = "庚辛金" if dm in {"庚","辛"} else "甲乙木"
                return {"调候": f"{tag}冬生无火", "降级": True}
            return {"调候": "冬生藏火余气", "降级": False}
        return {"调候": "冬生有火", "降级": False}
    
    return {"调候": "不需调候", "降级": False}

def gaitou_jiejiao(dayun_gan, dayun_zhi, xiyong=None):
    """大运干支关系判定：盖头/截脚/天覆/地载/同五行 + 喜用匹配
    返回: (关系类型, 关系说明, 喜用匹配说明)
    """
    WU = {"甲":"木","乙":"木","丙":"火","丁":"火","戊":"土","己":"土","庚":"金","辛":"金","壬":"水","癸":"水"}
    gan_wx = WU.get(dayun_gan, "")
    zhi_wx = ZHI_WX.get(dayun_zhi, "")
    
    SHENG = {"木":"火","火":"土","土":"金","金":"水","水":"木"}  # X生Y
    KE = {"木":"土","土":"水","水":"火","火":"金","金":"木"}      # X克Y
    
    rel = ""
    desc = ""
    
    if gan_wx == zhi_wx:
        rel = "同五行"
        desc = f"{dayun_gan}{dayun_zhi}干支同气"
    elif KE.get(gan_wx) == zhi_wx:
        rel = "盖头"
        desc = f"{dayun_gan}({gan_wx})克{dayun_zhi}({zhi_wx})→天干压制地支，有力使不出"
    elif KE.get(zhi_wx) == gan_wx:
        rel = "截脚"
        desc = f"{dayun_zhi}({zhi_wx})克{dayun_gan}({gan_wx})→地支拖累天干，被下面牵着走"
    elif SHENG.get(gan_wx) == zhi_wx:
        rel = "天覆"
        desc = f"{dayun_gan}({gan_wx})生{dayun_zhi}({zhi_wx})→天干滋养地支，顺遂通畅"
    elif SHENG.get(zhi_wx) == gan_wx:
        rel = "地载"
        desc = f"{dayun_zhi}({zhi_wx})生{dayun_gan}({gan_wx})→地支托举天干，根基稳固"
    
    # 喜用匹配
    xiyong_desc = ""
    if xiyong and isinstance(xiyong, dict):
        xi = xiyong.get('喜', '')
        yong = xiyong.get('用', '')
        if gan_wx in [xi, yong] and zhi_wx in [xi, yong]:
            xiyong_desc = "干支皆喜用→大吉"
        elif gan_wx in [xi, yong]:
            xiyong_desc = "天干为喜用但地支非→前段好"
        elif zhi_wx in [xi, yong]:
            xiyong_desc = "地支为喜用但天干非→后段好"
    
    return f"{rel} · {desc}" + (f" | {xiyong_desc}" if xiyong_desc else "")

# ===== 十、盲派补充技能 =====
HE_MAP = {"甲":"己","乙":"庚","丙":"辛","丁":"壬","戊":"癸","己":"甲","庚":"乙","辛":"丙","壬":"丁","癸":"戊"}

def tian_gan_wuhe(bazi_str):
    """盲派：天干五合做功检查"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"], b["month_gan"], b["hour_gan"]]
    
    results = {}
    for g in gans:
        if HE_MAP.get(dm) == g:
            ss = get_shishen(dm, g)
            results[f"日主合{g}"] = ss
    
    # 其他天干之间的五合
    for i, g1 in enumerate(gans):
        for g2 in gans[i+1:]:
            if HE_MAP.get(g1) == g2:
                ss1 = get_shishen(dm, g1)
                ss2 = get_shishen(dm, g2)
                results[f"{g1}{g2}合"] = f"{ss1}+{ss2}"
    
    return results

def cai_check_muku(bazi_str):
    """盲派修正：财透天干+有根→不算入墓"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"], b["month_gan"], b["hour_gan"]]
    zhis = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
    
    cai_tou = [g for g in gans if get_shishen(dm,g) in ["正财","偏财"]]
    
    if len(cai_tou) > 0:
        return {"入墓检查": "财透天干，不算入墓"}
    else:
        cai_wx = {"甲":"土","乙":"土","丙":"金","丁":"金","戊":"水","己":"水","庚":"木","辛":"木","壬":"火","癸":"火"}.get(dm,"")
        zai_muku = [z for z in zhis if z in "辰戌丑未" and ZHI_WX.get(z) == cai_wx]
        return {"入墓检查": "财不透干，可能入墓"} if zai_muku else {"入墓检查": "无财，不需查墓"}
        
def sushi_jialiwai(bazi_str):
    """素水：家里家外论——财官在日时比在年月容易得到"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"], b["month_gan"], b["hour_gan"]]
    
    jiali = []  # 日时（家里）
    jiawai = []  # 年月（家外）
    
    cai_guan_ss = ["正财","偏财","正官","七杀"]
    for i, g in enumerate(gans):
        ss = get_shishen(dm, g)
        if ss in cai_guan_ss:
            if i >= 2:  # 时干
                jiali.append(f"时{g}={ss}")
            elif i == 0:  # 年干
                jiawai.append(f"年{g}={ss}")
            else:  # 月干
                jiawai.append(f"月{g}={ss}")
    
    # 判断
    if jiali and not jiawai:
        mode = "财官全在家内 → 自己做/创业型"
    elif jiawai and not jiali:
        mode = "财官全在家外 → 打工/体制型"
    elif jiali and jiawai:
        mode = "家里家外都有 → 混合型（先打工后创业或体制内）"
    else:
        mode = "财官不显 → 需要大运引出"
    
    return {"家里": jiali, "家外": jiawai, "模式": mode}

def sushi_zuogong(bazi_str):
    """素水：做功识别——生还是制"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"], b["month_gan"], b["hour_gan"]]
    zhis = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
    
    zuogong = []
    
    # 制（克）
    for g in gans:
        ss = get_shishen(dm, g)
        if ss in ["食神","伤官"] and any(get_shishen(dm, g2) in ["七杀"] for g2 in gans):
            zuogong.append("食神/伤官制杀")
        if ss in ["比肩","劫财"] and any(get_shishen(dm, g2) in ["正财","偏财"] for g2 in gans):
            zuogong.append("比劫制财")
    
    # 生（生化）
    for g in gans:
        ss = get_shishen(dm, g)
        if ss in ["食神","伤官"] and any(get_shishen(dm, g2) in ["正财","偏财"] for g2 in gans):
            zuogong.append("食伤生财")
        if ss in ["正印","偏印"] and any(get_shishen(dm, g2) == g for g2 in gans if get_shishen(dm, g2) in ["正财","偏财","食神","伤官"]):
            zuogong.append("印生身")
    
    # 化杀生印
    for g in gans:
        if get_shishen(dm, g) in ["正官","七杀"]:
            for g2 in gans:
                if get_shishen(dm, g2) in ["正印","偏印"]:
                    zuogong.append("化杀生印")
                    break
    
    if not zuogong:
        zuogong.append("做功不明显→按常规五行生克判断")
    
    return {"做功": list(set(zuogong))}

# ===== 十一、十干喜忌（阿财命理文集） =====
GAN_XIJI = {
    "甲": {"旺喜":["庚金伐","戊土疏"], "弱喜":["癸水润"], 
           "忌":["己土合","辛金弱"], "备注":"甲旺喜庚金削成大才，甲弱喜癸水雨露"},
    "乙": {"旺喜":["丙火暖","癸水润"], "弱喜":["己土培"],
           "忌":["辛金绊"], "备注":"乙木喜丙火解寒，己土培根"},
    "丙": {"旺喜":["壬水济"], "弱喜":["乙木生"],
           "忌":["癸水混"], "备注":"丙火配壬水成大格局，配癸水小富小贵"},
    "丁": {"旺喜":["庚金配","甲木引"], "弱喜":["甲木生"],
           "忌":["无根"], "备注":"丁火喜庚金带甲，无甲命贫苦"},
    "戊": {"旺喜":["甲木疏","丙火暖"], "弱喜":["丙火生"],
           "忌":["太燥无水"], "备注":"戊土喜甲木来疏，丙火暖局"},
    "己": {"旺喜":["丙火照","庚金泄"], "弱喜":["丙火生"],
           "忌":["癸水混杂"], "备注":"己土喜丙火照拂，庚金泄秀"},
    "庚": {"旺喜":["丁火炼"], "弱喜":["戊土生"],
           "忌":["己土浊","水冷"], "备注":"庚金喜丁火锻炼成器，忌己土污浊"},
    "辛": {"旺喜":["壬水洗"], "弱喜":["戊土生"],
           "忌":["己土浊","火过旺"], "备注":"辛金喜壬水淘洗，忌太旺之火"},
    "壬": {"旺喜":["丙火济","戊土堤"], "弱喜":["庚金生"],
           "忌":["己土混"], "备注":"壬水喜丙火既济，戊土作堤"},
    "癸": {"旺喜":["丙火映"], "弱喜":["辛金生"],
           "忌":["戊土合"], "备注":"癸水喜丙火映彩云，忌戊土合化"},
}

def gan_xiji(dm):
    """十干喜忌查询"""
    return GAN_XIJI.get(dm, {})

# ===== 十二、命诀十八口（阿财命理文集） =====
KOUJUE_DIZHI = {
    # 六冲 (6)
    "子午": "子午水火冲心不定，事业感情两难平",
    "丑未": "丑未土冲脾胃伤，是非纠缠有牢灾",
    "寅申": "寅申金木冲路险，奔波劳碌职难安",
    "卯酉": "卯酉金木冲门户，家庭离散灾难多",
    "辰戌": "辰戌魁罡冲黄泉，天罗地网运难逃",
    "巳亥": "巳亥水火冲驿马，经风见雨走天涯",
    # 六害 (6)
    "子未": "子未相害水浊土，暗中损耗不自知",
    "丑午": "丑午相害湿热缠，相逢即在病中眠",
    "寅巳": "寅巳相害无恩义，表面客气暗较劲",
    "卯辰": "卯辰相害木穿土，好事多磨总成空",
    "申亥": "申亥相害金生水，技艺超群出名人",
    "酉戌": "酉戌相害金埋火，怀才不遇暗伤神",
    # 三刑 — 无礼之刑 (1)
    "子卯": "子卯无礼是非多，口舌之争惹人烦",
    # 三刑 — 恃势之刑 (3)
    "丑戌": "丑戌恃势刑自战，固执己见不听劝",
    "戌未": "戌未持势刑土燥，刚愎自用反被欺",
    "寅巳": "寅巳申刑无恩义，明争暗斗三败伤",
    "巳申": "巳申刑合反复间，成也是它败也是它",
    # 自刑 (4)
    "辰辰": "辰辰自刑身不安，自己跟自己过不去",
    "午午": "午午自刑火太旺，急躁伤身心难静",
    "酉酉": "酉酉自刑金自伤，孤独多思少人知",
    "亥亥": "亥亥自刑水上漂，心思飘忽难定锚",
    # 地支半合/暗合 (4)
    "丑酉": "丑酉半合金库开，暗中得助有人抬",
    "丑卯": "丑卯暗合木穿土，表面风光内里虚",
    "寅辰": "寅辰拱会东方木，时运不济少良机",
    "午未": "午未合土婚自合，东南方向见喜神",
}

def koujue_18(zhi_pairs):
    """命诀十八口查询——按地支对应关系返回口诀"""
    results = []
    checked = set()
    for i, z1 in enumerate(zhi_pairs):
        for z2 in zhi_pairs[i+1:]:
            key = "".join(sorted(z1+z2))
            if key not in checked and key in KOUJUE_DIZHI:
                checked.add(key)
                results.append(f"{z1}{z2}: {KOUJUE_DIZHI[key]}")
    return results

# ===== 十三、三种论命体系切换（阿财命理文集） =====
def tixi_recommend(bazi_str):
    """推荐最适合的论命体系"""
    b = parse_bazi(bazi_str)
    if not b: return {"推荐": "常规体系", "理由": "无法解析"}
    
    dm = b["day_gan"]
    gans = [b["year_gan"], b["month_gan"], b["hour_gan"]]
    zhis = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
    
    # 判断条件
    is_cong = is_cong_ge(bazi_str)
    is_special = any(get_shishen(dm,g) in ["正官","七杀"] and get_shishen(dm,g2) in ["正印","偏印"] for g in gans for g2 in gans)
    has_all_five = len(set(GAN_WX[g] for g in gans)) >= 4  # 五行驳杂
    missing_element = False
    all_wx = set(GAN_WX[g] for g in gans) | set(ZHI_WX[z] for z in zhis)
    for wx in "金木水火土":
        if wx not in all_wx:
            missing_element = True
            break
    
    if is_cong:
        return {"推荐": "从格体系（五行论命）", "理由": f"从{is_cong}格，按从格论"}
    elif is_special:
        return {"推荐": "十神做功体系（十神论命）", "理由": "杀印相生/食神制杀等做功明确"}
    elif missing_element:
        return {"推荐": "缺五行体系（五行论命）", "理由": f"缺{'/'.join(wx for wx in '金木水火土' if wx not in all_wx)}，从缺五行入手"}
    elif has_all_five:
        return {"推荐": "扶抑调候体系（用神论命）", "理由": "五行俱备，宜取用神调候"}
    else:
        return {"推荐": "常规体系（用神论命）", "理由": "按旺衰扶抑论"}

# ===== 十四、功神废神判定 =====
def gong_shen(bazi_str):
    """功神废神判定：做功的字=功神，不做功的字=废神"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"], b["month_gan"], b["hour_gan"]]
    zhis = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
    all_zhis = zhis
    
    # 刑冲合害关系表
    liuhe = {"子":"丑","丑":"子","寅":"亥","卯":"戌","辰":"酉","巳":"申","午":"未","未":"午","申":"巳","酉":"辰","戌":"卯","亥":"寅"}
    sanhe_groups = [{"申","子","辰"},{"亥","卯","未"},{"寅","午","戌"},{"巳","酉","丑"}]
    liuchong = {"子":"午","丑":"未","寅":"申","卯":"酉","辰":"戌","巳":"亥"}
    liuhai = {"子":"未","丑":"午","寅":"巳","卯":"辰","申":"亥","酉":"戌"}
    xing_groups = [{"寅","巳","申"},{"丑","戌","未"},{"子","卯"}]
    zichong = {"辰","午","酉","亥"}  # 辰辰/午午/酉酉/亥亥自刑
    
    # 每个地支是否做功
    gong_zhi = []
    fei_zhi = []
    for z in all_zhis:
        zuogong = False
        # 六合
        if liuhe.get(z) in all_zhis: zuogong = True
        # 三合
        for group in sanhe_groups:
            if z in group and len(group & set(all_zhis)) >= 2: zuogong = True
        # 六冲
        if liuchong.get(z) in all_zhis: zuogong = True
        # 六害
        if liuhai.get(z) in all_zhis: zuogong = True
        # 三刑
        for group in xing_groups:
            if z in group and len(group & set(all_zhis)) >= 2: zuogong = True
        # 自刑
        if z in zichong and sum(1 for z2 in all_zhis if z2 == z) >= 2: zuogong = True
        
        if zuogong:
            gong_zhi.append(z)
        else:
            fei_zhi.append(z)
    
    # 天干做功：有没有参与合克
    gong_gan = []
    fei_gan = []
    he_map = {"甲":"己","乙":"庚","丙":"辛","丁":"壬","戊":"癸","己":"甲","庚":"乙","辛":"丙","壬":"丁","癸":"戊"}
    for g in gans:
        if he_map.get(g) in gans:
            gong_gan.append(g)
        else:
            fei_gan.append(g)
    
    total = len(gong_gan) + len(fei_gan) + len(gong_zhi) + len(fei_zhi)
    gong_total = len(gong_gan) + len(gong_zhi)
    fei_total = len(fei_gan) + len(fei_zhi)
    ratio = round(gong_total / total, 2) if total > 0 else 0
    
    return {
        "功神": gong_gan + gong_zhi,
        "废神": fei_gan + fei_zhi,
        "功神比例": ratio,
        "判定": "层次高" if ratio >= 0.6 else ("层次中" if ratio >= 0.4 else "层次低")
    }

# ===== 十五、盲派应期精修（段建业+杨清娟） =====
MANGPAI_YINGQI = {
    "liuhe_yinqi": "原局有合，冲为应期；原局有冲，合为应期",
    "he_yinqi": "天干五合将夫妻星/财官与主位相合=应期",
    "chong_muku": "财官入墓喜刑冲，冲开墓库=应期",
    "chuan_dao": "穿是暗中破坏，穿倒宫位=凶应期",
    "xing_kai": "丑未戌三刑/寅巳申三刑，刑开墓库放出用神=吉应期",
    "huai_zuai": "坏掉阻碍婚姻/事业的字=应期（段建业核心）",
    "fu_yin": "伏吟事件重复，伏吟应期",
    "bao_ju": "两头包局不容易离婚/散伙",
}

def yingqi_3year(bazi_str, start_year=2026):
    """三年一跃叙事框架：松土/抽枝/成荫/遮风"""
    result = []
    try:
        # 空值保护
        pb = parse_bazi(bazi_str)
        if not pb:
            return []
        base = yingqi_analysis(bazi_str, start_year, start_year + 15)
        phases = ["松土年", "蓄力年", "抽枝年", "成荫年", "遮风年"]
        phase_desc = {
            "松土年": "压力最大但扎根最深的时候——不求出头，求站稳",
            "蓄力年": "外部压力稍减，内部能量开始积累",
            "抽枝年": "机会出现，可以适度出手——但别贪",
            "成荫年": "之前种下的开始有回报——收成期",
            "遮风年": "不是扩张的时候——守住已有的，帮住身边的人"
        }
        for i, year in enumerate(range(start_year, start_year + 15, 3)):
            phase = phases[i % 5]
            desc = phase_desc[phase]
            yq = yingqi_refined(bazi_str, year) if i == 0 else {}
            signals = yq.get("signals", []) if isinstance(yq, dict) else []
            sig_str = f"·{signals[0]}" if signals and isinstance(signals, list) else ""
            result.append({"year": year, "phase": phase, "desc": desc, "signal": sig_str})
    except Exception:
        pass
    return result

def tiyong_analyze(bazi_str):
    """体用分析：体=日主+比劫+印，用=食伤+财+官杀
    从格版：体=从神五行，用=日主能量
    藏干版：地支主气加入体用计量"""
    parsed = parse_bazi(bazi_str)
    if not parsed:
        return {}
    dm = parsed["day_gan"]
    gans = [parsed["year_gan"], parsed["month_gan"], parsed["hour_gan"]]
    zhis = [parsed["year_zhi"], parsed["month_zhi"], parsed["day_zhi"], parsed["hour_zhi"]]
    sw = is_shenwang(bazi_str)
    qiangruo = sw.get("强弱", "中")
    
    # 藏干主气映射（第一位=主气）
    canggan_zhugi = {"子":"癸","丑":"己","寅":"甲","卯":"乙","辰":"戊",
                      "巳":"丙","午":"丁","未":"己","申":"庚","酉":"辛","戌":"戊","亥":"壬"}
    
    # ===== 从格检测 =====
    cg = is_cong_ge(bazi_str)
    is_cong = cg.get("从格", False)
    
    # ===== 体用计量 =====
    ti = 1  # 日主
    yong = 0
    ti_detail = [f"日主{dm}"]
    yong_detail = []
    
    # 天干体用
    for g in gans:
        ss = get_shishen(dm, g)
        if ss in ("比肩", "劫财", "偏印", "正印"):
            ti += 1
            ti_detail.append(ss)
        else:
            yong += 1
            yong_detail.append(ss)
    
    # 地支藏干主气体用（新增⚡）
    for z in zhis:
        zg = canggan_zhugi.get(z, "")
        if zg:
            zg_ss = get_shishen(dm, zg)
            if zg_ss in ("比肩", "劫财", "偏印", "正印"):
                ti += 1
                ti_detail.append(f"{z}藏{zg}({zg_ss})")
            else:
                yong += 1
                yong_detail.append(f"{z}藏{zg}({zg_ss})")
    
    ratio = round(ti / max(yong + ti, 1), 2)
    
    # ===== 从格特殊翻译 =====
    if is_cong:
        cong_type = cg.get("类型", "")
        # 从格的核心矛盾：从神强但日主也想出头
        balance = f"从格·{cong_type}——从神为体日主为用，表面顺从而内心有骨；不是没能力，是方向选对了"
    # ===== 正格翻译 =====
    elif ratio >= 0.6 and ("旺" in qiangruo or "强" in qiangruo):
        balance = "体强用弱——自己能力过剩但外部目标不足，容易有力没处使"
    elif ratio <= 0.4 and qiangruo in ("身弱", "中/偏弱"):
        balance = "用强体弱——外部诱惑/压力大但自身能量不足，容易疲于奔命"
    elif 0.4 < ratio < 0.6:
        balance = "体用均衡——能扛也能放，但容易两头都不够极致"
    else:
        balance = f"体{ti}用{yong}，{qiangruo}之局"
    
    return {
        "体": ti_detail, "用": yong_detail, "比例": ratio, "平衡": balance,
        "从格标记": is_cong, "从格类型": cg.get("类型","")
    }

def zhengfanju_analysis(bazi_str):
    """正局反局分析：做功方向与日主意向是否一致
    暗局仅当精确符合标准自刑（辰辰/午午/酉酉/亥亥）"""
    parsed = parse_bazi(bazi_str)
    if not parsed:
        return {}
    dm = parsed["day_gan"]
    gans = [parsed["year_gan"], parsed["month_gan"], parsed["hour_gan"]]
    zhis = [parsed["year_zhi"], parsed["month_zhi"], parsed["day_zhi"], parsed["hour_zhi"]]
    
    zuogong = sushi_zuogong(bazi_str)
    gong_list = zuogong.get("做功", [])
    
    # 判断日主意向
    shishen_list = [get_shishen(dm, g) for g in gans]
    ss_joined = " ".join(shishen_list)
    yixiang = ""
    if "七杀" in ss_joined or "正官" in ss_joined:
        yixiang = "想求名/求地位"
    elif "偏财" in ss_joined or "正财" in ss_joined:
        yixiang = "想求财/求实在"
    elif "伤官" in ss_joined:
        yixiang = "想表达/想突破"
    elif "食神" in ss_joined:
        yixiang = "想安稳/想输出"
    else:
        yixiang = "随势而动"
    
    # 精确自刑检测（标准四组：辰辰/午午/酉酉/亥亥）⚡
    selfxing = False
    selfxing_groups = {"辰": 0, "午": 0, "酉": 0, "亥": 0}
    for z in zhis:
        if z in selfxing_groups:
            selfxing_groups[z] += 1
    if any(v >= 2 for v in selfxing_groups.values()):
        selfxing = True
        sx_zhi = [k for k, v in selfxing_groups.items() if v >= 2][0]
    
    if "比劫制财" in gong_list:
        ju_type = "反局" if "求财" in yixiang else "正局"
        note = "比劫制财" + ("—想要但不好明抢" if "求财" in yixiang else "—竞争中的自我保护")
    elif "食伤生财" in gong_list:
        ju_type = "正局" if "求财" in yixiang or "想输出" in yixiang else "正局偏反"
        note = "食伤生财" + "—用本事换钱，路径清晰"
    elif "化杀生印" in gong_list:
        ju_type = "正局"
        note = "化杀生印" + "—压力化资源，能扛事也能成事"
    else:
        ju_type = "不明"
        note = "做功模式不明朗"
    
    if selfxing:
        ju_type += "·暗局"
        note += f"；内在有自耗（{sx_zhi}{sx_zhi}自刑），表面顺内心卷"
    
    return {"日主意向": yixiang, "做功方向": " ".join(gong_list), "局判定": ju_type, "解读": note}

def yingqi_refined(bazi_str, year):
    """盲派精修应期检测"""
    b = parse_bazi(bazi_str)
    if not b: return []
    dm = b["day_gan"]
    gans = [b["year_gan"], b["month_gan"], b["hour_gan"]]
    zhis = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
    
    liu_gan = gan_list = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
    liu_zhi = zhi_list = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]
    lg = liu_gan[(year-4) % 10]
    lz = liu_zhi[(year-4) % 12]
    
    he_map = {"甲":"己","乙":"庚","丙":"辛","丁":"壬","戊":"癸","己":"甲","庚":"乙","辛":"丙","壬":"丁","癸":"戊"}
    liuhe = {"子":"丑","丑":"子","寅":"亥","卯":"戌","辰":"酉","巳":"申","午":"未","未":"午","申":"巳","酉":"辰","戌":"卯","亥":"寅"}
    liuchong = {"子":"午","丑":"未","寅":"申","卯":"酉","辰":"戌","巳":"亥","午":"子","未":"丑","申":"寅","酉":"卯","戌":"辰","亥":"巳"}
    liuhai = {"子":"未","丑":"午","寅":"巳","卯":"辰","申":"亥","酉":"戌","未":"子","午":"丑","巳":"寅","辰":"卯","亥":"申","戌":"酉"}
    sanhe_groups = [{"申","子","辰"},{"亥","卯","未"},{"寅","午","戌"},{"巳","酉","丑"}]
    
    signals = []
    
    # 1. 坏掉阻碍的字（段建业核心）
    for g in gans:
        if he_map.get(g) == lg:
            ss = get_shishen(dm, g)
            if ss in ["七杀","劫财","伤官"]:
                signals.append(f"合走忌神:{lg}合{g}({ss})→阻碍去,应吉")
        if g == lg:
            ss = get_shishen(dm, g)
            if ss in ["正财","偏财","正官"]:
                signals.append(f"喜神到位:{lg}({ss})→好事应期")
    
    # 2. 冲开墓库（辰戌冲/丑未冲）
    for z in zhis:
        if liuchong.get(z) == lz:
            if z in "辰戌丑未":
                signals.append(f"冲开墓库:{lz}冲{z}→墓库开,吉凶看所藏")
            else:
                signals.append(f"地支冲:{lz}冲{z}→宫位动")
    
    # 3. 穿害应期（暗中有变）
    for z in zhis:
        if liuhai.get(z) == lz:
            signals.append(f"穿害应期:{lz}穿{z}→暗中破坏,凶应")
    
    # 4. 三刑开库
    xing_groups = [{"寅","巳","申"},{"丑","戌","未"}]
    for group in xing_groups:
        if lz in group:
            matched = [z for z in zhis if z in group]
            if len(matched) >= 2:
                signals.append(f"三刑应期:{lz}刑{','.join(matched)}→刑开,应事")
    
    # 5. 合动应期
    if liuhe.get(lz) in zhis:
        signals.append(f"合动应期:{lz}合{liuhe[lz]}→关系引动")
    
    # 6. 三合/三会引动
    for group in sanhe_groups:
        if lz in group:
            matched = [z for z in zhis if z in group]
            if len(matched) >= 2:
                signals.append(f"三合引动:{lz}入{'-'.join(list(set(matched)|{lz}))}局→能量到")
    
    # 7. 兜底分析：即使无盲派信号，也要给基础流年信息
    if not signals:
        # 7a. 伏吟检测
        for i, (gz, pillar_name) in enumerate(zip(
            [b["year_gan"]+b["year_zhi"], b["month_gan"]+b["month_zhi"], 
             b["day_gan"]+b["day_zhi"], b["hour_gan"]+b["hour_zhi"]],
            ["年柱","月柱","日柱","时柱"])):
            if gz == lg+lz:
                signals.append(f"伏吟{pillar_name}:{lg}{lz}伏吟→事件反复/停滞感")
        # 7b. 透干分析
        if not signals:
            ss = get_shishen(dm, lg)
            signals.append(f"流年透{ss}:{lg}({ss})透干→事件表象")
        # 7c. 太岁与日主关系
        dm_lg_rel = ""
        if dm == lg: dm_lg_rel = "比肩帮身→有人助"
        elif he_map.get(dm) == lg: dm_lg_rel = "合身→合作/缘分"
        elif {"甲":"庚","乙":"辛","丙":"壬","丁":"癸","戊":"甲","己":"乙","庚":"丙","辛":"丁","壬":"戊","癸":"己"}.get(dm) == lg: dm_lg_rel = "七杀克身→压力"
        if dm_lg_rel and dm_lg_rel not in str(signals):
            signals.append(f"日主关系:{dm_lg_rel}")
        # 7d. 流年地支宫位引动
        for z, pillar_name in zip(zhis, ["年柱","月柱","日柱","时柱"]):
            if z == lz:
                guiwei = {"年柱":"祖上/根基","月柱":"事业/父母","日柱":"婚姻/自身","时柱":"子女/投资"}
                signals.append(f"宫位引动:{pillar_name}={guiwei.get(pillar_name,'')}→该领域有变")
    
    return signals if signals else ["此年无明确盲派应期信号"]

# ===== 月级应期系统（P0升级：年→月精度）=====

def get_month_gan(year_gan, month_zhi):
    """五虎遁求月干
    甲己之年丙作首，乙庚之岁戊为头
    丙辛必定寻庚起，丁壬壬位顺行流
    戊癸何方发，甲寅之上好追求
    """
    # 寅=1,卯=2,辰=3,巳=4,午=5,未=6,申=7,酉=8,戌=9,亥=10,子=11,丑=12
    month_num = {"寅":1,"卯":2,"辰":3,"巳":4,"午":5,"未":6,"申":7,"酉":8,"戌":9,"亥":10,"子":11,"丑":12}
    # 年干 → 寅月天干
    yin_gan = {"甲":"丙","乙":"戊","丙":"庚","丁":"壬","戊":"甲",
               "己":"丙","庚":"戊","辛":"庚","壬":"壬","癸":"甲"}
    gan_list = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
    start = yin_gan.get(year_gan, "丙")
    start_idx = gan_list.index(start)
    offset = (month_num.get(month_zhi, 1) - 1) % 10
    return gan_list[(start_idx + offset) % 10]


# ===== 事件类型分类系统（P0升级：模糊→精确）=====

# 十神→具体事件类型映射
TENGOD_EVENTS = {
    "正财":   ["薪资调整", "稳定收入进账", "节约支出", "财务规划"],
    "偏财":   ["意外得财", "投资收益", "生意进账", "大额支出", "借贷往来"],
    "正官":   ["升职加薪", "考核通过", "获得认可", "规则约束", "官方文件"],
    "七杀":   ["跳槽变动", "竞争上岗", "突发压力", "权威冲突", "健康危机"],
    "正印":   ["学习考证", "文书合同签署", "长辈帮助", "房产事宜", "名誉提升"],
    "偏印":   ["技能突破", "冷门机会", "非主流收入", "神秘/宗教兴趣"],
    "食神":   ["创意落地", "子女喜事", "吃喝应酬", "技术成果", "表达成功"],
    "伤官":   ["辞职/离职", "口舌是非", "维权抗争", "名声受损", "创新突破"],
    "比肩":   ["朋友合作", "团队协作", "同行竞争", "人脉拓展", "并肩作战"],
    "劫财":   ["破财损财", "合伙纠纷", "朋友借贷", "资源争夺", "竞争失利"],
}

# 信号类型→事件性质映射
SIGNAL_EVENT_NATURE = {
    "冲":     {"性质":"突发/打破", "吉凶倾向":"中性偏凶", "说明":"容易出意料之外的事"},
    "合":     {"性质":"关系锁定/达成", "吉凶倾向":"中性偏吉", "说明":"合作/姻缘/项目落地"},
    "自刑":   {"性质":"内耗/纠结", "吉凶倾向":"凶", "说明":"自己跟自己过不去"},
    "三刑":   {"性质":"刑开应事/纠纷", "吉凶倾向":"凶", "说明":"法律/口舌/人事纠纷"},
    "穿害":   {"性质":"暗中破坏/慢性损耗", "吉凶倾向":"凶", "说明":"小人/背后捅刀/慢性病"},
    "伏吟":   {"性质":"重复/停滞", "吉凶倾向":"中性", "说明":"原地踏步/同一事件反复"},
    "三合":   {"性质":"三方能量汇聚", "吉凶倾向":"偏吉", "说明":"新助力/新资源/新方向"},
    "值太岁": {"性质":"能量集中释放", "吉凶倾向":"中性", "说明":"该年主题在此月兑现"},
}

# 宫位→领域事件映射
PILLAR_SPECIFIC_EVENTS = {
    "year": ["公司层面变动", "长辈健康/事务", "大环境政策影响", "远距离事务"],
    "month": ["职场变动", "父母事务", "社交圈变化", "工作环境变动", "直接上级关系"],
    "day": ["自身健康", "婚姻/感情事件", "核心决策", "自我认知变化"],
    "hour": ["子女事务", "投资/项目结果", "下属变动", "晚年规划", "远行/位移"],
}

# 墓库冲→具体事件
MUKU_CHONG_EVENTS = {
    "辰": "水库→财务/资源池变动,资金进出频繁",
    "戌": "火库→事业/权力/健康,组织变动或身体警报",
    "丑": "金库→金属/机械/投资/法律文书变动",
    "未": "木库→房产/仓储/家宅变动",
}


def classify_month_events(bazi_str, year, month_name, signals, triggered_pillars, 
                            month_gan, month_zhi, event_tendency=""):
    """将月级应期信号分类为具体事件类型
    
    返回: [(事件类型, 置信度0-1, 事件说明, 吉凶倾向), ...]
    """
    pb = parse_bazi(bazi_str)
    if not pb:
        return []
    dm = pb["day_gan"]
    month_ss = get_shishen(dm, month_gan)
    
    events = []
    signal_text = "\n".join(signals)
    
    # ---- 事件类型判定规则（按优先级）----
    
    # 规则1: 墓库冲 → 财务/事业重大事件
    if "墓库" in signal_text:
        # 通用墓库冲检测：信号中可能包含"冲year辰"/"冲day辰"等,需要柔性匹配
        bazi_zhi = [pb["year_zhi"], pb["month_zhi"], pb["day_zhi"], pb["hour_zhi"]]
        for z in bazi_zhi:
            if z in MUKU_CHONG_EVENTS:
                # 在signals中找"冲"后面任意字符再跟地支z的模式
                import re
                if any(re.search(rf"冲.+{z}", s) and "墓库" in s for s in signals):
                    events.append(("财务/资产变动", 0.9, MUKU_CHONG_EVENTS[z], "中性偏凶"))
                    break
    
    # 规则2: 穿害 → 暗中小人/口舌/慢性损耗
    if "穿害" in signal_text:
        events.append(("人际口舌/暗中损耗", 0.7, "背后小人或慢性问题爆发", "凶"))
    
    # 规则3: 自刑 → 内耗/决策困难/心理消耗 + 财库自刑附加
    if "自刑" in signal_text:
        events.append(("内心消耗/决策困难", 0.8, "自己跟自己较劲,容易失眠焦虑", "凶"))
        # 附加：如果是辰辰自刑（财库自刑）→ 财务决策纠结
        if "辰自刑" in signal_text:
            events.append(("财务决策反复", 0.7, "财库自刑—在钱的问题上反复纠结,想花又不敢花", "中性"))
    
    # 规则4: 三合引动 → 新资源/新合作/新方向
    if "三合引动" in signal_text:
        events.append(("新资源/新助力", 0.8, "外部力量进入,三方能量汇聚", "吉"))
    
    # 规则5: 合动 → 合作/关系锁定
    if "合宫" in signal_text or "合太岁" in signal_text:
        if "冲" not in signal_text:  # 没有对冲信号才认定为合作
            events.append(("合作/关系进展", 0.6, "合为锁定,项目或人际有阶段性成果", "吉"))
    
    # 规则6: 伏吟 → 停滞/重复
    if "伏吟" in signal_text:
        events.append(("事务重复/进度停滞", 0.6, "已在做的事在此月没有突破性进展", "中性"))
    
    # 规则7: 月冲太岁 → 变数大
    if "月冲太岁" in signal_text:
        events.append(("计划外变动", 0.8, "与年初计划冲突的事件发生", "凶"))
    
    # 规则8: 十神主导事件（如果没有更具体的信号）
    if not events:
        # 根据月干十神给出事件范围
        ten_events = TENGOD_EVENTS.get(month_ss, ["一般事务"])
        events.append((ten_events[0], 0.5, f"月{month_ss}引动,此方向有事件", "中性"))
    
    # 规则9: 结合宫位精化事件
    if triggered_pillars:
        for pn in triggered_pillars:
            p_events = PILLAR_SPECIFIC_EVENTS.get(pn, [])
            if p_events and len(events) < 3:
                events.append((p_events[0], 0.4, f"{pn}宫位被引动", "中性"))
    
    # 去重
    seen = set()
    unique_events = []
    for e in events:
        if e[0] not in seen:
            seen.add(e[0])
            unique_events.append(e)
    
    return unique_events[:3]  # 最多3个


def monthly_triggers(bazi_str, year, month_name, liu_nian_gan, liu_nian_zhi, dayun_gan="", dayun_zhi=""):
    """逐月应期检测：单月刑冲合害值 + 十神引动
    
    月支固定序列: 寅卯辰巳午未申酉戌亥子丑
    返回: (信号强度[0-5], 信号描述列表, 引动宫位, 事件倾向)
    """
    pb = parse_bazi(bazi_str)
    if not pb:
        return (0, [], "", "")
    
    dm = pb["day_gan"]
    month_zhi = month_name
    month_gan = get_month_gan(liu_nian_gan, month_zhi)
    
    gans = [pb["year_gan"], pb["month_gan"], pb["day_gan"], pb["hour_gan"]]
    zhis = [pb["year_zhi"], pb["month_zhi"], pb["day_zhi"], pb["hour_zhi"]]
    
    # 刑冲合害表
    liuhe = {"子":"丑","丑":"子","寅":"亥","卯":"戌","辰":"酉","巳":"申",
             "午":"未","未":"午","申":"巳","酉":"辰","戌":"卯","亥":"寅"}
    liuchong = {"子":"午","丑":"未","寅":"申","卯":"酉","辰":"戌","巳":"亥",
                "午":"子","未":"丑","申":"寅","酉":"卯","戌":"辰","亥":"巳"}
    liuhai = {"子":"未","丑":"午","寅":"巳","卯":"辰","申":"亥","酉":"戌",
              "未":"子","午":"丑","巳":"寅","辰":"卯","亥":"申","戌":"酉"}
    sanhe_groups = [{"申","子","辰"},{"亥","卯","未"},{"寅","午","戌"},{"巳","酉","丑"}]
    selfxing = {"辰":"辰","午":"午","酉":"酉","亥":"亥"}
    
    # 宫位名称映射
    guiwei_names = {"year":"年柱·祖上/根基/大环境","month":"月柱·事业/父母/社交",
                    "day":"日柱·自身/婚姻/核心","hour":"时柱·子女/投资/晚年"}
    guiwei_short = {"year":"年","month":"月","day":"日","hour":"时"}
    
    signals = []
    triggered_pillars = set()
    event_tendency = ""
    strength = 0
    
    # 宫位索引
    pillar_idx = {"year":0, "month":1, "day":2, "hour":3}
    pillar_names = ["year","month","day","hour"]
    
    # ---- 检测月支 vs 原局四柱 ----
    for pn in pillar_names:
        pz = zhis[pillar_idx[pn]]
        pg = gans[pillar_idx[pn]]
        
        # 1. 月支 冲 原局地支 → 宫位被引动（强度高）
        if liuchong.get(month_zhi) == pz or liuchong.get(pz) == month_zhi:
            ss = get_shishen(dm, pg)
            if pz in "辰戌丑未":
                signals.append(f"月冲墓库:月{month_zhi}冲{pn}{pz}({ss})→墓库被掀,吉凶看所藏")
            else:
                signals.append(f"月冲宫:月{month_zhi}冲{pn}{pz}({ss})→宫位震荡")
            triggered_pillars.add(pn)
            strength += 2
        
        # 2. 月支 合 原局地支 → 关系引动
        if liuhe.get(month_zhi) == pz or liuhe.get(pz) == month_zhi:
            ss = get_shishen(dm, pg)
            signals.append(f"月合宫:月{month_zhi}合{pn}{pz}({ss})→关系锁定/合作引动")
            triggered_pillars.add(pn)
            strength += 1
        
        # 3. 月支 刑 原局 → 内耗/自刑
        if month_zhi == pz and month_zhi in selfxing:
            signals.append(f"月自刑:月{month_zhi}自刑{selfxing[month_zhi]}→当月自我消耗重")
            triggered_pillars.add(pn)
            strength += 2
        
        # 三刑
        xing_groups = [{"寅","巳","申"},{"丑","戌","未"}]
        for xg in xing_groups:
            if month_zhi in xg and pz in xg and month_zhi != pz:
                signals.append(f"月三刑:{month_zhi}刑{pn}{pz}(三刑)→刑开应事")
                triggered_pillars.add(pn)
                strength += 2
        
        # 4. 月支 害 原局 → 暗中破坏
        if liuhai.get(month_zhi) == pz or liuhai.get(pz) == month_zhi:
            signals.append(f"月穿害:月{month_zhi}害{pn}{pz}→暗中小人/口舌")
            triggered_pillars.add(pn)
            strength += 1
        
        # 5. 月支 值 原局 → 伏吟
        if month_zhi == pz:
            signals.append(f"月伏吟:月{month_zhi}伏吟{pn}→此月该领域重复/停滞感")
            triggered_pillars.add(pn)
            strength += 1
    
    # ---- 月干引动（十神层面）----
    month_ss = get_shishen(dm, month_gan)
    
    # 月干 vs 流年天干 → 干上引动
    if month_gan == liu_nian_gan:
        signals.append(f"月干值年干:{month_gan}({month_ss})当月引动流年能量")
        strength += 1
    
    # 月干 合 原局天干
    tianhe = {"甲":"己","乙":"庚","丙":"辛","丁":"壬","戊":"癸",
              "己":"甲","庚":"乙","辛":"丙","壬":"丁","癸":"戊"}
    for pn in pillar_names:
        pg = gans[pillar_idx[pn]]
        if tianhe.get(month_gan) == pg:
            ss = get_shishen(dm, pg)
            signals.append(f"月干合{pg}({ss})→当月{month_ss}合{pn}星,感应强烈")
            triggered_pillars.add(pn)
            strength += 1
    
    # ---- 三合局检测 ----
    sanhe_triggers = {"申":"辰","子":"辰","亥":"未","卯":"未",
                      "寅":"戌","午":"戌","巳":"丑","酉":"丑"}
    if month_zhi in sanhe_triggers:
        need = sanhe_triggers[month_zhi]
        for pn in pillar_names:
            pz = zhis[pillar_idx[pn]]
            if pz == need and month_zhi != need:
                signals.append(f"三合引动:月{month_zhi}合{pn}{need}→三方能量到")
                triggered_pillars.add(pn)
                strength += 2
    
    # ---- 与流年柱的交互 ----
    if month_zhi == liu_nian_zhi:
        signals.append(f"月值太岁→当月能量集中释放")
        strength += 1
    if liuhe.get(month_zhi) == liu_nian_zhi:
        signals.append(f"月合太岁→当月有阶段性成果/关系锁定")
        strength += 1
    if liuchong.get(month_zhi) == liu_nian_zhi:
        signals.append(f"月冲太岁→当月变数大,忌冲动决策")
        strength += 2
    
    # ---- 与大运的交互 ----
    if dayun_gan and dayun_zhi:
        # 月支 合 大运支
        if liuhe.get(month_zhi) == dayun_zhi or liuhe.get(dayun_zhi) == month_zhi:
            signals.append(f"月合大运:运岁交集,此月大运能量释放")
            strength += 1
        if liuchong.get(month_zhi) == dayun_zhi:
            signals.append(f"月冲大运:大运被当月引动,吉凶应期")
            strength += 2
        # 月干 合 大运干
        if tianhe.get(month_gan) == dayun_gan:
            signals.append(f"月干合大运干→天人感应,此月关键时刻")
            strength += 1
    
    # ---- 事件倾向判定 ----
    if month_ss in ("正财","偏财"):
        event_tendency = "财运"
        signals.append(f"月{month_ss}→当月关注财务/收入/支出")
    elif month_ss in ("正官","七杀"):
        event_tendency = "事业"
        signals.append(f"月{month_ss}→当月关注工作/压力/晋升")
    elif month_ss in ("正印","偏印"):
        event_tendency = "文书/学习/贵人"
        signals.append(f"月{month_ss}→当月关注学习/文书/长辈")
    elif month_ss in ("食神","伤官"):
        event_tendency = "表达/创意/变动"
        signals.append(f"月{month_ss}→当月关注表达/创意/子女/变动")
    elif month_ss in ("比肩","劫财"):
        event_tendency = "人际/竞争"
        signals.append(f"月{month_ss}→当月关注人际/竞争/合伙/破财")
    
    # ---- 季节能量（旺相休囚死）----
    wangxiang = {"寅":"木旺","卯":"木旺","辰":"土旺(水库)",
                 "巳":"火旺","午":"火旺","未":"土旺(火库)",
                 "申":"金旺","酉":"金旺","戌":"土旺(火库)",
                 "亥":"水旺","子":"水旺","丑":"土旺(金库)"}
    if month_zhi in wangxiang:
        signals.append(f"季节能量:{wangxiang[month_zhi]}月")
    
    # 强度上限5
    strength = min(strength, 5)
    return (strength, signals, triggered_pillars, event_tendency)


def yingqi_monthly(bazi_str, year):
    """月级应期：逐月分析全年12个月
    
    返回: [
        {
            "month": "寅",   # 农历月支
            "month_num": 1,   # 序号1-12
            "月干": "甲",
            "月支": "寅",
            "节气区间": "2月4日-3月5日",
            "强度": 0-5,
            "信号": ["信号1","信号2"],
            "引动宫位": {"year","month","day","hour"},
            "事件倾向": "财运/事业/人际...",
            "叙事": "白话描述"
        },
        ...
    ]
    """
    pb = parse_bazi(bazi_str)
    if not pb:
        return []
    
    # 年柱干支
    liu_gan_list = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
    liu_zhi_list = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]
    lg = liu_gan_list[(year-4) % 10]
    lz = liu_zhi_list[(year-4) % 12]
    
    # 大运
    try:
        dy = calc_dayun_from_bazi(bazi_str)
        dy_gan = dy.get("当前大运_gan", "")
        dy_zhi = dy.get("当前大运_zhi", "")
    except:
        dy_gan, dy_zhi = "", ""
    
    # 12个月支（农历顺序：寅为首）
    months_zhi = ["寅","卯","辰","巳","午","未","申","酉","戌","亥","子","丑"]
    # 节气区间
    jieqi_map = {
        "寅":"立春(2/4)~惊蛰(3/5)","卯":"惊蛰(3/5)~清明(4/4)","辰":"清明(4/4)~立夏(5/5)",
        "巳":"立夏(5/5)~芒种(6/5)","午":"芒种(6/5)~小暑(7/6)","未":"小暑(7/6)~立秋(8/7)",
        "申":"立秋(8/7)~白露(9/7)","酉":"白露(9/7)~寒露(10/8)","戌":"寒露(10/8)~立冬(11/7)",
        "亥":"立冬(11/7)~大雪(12/6)","子":"大雪(12/6)~小寒(1/5)","丑":"小寒(1/5)~立春(2/4)"
    }
    
    results = []
    for i, mzhi in enumerate(months_zhi):
        mg = get_month_gan(lg, mzhi)
        strength, signals, triggered, event_type = monthly_triggers(
            bazi_str, year, mzhi, lg, lz, dy_gan, dy_zhi
        )
        
        # 事件类型分类（P0升级）
        classified = classify_month_events(
            bazi_str, year, mzhi, signals, triggered, mg, mzhi, event_type
        )
        event_types = [{"event": e[0], "confidence": e[1], "detail": e[2], "nature": e[3]} 
                       for e in classified]
        
        # 叙事翻译
        narrative = _monthly_narrative_single(
            mzhi, mg, year, lg, lz, 
            get_shishen(pb["day_gan"], mg),
            strength, signals, event_type, event_types
        )
        
        results.append({
            "month": mzhi,
            "月干": mg,
            "月支": mzhi,
            "节气区间": jieqi_map.get(mzhi, ""),
            "强度": strength,
            "信号": signals[:3],  # 最多3条
            "引动宫位": list(triggered),
            "事件倾向": event_type,
            "具体事件": event_types,  # P0升级
            "叙事": narrative
        })
    
    return results


def _monthly_narrative_single(month_zhi, month_gan, year, liu_gan, liu_zhi, 
                                month_shishen, strength, signals, event_type, 
                                specific_events=None):
    """单月叙事翻译（含P0事件类型）"""
    # 级别标签
    level_map = {0:"●平静",1:"○微动",2:"▲变化",3:"★关键",4:"★★重大",5:"★★★转折"}
    level = level_map.get(strength, "普通月")
    
    # 信号精简
    sigs = signals[:2]
    sig_text = "；".join(sigs) if sigs else "无特殊应期信号"
    
    # 月支特征
    month_features = {
        "寅":"春木萌动","卯":"木气最盛","辰":"土旺水库开","巳":"初夏火起",
        "午":"盛夏火旺","未":"土燥火余","申":"金秋初至","酉":"金气最盛",
        "戌":"土收火库","亥":"冬水初生","子":"水气最盛","丑":"土冻金藏"
    }
    feature = month_features.get(month_zhi, "")
    
    # 具体事件（P0升级）
    event_tip = ""
    if specific_events:
        top = specific_events[0]
        confidence = int(top["confidence"] * 100)
        event_tip = f" ▶ 大概率: {top['event']}({top['nature']}, 可信{confidence}%)"
    
    return f"{month_zhi}月({feature})·{level}: {sig_text}{event_tip}"


def yingqi_monthly_narrative(bazi_str, year, name=""):
    """月级应期叙事体输出（完整版）
    
    输出结构：
    - 年度总览
    - 重点月份标红
    - 逐月白话叙事
    """
    monthly = yingqi_monthly(bazi_str, year)
    if not monthly:
        return "排盘失败"
    
    pb = parse_bazi(bazi_str)
    liu_gan_list = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
    liu_zhi_list = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]
    lg = liu_gan_list[(year-4) % 10]
    lz = liu_zhi_list[(year-4) % 12]
    
    # 年度级别
    high_months = [m for m in monthly if m["强度"] >= 3]
    mid_months = [m for m in monthly if m["强度"] == 2]
    total_strength = sum(m["强度"] for m in monthly)
    
    name_tag = f"【{name}】" if name else ""
    output = [f"\n## {name_tag}{year}年({lg}{lz})逐月应期分析\n"]
    output.append(f"年度总览: 此年{len(high_months)}个关键月({', '.join(m['month'] for m in high_months)})"
                  f"，{len(mid_months)}个变化月，全年能量值{total_strength}/60\n")
    
    # 重点月份高亮
    if high_months:
        output.append("### 🔴 重点月份\n")
        for m in high_months:
            month_name = f"{m['月干']}{m['月支']}"
            output.append(f"**{m['month']}月({month_name}—{m['节气区间']})** ⭐ 强度{m['强度']}/5")
            output.append(f"> 事件倾向: {m['事件倾向']}")
            # P0升级: 具体事件类型
            if m.get('具体事件'):
                for ev in m['具体事件'][:2]:
                    conf_pct = int(ev['confidence'] * 100)
                    icon = {"吉":"✅","凶":"⚠️","中性":"➡️","偏吉":"✅"}.get(ev['nature'], "➡️")
                    output.append(f"> {icon} 可能事件: {ev['event']}（可信度{conf_pct}%）")
            for sig in m['信号']:
                output.append(f"> {sig}")
            if m['引动宫位']:
                pillars = [{'year':'年·祖上/根基','month':'月·事业/社交','day':'日·自身/婚姻','hour':'时·子女/投资'}.get(p,p) for p in m['引动宫位']]
                output.append(f"> 引动宫位: {'、'.join(pillars)}")
            output.append("")
    
    # 逐月概览（P0升级：增加具体事件列）
    output.append("### 逐月概览\n")
    output.append(f"| 月份 | 干支 | 节气 | 等级 | 事件倾向 | 具体事件 |")
    output.append(f"|:---:|:---:|------|:---:|:--------:|---------|")
    for m in monthly:
        gz = f"{m['月干']}{m['月支']}"
        level = {0:"●平静",1:"○微动",2:"▲变化",3:"★关键",4:"★★重大",5:"★★★转折"}.get(m["强度"],"○")
        jq = m["节气区间"].replace("~","→")
        evt = m["事件倾向"] if m["事件倾向"] else "—"
        # 具体事件
        spec_evt = ""
        if m.get('具体事件'):
            spec_evt = m['具体事件'][0]['event'][:12]
        output.append(f"| {m['month']}月 | {gz} | {jq} | {level} | {evt} | {spec_evt} |")
    
    output.append("")
    
    # 全年节奏总结
    if high_months:
        hm_str = "、".join([f"{m['month']}月({m['事件倾向']})" for m in high_months])
        output.append(f"**年度节奏**: 重点关注{hm_str}。")
        if any("财运" in m['事件倾向'] for m in high_months):
            output.append("💰 财运信号强——重大收支注意时机。")
        if any("事业" in m['事件倾向'] for m in high_months):
            output.append("💼 事业信号强——升职/转岗/压力集中期。")
        if any("人际" in m['事件倾向'] for m in high_months):
            output.append("🤝 人际信号强——合伙/竞争/交际密集期。")
    output.append("")
    
    return "\n".join(output)


# 辅助：从现有数据推算大运（简化版）
def calc_dayun_from_bazi(bazi_str, age=49):
    """从八字推算当前大运（简化版，仅用于岁运评分）
    基于年干阴阳和月柱推算大运顺序，age估算起运
    """
    pb = parse_bazi(bazi_str)
    if not pb:
        return {}
    year_gan = pb["year_gan"]
    month_gan = pb["month_gan"]
    month_zhi = pb["month_zhi"]
    is_yang = year_gan in "甲丙戊庚壬"
    # 默认男命
    forward = is_yang
    dayun_list = []
    for i in range(8):
        if forward:
            dg = gan_step(month_gan, i + 1)
            dz = zhi_step(month_zhi, i + 1)
        else:
            dg = gan_step(month_gan, -(i + 1))
            dz = zhi_step(month_zhi, -(i + 1))
        dayun_list.append(f"{dg}{dz}")
    # 起运年龄估算（简化：一律3岁起运）
    qiyun = 3
    # 当前年龄对应的第几步大运
    step = (age - qiyun) // 10
    if 0 <= step < len(dayun_list):
        cur = dayun_list[step]
        return {
            "起运年龄": qiyun,
            "大运列表": dayun_list,
            "当前大运": cur,
            "当前大运_gan": cur[0],
            "当前大运_zhi": cur[1],
        }
    return {"当前大运_gan": "", "当前大运_zhi": ""}


# ===== 十六、盖头截脚精修——三年分断+逐月喜忌联动 =====
# 逐月喜忌简表（金不换断精华）
ZHUKUAI_XIJI = {
    "甲": {"申":"喜火","酉":"喜火","戌":"喜水","亥":"喜火","子":"火土","丑":"喜火"},
    "乙": {"申":"喜火","酉":"喜火","戌":"喜火","亥":"喜火","子":"喜火","丑":"喜火"},
    "丙": {"申":"喜火","酉":"喜火","戌":"喜火","亥":"喜火","子":"喜火","丑":"喜火"},
    "丁": {"申":"喜火","酉":"喜火","戌":"喜火","亥":"喜火","子":"喜火","丑":"喜火"},
    "戊": {"申":"喜火","酉":"喜火","戌":"喜火","亥":"喜火","子":"喜水","丑":"喜火"},
    "己": {"申":"喜火","酉":"喜火","戌":"喜火","亥":"喜火","子":"喜水","丑":"喜火"},
    "庚": {"申":"喜火","酉":"喜火","戌":"喜火","亥":"喜火","子":"喜火","丑":"喜火"},
    "辛": {"申":"喜火","酉":"喜火","戌":"喜火","亥":"喜火","子":"喜火","丑":"喜火"},
    "壬": {"申":"喜火","酉":"喜火","戌":"喜火","亥":"喜火","子":"喜火","丑":"喜火"},
    "癸": {"申":"喜火","酉":"喜火","戌":"喜火","亥":"喜火","子":"喜火","丑":"喜火"},
}

def dayun_3year(bazi_str, dayun_gan, dayun_zhi):
    """
    大运三年分断精修版
    盖头：天干克地支 → 前3年天干力弱（被地支泄），后7年地支力强
    截脚：地支克天干 → 前7年天干有气，后3年地支不载
    天覆：天干生地支 → 10年通顺
    地载：地支生天干 → 10年通顺
    """
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    mzhi = b["month_zhi"]
    gans = [b["year_gan"], b["month_gan"], b["hour_gan"]]
    zhis = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
    
    gan_wx = GAN_WX.get(dayun_gan, "")
    zhi_wx = ZHI_WX.get(dayun_zhi, "")
    
    # 喜用五行判定（从月令和十神推断）
    xiyong = "火"  # 默认（安全值）
    dm_wx = GAN_WX.get(dm, "")
    sheng_map = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
    ke_map = {"木":"土","火":"金","土":"水","金":"木","水":"火"}
    month_wx = ZHI_WX.get(mzhi, "")
    
    if month_wx == dm_wx:  # 月令同日主→建禄/帝旺→喜克泄
        xiyong = ke_map.get(dm_wx, "土")
    elif sheng_map.get(month_wx) == dm_wx:  # 月令生日主→印月→身旺→喜克泄耗
        xiyong = ke_map.get(dm_wx, "土")
    elif ke_map.get(month_wx) == dm_wx:  # 月令克日主→官杀月→身弱→喜印比
        xiyong = {v:k for k,v in sheng_map.items()}.get(dm_wx, "水")  # 生我者为印
    elif sheng_map.get(dm_wx) == month_wx:  # 日主生月令→食伤月→泄身→身弱→喜印比
        xiyong = {v:k for k,v in sheng_map.items()}.get(dm_wx, "水")
    elif ke_map.get(dm_wx) == month_wx:  # 日主克月令→财月→需综合判断
        xiyong = sheng_map.get(dm_wx, "木")
    
    # 盖头截脚判定（独立计算干支五行关系）
    wu = {"甲":"木","乙":"木","丙":"火","丁":"火","戊":"土","己":"土","庚":"金","辛":"金","壬":"水","癸":"水"}
    ke_map2 = {"木":"土","火":"金","土":"水","金":"木","水":"火"}
    gan_wx2 = wu.get(dayun_gan, "")
    zhi_wx2 = ZHI_WX.get(dayun_zhi, "")
    
    if gan_wx2 != zhi_wx2:
        if ke_map2.get(gan_wx2) == zhi_wx2:
            gj_simple = f"盖头（{dayun_gan}{gan_wx2}克{dayun_zhi}{zhi_wx2}）→天干力弱"
        elif ke_map2.get(zhi_wx2) == gan_wx2:
            gj_simple = f"截脚（{dayun_zhi}{zhi_wx2}克{dayun_gan}{gan_wx2}）→地支不载"
        elif ke_map2.get(gan_wx2) == zhi_wx2 or ke_map2.get(zhi_wx2) == gan_wx2:
            gj_simple = "干支相克"
        else:
            # 相生关系
            sheng_map2 = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
            if sheng_map2.get(gan_wx2) == zhi_wx2:
                gj_simple = f"天覆（{dayun_gan}{gan_wx2}生{dayun_zhi}{zhi_wx2}）→10年通顺"
            elif sheng_map2.get(zhi_wx2) == gan_wx2:
                gj_simple = f"地载（{dayun_zhi}{zhi_wx2}生{dayun_gan}{gan_wx2}）→10年有力"
            else:
                gj_simple = f"干支不同行（{gan_wx2}{zhi_wx2}）→各管各的"
    else:
        gj_simple = f"干支同一五行（{gan_wx2}）→稳定持续"
    
    gj = gaitou_jiejiao(dayun_gan, dayun_zhi, xiyong)
    
    segments = []
    ten_year_detail = []
    
    if "盖头" in gj_simple:
        # 天干克地支 — 天干被地支泄，力量弱
        segments = [
            f"第1-3年(入运初期): {dayun_gan}天干虚浮被{dayun_zhi}地支盖住,吉凶减半",
            f"第4-7年(运中): {dayun_zhi}地支力量渐显,宫位开始发挥作用",
            f"第8-10年(运末): {dayun_zhi}地支全力显现,此运最关键的3年"
        ]
        ten_year_detail = [
            f"前3年:{dayun_gan}主导但力弱(盖头),事倍功半",
            f"中4年:由{dayun_gan}转{dayun_zhi},过渡期,看流年",
            f"后3年:{dayun_zhi}主导,全力落实"
        ]
    elif "截脚" in gj_simple:
        # 地支克天干 — 地支不载天干
        segments = [
            f"第1-4年(入运初期): {dayun_gan}天干尚有根气,仍可发力",
            f"第5-7年(运中): {dayun_gan}力量开始衰减,{dayun_zhi}克力渐强",
            f"第8-10年(运末): 截脚显现,{dayun_gan}无力→此运最差的3年"
        ]
        ten_year_detail = [
            f"前4年:{dayun_gan}有根气,能发力但已受压",
            f"中3年:过渡——{dayun_gan}减力,{dayun_zhi}克制渐显",
            f"后3年:截脚效应→天干无力,事情卡住"
        ]
    elif "倍增" in gj:
        segments = ["10年全程: 天覆地载,上下同力,此运是人生重要时期"]
        ten_year_detail = ["前3年{dayun_gan}先行→中4年{dayun_gan}+{dayun_zhi}同力→后3年{dayun_zhi}落实成果"]
    else:
        segments = [f"10年全程: 干支同五行({gan_wx}),稳定持续"]
        ten_year_detail = [f"前3年{dayun_gan}先动→中4年稳健→后3年{dayun_zhi}收尾"]
    
    # 判断该大运对喜用的影响
    gan_is_xi = "吉运" if (gan_wx == xiyong) else ("平运" if gan_wx in ["木","火","土","金","水"] else "未知")
    zhi_is_xi = "吉运" if (zhi_wx == xiyong) else ("平运" if zhi_wx in ["木","火","土","金","水"] else "未知")
    
    if gan_is_xi == "吉运" and zhi_is_xi == "吉运":
        whole = f"此运干支均为喜用({xiyong})→整体吉"
    elif gan_is_xi == "吉运" and zhi_is_xi != "吉运":
        whole = f"天干吉({dayun_gan}={xiyong})但地支不助→前段好,后段转平"
    elif gan_is_xi != "吉运" and zhi_is_xi == "吉运":
        whole = f"地支吉({dayun_zhi}={xiyong})但天干不助→前段平,后段转好"
    else:
        whole = f"此运干支均不助喜用→整体偏阻"
    
    return {
        "盖头截脚": gj,
        "干支关系": gj_simple,
        "逐月喜忌参考": ZHUKUAI_XIJI.get(dm, {}).get(mzhi, "通用"),
        "三年分断": segments,
        "十年细目": ten_year_detail,
        "整体评价": whole
    }
def log_review(bazi_str, prediction, actual_event, correct):
    """记录翻车/正确案例"""
    entry = {
        "bazi": bazi_str,
        "prediction": prediction,
        "actual": actual_event,
        "correct": correct,
        "timestamp": __import__("datetime").datetime.now().isoformat()
    }
    REVIEW_LOG.append(entry)
    with open(REVIEW_PATH, 'w') as f:
        json.dump(REVIEW_LOG, f, ensure_ascii=False, indent=2)
    return entry

def get_review_stats():
    """复盘统计"""
    total = len(REVIEW_LOG)
    if total == 0:
        return {"total": 0, "正确率": "无数据"}
    correct = sum(1 for r in REVIEW_LOG if r.get("correct"))
    return {"total": total, "正确率": f"{correct*100//total}%", "正确": correct, "翻车": total-correct}

# ===== 八、十神类象查询 =====
def shishen_leixiang(shishen_name):
    """查询十神对应的人事类象"""
    if shishen_name in SHISHEN_TABLE:
        return SHISHEN_TABLE[shishen_name]
    return {"人事": [], "事物": [], "六亲": []}

# ===== 六、主引擎 =====
def auto_prediction(bazi_str, result, name="", case_id=""):
    """自动记录预测到回测系统（v2：特征驱动+三要素格式）"""
    if not PREDICT_AVAILABLE or not bazi_str:
        return None

    score = result.get("格局评分", {}).get("score", 0)
    level = result.get("格局评分", {}).get("level", "未知")
    confidence = result.get("置信度", "中")

    cat_map = {"高": 0.85, "较高": 0.7, "中": 0.55, "低": 0.35}
    conf_val = cat_map.get(confidence, 0.5)

    # === v2：特征驱动预测 ===
    from datetime import datetime, timedelta

    # 解析八字特征
    parsed = parse_bazi(bazi_str)
    if not parsed:
        return None

    gans = parsed["天干"]
    zhis = parsed["地支"]
    dm = gans[2]  # 日干

    # 获取格局信息
    is_cong = result.get("格局评分", {}).get("details", [""])[0]
    cong_flag = "从格" in is_cong or "从" in is_cong[:4]

    # 获取强弱
    sw = is_shenwang(bazi_str)
    qiangruo = sw.get("强弱", "中")
    root_type = sw.get("根类型", "无根")

    # 获取调候
    th = result.get("调候", "无")
    th_str = th if isinstance(th, str) else th.get("调候", "")

    # 获取做功
    zuogong = sushi_zuogong(bazi_str)
    gong_list = zuogong.get("做功", [])

    # 获取财星
    caixin = cai_tag(bazi_str)
    caixiang = caixin.get("偏财", "无")

    # 获取家里家外
    jiali = sushi_jialiwai(bazi_str)
    jiali_mode = jiali.get("模式", "未定")

    # --- 生成预测 ---
    pred_parts = []

    # 1) 格局定调（用特征，不用评分等级词）
    if cong_flag:
        pred_parts.append("从格之命，顺势而为")
    elif score >= 4.2 and qiangruo in ("身强", "强"):
        pred_parts.append("身强能扛，格局有成")
    elif score >= 4.0:
        pred_parts.append("格局中上，有根基")
    elif score >= 3.5:
        pred_parts.append("普通格局，大运定成败")
    else:
        pred_parts.append("格局偏低，需运来扶")

    # 2) 应期——调用 yingqi_refined 看未来一年
    this_year = datetime.now().year
    try:
        yq = yingqi_refined(bazi_str, this_year)
        if yq and yq.get("signals"):
            signals = yq["signals"]
            top_sig = signals[0] if isinstance(signals, list) else list(signals.values())[0] if isinstance(signals, dict) else ""
            if top_sig:
                pred_parts.append(f"{this_year}年应期：{top_sig}")
    except Exception:
        pass

    # 3) 特殊特征翻译（硬编码规则匹配常见八字特征）
    for zi_zhi in ["辰", "午", "酉", "亥"]:
        zhi_count = str(zhis).count(zi_zhi)
        if zi_zhi == "辰" and zhi_count >= 2:
            pred_parts.append("自刑：在脑子里已经跟自己过不去很多次了")
            break
        elif zi_zhi == "午" and zhi_count >= 2:
            pred_parts.append("自刑：爆发后否定，明明可以更好被情绪拖住")
            break

    # 偏财透干检测（通过十神判定）
    hour_ss = get_shishen(dm, gans[3])
    if "偏财" in hour_ss:
        pred_parts.append("感情：行动式表达——做了但不说")

    # 甲木+午月（比肩坐午火）
    if dm == "甲" and "午" in str(zhis):
        pred_parts.append("表达：话到嘴边过三关")

    # 从格+有火（调候）
    if cong_flag and ("火" in str(gans) or "巳" in str(zhis) or "午" in str(zhis)):
        pred_parts.append("调候：冬生有火，有贵人灯")
    elif "无水" in th_str or ("夏" in str(zhis) and "水" not in str(gans)):
        pred_parts.append("调候：缺水，需补水润局")

    # 家里家外模式
    if "创业" in jiali_mode:
        pred_parts.append("路径：适合自己干")
    elif "打工" in jiali_mode:
        pred_parts.append("路径：适合在体制/大机构")
    elif "混合" in jiali_mode:
        pred_parts.append("路径：混合型，灵活切换")

    # 4) 财星/事业
    if caixiang in ("为财所累", "待用潜财"):
        if jiali_mode and "创业" in jiali_mode:
            pred_parts.append("事业：创业型，财运待启")
        else:
            pred_parts.append("事业：稳中求财，不宜冒进")
    elif caixiang in ("财旺身弱",):
        pred_parts.append("事业：财旺但扛力不足，需借力")

    # 5) 做功
    for g in gong_list:
        if g == "化杀生印":
            pred_parts.append("模式：压力化资源，能扛事")
            break
        elif g == "食伤生财":
            pred_parts.append("模式：以技能/创意生财")
            break
        elif g == "比劫制财":
            pred_parts.append("模式：合作中有竞争")
            break

    # 6) 相似案例
    similar = result.get("相似案例", [])
    if similar:
        top = similar[0]["案例"]
        pred_parts.append(f"参考：{top}")

    # 7) 调候提示（关键时才加）
    if th_str and ("无水" in th_str or "无火" in th_str):
        pred_parts.append(f"注意：{th_str}")

    # 组装预测词
    pred_text = " · ".join(pred_parts) if pred_parts else f"格局{level}，评分{score}"

    # 记录预测（1年期限 + 3个月短期锚点）
    deadline = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
    short_deadline = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

    pid = add_prediction(
        bazi=bazi_str,
        name=name or "自动分析",
        category="综合",
        prediction=pred_text,
        deadline=deadline,
        confidence=conf_val,
        tags=[level, confidence, short_deadline],
        source_case_id=case_id
    )
    return pid

def prediction_feedback(pred_id, actual_result, is_accurate=True):
    """修正闭环：不准的预测反馈回引擎"""
    if not PREDICT_AVAILABLE:
        return
    
    status = "✅ 准确的" if is_accurate else "❌ 不准确的"
    verify_prediction(pred_id, status, actual_result)
    
    if not is_accurate:
        # 不准的预测记录到修正日志
        review = load_review_log()
        record = {
            "pred_id": pred_id,
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "actual": actual_result,
            "adjusted": True
        }
        review.append(record)
        save_review_log(review)

def load_review_log():
    """加载修正日志"""
    if os.path.exists(REVIEW_PATH):
        try:
            with open(REVIEW_PATH, encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_review_log(log):
    """保存修正日志"""
    with open(REVIEW_PATH, 'w') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def backtest_stats():
    """获取回测统计摘要"""
    if not PREDICT_AVAILABLE:
        return {"error": "预测系统未加载"}
    s = get_stats()
    overdue = get_overdue()
    return {
        "total": s["total"],
        "accurate": s["accurate"],
        "semi": s["semi_accurate"],
        "inaccurate": s["inaccurate"],
        "pending": s["pending"],
        "accuracy_pct": round(s["accurate"] / s["total"] * 100, 1) if s["total"] > 0 else 0,
        "overdue": len(overdue),
        "by_category": s["by_category"]
    }

# ===== P1第三模块：六亲分析（父母·子女·兄弟）=====

# 六亲星定位表
LIUQIN_STAR = {
    "父": {"男":{"偏财":"父"}, "女":{"偏财":"父"}},
    "母": {"男":{"正印":"母"}, "女":{"正印":"母"}},
    "子": {"男":{"七杀":"子","正官":"女"}, "女":{"食神":"女","伤官":"子"}},
    "兄弟": {"男":{"比肩":"兄弟","劫财":"姐妹"}, "女":{"比肩":"姐妹","劫财":"兄弟"}},
}

# 宫位定位
LIUQIN_GONG = {
    "年柱": "祖上/父母早年环境",
    "月柱": "父母/兄弟/社交圈",
    "日支": "配偶/自身家庭",
    "时柱": "子女/晚年"
}

# 六亲位置（传统定位）
FUGONG = {"年干":"年支","月干":"月支"}  # 父看偏财在的年/月柱
MUGONG = {"年干":"年支","月干":"月支"}  # 母看正印在的年/月柱
ZINVGONG = "时柱"  # 子女看时柱
XIONGDIGONG = "月柱"  # 兄弟看月柱



def shensha_predictive(bazi_str):
    """精简神煞：只取预测价值最高的6个"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    gans = [b["year_gan"],b["month_gan"],b["day_gan"],b["hour_gan"]]
    dm = b["day_gan"]
    
    result = {}
    
    # 1. 天乙贵人（最强吉星）
    tianyi_map = {"甲":"丑未","乙":"子申","丙":"亥酉","丁":"亥酉","戊":"丑未","己":"子申","庚":"丑未","辛":"午寅","壬":"卯巳","癸":"卯巳"}
    tianyi_zhi = tianyi_map.get(dm,"")
    for z in zhis:
        if z in tianyi_zhi:
            result["天乙贵人"] = f"逢凶化吉，贵人相助（{z}）"
    
    # 2. 桃花（感情/人缘）
    taohua_map = {"申子辰":"酉","寅午戌":"卯","亥卯未":"子","巳酉丑":"午"}
    for key, val in taohua_map.items():
        if all(z in zhis for z in key):
            if val in zhis:
                result["桃花"] = f"人缘佳，异性缘旺（{val}）"
    
    # 3. 驿马（奔波/变动）
    yima_map = {"申子辰":"寅","寅午戌":"申","亥卯未":"巳","巳酉丑":"亥"}
    for key, val in yima_map.items():
        if all(z in zhis for z in key):
            if val in zhis:
                result["驿马"] = "奔波劳碌，多动少静"
    
    # 4. 羊刃（性格刚烈）
    yangren = {"甲":"卯","乙":"寅","丙":"午","丁":"巳","戊":"午","己":"巳","庚":"酉","辛":"申","壬":"子","癸":"亥"}
    yr_zhi = yangren.get(dm,"")
    if yr_zhi in zhis:
        result["羊刃"] = f"性格刚烈，不服输（{yr_zhi}）"
    
    # 5. 华盖（孤独/艺术）
    huagai = {"申子辰":"辰","寅午戌":"戌","亥卯未":"未","巳酉丑":"丑"}
    for key, val in huagai.items():
        if all(z in zhis for z in key):
            if val in zhis:
                result["华盖"] = "孤独感强，有艺术天赋"
    
    # 6. 孤辰寡宿
    guchen_map = {"亥子丑":"寅","寅卯辰":"巳","巳午未":"申","申酉戌":"亥"}
    guasu_map = {"亥子丑":"戌","寅卯辰":"丑","巳午未":"辰","申酉戌":"未"}
    nz = b["year_zhi"]
    for key, val in guchen_map.items():
        if nz in key and val in zhis:
            result["孤辰"] = "性格孤僻，不善社交"
    for key, val in guasu_map.items():
        if nz in key and val in zhis:
            result["寡宿"] = "喜欢独处，晚婚倾向"
    
    return result


def yingqi_accuracy_test():
    from pathlib import Path
    """快速流年验证：用10条有标签案例测试应期准确率"""
    import json, re
    case_path = Path(__file__).parent / "case_index.json"
    if not case_path.exists(): return "案例库不存在"
    
    data = json.loads(case_path.read_text())
    labeled = []
    for case in data:
        m = re.match(r'C_(\w+)_\d+_(.+)', case.get('name',''))
        if m:
            labeled.append({'bazi':case['bazi'],'cat':m.group(1),'label':m.group(2)})
    
    # 只测婚姻类（标签最明确）
    marriage = [l for l in labeled if l['cat']=='婚姻']
    results = []
    for item in marriage[:8]:
        m = marriage_analyze(item['bazi'])
        tag = m.get('标签','')
        label = item['label']
        # 粗糙匹配
        match = any(kw in tag for kw in ['波折','多婚','混杂','重重','多变'])
        expected_match = any(kw in label for kw in ['多婚','夫妻不和','孤独'])
        ok = match == expected_match
        results.append(ok)
    
    acc = sum(results)/len(results) if results else 0
    return {"样本": len(results), "准确": sum(results), "准确率": round(acc,3)}

def liuqin_fumu(bazi_str, dayun_gan="", dayun_zhi=""):
    """父母分析：父看偏财，母看正印
    返回: {父: {存在, 位置, 强旺, 关系, 叙事}, 母: {...}}
    """
    pb = parse_bazi(bazi_str)
    if not pb:
        return {}
    dm = pb["day_gan"]
    gans = [("year", pb["year_gan"]), ("month", pb["month_gan"]), 
            ("day", pb["day_gan"]), ("hour", pb["hour_gan"])]
    zhis = [("year", pb["year_zhi"]), ("month", pb["month_zhi"]), 
            ("day", pb["day_zhi"]), ("hour", pb["hour_zhi"])]
    
    # 藏干表
    CANGAN = {"子":"癸","丑":"己癸辛","寅":"甲丙戊","卯":"乙","辰":"戊乙癸",
              "巳":"丙庚戊","午":"丁己","未":"己丁乙","申":"庚壬戊",
              "酉":"辛","戌":"戊辛丁","亥":"壬甲"}
    
    result = {}
    
    # ---- 父：偏财 ----
    fu_info = {"星": "偏财", "状况": "", "位置": "", "强弱": "", "叙事": ""}
    fu_gan = None
    fu_zhi = None
    
    # 查找偏财在天干
    for pos, g in gans:
        if get_shishen(dm, g) == "偏财":
            fu_gan = g
            fu_info["位置"] += f"天干{pos}干({g}) "
            break
    
    # 查找偏财在地支藏干
    for pos, z in zhis:
        cg = CANGAN.get(z, "")
        for c in cg:
            if get_shishen(dm, c) == "偏财":
                fu_zhi = z
                fu_info["位置"] += f"地支{pos}支藏({z}藏{c})"
                break
        if fu_zhi:
            break
    
    if fu_gan or fu_zhi:
        fu_info["状况"] = "父亲星存在"
        if fu_gan:
            fu_info["强弱"] = "透干有力" 
        elif fu_zhi:
            fu_info["强弱"] = "藏支不显"
        # 叙事
        cai_ss = get_shishen(dm, "戊") if "戊" in f"{fu_gan}{fu_zhi}" else get_shishen(dm, fu_gan or "戊")
        if "偏财" in str(fu_info):
            fu_info["叙事"] = "偏财透干父爱是行动式的——给最好的但不一定说出口。他不靠嘴皮子表达，是靠做、靠给、靠扛。"
        if "藏" in fu_info["强弱"]:
            fu_info["叙事"] += "父星藏而不透，父亲在家庭中话不多、存在感不强，但他的支持是背后型的。"
    else:
        fu_info["状况"] = "原局无明财星"
        fu_info["叙事"] = "命局无偏财透出，父亲缘分较浅或早年不在身边。需从大运流年找父星应期。"
    
    result["父"] = fu_info
    
    # ---- 母：正印 ----
    mu_info = {"星": "正印", "状况": "", "位置": "", "强弱": "", "叙事": ""}
    for pos, g in gans:
        if get_shishen(dm, g) == "正印":
            mu_info["位置"] += f"天干{pos}干({g}) "
            mu_info["状况"] = "母亲星存在"
            mu_info["强弱"] = "透干"
    
    for pos, z in zhis:
        cg = CANGAN.get(z, "")
        for c in cg:
            if get_shishen(dm, c) == "正印":
                if not mu_info["位置"]:
                    mu_info["位置"] = f"地支{pos}支藏({z}藏{c})"
                    mu_info["状况"] = "母亲星存在"
                    mu_info["强弱"] = "藏支"
    
    if not mu_info["位置"]:
        mu_info["状况"] = "原局无正印"
        mu_info["叙事"] = "命局无正印透出，母亲在命主生命中不显山露水。她的付出是幕后的——不是没做，是做了但没被发现。"
    else:
        mu_info["叙事"] = f"母星{'透干' if mu_info['强弱']=='透干' else '藏支'}，{'母亲是家里的精神支撑' if mu_info['强弱']=='透干' else '母亲的付出是润物细无声型——不声张但一直在'}。"
        
        # 母星被冲/刑检测
        for pos, z in zhis:
            if mu_info["位置"] and pos in mu_info["位置"]:
                cg = CANGAN.get(z, "")
                if "癸" in cg:
                    # 正印在辰中（辰是水库也是土）
                    mu_info["叙事"] += "母星藏于辰中（土克水），母亲的被家庭事务压着——她的付出很多时候是被动的操劳而不是主动的选择。"
    
    result["母"] = mu_info
    
    return result


def liuqin_zinv(bazi_str, age=None):
    """子女分析：时柱为子女宫，官杀为子星（男命）
    
    两套逻辑：
    - age>=45 且原局无官杀 → 看"有无/早晚"
    - age<45 或原局有官杀 → 看"相处模式/关系质量"
    返回: {子女: {状况, 宫位状态, 叙事}}
    """
    pb = parse_bazi(bazi_str)
    if not pb:
        return {}
    dm = pb["day_gan"]
    sg = pb["hour_gan"]
    sz = pb["hour_zhi"]
    
    CANGAN = {"子":"癸","丑":"己癸辛","寅":"甲丙戊","卯":"乙","辰":"戊乙癸",
              "巳":"丙庚戊","午":"丁己","未":"己丁乙","申":"庚壬戊",
              "酉":"辛","戌":"戊辛丁","亥":"壬甲"}
    
    result = {"子女": {}}
    
    # 时柱为子女宫
    gong_condition = "正常"
    liuchong = {"子":"午","丑":"未","寅":"申","卯":"酉","辰":"戌","巳":"亥",
                "午":"子","未":"丑","申":"寅","酉":"卯","戌":"辰","亥":"巳"}
    for z_key, z_val in [("year", pb["year_zhi"]), ("month", pb["month_zhi"]), ("day", pb["day_zhi"])]:
        if liuchong.get(sz) == z_val:
            gong_condition = "冲"
            break
    
    # 查官杀（男命子女星）— 原局天干 + 时支藏干
    zinv_gan = None
    zinv_zhi = None
    all_gans = [pb["year_gan"], pb["month_gan"], pb["hour_gan"]]
    for g in all_gans:
        if get_shishen(dm, g) in ("七杀", "正官"):
            zinv_gan = g
    cg = CANGAN.get(sz, "")
    for c in cg:
        if get_shishen(dm, c) in ("七杀", "正官"):
            zinv_zhi = c
    
    story = []
    
    # 判断用户年龄段
    # 默认：如果age未提供或age<45，用"相处模式"逻辑
    use_youwu_logic = (age is not None and age >= 45) or (age is None and not zinv_gan and not zinv_zhi)
    
    if use_youwu_logic and not zinv_gan and not zinv_zhi:
        # 45岁以上且原局无官杀 → 看有无
        story.append("时柱无官杀星透藏，子女缘较薄或孩子来得晚。需走官杀大运方有子息。")
    else:
        # 默认：已有子女 → 分析相处模式
        # 时干十神 = 他对孩子的方式
        ss = get_shishen(dm, sg)
        
        if ss == "偏财":
            story.append("时干偏财透——你对孩子的方式是'给最好的物质条件'。你的父爱是买给他、安排好、不让他在钱上吃亏。")
            story.append("但你给的未必是他要的——孩子可能更想要的是你的时间，不是你的钱。")
        elif ss == "正财":
            story.append("时干正财——你对孩子踏实、务实，注重他的教育和未来。但你容易用'有没有用'来衡量一切，包括他的兴趣。")
        elif ss in ("食神", "伤官"):
            story.append(f"时干{ss}——你对孩子的方式像朋友，不端架子，但容易宠。")
        elif ss in ("正印", "偏印"):
            story.append(f"时干{ss}——你对孩子保护欲强，事事操心，但容易替他做太多。")
        elif ss in ("正官", "七杀"):
            story.append(f"时干{ss}——你对孩子要求高，规矩严，是严父类型。")
        elif ss in ("比肩", "劫财"):
            story.append(f"时干{ss}——你跟孩子处得像兄弟，平等、没架子，但少了点父亲的威严。")
        else:
            story.append(f"时干{ss}——你对孩子有自己的方式，不随大流。")
        
        # 时支藏干 → 心里藏着的另一面
        cg_list = list(CANGAN.get(sz, ""))
        for c in cg_list:
            css = get_shishen(dm, c)
            if css == "正印" and ss != "正印":
                story.append("但时支藏正印——你心里对孩子其实很柔软，只是没表现出来。")
                break
            if css == "劫财" and ss != "劫财":
                story.append("但时支藏劫财——你对孩子有亏欠感，总想补偿。")
                break
    
    # 宫位冲
    if gong_condition == "冲":
        story.append("时柱被冲——孩子可能远行/留学/不在身边，或你们之间有时差（物理或心理上的）。")
    
    result["子女"] = {
        "状况": "子女星" + ("透干" if zinv_gan else "藏支" if zinv_zhi else "隐"),
        "宫位": gong_condition,
        "叙事": " ".join(story)
    }
    
    return result


def liuqin_xiongdi(bazi_str):
    """兄弟/朋友分析：月柱为兄弟宫，比劫为兄弟星
    """
    pb = parse_bazi(bazi_str)
    if not pb:
        return {}
    dm = pb["day_gan"]
    mg = pb["month_gan"]
    mz = pb["month_zhi"]
    
    CANGAN = {"子":"癸","丑":"己癸辛","寅":"甲丙戊","卯":"乙","辰":"戊乙癸",
              "巳":"丙庚戊","午":"丁己","未":"己丁乙","申":"庚壬戊",
              "酉":"辛","戌":"戊辛丁","亥":"壬甲"}
    
    biji_count = 0
    biji_info = []
    gans = [("year", pb["year_gan"]), ("month", pb["month_gan"]), ("hour", pb["hour_gan"])]
    zhis = [("year", pb["year_zhi"]), ("month", pb["month_zhi"]), ("day", pb["day_zhi"]), ("hour", pb["hour_zhi"])]
    
    # 查天干比劫
    for pos, g in gans:
        if get_shishen(dm, g) in ("比肩", "劫财"):
            biji_count += 1
            biji_info.append((pos, g, get_shishen(dm, g), "透干"))
    
    # 查地支比劫（藏干）
    for pos, z in zhis:
        cg = CANGAN.get(z, "")
        for c in cg:
            if get_shishen(dm, c) in ("比肩", "劫财"):
                if not any(b[0]==pos and b[1]==c for b in biji_info):
                    biji_count += 1
                    biji_info.append((pos, c, get_shishen(dm, c), "藏支"))
    
    # 叙事
    if biji_count >= 3:
        story = "比劫多现，朋友兄弟多、人缘广——但人多是非也多。"
    elif biji_count >= 1:
        story = "有朋友兄弟缘，但不泛滥——属于几个知心好友就够的类型。"
    else:
        story = "比劫少现，独立性强——不靠朋友靠自己的类型。"
    
    # 朋友质量
    if any("劫财" in str(b) for b in biji_info):
        story += "劫财藏现，朋友中有人会跟你产生金钱往来——帮人的时候多，被借的钱难要回。"
    else:
        story += "比肩为主，朋友多是志同道合型——相互帮衬但不沾钱。"
    
    # 月柱状态
    liuchong = {"子":"午","丑":"未","寅":"申","卯":"酉","辰":"戌","巳":"亥",
                "午":"子","未":"丑","申":"寅","酉":"卯","戌":"辰","亥":"巳"}
    mz_chong = [liuchong.get(mz) == zh for p, zh in zhis]
    if any(liuchong.get(mz) == zh for p, zh in zhis):
        story += "⚠️ 月柱被冲，兄弟/朋友关系不稳定——有人来来去去。"
    
    result = {
        "兄弟": {
            "比劫数量": biji_count,
            "叙事": story,
            "详情": biji_info
        }
    }
    
    return result




def caifu_shangxian(bazi_str):
    """财富上限分析：盲派财星+子平格局+纳音库开三套互参"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    
    # 盲派: 财星状态
    ct = cai_tag(bazi_str)
    zc = ct.get("正财","")
    pc = ct.get("偏财","")
    sw = ct.get("身旺","")
    
    # 子平: 格局评分+大运财星
    score = rate_mingju(bazi_str)["score"]
    xy = calc_xiyong(bazi_str)
    ji = xy.get("忌神",[])
    xi = xy.get("喜神",[])
    dm_wx = GAN_WX.get(dm,"")
    
    # 纳音: 库开检测
    ku = {"辰":"水库","戌":"火库","丑":"金库","未":"木库"}
    ku_list = [ku.get(z,"") for z in zhis if z in ku]
    ku_count = sum(1 for z in zhis if z in ["辰","戌","丑","未"])
    
    # 综合评级
    base = "温饱"
    reasons = []
    
    # 因素1: 格局分数
    if score >= 4.5: base = "大富"
    elif score >= 3.8: base = "中富"
    elif score >= 3.0: base = "小康"
    elif score >= 2.5: base = "温饱"
    else: base = "贫"
    reasons.append(f"格局{score}→{base}级")
    
    # 因素2: 从格加成
    cg = is_cong_ge(bazi_str)
    if cg.get("从格"):
        upgrade_cg = {"贫":"温饱","温饱":"小康","小康":"中富","中富":"大富"}
        base = upgrade_cg.get(base, base)
        reasons.append("从格→财富升一级")
    
    # 因素3: 财重身弱/身旺财旺
    if "身弱" in sw:
        reasons.append("身弱→扛财能力受限")
    elif "身旺" in sw:
        reasons.append("身旺→能扛大财")
    
    # 因素4: 库多=财底厚
    if ku_count >= 3:
        reasons.append(f"{ku_count}库→财底厚/资产型")
    
    # 因素5: 食伤生财
    shi = sum(1 for g in gans if get_shishen(dm,g) in ["食神","伤官"])
    cai = sum(1 for g in gans if get_shishen(dm,g) in ["正财","偏财"])
    if shi >= 1 and cai >= 1:
        reasons.append("食伤生财→靠技能持续变现")
    
    return {"财富等级": base, "判定依据": reasons, "格局分": score}

def marriage_analyze(bazi_str, gender="female"):
    """婚姻综合评估 v3.3: 含藏干+位置+强弱+官杀混杂"""
    b = parse_bazi(bazi_str)
    if not b: return {"状态": "排盘失败"}
    
    dm = b["day_gan"]
    gans = [b["year_gan"], b["month_gan"], b["hour_gan"]]
    zhis = [b["year_zhi"], b["month_zhi"], b["day_zhi"], b["hour_zhi"]]
    
    # 1. 天干官杀
    guan_tg = [(g, get_shishen(dm,g)) for g in gans if get_shishen(dm,g) in ["正官","七杀"]]
    # 2. 藏干官杀
    guan_cg = []
    for i, z in enumerate(zhis):
        for cg in ZHI_CANGGAN.get(z, ""):
            ss = get_shishen(dm, cg)
            if ss in ["正官","七杀"]:
                pos = ["年支","月支","日支(夫宫)","时支"][i]
                guan_cg.append((cg, ss, pos))
    
    # 3. 汇总
    all_guan = guan_tg + [(c[0],c[1]) for c in guan_cg]
    zhengguan = [g for g,s in all_guan if s=="正官"]
    qisha = [g for g,s in all_guan if s=="七杀"]
    
    # 4. 判定
    has_mix = bool(zhengguan) and bool(qisha)
    total = len(all_guan)
    in_fugong = any("夫宫" in str(c) for c in guan_cg)
    
    if gender == "female":
        if total == 0:
            tag = "官星不显·晚婚/独身倾向"
        elif has_mix:
            tag = "官杀混杂·感情多波折"
        elif total == 1:
            tag = "正官一位·婚姻清贵" if zhengguan else "单七杀·先难后成"
        elif total >= 3:
            tag = "官杀重重·婚姻多变"
        else:
            tag = "正官有气·婚姻平顺" if in_fugong else "官星浮露·感情浅"
    else:  # male
        # Same logic for 财星
        cai_tg = [(g, get_shishen(dm,g)) for g in gans if get_shishen(dm,g) in ["正财","偏财"]]
        cai_cg = []
        for i, z in enumerate(zhis):
            for cg in ZHI_CANGGAN.get(z, ""):
                if get_shishen(dm,cg) in ["正财","偏财"]:
                    cai_cg.append(cg)
        all_cai = cai_tg + [(c,"") for c in cai_cg]
        total = len(all_cai)
        in_fugong = any("日支" in str(c) for c in cai_cg) if hasattr(cai_cg,'__iter__') else False
        if total == 0: tag = "财星不显·晚婚"
        elif total >= 3: tag = "财星重重·多婚倾向"
        elif total == 1: tag = "一财得位·婚姻稳定"
        else: tag = "财星有气·婚姻平顺"
    
    # 5. 强弱修正
    sw = is_shenwang(bazi_str)["强弱"]
    if "弱" in sw and total >= 2:
        tag += "·身弱官杀为忌"
    elif "旺" in sw and total <= 1:
        tag += "·需大运引出"
    
    return {
        "标签": tag,
        "正官数": len(zhengguan),
        "七杀数": len(qisha),
        "官杀混杂": has_mix,
        "夫宫有官": in_fugong,
        "天干官杀": [g for g,s in guan_tg],
        "藏干官杀": [(c[0],c[2]) for c in guan_cg],
    }

def liuqin_analyze(bazi_str, age=None):
    """六亲综合分析"""
    result = {}
    try:
        result["父母"] = liuqin_fumu(bazi_str)
    except Exception:
        result["父母"] = {}
    try:
        result["子女"] = liuqin_zinv(bazi_str, age=age)
    except Exception:
        result["子女"] = {}
    try:
        result["兄弟朋友"] = liuqin_xiongdi(bazi_str)
    except Exception:
        result["兄弟朋友"] = {}
    return result


# ===== 喜用神系统（精度地基）=====

def calc_xiyong(bazi_str):
    """喜用神综合判断：身强弱 + 调候 + 月令 + 格局
    
    返回: {
        身强弱: str,
        调候: str,
        喜神: [五行],
        用神: [五行],
        忌神: [五行],
        闲神: [五行],
        叙事: str,
        详细: str
    }
    """
    pb = parse_bazi(bazi_str)
    if not pb:
        return {}
    
    dm = pb["day_gan"]
    WX_MAP = {"甲乙":"木","丙丁":"火","戊己":"土","庚辛":"金","壬癸":"水"}
    dm_wx = ""
    for k, v in WX_MAP.items():
        if dm in k:
            dm_wx = v
    
    mz = pb["month_zhi"]
    ZHI_WX = {"寅":"木","卯":"木","辰":"土","巳":"火","午":"火","未":"土",
              "申":"金","酉":"金","戌":"土","亥":"水","子":"水","丑":"土"}
    mz_wx = ZHI_WX.get(mz, "")
    
    WX_SHENG = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
    WX_BEISHENG = {"木":"水","火":"木","土":"火","金":"土","水":"金"}  # 生我的五行
    WX_KE = {"木":"土","土":"水","水":"火","火":"金","金":"木"}
    WX_BEIKE = {"木":"金","火":"水","土":"木","金":"火","水":"土"}  # 克我的五行
    all_wx = ["木","火","土","金","水"]
    
    # 1. 身强弱
    sw = is_shenwang(bazi_str)
    qiangruo = sw.get("强弱", "中")
    
    # 2. 调候
    th = check_tiaohou(bazi_str)
    is_summer = mz in ("巳","午","未")  # 夏生
    is_winter = mz in ("亥","子","丑")  # 冬生
    
    # 3. 格局倾向
    try:
        cg = is_cong_ge(bazi_str)
        is_cong = cg.get("从格", False)
    except:
        is_cong = False
    
    xi = []   # 喜神
    yong = [] # 用神
    ji = []   # 忌神
    xian = [] # 闲神
    
    if is_cong:
        # 从格：使用 is_cong_ge 返回的从格类型
        cong_type = cg.get("类型", "")
        # 从类型字符串提取五行：假从水格 → 水, 从火格 → 火
        cong_wx = dm_wx
        for wx in ["木","火","土","金","水"]:
            if wx in cong_type:
                cong_wx = wx
                break
        for wx in all_wx:
            if wx in WX_SHENG.get(cong_wx, "") or wx in WX_KE.get(cong_wx, ""):
                yong.append(wx)
            elif wx == cong_wx:
                xi.append(wx)
            else:
                ji.append(wx)
        detail = f"从{dm_wx}格，顺其势为用"
    else:
        # 正格：v3.2 身强弱优先，调候修正不覆盖
        
        # 偏弱按身弱处理
        effective_weak = qiangruo in ("身弱", "偏弱", "中/偏弱")
        effective_strong = qiangruo in ("身旺", "偏旺", "中/偏旺")
        
        if effective_weak:
            # 身弱喜生扶: 印(生我) + 比劫(同我)
            xi = [WX_BEISHENG.get(dm_wx, "")]  # 印=生我
            yong = [dm_wx]  # 比劫=同我
            # 忌克泄耗: 官杀(克我) + 财(我克) + 食伤(我生)
            ji = [WX_BEIKE.get(dm_wx, ""),      # 官杀=克我
                  WX_KE.get(dm_wx, ""),          # 财=我克
                  WX_SHENG.get(dm_wx, "")]       # 食伤=我生
            # 调候修正(不覆盖身弱逻辑)：加入闲神位置
            if is_summer and "水" not in xi:
                xian.append("水")  # 水可调候但不能取代印比
            elif is_winter and "火" not in xi:
                xian.append("火")  # 火可暖局但不能取代印比
        
        elif effective_strong:
            # 身旺喜克泄耗: 官杀(克我) + 食伤(我生) + 财(我克)
            sha_wx = WX_BEIKE.get(dm_wx, "")  # 官杀克我
            shi_wx = WX_SHENG.get(dm_wx, "")  # 食伤我生
            cai_wx = WX_KE.get(dm_wx, "")      # 财我克
            bi_wx = dm_wx                        # 比劫同我
            yin_wx = WX_BEISHENG.get(dm_wx, "") # 印生我
            
            # 用神：可克泄耗之物
            yong = []
            if sha_wx: yong.append(sha_wx)
            if shi_wx: yong.append(shi_wx)
            if cai_wx not in yong: yong.append(cai_wx)
            # 忌神：再来帮扶就是火上浇油
            ji = []
            if bi_wx not in ji: ji.append(bi_wx)
            if yin_wx not in ji: ji.append(yin_wx)
            # 调候修正
            if is_summer and "水" not in ji and "水" not in yong:
                yong.append("水")
            elif is_winter and "火" not in ji and "火" not in yong:
                yong.append("火")
        else:
            # 真中和
            yong = [WX_SHENG.get(dm_wx, "")]
            xi = [dm_wx]
            ji = [WX_KE.get(dm_wx, "")]
        
        # 调候降级标记
        if th.get("降级"):
            detail = f"v3.2·身{qiangruo}·{th.get('调候','')}·调候降级"
        else:
            detail = f"v3.2·身{qiangruo}·调候得位"
    
    # 去重、去空
    xi = list(dict.fromkeys([x for x in xi if x]))
    yong = list(dict.fromkeys([x for x in yong if x]))
    ji = list(dict.fromkeys([x for x in ji if x]))
    xian = list(dict.fromkeys([x for x in xian if x]))
    
    # 叙事
    if is_cong:
        cg_type = cg.get("类型", "")
        narr = f"从{cong_wx}格（{cg_type}），顺势而为——你的五行能量高度集中，不需要补什么，跟着大势走就是最好的策略。"
    elif qiangruo == "身弱":
        narr = f"身弱喜帮扶——需要{''.join(yong)}来帮你（比劫帮身），{''.join(xi)}来生你（印星滋养）。"
        if ji:
            narr += f"忌讳{''.join(ji)}——这些五行会消耗你，让你更累。"
        if is_summer and "水" in xi:
            narr += "夏生缺水，你像一棵长在沙漠里的树，最需要的一是水(降温)，二是木(帮身)。"
    elif qiangruo == "身旺":
        narr = f"身旺喜克泄——需要用{''.join(yong)}来疏通你的能量（官杀制衡+食伤输出）。"
        if ji:
            narr += f"忌讳{''.join(ji)}——这些五行会让你过旺失衡。"
    else:
        narr = "身中和——五行相对均衡，没有特别需要补的，也没有特别忌讳的。"
    
    return {
        "身强弱": qiangruo,
        "调候": th.get("调候", ""),
        "日主五行": dm_wx,
        "喜神": xi,
        "用神": yong,
        "忌神": ji,
        "闲神": xian,
        "叙事": narr,
        "详细": detail
    }


# ===== 整合：analyze中自动调用 =====

# ===== ① 大运年龄自动推算 =====

def infer_age_and_dayun(bazi_str, known_age=None, gender="male", birth_lunar=None):
    """从八字推断当前年龄和大运，gender用于决定顺/逆排。
    birth_lunar: 可选,(农历年,月,日)元组，用于精确起运计算
    如果birth_lunar未传，自动从birth_registry.json查询"""
    pb = parse_bazi(bazi_str)
    if not pb:
        return {"年龄": known_age or 30, "大运": "", "大运列表": [], "起运年龄": 0}
    
    # 自动查注册表
    if birth_lunar is None:
        import json as _j, os as _o
        _reg_path = _o.path.join(_o.path.dirname(__file__), "birth_registry.json")
        if _o.path.exists(_reg_path):
            try:
                _reg = _j.load(open(_reg_path, encoding='utf-8'))
                if bazi_str in _reg:
                    birth_lunar = tuple(_reg[bazi_str]["birth_lunar"])
                    if _reg[bazi_str].get("gender"):
                        gender = _reg[bazi_str]["gender"]
            except:
                pass
    
    year_gan = pb["year_gan"]
    GAN_YEAR_TAIL = {"甲":4,"乙":5,"丙":6,"丁":7,"戊":8,"己":9,"庚":0,"辛":1,"壬":2,"癸":3}
    tail = GAN_YEAR_TAIL.get(year_gan, 0)
    current_year = 2026
    ZHI_LIST = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]
    
    candidates = []
    for y in range(current_year - 120, current_year):
        if y % 10 == tail and ZHI_LIST[(y-4)%12] == pb["year_zhi"]:
            candidates.append((y, current_year - y))
    
    # 优先从年柱推算出生年份；known_age仅用于确定60年周期
    if candidates:
        if known_age is not None:
            # 在candidates中找最接近known_age的（允许±60年周期），同分选合理年龄段
            def dist(c):
                raw = c[1]
                d60 = abs(raw - known_age) % 60
                return d60 if d60 <= 30 else 60 - d60
            best = min(candidates, key=lambda c: (dist(c), abs(c[1]-known_age)))
            birth_year = best[0]
            age = known_age  # 报告用户给的年龄
        else:
            reasonable = [c for c in candidates if 18 <= c[1] <= 80]
            birth_year, age = reasonable[0] if reasonable else candidates[0]
    elif known_age is not None:
        birth_year = current_year - known_age
        age = known_age
    else:
        birth_year, age = current_year - 30, 30
    
    # 时辰→小时映射（取每个时辰的中点）
    SHICHEN_HOUR = {"子":23,"丑":2,"寅":4,"卯":6,"辰":8,"巳":10,"午":12,"未":14,"申":16,"酉":18,"戌":20,"亥":22}
    
    from bazi import calc_dayun
    try:
        is_male = (gender == "male")
        
        # 从时柱取出生时辰
        hour_zhi = pb.get("hour_zhi", "辰")
        birth_hour = SHICHEN_HOUR.get(hour_zhi, 8)
        
        # 推算出生月份和日期
        if birth_lunar:
            # 精确模式：用农历生日精确计算
            ly, lm, ld = birth_lunar
            from lunar_python import Lunar
            lunar = Lunar.fromYmd(ly, lm, ld)
            solar = lunar.getSolar()
            birth_m = solar.getMonth()
            birth_d = solar.getDay()
        else:
            # 估算模式：从月支反推公历月份
            # 节气月映射到公历月（取月中）
            ZHI_SOLAR_MONTH = {
                "寅":2,"卯":3,"辰":4,"巳":5,"午":6,"未":7,
                "申":8,"酉":9,"戌":10,"亥":11,"子":12,"丑":1
            }
            birth_m = ZHI_SOLAR_MONTH.get(pb["month_zhi"], 6)
            birth_d = 15  # 月中占位
        
        dy = calc_dayun(birth_year, birth_m, birth_d, birth_hour, 0, is_male)
        dayun_list = dy.get("大运", [])
        current_dayun = ""
        for g, z, s, e in dayun_list:
            if s <= age <= e:
                current_dayun = f"{g}{z}"
                break
    except:
        dayun_list, current_dayun = [], ""
    
    return {"年龄": age, "出生年": birth_year, "大运": current_dayun,
            "大运列表": [f"{g}{z}({s}-{e})" for g,z,s,e in dayun_list],
            "起运": dy.get("起运年龄", 3)}

# ===== ② 案例格局级匹配 =====

def find_similar_by_gege(bazi_str, top_n=3):
    """按格局+做功匹配相似案例"""
    pb = parse_bazi(bazi_str)
    if not pb or not isinstance(pb, dict):
        return []
    dm = pb.get("day_gan", "")
    gans = [pb.get("year_gan",""), pb.get("month_gan",""), pb.get("hour_gan","")]
    
    # 本命格局
    try: primary = _detect_gege(bazi_str)[0]
    except: primary = ""
    
    case_path = os.path.join(_SCRIPT_DIR, "case_master_unified.json")
    if not os.path.exists(case_path):
        return []
    import json
    with open(case_path, encoding='utf-8') as f:
        cases_data = json.load(f)
    case_list = list(cases_data.values()) if isinstance(cases_data, dict) else cases_data
    
    scored = []
    for c in case_list:
        if not isinstance(c, dict): continue
        cb = c.get("bazi", "")
        if not cb or len(cb.split()) != 4: continue
        try:
            cpb = parse_bazi(cb)
            if not cpb: continue
        except: continue
        
        score = 0
        c_tag = str(c.get("tag", ""))
        if primary and primary in c_tag: score += 50
        if dm == cpb.get("day_gan",""): score += 20
        if pb.get("month_zhi","") == cpb.get("month_zhi",""): score += 15
        try:
            my_ss = [get_shishen(dm, g) for g in gans]
            their_ss = [get_shishen(cpb["day_gan"], g) for g in [cpb["year_gan"], cpb["month_gan"], cpb["hour_gan"]]]
            score += len(set(my_ss) & set(their_ss)) * 5
        except: pass
        if score > 0: scored.append((score, c))
    
    scored.sort(key=lambda x: -x[0])
    return [(s, c) for s, c in scored[:top_n]]

# ===== ③ 跨月叙事弧 =====

def monthly_narrative_arc(monthly_data, year):
    """12个月串成叙事弧"""
    if not monthly_data: return ""
    seasons = {"春":["寅","卯","辰"],"夏":["巳","午","未"],"秋":["申","酉","戌"],"冬":["亥","子","丑"]}
    arcs = []
    for sn, ms in seasons.items():
        hits = [m for m in monthly_data if m["month"] in ms and m["强度"] >= 2]
        if hits:
            tops = []
            for h in hits:
                ev = h.get('具体事件',[])
                tops.append(f"{h['month']}月{ev[0]['event']}" if ev else f"{h['month']}月{h['事件倾向']}")
            arcs.append(f"{sn}({'、'.join(tops)})")
    peak = max(monthly_data, key=lambda m: m["强度"]) if monthly_data else None
    peak_txt = f"高峰在{peak['month']}月" if peak else ""
    return f"{year}年：{'→'.join(arcs)}。{peak_txt}。" if arcs else f"{year}年无明显季节波动。"

# ===== ④ 流月→特定事件细化 =====

def refine_monthly_event(bazi_str, month_data):
    """泛化事件→具体事件（细化）"""
    pb = parse_bazi(bazi_str)
    if not pb: return month_data
    dm = pb.get("day_gan","")
    mg = month_data.get("月干","")
    events = month_data.get("具体事件", [])
    if not events: return month_data
    
    month_ss = get_shishen(dm, mg) if dm else ""
    for ev in events:
        en = ev["event"]
        if en == "新资源/新助力":
            m = {"偏财":"投资/项目资金到位","正财":"客户签约/收入增长","正官":"贵人提拔/新职位",
                 "七杀":"跳槽机会/竞争上位","食神":"技术/创意合作","正印":"学习/证书机会",
                 "比肩":"朋友/同行引荐"}.get(month_ss, "新机会出现")
            ev["event"] = m
            ev["detail"] = f"{month_ss}月引动,细化方向: {m}"
            ev["confidence"] = min(ev.get("confidence",0.8)+0.1, 1.0)
        if en == "财务/资产变动":
            m = {"偏财":"大额投资/资产重组","正财":"固定资产变动/买房","劫财":"被迫支出/合伙拆账",
                 "七杀":"因压力变现资产","偏印":"非主流投资收益"}.get(month_ss, "重大财务变动")
            ev["event"] = m
        if en == "合作/关系进展":
            m = {"比肩":"同行合作敲定","劫财":"朋友合伙推进","正财":"商业客户锁定",
                 "偏财":"项目合作签约","正官":"官方/上级关系推进","食神":"技术合作"}.get(month_ss, "合作推进")
            ev["event"] = m
    return month_data

def apply_all_refinements(bazi_str, monthly_data):
    return [refine_monthly_event(bazi_str, m) for m in monthly_data]

# ===== ⑤ 用户反馈自动学习 =====

FEEDBACK_PATH = os.path.join(_SCRIPT_DIR, "feedback_db.json")
def _init_fb():
    if not os.path.exists(FEEDBACK_PATH):
        with open(FEEDBACK_PATH, 'w', encoding='utf-8') as f:
            json.dump({"corrections":[],"rules":[]}, f)

def record_feedback(bazi, field, feedback):
    _init_fb()
    with open(FEEDBACK_PATH, encoding='utf-8') as f:
        db = json.load(f)
    db["corrections"].append({"bazi":bazi, "field":field, "feedback":feedback, 
                               "time":__import__('datetime').datetime.now().isoformat()})
    with open(FEEDBACK_PATH, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def get_feedback(bazi, field=None):
    _init_fb()
    with open(FEEDBACK_PATH, encoding='utf-8') as f:
        db = json.load(f)
    hits = [c for c in db["corrections"] if c["bazi"]==bazi]
    if field: hits = [c for c in hits if c["field"]==field]
    return hits


# ===== P1第四模块：健康分析（五行→脏腑+疾病倾向+流年应期）=====

# 五行旺衰→脏腑映射
WUXING_ZANGFU = {
    "木": {"旺": ["肝胆功能亢进", "易怒", "偏头痛", "颈椎问题"],
           "弱": ["肝胆虚弱", "视力下降", "筋腱僵硬", "指甲脆"], 
           "过": ["脂肪肝", "高血压(木火上炎)", "胆囊炎"]},
    "火": {"旺": ["心火亢盛", "失眠多梦", "口腔溃疡", "心悸"],
           "弱": ["心气不足", "怕冷", "手脚冰凉", "循环弱"],
           "过": ["心血管负担", "脑溢血风险", "眼疾"]},
    "土": {"旺": ["脾胃湿热", "消化不良", "腹胀", "便秘"],
           "弱": ["脾虚", "食欲不振", "消瘦", "肌肉无力"],
           "过": ["痰湿体质", "高血糖倾向", "关节沉重"]},
    "金": {"旺": ["肺气充沛", "皮肤致密", "呼吸系统强"],
           "弱": ["肺气虚", "易感冒", "皮肤敏感", "过敏体质"],
           "过": ["哮喘倾向", "便秘(金过制木)", "皮肤干燥"]},
    "水": {"旺": ["肾气充足", "泌尿系统好", "生殖系统强"],
           "弱": ["肾虚", "腰膝酸软", "耳鸣", "脱发", "尿频"],
           "过": ["水肿", "怕冷", "性功能亢进/减退"]},
}

# 五行→季节/器官
WUXING_SEASON_RISK = {
    "木": {"春": "肝气生发太过,注意血压", "夏": "木火通明,注意心火", 
           "秋": "金克木,注意肝胆抑郁", "冬": "水能生木,安好"},
    "火": {"春": "木生火,心火渐升", "夏": "火旺之季,心血管最紧张", 
           "秋": "火气退,心脏负担减缓", "冬": "水克火,注意心梗风险"},
    "土": {"春": "木克土,脾胃易不适", "夏": "火生土,脾胃最旺", 
           "秋": "土生金,健康平稳", "冬": "土克水,注意关节"},
    "金": {"春": "金克木,注意过敏", "夏": "火克金,肺热干燥", 
           "秋": "金旺之季,呼吸系统最强", "冬": "金生水,安好"},
    "水": {"春": "水生木,肾气消耗", "夏": "水被火耗,注意肾亏", 
           "秋": "金生水,肾气充沛", "冬": "水旺之季,注意水肿怕冷"},
}

# 十神→疾病倾向
TENGOD_SICKNESS = {
    "七杀": "压力病——七杀攻身:头痛/失眠/免疫力下降/骨骼问题",
    "伤官": "消耗病——伤官泄身:内分泌失调/焦虑/炎症反复",
    "劫财": "争财病——劫财夺财:胃病/消化不良/肝胆不适",
    "正官": "约束病——正官克身:慢性病/风湿/肌肉紧张",
    "偏印": "怪异病——偏印过旺:神经衰弱/疑病症/免疫紊乱"
}


def health_wuxing(bazi_str):
    """五行体质分析：五行旺衰→脏腑强弱"""
    pb = parse_bazi(bazi_str)
    if not pb:
        return {}
    
    # 五行计数
    WX_MAP = {"甲乙":"木","丙丁":"火","戊己":"土","庚辛":"金","壬癸":"水"}
    ZHI_WX = {"寅":"木","卯":"木","辰":"土","巳":"火","午":"火","未":"土",
              "申":"金","酉":"金","戌":"土","亥":"水","子":"水","丑":"土"}
    
    wx_count = {"木":0,"火":0,"土":0,"金":0,"水":0}
    
    gans = [pb["year_gan"], pb["month_gan"], pb["day_gan"], pb["hour_gan"]]
    zhis = [pb["year_zhi"], pb["month_zhi"], pb["day_zhi"], pb["hour_zhi"]]
    
    for g in gans:
        for key, wx in WX_MAP.items():
            if g in key:
                wx_count[wx] += 1
    
    for z in zhis:
        wx = ZHI_WX.get(z, "")
        if wx:
            wx_count[wx] += 1
    
    # 藏干（增加精度）
    CANGAN = {"子":"癸","丑":"己癸辛","寅":"甲丙戊","卯":"乙","辰":"戊乙癸",
              "巳":"丙庚戊","午":"丁己","未":"己丁乙","申":"庚壬戊",
              "酉":"辛","戌":"戊辛丁","亥":"壬甲"}
    for z in zhis:
        cg = CANGAN.get(z, "")
        for c in cg:
            for key, wx in WX_MAP.items():
                if c in key:
                    wx_count[wx] += 0.5  # 藏干算半格
    
    # 五行分析
    results = {}
    for wx in ["木","火","土","金","水"]:
        count = wx_count[wx]
        if count >= 4:
            status = "过旺"
        elif count >= 2.5:
            status = "偏旺"
        elif count >= 1.5:
            status = "适中"
        elif count >= 0.5:
            status = "偏弱"
        else:
            status = "过弱"
        
        # 倾向
        if status == "过旺" or status == "偏旺":
            diseases = WUXING_ZANGFU[wx]["旺"][:3]
        elif status == "偏弱" or status == "过弱":
            diseases = WUXING_ZANGFU[wx]["弱"][:3]
        else:
            diseases = WUXING_ZANGFU[wx]["旺"][:2]  # 适中也要注意
        
        results[wx] = {"计数": count, "状态": status, "倾向": diseases}
    
    # 综合体质（找出最弱+最强）
    sorted_wx = sorted(wx_count.items(), key=lambda x: x[1])
    weakest = sorted_wx[0][0] if sorted_wx[0][1] < 2 else None
    strongest = sorted_wx[-1][0] if sorted_wx[-1][1] >= 3 else None
    
    return {
        "五行计数": wx_count,
        "各脏腑": results,
        "最弱脏腑": weakest,
        "最强脏腑": strongest,
        "体质总评": f"★ {strongest if strongest else '无明显偏旺'}偏旺，{weakest if weakest else '无明显偏弱'}偏弱" if weakest or strongest else "五行相对均衡"
    }


def health_tendency(bazi_str):
    """疾病倾向综合分析"""
    pb = parse_bazi(bazi_str)
    if not pb:
        return {}
    dm = pb["day_gan"]
    gans = [pb["year_gan"], pb["month_gan"], pb["hour_gan"]]
    
    wx = health_wuxing(bazi_str)
    
    warnings = []
    health_tips = []
    
    # 1. 调候警告
    try:
        th = check_tiaohou(bazi_str)
        if th.get("降级"):
            if "无水" in th.get("调候", ""):
                warnings.append("调候缺水——肾阴不足体质，易上火/失眠/口干")
                health_tips.append("多补水——枸杞菊花茶/银耳汤，少吃辛辣烧烤")
            elif "无火" in th.get("调候", ""):
                warnings.append("调候缺火——阳气不足体质，畏寒怕冷")
                health_tips.append("多晒太阳/泡脚，适量吃温热食物")
    except:
        pass
    
    # 2. 五行偏枯警告
    wx_count = wx.get("五行计数", {})
    for w, c in wx_count.items():
        if c >= 4:
            warnings.append(f"{w}过旺——注意{WUXING_ZANGFU[w]['过'][0]}")
        elif c < 1:
            warnings.append(f"{w}过弱——注意{WUXING_ZANGFU[w]['弱'][0]}")
    
    # 3. 十神克身
    for g in gans:
        ss = get_shishen(dm, g)
        if ss in TENGOD_SICKNESS:
            if ss in ("七杀", "伤官", "劫财"):
                warnings.append(TENGOD_SICKNESS[ss])
    
    # 4. 季节风险（全四季）
    wx_strong = wx.get("最强脏腑", "")
    wx_weak = wx.get("最弱脏腑", "")
    current_year = 2026
    # 简单的季节判定
    season_now = "夏"  # 默认夏季
    
    # 按最强脏腑出警告
    if wx_strong and wx_strong in WUXING_SEASON_RISK:
        for season, risk in WUXING_SEASON_RISK[wx_strong].items():
            warnings.append(f"{season}{wx_strong}:{risk}")
    
    # 按最弱脏腑给出保健建议
    if wx_weak and wx_weak in WUXING_SEASON_RISK:
        for season, risk in WUXING_SEASON_RISK[wx_weak].items():
            if season == season_now:
                health_tips.append(f"当前{season}季，{wx_weak}弱之体需注意：{risk}")
    
    return {
        "警告": warnings[:5],
        "建议": health_tips[:3],
        "体质": wx.get("体质总评", "")
    }


def health_flow_year(bazi_str, year):
    """流年健康应期：五行流年→对应脏腑"""
    pb = parse_bazi(bazi_str)
    if not pb:
        return {}
    
    liu_gan = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
    liu_zhi = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]
    lg = liu_gan[(year-4) % 10]
    lz = liu_zhi[(year-4) % 12]
    
    ZHI_WX = {"寅":"木","卯":"木","辰":"土","巳":"火","午":"火","未":"土",
              "申":"金","酉":"金","戌":"土","亥":"水","子":"水","丑":"土"}
    WX_MAP = {"甲乙":"木","丙丁":"火","戊己":"土","庚辛":"金","壬癸":"水"}
    
    # 流年五行
    lz_wx = ZHI_WX.get(lz, "")
    lg_wx = ""
    for key, wx in WX_MAP.items():
        if lg in key:
            lg_wx = wx
    
    # 健康应期判断
    signals = []
    body_parts = []
    
    # 流年地支与原局冲刑
    zhis = [pb["year_zhi"], pb["month_zhi"], pb["day_zhi"], pb["hour_zhi"]]
    liuchong = {"子":"午","丑":"未","寅":"申","卯":"酉","辰":"戌","巳":"亥",
                "午":"子","未":"丑","申":"寅","酉":"卯","戌":"辰","亥":"巳"}
    liuhai = {"子":"未","丑":"午","寅":"巳","卯":"辰","申":"亥","酉":"戌",
              "未":"子","午":"丑","巳":"寅","辰":"卯","亥":"申","戌":"酉"}
    
    for z in zhis:
        # 冲
        if liuchong.get(lz) == z:
            wx = ZHI_WX.get(z, "")
            if wx in WUXING_ZANGFU:
                issues = WUXING_ZANGFU[wx].get("弱" if wx == "土" else "旺", [])
                if issues and issues[0] not in [s for s in signals]:
                    signals.append(f"流年{lz}冲{z}({wx})——注意{issues[0]}")
                    body_parts.append(wx + "系" if wx else "")
        # 刑
        if lz == z and lz in ("辰","午","酉","亥"):
            signals.append(f"流年{lz}自刑——精神压力大，注意心脑血管")
            body_parts.append("精神/心脑血管")
    
    # 流年五行与原局
    dm = pb["day_gan"]
    for key, wx in WX_MAP.items():
        if dm in key:
            dm_wx = wx
    
    if lz_wx == "金" and dm_wx == "木":
        signals.append(f"流年{lz}(金)克日主(dm_wx)(木)——肝胆压力大的一年")
        body_parts.append("肝胆")
    if lz_wx == "木" and dm_wx == "土":
        signals.append(f"流年{lz}(木)克日主土——脾胃受克，注意消化")
        body_parts.append("脾胃")
    
    if not signals:
        signals.append("此年无重大健康应期信号")
    
    return {
        "年份": year,
        "流年": f"{lg}{lz}",
        "信号": signals[:3],
        "注意部位": list(set(body_parts)) or ["一般保健"]
    }


def health_analyze(bazi_str, year=2026):
    """健康综合分析"""
    result = {}
    try:
        result["体质"] = health_wuxing(bazi_str)
    except Exception:
        result["体质"] = {}
    try:
        result["疾病倾向"] = health_tendency(bazi_str)
    except Exception:
        result["疾病倾向"] = {}
    try:
        result["流年健康"] = health_flow_year(bazi_str, year)
    except Exception:
        result["流年健康"] = {}
    return result


def shishen_chain(bazi_str):
    """素水·十神生克链：食神→财→官→印→身，找主线"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    ss = [get_shishen(dm,g) for g in gans]
    
    chain = []
    has_shi = any(s in ["食神","伤官"] for s in ss)
    has_cai = any(s in ["正财","偏财"] for s in ss)
    has_guan = any(s in ["正官","七杀"] for s in ss)
    has_yin = any(s in ["正印","偏印"] for s in ss)
    
    if has_shi and has_cai:
        chain.append("食伤生财 → 技术/手艺赚钱")
    if has_cai and has_guan:
        chain.append("财生官 → 钱权转换")
    if has_guan and has_yin:
        chain.append("官生印 → 体制/稳定")
    if has_shi and has_guan:
        chain.append("食神制杀 → 以技制敌")
    
    return {"链条": chain, "完整": len(chain)>=2}

def he_ban_check(bazi_str):
    """素水·合绊检测：天干五合+地支六合的影响"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["day_gan"],b["hour_gan"]]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    
    he_map = {"甲":"己","乙":"庚","丙":"辛","丁":"壬","戊":"癸","己":"甲","庚":"乙","辛":"丙","壬":"丁","癸":"戊"}
    zhi_he = {"子":"丑","丑":"子","寅":"亥","亥":"寅","卯":"戌","戌":"卯","辰":"酉","酉":"辰","巳":"申","申":"巳","午":"未","未":"午"}
    
    results = []
    for i,g in enumerate(gans):
        if g in he_map and he_map[g] in gans:
            pos = ["年","月","日","时"][i]
            ss = get_shishen(dm,g)
            if ss in ["正财","偏财"]:
                results.append(f"{pos}干{g}合绊→财被合，难取财")
            elif ss in ["正官","七杀"]:
                results.append(f"{pos}干{g}合绊→官被合，工作受阻")
    
    return {"合绊": results, "有合绊": len(results)>0}

def jibing_dingwei(bazi_str):
    """疾病定位法则：日主五行→脏腑→五官+受伤方向+恢复力"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    
    wu_zang = {"甲":"肝→目","乙":"肝→目","丙":"心→舌","丁":"心→舌",
               "戊":"脾→口","己":"脾→口","庚":"肺→鼻","辛":"肺→鼻",
               "壬":"肾→耳","癸":"肾→耳"}
    target = wu_zang.get(dm, "?")
    
    yang_gan = "甲丙戊庚壬"
    side = "右侧" if dm in yang_gan else "左侧"
    
    tu_zhong = sum(1 for z in zhis if z in ["辰","戌","丑","未"])
    recover = "差" if tu_zhong >= 3 else ("中" if tu_zhong >= 2 else "好")
    
    dm_wx = GAN_WX.get(dm, "")
    xy = calc_xiyong(bazi_str)
    ji_wx = xy.get("忌神",[])
    weak_point = ""
    if "火" in ji_wx and dm_wx == "木": weak_point = "木被火焚→目/肝最脆弱"
    elif "金" in ji_wx and dm_wx == "木": weak_point = "金克木→头/目易外伤"
    elif "土" in ji_wx and dm_wx == "水": weak_point = "土克水→肾/耳最脆弱"
    
    chronic = "高" if tu_zhong >= 3 else "中" if tu_zhong >= 2 else "低"
    
    return {"脆弱器官":target,"受伤方向":side,"恢复力":recover,"忌神攻击点":weak_point,"慢性风险":chronic}


def education_eval(bazi_str):
    """素水·学历评估：印星体系"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    
    yin_tg = [g for g in gans if get_shishen(dm,g) in ["正印","偏印"]]
    yin_zhi = []
    for z in zhis:
        for cg in ZHI_CANGGAN.get(z,""):
            if get_shishen(dm,cg) in ["正印","偏印"]:
                yin_zhi.append((cg, z))
    
    total_yin = len(yin_tg) + len(yin_zhi)
    has_guan = any(get_shishen(dm,g) in ["正官","七杀"] for g in gans)
    
    # v3.6: 拦截检查
    deductions = []
    # 财克印: 天干有财+天干有印
    cai_tg = [g for g in gans if get_shishen(dm,g) in ["正财","偏财"]]
    if cai_tg and yin_tg: deductions.append("财克印")
    # 印被穿破: 藏印之支被穿（去重）
    chuan_pairs = [("子","未"),("丑","午"),("寅","巳"),("卯","辰"),("申","亥"),("酉","戌")]
    chuan_found = False
    for cy, cz in yin_zhi:
        if chuan_found: break
        for a,b2 in chuan_pairs:
            if (cz==a and b2 in zhis) or (cz==b2 and a in zhis):
                if not chuan_found:
                    deductions.append("印被穿破")
                    chuan_found = True
                break
    # 官杀混杂干扰
    sha_tg = [g for g in gans if get_shishen(dm,g)=="七杀"]
    guan_tg = [g for g in gans if get_shishen(dm,g)=="正官"]
    if sha_tg and guan_tg: deductions.append("官杀混杂")
    # 劫财分资源
    if sum(1 for g in gans if get_shishen(dm,g)=="劫财") >= 1: deductions.append("劫财分源")
    # 印在藏干被土压(日主为木, 辰丑土重)
    mz = b["month_zhi"]
    is_summer = mz in ["巳","午","未"]
    chen_chou = sum(1 for z in zhis if z in ["辰","戌","丑","未"])
    if total_yin >= 2 and yin_tg == [] and chen_chou >= 2: deductions.append("藏印被土重压")
    if total_yin >= 1 and yin_tg == [] and is_summer: deductions.append("夏生印藏无水润")
    # v3.7: 从格(不含专旺/天元一气) + 早年帮身运 → 学业受扰
    try:
        cg = is_cong_ge(bazi_str)
        cong_type = cg.get("类型","")
        if cg.get("从格") and "专旺" not in cong_type:
            deductions.append("从格局·早年帮身运扰学")
    except: pass
    # 印得地: 印在月令(提纲) → 学业有底, 抵消一级拦截
    yin_zhi_positions = [cz for cy,cz in yin_zhi]
    yin_in_month = b["month_zhi"] in yin_zhi_positions
    
    # v3.8: 专旺格印星减半(格局整体,非学历专属)
    if "专旺" in cong_type:
        total_yin = max(0, total_yin - 1)
    # 判定
    if total_yin >= 3: base = "高学历"
    elif total_yin >= 1 and has_guan: base = "中高学历"
    elif total_yin >= 1: base = "中低学历"
    else: base = "无印星"
    
    # ===== 子平四补充 =====
    # 补充1: 杀印相生力度——官杀在天干+印在天干=真官印; 官杀在天干+印在藏干=打折
    sha_in_tg = [g for g in gans if get_shishen(dm,g)=="七杀"]
    if sha_in_tg and yin_tg and base in ["中高学历","中低学历"]:
        base = "高学历" if base == "中高学历" else "中高学历"  # 真杀印相生升一级
        deductions.append("子平:真杀印相生→升")
    
    # 补充2: 食神制杀——聪明但考试不一定行,不降不升
    shi_in_tg = [g for g in gans if get_shishen(dm,g)=="食神"]
    if shi_in_tg and sha_in_tg:
        deductions.append("子平:食神制杀→聪明型")
        # 食神制杀的人学历看其他因素,不自动升降
    
    # 补充3: 文昌/学堂神煞加分
    wenchang_map = {"甲":"巳","乙":"午","丙":"申","丁":"酉","戊":"申","己":"酉","庚":"亥","辛":"子","壬":"寅","癸":"卯"}
    xuetang_map = {"甲":"亥","乙":"午","丙":"寅","丁":"酉","戊":"寅","己":"酉","庚":"巳","辛":"子","壬":"申","癸":"卯"}
    wc_zhi = wenchang_map.get(dm,"")
    xt_zhi = xuetang_map.get(dm,"")
    if wc_zhi in zhis or xt_zhi in zhis:
        if base in ["中低学历","低学历"]:
            upgrade_wx = {"中低学历":"中高学历","低学历":"中低学历"}
            base = upgrade_wx.get(base, base)
            deductions.append("子平:文昌/学堂→升")
    
    # 补充4: 印旺身强反降——子平真诠:"印旺身强,何劳印生"
    sw = is_shenwang(bazi_str)["强弱"]
    if total_yin >= 2 and "旺" in sw:
        deductions.append("子平:印旺身强→反降")
        # 不直接降,作为拦截计数
    
    # ===== 纳音三补充 =====
    # 补充5: 魁星旬——日柱在甲辰到癸丑间=科甲种子
    kuixing_xun = ["甲辰","乙巳","丙午","丁未","戊申","己酉","庚戌","辛亥","壬子","癸丑"]
    day_pillar = b["day_gan"] + b["day_zhi"]
    if day_pillar in kuixing_xun:
        deductions.append("纳音:魁星旬→科甲种子")
        if base in ["中低学历","低学历","极低"]:
            upgrade_kx = {"中低学历":"中高学历","低学历":"中低学历","极低":"低学历"}
            base = upgrade_kx.get(base, base)
    
    # 补充6: 墨池格——年支为子+时柱癸亥=文章士
    if b["year_zhi"] == "子" and b["hour_gan"]+b["hour_zhi"] == "癸亥":
        deductions.append("纳音:墨池格→文章士")
        upgrade_mc = {"中高学历":"高学历","中低学历":"中高学历","低学历":"中低学历"}
        base = upgrade_mc.get(base, base)
    
    # 补充7: 水火既济——年月纳音水+日时纳音火=功名
    try:
        ny_table = nayan_60jiazi()
        ny_year = nayan_wuxing(ny_table.get(b["year_gan"]+b["year_zhi"],""))
        ny_month = nayan_wuxing(ny_table.get(b["month_gan"]+b["month_zhi"],""))
        ny_day = nayan_wuxing(ny_table.get(day_pillar,""))
        ny_hour = nayan_wuxing(ny_table.get(b["hour_gan"]+b["hour_zhi"],""))
        if ny_year==ny_month=="水" and ny_day==ny_hour=="火":
            deductions.append("纳音:水火既济→功名")
            if base in ["中高学历","中低学历"]:
                base = "高学历"
    except: pass
    
    # 3条以上拦截 → 降两级, 2条 → 降一级
    if len(deductions) >= 3:
        downgrade2 = {"高学历":"中低学历","中高学历":"低学历","中低学历":"极低","无印星":"极低","低学历":"极低"}
        base = downgrade2.get(base, base)
    elif len(deductions) >= 2:
        downgrade = {"高学历":"中高学历","中高学历":"中低学历","中低学历":"低学历","无印星":"极低"}
        base = downgrade.get(base, base)
    
    # 调整: 印在月令 + 非从格 + 非专旺 → 升一级
    if yin_in_month and not cg.get("从格", False) and "专旺" not in cong_type:
        upgrade = {"极低":"低学历","低学历":"中低学历","中低学历":"中高学历","中高学历":"高学历","高学历":"高学历"}
        base = upgrade.get(base, base)
    # 无印但食伤泄秀有力 → 聪明自学型 → 升一级
    if total_yin <= 1 and not has_guan:
        shi_shang = sum(1 for g in gans if get_shishen(dm,g) in ["食神","伤官"])
        if shi_shang >= 2:
            upgrade2 = {"低学历":"中低学历","中低学历":"中高学历","极低":"低学历","无印星":"中低学历"}
            base = upgrade2.get(base, base)
    
    return {"印星数": total_yin, "官印相生": has_guan, "拦截": deductions, "印在月令": yin_in_month, "评估": base}


def shangguan_jianguan(bazi_str):
    """素水·伤官见官判定：身越旺越严重，有印则减"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    ss = [get_shishen(dm,g) for g in gans]
    
    # Check 天干 + 地支藏干
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    all_ss = list(ss)
    for z in zhis:
        for cg in ZHI_CANGGAN.get(z,""):
            all_ss.append(get_shishen(dm,cg))
    has_shang = "伤官" in all_ss
    has_guan = any(s in ["正官","七杀"] for s in all_ss)
    has_yin = any(s in ["正印","偏印"] for s in all_ss)
    has_yin = any(s in ["正印","偏印"] for s in ss)
    sw = is_shenwang(bazi_str)["强弱"]
    
    if not (has_shang and has_guan):
        return {"伤官见官": False, "风险": "无"}
    
    risk = "低"
    notes = []
    if "身旺" in sw:
        risk = "高"
        notes.append("身旺伤官见官→最凶（丢官/牢狱）")
    elif "身弱" in sw:
        risk = "中"
        notes.append("身弱伤官见官→问题不大")
    
    if has_yin:
        risk = "低" if risk != "高" else "中"
        notes.append("有印制伤→减凶")
    
    return {"伤官见官": True, "风险": risk, "说明": notes, "素水原话": "身越旺越严重，阴制阳严重"}

def disaster_warning(bazi_str):
    """素水·灾祸预警：刑冲克害+官杀无制"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    
    warnings = []
    
    # 官杀无制
    sha_count = sum(1 for g in gans if get_shishen(dm,g) == "七杀")
    shi_count = sum(1 for g in gans if get_shishen(dm,g) in ["食神","伤官"])
    if sha_count > 0 and shi_count == 0:
        warnings.append("七杀无制·压力/灾祸风险")
    
    # 刑冲
    chong_pairs = [("子","午"),("丑","未"),("寅","申"),("卯","酉"),("辰","戌"),("巳","亥")]
    for a,b in chong_pairs:
        if a in zhis and b in zhis:
            warnings.append(f"{a}{b}冲·动荡/冲突")
    
    # 自刑
    for z in ["辰","午","酉","亥"]:
        if zhis.count(z) >= 2:
            warnings.append(f"双{z}自刑·内心煎熬")
    
    # ===== 子平五补充 =====
    # 补充1: 忌神辗转攻——三方向忌神同时发力
    xy = calc_xiyong(bazi_str)
    ji_list = xy.get("忌神",[])
    ji_in_gans = [g for g in gans if GAN_WX.get(g,"") in ji_list]
    ji_in_zhis = [z for z in zhis if ZHI_WX.get(z,"") in ji_list]
    if len(ji_in_gans) >= 2 and len(ji_in_zhis) >= 2:
        warnings.append("子平:忌神辗转攻→多重灾祸风险")
    
    # 补充2: 气浊神枯——格局不清+用神无力
    qz = check_qingzhuo(bazi_str)
    score = rate_mingju(bazi_str)["score"]
    if qz[0] == "浊" and score < 2.5:
        warnings.append("子平:气浊神枯→先天灾祸体质")
    
    # 补充3: 四库即牢狱——辰戌丑未多
    ku_count = sum(1 for z in zhis if z in ["辰","戌","丑","未"])
    if ku_count >= 3:
        warnings.append(f"子平:{ku_count}库→牢狱基因·易官非/被困")
    
    # 补充4: 阳冲快灾/阴支慢病
    yang_chong = [("子","午"),("卯","酉")]
    yin_chong = [("辰","戌"),("丑","未")]
    has_yang = any(a in zhis and b in zhis for a,b in yang_chong)
    has_yin = any(a in zhis and b in zhis for a,b in yin_chong)
    if has_yang:
        warnings.append("子平:阳冲→快灾(突发)")
    if has_yin:
        warnings.append("子平:阴冲→慢病(积累)")
    
    # 补充5: 用神被制——忌神在原局压用神
    xi_list = xy.get("喜神",[])
    xi_in_gans = [g for g in gans if GAN_WX.get(g,"") in xi_list]
    if xi_in_gans and ji_in_gans:
        warnings.append("子平:用神被忌神压制→大运引动则灾")
    
    # ===== 纳音三补充 =====
    # 补充6: 三戌重冲=家破人亡
    xu_count = sum(1 for z in zhis if z == "戌")
    chen_count = sum(1 for z in zhis if z == "辰")
    if xu_count >= 3:
        warnings.append("纳音:三戌重冲破门→家破人亡风险")
    if chen_count >= 3 and xu_count >= 1:
        warnings.append("纳音:三辰遇戌冲→库破灾出")
    
    # 补充7: 火命入墓——火纳音命+戌=入墓风险
    try:
        ny_t = nayan_60jiazi()
        day_ny = ny_t.get(b["day_gan"]+b["day_zhi"], "")
        dm_nx = nayan_wuxing(day_ny)
        if dm_nx == "火" and "戌" in zhis:
            warnings.append("纳音:火命入戌墓→逢戌年/戌运大病风险")
    except: pass
    
    # 补充8: 午为烽堠——午重=血光/战火/手术
    wu_count = sum(1 for z in zhis if z == "午")
    if wu_count >= 2:
        warnings.append(f"纳音:双午烽堠→血光/手术/突发病灾")
    
    return {"预警": warnings, "风险等级": "高" if len(warnings)>=3 else "中" if len(warnings)>=1 else "低"}


def tongguan_optimize(bazi_str):
    """老人参·通关优化：财坏印→官杀通关最优"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    
    ss_all = [get_shishen(dm,g) for g in gans]
    has_cai = any(s in ["正财","偏财"] for s in ss_all)
    has_yin = any(s in ["正印","偏印"] for s in ss_all)
    has_guan = any(s in ["正官","七杀"] for s in ss_all)
    
    if not (has_cai and has_yin):
        return {"通关": False}
    
    advices = []
    if has_guan:
        advices.append("最优：财生官→官生印→印生身（通关法）")
    else:
        advices.append("次优：用比劫克财护印（耗财法）")
    
    if has_guan:
        advices.append("老人参原话：用官来通关，让凶的东西来生我，效率最高")
    
    return {"通关": True, "建议": advices, "配置": f"财{'有' if has_cai else '无'}·官{'有' if has_guan else '无'}·印有"}


def chihuangliang(bazi_str):
    """素水·吃皇粮判定：家里家外有关系=体制内"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    
    # Check 杀印同宫
    sha_zhi = [z for z in zhis for cg in ZHI_CANGGAN.get(z,"") if get_shishen(dm,cg)=="七杀"]
    yin_zhi = [z for z in zhis for cg in ZHI_CANGGAN.get(z,"") if get_shishen(dm,cg) in ["正印","偏印"]]
    same_zhi = set(sha_zhi) & set(yin_zhi)
    
    has_sha = any(get_shishen(dm,g)=="七杀" for g in gans)
    has_yin = any(get_shishen(dm,g) in ["正印","偏印"] for g in gans)
    
    if same_zhi:
        return {"吃皇粮": True, "模式": "杀印同宫→铁饭碗", "级别": "高"}
    elif has_sha and has_yin:
        return {"吃皇粮": True, "模式": "杀印配合→体制内", "级别": "中"}
    else:
        return {"吃皇粮": False, "模式": "非体制"}

def yongshen_conflict(bazi_str):
    """素水·两个用神打架检测"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    xy = calc_xiyong(bazi_str)
    yong = xy.get("用神",[])
    xi = xy.get("喜神",[])
    all_good = yong + xi
    
    # Check if any two 用神 五行相克
    ke_map = {"木":"土","土":"水","水":"火","火":"金","金":"木"}
    conflicts = []
    for i, wx1 in enumerate(all_good):
        for wx2 in all_good[i+1:]:
            if ke_map.get(wx1) == wx2 or ke_map.get(wx2) == wx1:
                conflicts.append(f"{wx1}克{wx2}→用神互克")
    
    return {"用神打架": len(conflicts)>0, "冲突": conflicts, "建议": "两个用神互相克制→格局降分" if conflicts else "用神协调"}

def shigan_xiji_deep(dm):
    """素水六期·十干喜忌深化"""
    table = {
        "庚": {"喜":"丁火锻炼+壬水淘洗","忌":"火弱土厚","格局":"用食伤制杀最好"},
        "辛": {"喜":"壬水淘洗","忌":"太旺的火","格局":"火制成格也只是小富贵"},
        "丙": {"喜":"配壬水(成大格局)","忌":"配癸水(小富小贵)","格局":"壬水格局远大于癸水"},
        "戊": {"喜":"甲木来疏","忌":"无甲则土过重","格局":"甲木来制才有效"},
        "甲": {"喜":"庚金雕琢+癸水滋润","忌":"丙火焚身","格局":"庚劈甲引丁为上"},
        "乙": {"喜":"丙火暖身+癸水滋养","忌":"辛金小刀","格局":"藤萝系甲可春可秋"},
        "丁": {"喜":"甲木为薪+庚金劈甲","忌":"癸水灭火","格局":"甲庚齐透为上"},
        "己": {"喜":"丙火暖土+癸水润土","忌":"乙木克土","格局":"火土功成"},
        "壬": {"喜":"戊土堤防+甲木泄水","忌":"己土混水","格局":"汪洋需堤"},
        "癸": {"喜":"辛金发源+丙火暖水","忌":"戊土填水","格局":"雨露润物"},
    }
    return table.get(dm, {"喜":"","忌":"","格局":""})

def xiangliji_sanfen(bazi_str):
    """素水·象法理法技法三分：象=行业，理=层次，技=时间"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    zuogong = sushi_zuogong(bazi_str).get("做功",[])
    score = rate_mingju(bazi_str)["score"]
    
    xiang = ""
    if "食伤生财" in str(zuogong): xiang = "技术/手艺/贸易"
    elif "化杀生印" in str(zuogong): xiang = "体制/管理/文化"
    elif "食神制杀" in str(zuogong): xiang = "军警/医疗/执法"
    elif "比劫制财" in str(zuogong): xiang = "合作/制造/体力"
    
    li = ""
    if score >= 4.0: li = "行业顶尖/大企业/高层"
    elif score >= 3.3: li = "中层/稳定/小康以上"
    elif score >= 2.8: li = "基层/温饱/打工"
    else: li = "底层/生存压力大"
    
    return {"象(行业)": xiang, "理(层次)": li, "技(时间)": "大运流年应期详见 yingqi 分析"}

def renling_faze(bazi_str):
    """素水网络三期·认领法则：外来的财谁认领谁得"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    
    # Check for 认领 pattern: 天干有庚金（领） + 地支有申/酉
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    has_geng = "庚" in gans or "申" in zhis
    
    if has_geng:
        return {"认领": True, "规则": "庚金认领外财→外来之财可得", "原话": "酉金来了就被庚金认领"}
    return {"认领": False}


def jinbuhuan_eval(bazi_str):
    """命理正宗·金不换断：十日干十二月逐月口诀评估"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    mz = b["month_zhi"]
    
    # Abbreviated rules from 金不换断
    table = {
        ("甲","寅"):"煞重喜冲，顺火逆金",
        ("甲","卯"):"羊刃驾杀，南运忌火",
        ("甲","午"):"夏木用水，庚金劈甲",
        ("乙","午"):"午月癸水，丙火暖根",
        ("丙","子"):"正官配印，东南发达",
        ("丁","丑"):"食神怕土，东运发达",
        ("戊","子"):"正财坐辰戌，怕东又怕西",
        ("庚","子"):"冬金用火，调候为先",
        ("辛","酉"):"建禄用食，壬水淘洗",
        ("壬","子"):"羊刃架杀，戊土堤防",
    }
    
    key = (dm, mz)
    advice = table.get(key, f"{dm}生{mz}月→按常规调候取用")
    
    return {"金不换口诀": advice, "日干": dm, "月令": mz}

def shigan_imagery(dm):
    """三命通会·十干类象：用于叙事取象"""
    imagery = {
        "甲":"参天之木·雷声·栋梁·松柏",
        "乙":"花草藤萝·柔木·禾苗·风",
        "丙":"太阳之火·光明·文明·礼仪",
        "丁":"灯烛之星·文明·智慧·内秀",
        "戊":"城墙之土·厚重·承载·诚信",
        "己":"田园之土·云·卑湿·包容",
        "庚":"斧钺之金·月亮·刚健·杀伐",
        "辛":"珠玉之金·霜雪·温润·清贵",
        "壬":"江河之水·秋露·流通·智慧",
        "癸":"雨露之水·春霖·至阴·柔韧",
    }
    return imagery.get(dm, "")

def shierzhi_imagery(zhi):
    """三命通会·地支取象"""
    imagery = {
        "子":"墨池·深夜·北方·水之源",
        "丑":"柳岸·金库·湿土·暗藏",
        "寅":"广谷·山林·黎明·生机",
        "卯":"琼林·花园·晨光·柔软",
        "辰":"草泽·水库·清晨·龙宫",
        "巳":"大驿·热闹·午前·火热",
        "午":"烽堠·正午·鼎盛·极点",
        "未":"花园·午后·木库·收藏",
        "申":"名都·下午·变革·传送",
        "酉":"时钟·黄昏·收获·精致",
        "戌":"燎原·傍晚·火库·收敛",
        "亥":"悬河·深夜·北方·源头",
    }
    return imagery.get(zhi, "")


# ====================
# 三命通会·纳音+格局体系
# ====================

def nayan_60jiazi():
    """三命通会·六十甲子纳音全表"""
    return {
        "甲子":"海中金","乙丑":"海中金","丙寅":"炉中火","丁卯":"炉中火",
        "戊辰":"大林木","己巳":"大林木","庚午":"路旁土","辛未":"路旁土",
        "壬申":"剑锋金","癸酉":"剑锋金","甲戌":"山头火","乙亥":"山头火",
        "丙子":"涧下水","丁丑":"涧下水","戊寅":"城头土","己卯":"城头土",
        "庚辰":"白蜡金","辛巳":"白蜡金","壬午":"杨柳木","癸未":"杨柳木",
        "甲申":"泉中水","乙酉":"泉中水","丙戌":"屋上土","丁亥":"屋上土",
        "戊子":"霹雳火","己丑":"霹雳火","庚寅":"松柏木","辛卯":"松柏木",
        "壬辰":"长流水","癸巳":"长流水","甲午":"沙中金","乙未":"沙中金",
        "丙申":"山下火","丁酉":"山下火","戊戌":"平地木","己亥":"平地木",
        "庚子":"壁上土","辛丑":"壁上土","壬寅":"金箔金","癸卯":"金箔金",
        "甲辰":"覆灯火","乙巳":"覆灯火","丙午":"天河水","丁未":"天河水",
        "戊申":"大驿土","己酉":"大驿土","庚戌":"钗钏金","辛亥":"钗钏金",
        "壬子":"桑柘木","癸丑":"桑柘木","甲寅":"大溪水","乙卯":"大溪水",
        "丙辰":"沙中土","丁巳":"沙中土","戊午":"天上火","己未":"天上火",
        "庚申":"石榴木","辛酉":"石榴木","壬戌":"大海水","癸亥":"大海水",
    }

def nayan_wuxing(nayin_str):
    """三命通会·纳音提取五行"""
    map = {"金":"金","木":"木","水":"水","火":"火","土":"土"}
    for k,v in map.items():
        if k in nayin_str: return v
    return "?"

def nayan_level(bazi_str):
    """三命通会·纳音层次评估"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    gans = [b["year_gan"],b["month_gan"],b["day_gan"],b["hour_gan"]]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    table = nayan_60jiazi()
    nayan_list = [table.get(g+z,"") for g,z in zip(gans,zhis)]
    
    # 纳音五行生克链
    wx_chain = [nayan_wuxing(n) for n in nayan_list]
    scores = {"金金相生":"宝器","火土相生":"文明","水木相生":"秀气","土金相生":"厚重",
              "金木相克":"雕琢","水火相克":"动荡","火金相克":"锻炼"}
    
    return {"纳音": nayan_list, "五行链": "→".join(wx_chain), "质地": scores.get("".join(wx_chain[:2]),"中和")}

def jiage_panduan(bazi_str):
    """神峰通考+三命通会·综合格局判定"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    mz = b["month_zhi"]
    
    checks = []
    # 正官格
    if any(get_shishen(dm,g)=="正官" for g in gans) and any(get_shishen(dm,g)=="伤官" for g in gans):
        checks.append("神峰:正官见伤→破格")
    # 时上一位贵
    shi_sha = get_shishen(dm,b["hour_gan"])=="七杀"
    other_sha = sum(1 for g in [b["year_gan"],b["month_gan"]] if get_shishen(dm,g)=="七杀")
    if shi_sha and other_sha == 0:
        checks.append("神峰:时上一位贵格")
    # 官杀去留
    zheng_all = [g for g in gans if get_shishen(dm,g)=="正官"]
    sha_all = [g for g in gans if get_shishen(dm,g)=="七杀"]
    if zheng_all and sha_all:
        checks.append("神峰:官杀混杂→去留为贵")
    
    return {"格局判定": checks if checks else ["常规格局"], "神峰原话": "欲知贵贱先观月令，次断吉凶专用日干"}

# ====================
# 滴天阴本·京南道人体系
# ====================

def jingnan_yaoyi(bazi_str):
    """滴天阴本·京南道人十干要义"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    sw = is_shenwang(bazi_str)["强弱"]
    mz = b["month_zhi"]
    
    yaoyi = {
        "乙": ["春生用火·夏生用水·秋生用火·冬生用火","丑月进气·金强透火不惧·藤萝系甲"],
        "丙": ["火多木焚·己土泄秀·水火既济为贵","虎马犬乡甲来必灭"],
        "丁": ["抱乙而孝·合壬而忠","旺而不烈·衰而不穷"],
        "己": ["湿土养金·火土功成·春生喜丙·秋生喜火","卑湿中正蓄藏"],
        "庚": ["秋令壬水泄秀·顽金得丁而锐·水冷金寒用火"],
        "壬": ["汪洋需戊土为堤·甲木泄水·己土混水不吉"],
    }
    
    advices = yaoyi.get(dm, [f"{dm}日主按常规论"])
    return {"京南要义": advices, "日主": dm, "身强弱": sw}

def muyuan_miezi(bazi_str):
    """滴天阴本·母慈灭子+夫健怕妻判定"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    
    yin_count = sum(1 for g in gans if get_shishen(dm,g) in ["正印","偏印"])
    cai_count = sum(1 for g in gans if get_shishen(dm,g) in ["正财","偏财"])
    sha_count = sum(1 for g in gans if get_shishen(dm,g) == "七杀")
    
    msgs = []
    if yin_count >= 3: msgs.append("母慈灭子→印重身弱溺爱过多")
    if cai_count >= 2 and "弱" in is_shenwang(bazi_str)["强弱"]: msgs.append("夫健怕妻→财旺身弱反被财累")
    if sha_count >= 2: msgs.append("众煞混行,一仁可化→需印星通关")
    
    return {"滴天警告": msgs, "口诀": "母慈灭子关因异,夫健何谓又怕妻"}

# ====================
# 千里命稿·现代论命法
# ====================

def qianli_tuinian(bazi_str):
    """千里命稿·推年法: 干支分推"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    yg = b["year_gan"]
    yz = b["year_zhi"]
    
    # 韦千里的推年法: 年柱纳音+年干年支分论
    table = nayan_60jiazi()
    ny = table.get(yg+yz, "?")
    
    return {"年命": ny, "年干": f"{yg}主事", "年支": f"{yz}根基", 
            "千里原话": "推年之法多端,干支分推较为简便"}

def qianli_geju(bazi_str):
    """千里命稿·格局辩证: 月令取格+十神论格"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    mz = b["month_zhi"]
    
    # 月令取格
    mz_ss = {}
    for cg in ZHI_CANGGAN.get(mz,""):
        mz_ss[get_shishen(dm,cg)] = cg
    
    main_ge = "正官格" if "正官" in mz_ss else               "七杀格" if "七杀" in mz_ss else               "财格" if any(s in mz_ss for s in ["正财","偏财"]) else               "印格" if any(s in mz_ss for s in ["正印","偏印"]) else               "食神格" if "食神" in mz_ss else               "伤官格" if "伤官" in mz_ss else "建禄/阳刃格"
    
    return {"月令取格": main_ge, "藏干主气": mz_ss, "千里原话": "禄命之学有三派,子平以日干为主月令为纲"}

# ====================
# 兰台妙选·奇格异局
# ====================

def lantai_qige(bazi_str):
    """兰台妙选·奇格异局检测"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    gans = [b["year_gan"],b["month_gan"],b["day_gan"],b["hour_gan"]]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    table = nayan_60jiazi()
    
    checks = []
    # 兔入月宫: 卯年+己未
    if b["year_zhi"] == "卯" and "未" in zhis:
        checks.append("兔入月宫格·清贵")
    # 龙跃天门: 辰+亥
    if "辰" in zhis and "亥" in zhis:
        checks.append("龙跃天门·志在四方")
    # 无根之木得天河水: 甲+丙午/丁未
    if b["day_gan"] == "甲":
        ny_list = [table.get(g+z,"") for g,z in zip(gans,zhis)]
        if "天河水" in ny_list:
            checks.append("无根之木得天河水·江湖之士")
    
    return {"兰台奇格": checks if checks else ["无特殊奇格"], "出处": "兰台妙选·纳音取象"}

# ====================
# 调候正解+张神峰病药论
# ====================

def tiaohou_condition(bazi_str):
    """调候正解·调候使用条件：重新定义调候"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    mz = b["month_zhi"]
    dm = b["day_gan"]
    
    is_summer = mz in ["巳","午","未"]
    is_winter = mz in ["亥","子","丑"]
    is_spring = mz in ["寅","卯","辰"]
    is_autumn = mz in ["申","酉","戌"]
    
    # 调候正解核心：调候不是无条件补水火，而是看寒暖燥湿
    cond = []
    if is_summer and dm in ("甲","乙","丙","丁"): cond.append("夏木夏火→调候必用癸水·非壬水")
    if is_winter and dm in ("庚","辛","壬","癸"): cond.append("冬金冬水→调候必用丙火·非丁火")
    if is_spring and dm in ("庚","辛"): cond.append("春金尚寒→需火暖局")
    if is_autumn and dm in ("甲","乙"): cond.append("秋木凋零→需水滋润")
    
    return {"调候条件": cond if cond else ["无特殊调候需求"], "正解原话": "调候取之于寒暖燥湿,以节令为主"}

def bingyao_shenlun(bazi_str):
    """神峰通考·病药论深化：有病方为贵"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    th = check_tiaohou(bazi_str)
    
    bing = []
    yao = []
    if th.get("降级"): bing.append("调候不足→" + th.get("调候",""))
    else: yao.append("调候得位→" + th.get("调候",""))
    
    xy = calc_xiyong(bazi_str)
    ji_list = xy.get("忌神",[])
    xi_list = xy.get("喜神",[])
    
    if ji_list: bing.append(f"忌神{''.join(ji_list)}为病")
    if xi_list: yao.append(f"喜神{''.join(xi_list)}为药")
    
    return {"病": bing, "药": yao, "神峰原话": "有病方为贵,无伤不是奇"}

# ====================
# 综合入口：古籍全量分析
# ====================

def guji_full_analysis(bazi_str):
    """10部古籍全量分析入口"""
    return {
        "三命通会": {
            "纳音": nayan_level(bazi_str),
            "类象": {"日主": shigan_imagery(parse_bazi(bazi_str)["day_gan"]), "日支": shierzhi_imagery(parse_bazi(bazi_str)["day_zhi"])}
        },
        "滴天阴本": {
            "京南要义": jingnan_yaoyi(bazi_str),
            "滴天警告": muyuan_miezi(bazi_str)
        },
        "千里命稿": {
            "推年": qianli_tuinian(bazi_str),
            "格局": qianli_geju(bazi_str)
        },
        "神峰通考": {
            "格局判定": jiage_panduan(bazi_str),
            "病药": bingyao_shenlun(bazi_str)
        },
        "金不换": jinbuhuan_eval(bazi_str),
        "兰台妙选": lantai_qige(bazi_str),
        "调候正解": tiaohou_condition(bazi_str),
    }


def tizhinei_lujing(bazi_str, age=None, gender="male"):
    """素水盲派·体制内外路径判定：吃皇粮三模式+大运转折"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    
    # 1. 杀印关系判定
    sha_gan = [g for g in gans if get_shishen(dm,g)=="七杀"]
    guan_gan = [g for g in gans if get_shishen(dm,g)=="正官"]
    yin_gan = [g for g in gans if get_shishen(dm,g) in ["正印","偏印"]]
    yin_zhi_list = []
    for z in zhis:
        for cg in ZHI_CANGGAN.get(z,""):
            if get_shishen(dm,cg) in ["正印","偏印"]:
                yin_zhi_list.append((cg, z))
    
    # 杀印同宫: 七杀和印来自同一个地支
    sha_zhi_from = set()
    for z in zhis:
        for cg in ZHI_CANGGAN.get(z,""):
            if get_shishen(dm,cg)=="七杀":
                sha_zhi_from.add(z)
    yin_zhi_from = {cz for cy,cz in yin_zhi_list}
    sha_yin_tonggong = bool(sha_zhi_from & yin_zhi_from)
    
    # 2. 吃皇粮判定 (素水三模式)
    mode = ""
    reasons = []
    if sha_yin_tonggong:
        mode = "吃皇粮"
        reasons.append("杀印同宫→体制内根基")
    elif (sha_gan or guan_gan) and (yin_gan or yin_zhi_list):
        mode = "吃皇粮"
        reasons.append("杀/官+印→体制内通道")
    elif not (sha_gan or guan_gan):
        mode = "不吃皇粮"
        reasons.append("无官杀→与体制无缘")
    
    # 3. 家里家外判定(素水)
    jialiwai = sushi_jialiwai(bazi_str)
    jiali_mode = jialiwai.get("模式","") if jialiwai else ""
    if "全在家内" in jiali_mode:
        reasons.append("财官在家→自己干/创业倾向")
    elif "全在家外" in jiali_mode:
        reasons.append("财官在外→打工/体制倾向")
    elif "混合" in jiali_mode:
        reasons.append("家里家外都有→混搭型")
    
    # 食伤泄秀力度 (决定是否从体制内跳出)
    shi_shang = sum(1 for g in gans if get_shishen(dm,g) in ["食神","伤官"])
    # 地支藏干食伤也计入
    for z in zhis:
        for cg in ZHI_CANGGAN.get(z,""):
            if get_shishen(dm,cg) in ["食神","伤官"]:
                shi_shang += 1
    if shi_shang >= 2:
        reasons.append(f"食伤泄秀({shi_shang}透)→有跳出体制的冲动")
    
    # 4. 大运路径判定
    path = "纯体制外"
    try:
        from bazi import calc_dayun
        now = __import__('datetime').datetime.now().year
        dy = calc_dayun(now-50, 1, 1, 12, 0, is_male=(gender=="male")) if age is None else None
    except:
        dy = None
    
    # 从格修正: 从格的人不按正常吃皇粮论, 跟着格局走
    try:
        cg_check = is_cong_ge(bazi_str)
        if cg_check.get("从格"):
            reasons.append("从格局→不走体制路")
            mode = "不吃皇粮"  # 从格直接覆盖
            path = "纯体制外(从格)"
    except: pass
    
    if mode == "吃皇粮":
        if "创业" in jiali_mode or shi_shang >= 2:
            path = "先体制内→后体制外(下海)" if sha_yin_tonggong else "体制内外混搭"
        elif "打工" in jiali_mode and shi_shang < 2:
            path = "纯体制内"
        else:
            path = "体制内为主"
    else:
        if "创业" in jiali_mode:
            path = "纯体制外(创业型)"
        elif "打工" in jiali_mode:
            path = "纯体制外(打工型)"
        else:
            path = "体制外自由职业"
    
    # 5. 伤官见官修正
    sgjg = shangguan_jianguan(bazi_str)
    guansha_count = len([g for g in gans if get_shishen(dm,g) in ["正官","七杀"]])
    if sgjg and sgjg.get("伤官见官") and sgjg.get("风险") in ["高","中"]:
        reasons.append("伤官见官→体制内容易出问题")
        if guansha_count >= 2:
            reasons.append("官杀混杂+伤官见官→与体制不合")
            mode = "不吃皇粮"
            path = "纯体制外"
        elif "纯体制内" in path:
            path = "先体制内→后体制外(伤官逼退)"
    
    # 6. 子平五补充
    # 官杀纯杂
    guansha_chunza = "杂" if (guan_gan and sha_gan) else ("纯" if (guan_gan or sha_gan) else "无")
    if guansha_chunza == "杂":
        reasons.append("子平:官杀混杂→体制内难久留")
    # 印绶护官
    if yin_gan and (guan_gan or sha_gan):
        reasons.append("子平:印绶护官→体制内长期稳定")
    # 时上一位贵
    hour_ss_val = get_shishen(dm, b["hour_gan"])
    other_gs = sum(1 for g in [b["year_gan"],b["month_gan"]] if get_shishen(dm,g) in ["正官","七杀"])
    if hour_ss_val in ["正官","七杀"] and other_gs == 0:
        reasons.append("子平:时上一位贵→自己当老板")
    # 伤官不服官管
    if shi_shang >= 3:
        reasons.append("子平:伤官不服官管→迟到离开")
    
    # 7. 纳音三补充
    day_pillar = b["day_gan"] + b["day_zhi"]
    # 贵人捧印: 纳音墓库+官星=体制内做大
    try:
        ny_t = nayan_60jiazi()
        day_ny = ny_t.get(day_pillar,"")
        # 纳音印库: 火命戌为印,木命未,金命丑,水土辰
        nx_map = {"火":"戌","木":"未","金":"丑","水":"辰","土":"辰"}
        dm_nx = nayan_wuxing(day_ny)
        nx_zhi = nx_map.get(dm_nx,"")
        if nx_zhi in zhis and (guan_gan or sha_gan):
            reasons.append("纳音:贵人捧印→体制内可做大")
    except: pass
    
    # 攀龙附凤: 辰酉合=靠关系进体制
    if "辰" in zhis and "酉" in zhis:
        reasons.append("纳音:辰酉合·攀龙附凤→靠关系/跟对人")
    
    # 进神: 大运走到进神=晋升快 (标记)
    jinshen = ["甲子","己卯","甲午","己酉"]
    if day_pillar in jinshen:
        reasons.append("纳音:日柱进神→发迹亨快")
    
    return {
        "吃皇粮": mode == "吃皇粮",
        "模式": mode,
        "杀印同宫": sha_yin_tonggong,
        "路径": path,
        "判定依据": reasons,
        "素水原话": "杀和我有关系+印和我及外面都有关系→吃皇粮"
    }



def hunyin_jieju(bazi_str):
    """婚姻结局分析：稳定度+分离风险+晚年状态"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    
    # 稳定度因子
    stability = 5
    reasons = []
    
    # 官杀混杂 -2
    gs = sum(1 for g in gans if get_shishen(dm,g) in ["正官","七杀"])
    if gs >= 2: stability -= 2; reasons.append("官杀混杂-2")
    
    # 日支被穿 -1
    chuan = [("子","未"),("丑","午"),("寅","巳"),("卯","辰"),("申","亥"),("酉","戌")]
    dz = b["day_zhi"]
    for a,b2 in chuan:
        if (dz==a and b2 in zhis) or (dz==b2 and a in zhis):
            stability -= 1; reasons.append(f"日支被穿-1")
            break
    
    # 日时伏吟 -1
    if b["day_zhi"] == b["hour_zhi"]:
        stability -= 1; reasons.append("日时伏吟-1")
    
    # 从格 -1
    if is_cong_ge(bazi_str).get("从格"):
        stability -= 1; reasons.append("从格婚姻不稳-1")
    
    result = "稳固" if stability >= 4 else ("一般" if stability >= 2 else "高危")
    return {"稳定度": stability, "结局": result, "因素": reasons}

def shouyuan_fenxi(bazi_str):
    """寿元分析：格局浊枯+土重压身+从格风险"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    
    warnings = []
    score = rate_mingju(bazi_str)["score"]
    qz = check_qingzhuo(bazi_str)
    
    # 气浊神枯
    if qz[0] == "浊" and score < 2.5:
        warnings.append("气浊神枯→寿元先天不足")
    
    # 土重压身(四库多)
    ku = sum(1 for z in zhis if z in ["辰","戌","丑","未"])
    if ku >= 4: warnings.append("四库全→土重压身折寿")
    elif ku >= 3: warnings.append("三库→晚年大病风险")
    
    # 从格早折
    if is_cong_ge(bazi_str).get("从格") and score < 3.0:
        warnings.append("从格+低分→早折风险")
    
    # 午重=心脑血管
    wu = sum(1 for z in zhis if z == "午")
    if wu >= 2: warnings.append("双午→心脑血管高危")
    
    level = "高风险" if len(warnings)>=2 else ("中等" if warnings else "低风险")
    return {"风险等级": level, "预警": warnings}

def dayun_qiehuan(bazi_str, age=None):
    """大运切换精确时间点：前后3年过渡期"""
    if age is None:
        from datetime import datetime
        age = datetime.now().year - 1970
    dy = calc_dayun_from_bazi(bazi_str, age)
    if not dy: return {}
    
    qiehuan = []
    dy_list = dy.get("大运列表", [])
    start_age = dy.get("起运年龄", 0)
    for i in range(len(dy_list)-1):
        mid = start_age + (i+1)*10  # 大运结束年龄
        trans = {"大运": f"{dy_list[i]}→{dy_list[i+1]}",
                 "切换年龄": mid,
                 "过渡期": f"{mid-2}-{mid+1}岁",
                 "关键": "前两年旧运余气未消, 后一年新运开始发力"}
        qiehuan.append(trans)
    
    result = [t for t in qiehuan if age >= t["切换年龄"]-2 and age <= t["切换年龄"]+1]
    return {"当前过渡": result[0] if result else None, "全部切换点": qiehuan[:3]}



def shenruo_caiwang(bazi_str):
    """富屋贫人检测：身弱财旺+无印无比劫=看得见吃不着"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    sw = is_shenwang(bazi_str)["强弱"]
    cai_tg = sum(1 for g in gans if get_shishen(dm,g) in ["正财","偏财"])
    yin_tg = sum(1 for g in gans if get_shishen(dm,g) in ["正印","偏印"])
    bi_tg = sum(1 for g in gans if get_shishen(dm,g) in ["比肩","劫财"])
    
    if "弱" in sw and cai_tg >= 2 and yin_tg == 0 and bi_tg == 0:
        return {"富屋贫人": True, "渊海原话": "财多身弱,富屋贫人", "建议": "需大运印比帮身方能得财"}
    return {"富屋贫人": False}

def shishen_zhisha_pinqiong(bazi_str):
    """京南反直觉规则：身旺+食神制杀=贫穷(理论依据见京南过三关)"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    sw = is_shenwang(bazi_str)["强弱"]
    shi = sum(1 for g in gans if get_shishen(dm,g)=="食神")
    sha = sum(1 for g in gans if get_shishen(dm,g)=="七杀")
    
    if "旺" in sw and shi >= 1 and sha >= 1:
        return {"食神制杀贫穷": True, "京南原话": "身旺前提下食神制杀,基本都是贫穷的命", "原因": "食神格身旺再制杀,泄身过度反贫"}
    return {"食神制杀贫穷": False}

def yongshen_beipo(bazi_str):
    """京南规则：年月用神被破坏=家庭/出身问题"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    xy = calc_xiyong(bazi_str)
    xi = xy.get("喜神",[])
    yong = xy.get("用神",[])
    good = xi + yong
    
    year_gan = b["year_gan"]
    month_gan = b["month_gan"]
    year_wx = GAN_WX.get(year_gan,"")
    month_wx = GAN_WX.get(month_gan,"")
    
    problems = []
    if year_wx not in good:
        problems.append("年柱用神被破→祖业/父亲有损")
    if month_wx not in good:
        problems.append("月柱用神被破→父母/原生家庭问题")
    
    return {"年月用神": [year_wx, month_wx], "问题": problems, "京南原话": "年月用神被破坏,肯定是家庭上的问题"}

def shouyuan_dingwei(bazi_str):
    """寿元定位：寿元星+穿破死法(人命死亡信息探秘)"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    
    # 寿元星: 日主之禄=寿元星 (甲禄寅/乙禄卯/丙戊禄巳/丁己禄午/庚禄申/辛禄酉/壬禄亥/癸禄子)
    lu_map = {"甲":"寅","乙":"卯","丙":"巳","丁":"午","戊":"巳","己":"午","庚":"申","辛":"酉","壬":"亥","癸":"子"}
    shou_lu = lu_map.get(dm,"")
    
    warnings = []
    # 寿元星被穿=死亡信号
    chuan = [("子","未"),("丑","午"),("寅","巳"),("卯","辰"),("申","亥"),("酉","戌")]
    for a,b2 in chuan:
        if shou_lu and ((shou_lu==a and b2 in zhis) or (shou_lu==b2 and a in zhis)):
            warnings.append(f"寿元星{shou_lu}被穿→大限信号")
    # 寿元星被冲
    chong = {"子":"午","午":"子","寅":"申","申":"寅","卯":"酉","酉":"卯","巳":"亥","亥":"巳"}
    if shou_lu in chong and chong[shou_lu] in zhis:
        warnings.append(f"寿元星{shou_lu}被冲→突发风险")
    
    level = "高危" if len(warnings)>=2 else ("中等" if warnings else "低")
    return {"寿元星": shou_lu, "风险等级": level, "预警": warnings}



def fuhun_heping(bazi_str):
    """京南/杨清娟·夫宫喜静：穿/破/冲=婚姻不稳定度"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dz = b["day_zhi"]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    
    score = 5
    reasons = []
    
    # 穿
    chuan = [("子","未"),("丑","午"),("寅","巳"),("卯","辰"),("申","亥"),("酉","戌")]
    for a,b2 in chuan:
        if (dz==a and b2 in zhis) or (dz==b2 and a in zhis):
            score -= 2; reasons.append(f"夫宫被穿-2")
            break
    
    # 冲
    chong = {"子":"午","午":"子","寅":"申","申":"寅","卯":"酉","酉":"卯","巳":"亥","亥":"巳"}
    if dz in chong and chong[dz] in zhis:
        score -= 1; reasons.append("夫宫被冲-1")
    
    # 刑
    xing = {"寅":"巳","巳":"申","申":"寅","丑":"戌","戌":"未","未":"丑","子":"卯","卯":"子"}
    if dz in xing and xing[dz] in zhis:
        score -= 1; reasons.append("夫宫被刑-1")
    
    level = "稳定" if score >= 4 else ("一般" if score >= 2 else "高危")
    return {"稳定度": score, "等级": level, "因素": reasons, "杨清娟原话": "夫宫喜静不喜动-穿/破/冲"}

def caixing_taohua(bazi_str):
    """杨清娟·财星混杂=桃花：正财偏财同现=感情复杂"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    
    zc = [g for g in gans if get_shishen(dm,g)=="正财"]
    pc = [g for g in gans if get_shishen(dm,g)=="偏财"]
    
    if zc and pc:
        return {"财星混杂": True, "桃花风险": "高", "杨清娟原话": "财星混了就犯桃花"}
    return {"财星混杂": False, "桃花风险": "低"}

def nianyu_zuzai(bazi_str):
    """四柱详批·年月官杀为忌=祖上父母有官灾"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    xy = calc_xiyong(bazi_str)
    ji = xy.get("忌神",[])
    
    year_gan = b["year_gan"]
    month_gan = b["month_gan"]
    problems = []
    
    if get_shishen(dm, year_gan) in ["正官","七杀"] and GAN_WX.get(year_gan,"") in ji:
        problems.append("年官杀为忌→祖上有官灾/伤痛")
    if get_shishen(dm, month_gan) in ["正官","七杀"] and GAN_WX.get(month_gan,"") in ji:
        problems.append("月官杀为忌→父母有官灾/伤病")
    
    return {"祖上预警": problems, "四柱原话": "年月官杀为忌主祖上父母有官灾或伤痛灾"}

def zhonghe_hexin(bazi_str):
    """京南·中和核心：最旺五行=病/忌神, 专旺顺其势不可逆"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    gans = [b["year_gan"],b["month_gan"],b["day_gan"],b["hour_gan"]]
    
    # 统计五行分布
    wx_count = {"木":0,"火":0,"土":0,"金":0,"水":0}
    for g in gans: wx_count[GAN_WX.get(g,"")] = wx_count.get(GAN_WX.get(g,""),0) + 1
    for z in zhis: wx_count[ZHI_WX.get(z,"")] = wx_count.get(ZHI_WX.get(z,""),0) + 1
    
    strongest = max(wx_count, key=wx_count.get)
    weakest = min(wx_count, key=wx_count.get)
    
    # 检查是否专旺
    cg = is_cong_ge(bazi_str)
    is_zhuan = "专旺" in cg.get("类型","")
    
    advice = ""
    if is_zhuan: advice = f"专旺{strongest}格→顺其势不可逆"
    elif wx_count[strongest] >= 5: advice = f"{strongest}过旺为病→需泄耗不宜再生扶"
    else: advice = f"五行趋衡→中和为贵"
    
    return {"最强五行": strongest, "最弱五行": weakest, "建议": advice, "京南原话": "中和是万事万物的核心"}



def tiandi_wang(bazi_str):
    """素水·天地网检测：辰巳=天罗, 戌亥=地网 → 同样破财别人赔钱他坐牢"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    
    tianluo = "辰" in zhis and "巳" in zhis
    diwang = "戌" in zhis and "亥" in zhis
    
    warnings = []
    if tianluo: warnings.append("天罗(辰巳)→男犯天罗, 官非/牢狱加重")
    if diwang: warnings.append("地网(戌亥)→女犯地网, 疾病/婚姻加重")
    
    level = "高危" if (tianluo and diwang) else ("中" if (tianluo or diwang) else "无")
    return {"天罗地网": level, "预警": warnings, "素水原话": "同样劫财见财, 有天地网的人坐牢, 没有的只是破财"}

def erxuanyi_faze(bazi_str):
    """素水·二选一法则：吃皇粮vs自己干, 外面吸引力太小可能不去"""
    r = tizhinei_lujing(bazi_str)
    chl = r.get("吃皇粮", False)
    mode = r.get("模式", "")
    
    if chl and "混搭" in mode:
        return {"二选一": True, "法则": "当八字同时构成吃皇粮和自己干时, 以外部吸引力大小决定", "倾向": "外部官杀不够旺→倾向自己干; 外部官杀有力→吃皇粮"}
    return {"二选一": False, "法则": "路径单一, 无二选一冲突"}

def wenwu_chongtu(bazi_str):
    """素水·文武冲突：印不能夺食/制化不能同用"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    
    yin_tg = [g for g in gans if get_shishen(dm,g) in ["正印","偏印"]]
    shi_tg = [g for g in gans if get_shishen(dm,g) == "食神"]
    
    if yin_tg and shi_tg:
        return {"文武冲突": True, "说明": "印夺食→文武碰面必败", "素水原话": "印不能夺食, 夺食就完了"}
    return {"文武冲突": False}



def hunyin_cishu(bazi_str):
    """素水·婚姻次数铁律：财星/官星数量=婚姻次数, 不是看穿不穿"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    
    # 财星(男)/官杀(女) 总数 = 婚姻次数
    cai_tg = sum(1 for g in gans if get_shishen(dm,g) in ["正财","偏财"])
    cai_zg = 0
    for z in zhis:
        for cg in ZHI_CANGGAN.get(z,""):
            if get_shishen(dm,cg) in ["正财","偏财"]:
                cai_zg += 1
    
    total = cai_tg + cai_zg
    if total >= 4: result = f"{total}个→多次婚姻"
    elif total >= 3: result = f"{total}个→2次以上婚姻"
    elif total >= 2: result = f"{total}个→1-2次婚姻"
    else: result = f"{total}个→婚姻单一"
    
    return {"财官总数": total, "判定": result, "素水原话": "人数数量定几次婚姻, 不是穿不穿的问题"}

def zuogong_santiao(bazi_str):
    """素水·三条做功主线识别: 化杀生印/食伤生财/食神制杀"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    
    mains = []
    # 化杀生印: 七杀+印同现
    sha = sum(1 for g in gans if get_shishen(dm,g)=="七杀")
    yin = sum(1 for g in gans if get_shishen(dm,g) in ["正印","偏印"])
    if sha >= 1 and yin >= 1: mains.append("化杀生印→权力/体制主线")
    
    # 食伤生财: 食伤+财同现
    shi = sum(1 for g in gans if get_shishen(dm,g) in ["食神","伤官"])
    cai = sum(1 for g in gans if get_shishen(dm,g) in ["正财","偏财"])
    if shi >= 1 and cai >= 1: mains.append("食伤生财→技术/生意主线")
    
    # 食神制杀: 食神+七杀同现
    if shi >= 1 and sha >= 1: mains.append("食神制杀→权谋/抗争主线")
    
    dominant = mains[0] if mains else "无明确主线→看五行流通"
    return {"主线": mains, "主导": dominant, "素水原话": "三条主线:化杀生印/食伤生财/食神制杀"}

def cengci_quxiang(bazi_str):
    """素水·层次先于取象: 定完层次才取象, 不先取象"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    score = rate_mingju(bazi_str)["score"]
    jw = sushi_jialiwai(bazi_str)
    mode = jw.get("模式","") if jw else ""
    
    level = ""
    if score >= 4.0: level = "上层"
    elif score >= 3.3: level = "中上层"
    elif score >= 2.8: level = "中层"
    else: level = "基层"
    
    industry = ""
    dm_wx = GAN_WX.get(b["day_gan"],"")
    if mode and "创业" in mode:
        industry = "金水→金融/科技私企; 木火→文化/教育创业" if dm_wx in ["金","水","木","火"] else ""
    
    return {"层次": level, "模式": mode, "取象建议": industry, "素水原话": "先定层次再取象, 不加上前四步的铺垫上来就取象就是乱套"}



def nayin_ti_an(bazi_str):
    """王咸炽·纳音堤岸法则：纳音五行成堤防→富贵格局"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    gans = [b["year_gan"],b["month_gan"],b["day_gan"],b["hour_gan"]]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    ny_table = nayan_60jiazi()
    ny_list = [ny_table.get(g+z,"") for g,z in zip(gans,zhis)]
    
    checks = []
    # 纳音堤岸: 纳音木火相生/金水相生=有堤防
    wx_list = [nayan_wuxing(n) for n in ny_list]
    if wx_list.count("木") >= 2 and wx_list.count("火") >= 2:
        checks.append("纳音木火相生→文明富贵之堤")
    if wx_list.count("金") >= 2 and wx_list.count("水") >= 2:
        checks.append("纳音金水相生→智慧流通之堤")
    if wx_list.count("土") >= 3:
        checks.append("纳音土重为堤→厚重承载")
    
    return {"纳音": ny_list, "堤岸": checks if checks else ["无特殊堤岸"], "法则来源": "王咸炽·古传纳音论命法"}

def nayin_wuxing_juzu(bazi_str):
    """纳音法则·五行俱足：纳音五行全=贵格"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    gans = [b["year_gan"],b["month_gan"],b["day_gan"],b["hour_gan"]]
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    ny_table = nayan_60jiazi()
    wx_list = [nayan_wuxing(ny_table.get(g+z,"")) for g,z in zip(gans,zhis)]
    
    unique = set(wx_list)
    if len(unique) >= 4:
        return {"五行俱足": True, "纳音五行": list(unique), "判定": "纳音五行齐全→大贵之格"}
    return {"五行俱足": False, "纳音五行": list(unique)}

def nayin_ye_lian(bazi_str):
    """纳音冶炼法则：煞旺有印→以煞成权"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    gans = [b["year_gan"],b["month_gan"],b["hour_gan"]]
    
    sha = sum(1 for g in gans if get_shishen(dm,g)=="七杀")
    yin = sum(1 for g in gans if get_shishen(dm,g) in ["正印","偏印"])
    
    if sha >= 2 and yin >= 1:
        return {"冶炼": True, "判词": "纳音煞旺有印→冶炼成器, 以煞成权"}
    return {"冶炼": False}



def nayin_zhuben(bazi_str):
    """王咸炽·主本法则：年月=前半生(主), 日时=后半生(本)"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    ny_table = nayan_60jiazi()
    ny_year = ny_table.get(b["year_gan"]+b["year_zhi"],"")
    ny_month = ny_table.get(b["month_gan"]+b["month_zhi"],"")
    ny_day = ny_table.get(b["day_gan"]+b["day_zhi"],"")
    ny_hour = ny_table.get(b["hour_gan"]+b["hour_zhi"],"")
    
    zhu = f"{ny_year}→{ny_month}"  # 主=年月
    ben = f"{ny_day}→{ny_hour}"    # 本=日时
    
    # 纳音五行生克
    zhu_wx = [nayan_wuxing(ny_year), nayan_wuxing(ny_month)]
    ben_wx = [nayan_wuxing(ny_day), nayan_wuxing(ny_hour)]
    
    sheng = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
    zhu_sheng = zhu_wx[0] and zhu_wx[1] and sheng.get(zhu_wx[0])==zhu_wx[1]
    ben_sheng = ben_wx[0] and ben_wx[1] and sheng.get(ben_wx[0])==ben_wx[1]
    
    result = ""
    if zhu_sheng and ben_sheng: result = "主本皆生→一生顺遂"
    elif zhu_sheng: result = "主生本不生→早年好, 晚年差"
    elif ben_sheng: result = "本生主不生→早年苦, 晚年好"
    else: result = "主本皆不生→靠自己"
    
    return {"主(前半生)": zhu, "本(后半生)": ben, "判定": result, "王咸炽原话": "年月为主为前半生, 日时为本为后半生"}

def nayin_yinyong(bazi_str):
    """王咸炽·引用法则：年柱在日时有财官印=有引有用"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    dm = b["day_gan"]
    year_gan = b["year_gan"]
    
    # Check if year stem's十神 appears in day/hour
    day_ss = get_shishen(dm, b["day_gan"])  # 日干对日主的十神
    hour_ss = get_shishen(dm, b["hour_gan"])
    
    has_yin = any(ss in ["正财","偏财","正官","七杀","正印","偏印"] for ss in [get_shishen(dm, year_gan)])
    yin_in_day = get_shishen(dm, year_gan) == get_shishen(dm, b["day_gan"]) if False else False
    yin_in_hour = get_shishen(dm, year_gan) == get_shishen(dm, b["hour_gan"]) if False else False
    
    # Simplified: check if year stem has any relationship with day/hour stems
    day_rel = get_shishen(dm, b["day_gan"])
    hour_rel = get_shishen(dm, b["hour_gan"])
    year_rel = get_shishen(dm, year_gan)
    
    yin = year_rel in ["正财","偏财","正官","七杀","正印","偏印","食神","伤官"]
    yong_day = day_rel in ["正财","偏财","正官","七杀","正印","偏印"]
    yong_hour = hour_rel in ["正财","偏财","正官","七杀","正印","偏印"]
    
    if yin and yong_day and yong_hour: jie = "有引有用→一生富贵"
    elif yin and yong_day: jie = "有引无用→晚年不佳"
    elif yin and yong_hour: jie = "有用无引→中年劳累"
    else: jie = "无引无用→白手起家"
    
    return {"引用": jie, "年干": year_gan, "日干": b["day_gan"], "时干": b["hour_gan"]}

def nayin_sigui(bazi_str):
    """王咸炽·四贵四平四忌：年干在月日时支的吉凶分级"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    year_gan = b["year_gan"]
    zhis = [b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    
    # 四贵: 年干的禄/旺/长生/贵人所在支
    lu_map = {"甲":"寅","乙":"卯","丙":"巳","丁":"午","戊":"巳","己":"午","庚":"申","辛":"酉","壬":"亥","癸":"子"}
    wang_map = {"甲":"卯","乙":"寅","丙":"午","丁":"巳","戊":"午","己":"巳","庚":"酉","辛":"申","壬":"子","癸":"亥"}
    changsheng = {"甲":"亥","乙":"午","丙":"寅","丁":"酉","戊":"寅","己":"酉","庚":"巳","辛":"子","壬":"申","癸":"卯"}
    
    gui_zhi = {lu_map.get(year_gan,""), wang_map.get(year_gan,""), changsheng.get(year_gan,"")}
    
    gui_count = sum(1 for z in zhis if z in gui_zhi)
    level = "上等(四贵)" if gui_count >= 2 else ("中等" if gui_count >= 1 else "平凡")
    
    return {"四贵支": list(gui_zhi), "命中数": gui_count, "等级": level}



def nayin_ziren(bazi_str):
    """王咸炽·自刃检测：丙午/丁未/壬子/癸丑等日时自刃=损配偶/损子"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    day = b["day_gan"]+b["day_zhi"]
    hour = b["hour_gan"]+b["hour_zhi"]
    ziren = {"丙午":"阳刃","丁未":"阴刃","壬子":"阳刃","癸丑":"阴刃","戊午":"阳刃","己未":"阴刃"}
    
    warnings = []
    if day in ziren:
        warnings.append(f"日柱{day}自刃→半损配偶")
    if hour in ziren:
        warnings.append(f"时柱{hour}自刃→损子息")
    
    return {"自刃": warnings if warnings else ["无自刃"], "王咸炽原话": "自刃在日半损配偶, 在时损子"}

def nayin_bolang(bazi_str):
    """王咸炽·波浪限：纳音金命行子运=大凶"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    ny_table = nayan_60jiazi()
    ny_year = ny_table.get(b["year_gan"]+b["year_zhi"],"")
    ny_wx = nayan_wuxing(ny_year)
    
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    warnings = []
    if ny_wx == "金" and "子" in zhis:
        warnings.append("纳音金命逢子→波浪限, 大凶(行子运尤甚)")
    if ny_wx == "木" and "酉" in zhis:
        warnings.append("纳音木命逢酉→波浪限")
    if ny_wx == "水" and "午" in zhis:
        warnings.append("纳音水命逢午→波浪限")
    
    return {"波浪限": warnings if warnings else ["无"], "王咸炽原话": "年柱纳音金行子运为波浪限,大凶"}

def nayin_puzhai(bazi_str):
    """王咸炽·破宅杀：同纳音克年柱=破财散失"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    ny_table = nayan_60jiazi()
    ny_year = ny_table.get(b["year_gan"]+b["year_zhi"],"")
    ny_month = ny_table.get(b["month_gan"]+b["month_zhi"],"")
    
    year_wx = nayan_wuxing(ny_year)
    month_wx = nayan_wuxing(ny_month)
    
    ke = {"金":"木","木":"土","土":"水","水":"火","火":"金"}
    if month_wx == ke.get(year_wx,""):
        return {"破宅杀": True, "判词": "月纳音克年纳音→破宅杀, 主破财/祖业有损"}
    return {"破宅杀": False}



def nayin_liu_e(bazi_str):
    """王咸炽·六厄检测：纳音克年柱纳音=灾重/刑狱"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    ny_table = nayan_60jiazi()
    ny_year = ny_table.get(b["year_gan"]+b["year_zhi"],"")
    year_wx = nayan_wuxing(ny_year)
    ke = {"金":"木","木":"土","土":"水","水":"火","火":"金"}
    
    zhis = [b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    gans = [b["month_gan"],b["day_gan"],b["hour_gan"]]
    warnings = []
    for g,z in zip(gans, zhis):
        ny = ny_table.get(g+z,"")
        wx = nayan_wuxing(ny)
        if wx == ke.get(year_wx,""):
            warnings.append(f"{g}{z}{ny}克年柱纳音→六厄之柱, 主人心地奸险名望微贱, 岁运值之有刑狱破伤")
    
    return {"六厄": warnings if warnings else ["无"], "王咸炽原话": "六厄之柱纳音克年柱纳音为灾重"}

def nayin_jitou_gui(bazi_str):
    """王咸炽·劫头鬼/禄头鬼：劫杀柱天克年干=无官; 禄头鬼=甲科或口舌"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    year_gan = b["year_gan"]
    year_wx = GAN_WX.get(year_gan,"")
    ke_map = {"金":"木","木":"土","土":"水","水":"火","火":"金"}
    
    warnings = []
    for pos, g in [("月",b["month_gan"]),("日",b["day_gan"]),("时",b["hour_gan"])]:
        g_wx = GAN_WX.get(g,"")
        if g_wx == ke_map.get(year_wx,""):
            warnings.append(f"{pos}干{g}克年干→劫头鬼, 主无官职/免职")
    
    return {"劫头鬼": warnings if warnings else ["无"], "王咸炽原话": "劫头鬼者劫杀之柱天干五克年干五行, 主无官职"}

def nayin_xianchi_nv(bazi_str):
    """王咸炽·咸池(桃花)女命：日时咸池=克夫少子/损孕"""
    b = parse_bazi(bazi_str)
    if not b: return {}
    zhis = [b["year_zhi"],b["month_zhi"],b["day_zhi"],b["hour_zhi"]]
    # 咸池(桃花): 寅午戌在卯, 申子辰在酉, 亥卯未在子, 巳酉丑在午
    taohua = {"寅":"卯","午":"卯","戌":"卯","申":"酉","子":"酉","辰":"酉","亥":"子","卯":"子","未":"子","巳":"午","酉":"午","丑":"午"}
    
    day_th = taohua.get(b["day_zhi"],"")
    hour_th = taohua.get(b["hour_zhi"],"")
    warnings = []
    if day_th in zhis[:2]: warnings.append("日犯咸池→女命丈夫有损")
    if hour_th in zhis: warnings.append("时犯咸池→女命多损孕")
    
    return {"咸池": warnings if warnings else ["无"], "王咸炽原话": "女命日时犯咸池为恶应, 主克夫少子多病"}

def analyze(bazi_str, age=None, auto_record=True, year=None, gender="male", birth_lunar=None):
    result = {}
    
    # ===== v3.5 素水/盲派为主 → 子平为辅 =====
    sushi_analysis = {}
    try:
        sushi_analysis["做功"] = sushi_zuogong(bazi_str)
        sushi_analysis["家里家外"] = sushi_jialiwai(bazi_str)
        sushi_analysis["功神"] = gong_shen(bazi_str)
        sushi_analysis["吃皇粮"] = chihuangliang(bazi_str)
        sushi_analysis["伤官见官"] = shangguan_jianguan(bazi_str)
        sushi_analysis["十神链"] = shishen_chain(bazi_str)
        sushi_analysis["合绊"] = he_ban_check(bazi_str)
        sushi_analysis["认领"] = renling_faze(bazi_str)
        sushi_analysis["象理技"] = xiangliji_sanfen(bazi_str)
        sushi_analysis["十干喜忌"] = shigan_xiji_deep(pb["day_gan"]) if pb else {}
    except: pass
    result["素水盲派（主）"] = sushi_analysis
    
    # 子平辅助
    try:
        rating = rate_mingju(bazi_str)
        result["子平格局（辅）"] = rating
    except:
        rating = {}
    result["格局评分"] = rating
    
    # 置信度
    qz = check_qingzhuo(bazi_str)
    score = rating["score"]
    if "从格" in rating["level"]:
        confidence = "高（从格确认）"
    elif score >= 4.0 and qz[0] in ["清","中"]:
        confidence = "高"
    elif score >= 3.5 and qz[0] in ["清"]:
        confidence = "较高"
    elif score >= 3.0:
        confidence = "中"
    else:
        confidence = "低"
    result["置信度"] = confidence
    
    # 相似案例
    similar = find_similar(bazi_str)
    result["相似案例"] = [{"案例": s.get("name",""), "相似度": s.get("score",0)} for s in similar]
    
    # 古籍补充：调候检查
    th = check_tiaohou(bazi_str)
    if th["降级"]:
        result["调候"] = th["调候"]
        if score >= 3.5 and score < 4.0:
            result["格局评分"]["level"] = "中品（调候不足降级）"
        elif score >= 4.0:
            result["格局评分"]["score"] -= 0.3
            result["格局评分"]["level"] = "中品（调候不足降级）"
            result["格局评分"]["score"] = round(result["格局评分"]["score"], 1)
    
    # ===== 交叉验证（盲派 vs 子平） =====
    try:
        zuogong = sushi_zuogong(bazi_str)
        jialiwai = sushi_jialiwai(bazi_str)
        score = result["格局评分"]["score"]
        xv_result = {"盲派做功": zuogong.get("做功", []) if zuogong else [],
                     "盲派家里家外": jialiwai.get("模式", "") if jialiwai else "",
                     "子平评分": score,
                     "差异备注": []}
        
        if zuogong and zuogong.get("做功"):
            has_work = any(w not in ["做功不明显→按常规五行生克判断"] for w in zuogong["做功"])
            if has_work and score < 2.8:
                xv_result["差异备注"].append("⚠️ 盲派有做功但子平评分低：盲派认为可成事，子平认为格局不足")
            if not has_work and score >= 4.0:
                xv_result["差异备注"].append("ℹ️ 盲派无做功但子平评分高：子平调候/清纯维度得分，盲派未覆盖")
        
        if jialiwai and "全在家内" in jialiwai.get("模式","") and score < 3.0:
            xv_result["差异备注"].append("⚠️ 盲派创业型但评分低：有自主之心但时运未到")
        
        if not xv_result["差异备注"]:
            xv_result["差异备注"].append("✅ 两派结论一致")
        
        result["交叉验证"] = xv_result
    except Exception as e:
        result["交叉验证"] = {"盲派做功": [], "盲派家里家外": "", "子平评分": 0, "差异备注": [f"验证异常: {e}"]}
    
    # 体用分析（九大法则·第七层）
    try:
        result["体用分析"] = tiyong_analyze(bazi_str)
    except Exception:
        pass
    
    # 喜用神（精度地基）
    try:
        result["喜用神"] = calc_xiyong(bazi_str)
    except Exception:
        pass
    
    # 大运年龄自动推算
    try:
        inferred = infer_age_and_dayun(bazi_str, age, gender, birth_lunar)
        result["年龄推算"] = inferred
        if age is None:
            age = inferred.get("年龄", 30)
    except Exception:
        pass
    
    # 案例格局级匹配
    try:
        gege_similar = find_similar_by_gege(bazi_str, 3)
        result["相似案例_格局级"] = [{"案例": s[1].get("name", s[1].get("标签", "?")), "得分": s[0], "八字": s[1].get("bazi","")} 
                                   for s in gege_similar if isinstance(s, (list, tuple)) and len(s) >= 2]
    except Exception:
        pass
    
    # 正反局分析（九大法则·第六层）
    try:
        result["正反局"] = zhengfanju_analysis(bazi_str)
    except Exception:
        pass
    
    # 三年一跃应期（九大法则·第八层叙事版）
    try:
        result["三年一跃"] = yingqi_3year(bazi_str)
    except Exception:
        pass
    
    # ===== 月级应期（P0升级：年→月精度）=====
    try:
        target_years = [year] if year else list(range(2026, 2031))
        monthly_results = {}
        for y in target_years:
            monthly_results[str(y)] = yingqi_monthly(bazi_str, y)
        result["逐月应期"] = monthly_results
    except Exception:
        pass
    # ===== 月级应期结束 =====
    
    # ===== 精细化：叙事弧+事件细化 =====
    try:
        if result.get("逐月应期"):
            for y_str in result["逐月应期"]:
                raw = result["逐月应期"][y_str]
                # 事件细化
                result["逐月应期"][y_str] = apply_all_refinements(bazi_str, raw)
                # 叙事弧
                result[f"叙事弧_{y_str}"] = monthly_narrative_arc(result["逐月应期"][y_str], int(y_str))
    except Exception:
        pass
    # ===== 精细化结束 =====
    
    # ===== P1：六亲分析 =====
    try:
        result["六亲"] = liuqin_analyze(bazi_str, age=age)
    except Exception:
        pass
    # ===== 六亲结束 =====
    
    # ===== P1：健康分析 =====
    try:
        target_year = year if year else 2026
        result["健康"] = health_analyze(bazi_str, target_year)
    except Exception:
        pass
    # ===== 健康结束 =====
    
    # ===== 预测回测：自动记录 =====
    if auto_record and PREDICT_AVAILABLE:
        try:
            pid = auto_prediction(bazi_str, result, name="", case_id="")
            result["预测ID"] = pid
            result["预测记录"] = "已自动记录到回测系统"
        except Exception:
            result["预测记录"] = "回测记录失败"
    # ===== 预测回测结束 =====
    
    # ===== 全模块集成：通关 + 病药 + 翻译表 + 行动指南 =====
    try:
        result["通关"] = tongguan_analyze(bazi_str)
    except:
        pass
    try:
        result["病药"] = bingyao_analyze(bazi_str)
    except:
        pass
    try:
        result["行动指南"] = action_guide(bazi_str)
    except:
        pass
    try:
        score = result.get("格局评分", {}).get("score", 3.0)
        result["收尾"] = shuang_gui_shouwei(score)
    except:
        pass
    try:
        result["人群位置"] = get_simu_renqun(result.get("格局评分", {}).get("level", ""))
    except:
        pass
    try:
        if result.get("六亲"):
            mt = get_marriage_translation("", bazi_str)
            result["六亲"]["婚姻翻译"] = {"妻星翻译": mt, "六合引动": hehun_liuhe_translate("","")} if mt else {}
    except:
        pass
    
    return result

# ===== P2：合婚合盘系统 =====

# 纳音表（年柱纳音五行）
NAYIN_MAP = {
    "甲子乙丑": "金", "丙寅丁卯": "火", "戊辰己巳": "木", "庚午辛未": "土", "壬申癸酉": "金",
    "甲戌乙亥": "火", "丙子丁丑": "水", "戊寅己卯": "土", "庚辰辛巳": "金", "壬午癸未": "木",
    "甲申乙酉": "水", "丙戌丁亥": "土", "戊子己丑": "火", "庚寅辛卯": "木", "壬辰癸巳": "水",
    "甲午乙未": "金", "丙申丁酉": "火", "戊戌己亥": "木", "庚子辛丑": "土", "壬寅癸卯": "金",
    "甲辰乙巳": "火", "丙午丁未": "水", "戊申己酉": "土", "庚戌辛亥": "金", "壬子癸丑": "木",
    "甲寅乙卯": "水", "丙辰丁巳": "土", "戊午己未": "火", "庚申辛酉": "木", "壬戌癸亥": "水"
}

# 地支六合
ZHI_LIUHE = {"子":"丑","丑":"子","寅":"亥","卯":"戌","辰":"酉","巳":"申",
             "午":"未","未":"午","申":"巳","酉":"辰","戌":"卯","亥":"寅"}
# 地支三合
ZHI_SANHE = [{"申","子","辰"},{"亥","卯","未"},{"寅","午","戌"},{"巳","酉","丑"}]
# 地支六冲
ZHI_LIUCHONG = {"子":"午","丑":"未","寅":"申","卯":"酉","辰":"戌","巳":"亥",
                "午":"子","未":"丑","申":"寅","酉":"卯","戌":"辰","亥":"巳"}
# 地支六害
ZHI_LIUHAI = {"子":"未","丑":"午","寅":"巳","卯":"辰","申":"亥","酉":"戌",
              "未":"子","午":"丑","巳":"寅","辰":"卯","亥":"申","戌":"酉"}

WX_SHENG = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
WX_KE = {"木":"土","土":"水","水":"火","火":"金","金":"木"}
WX_MAP_GAN = {"甲乙":"木","丙丁":"火","戊己":"土","庚辛":"金","壬癸":"水"}
ZHI_WX_MAP = {"寅":"木","卯":"木","辰":"土","巳":"火","午":"火","未":"土",
              "申":"金","酉":"金","戌":"土","亥":"水","子":"水","丑":"土"}


def _nianzhu_nayin(年干, 年支):
    """获取年柱纳音五行"""
    gz = 年干 + 年支
    for pair, wx in NAYIN_MAP.items():
        if gz in pair:
            return wx
    return ""


def hehun_score(bazi_male, bazi_female, male_name="男方", female_name="女方"):
    """合婚合盘：两人八字综合匹配度
    
    返回: {
        total: 总分0-10,
        level: 上婚/中婚/下婚,
        dimensions: {五个维度},
        conclusion: str,
        建议: str
    }
    """
    pb_m = parse_bazi(bazi_male)
    pb_f = parse_bazi(bazi_female)
    if not pb_m or not pb_f:
        return {}
    
    dims = {}
    total = 0
    
    # ===== 1. 年柱纳音合（2分 → 扩展为多柱纳音3分）=====
    # 年柱纳音
    nf_m = _nianzhu_nayin(pb_m["year_gan"], pb_m["year_zhi"])
    nf_f = _nianzhu_nayin(pb_f["year_gan"], pb_f["year_zhi"])
    
    nayin_score = 0
    nayin_detail = []
    
    # 年柱纳音（1.5分）
    if nf_m and nf_f:
        if nf_m == nf_f:
            nayin_score += 1.0; nayin_detail.append(f"年纳音相同({nf_m})")
        elif WX_SHENG.get(nf_m) == nf_f or WX_SHENG.get(nf_f) == nf_m:
            nayin_score += 1.5; nayin_detail.append(f"年纳音相生({nf_m}生{nf_f})")
        elif WX_KE.get(nf_m) == nf_f or WX_KE.get(nf_f) == nf_m:
            nayin_score += 0; nayin_detail.append(f"年纳音相克({nf_m}克{nf_f})")
        else:
            nayin_score += 0.5; nayin_detail.append(f"年纳音无特殊关系")
    
    # 月柱纳音（0.75分）
    nf_m_m = _nianzhu_nayin(pb_m["month_gan"], pb_m["month_zhi"])
    nf_f_m = _nianzhu_nayin(pb_f["month_gan"], pb_f["month_zhi"])
    if nf_m_m and nf_f_m:
        if nf_m_m == nf_f_m or WX_SHENG.get(nf_m_m) == nf_f_m or WX_SHENG.get(nf_f_m) == nf_m_m:
            nayin_score += 0.75; nayin_detail.append(f"月纳音合({nf_m_m}/{nf_f_m})")
        elif WX_KE.get(nf_m_m) == nf_f_m or WX_KE.get(nf_f_m) == nf_m_m:
            nayin_score += 0; nayin_detail.append(f"月纳音相克({nf_m_m}克{nf_f_m})")
        else:
            nayin_score += 0.3
    
    # 日柱纳音（0.75分）
    nf_m_d = _nianzhu_nayin(pb_m["day_gan"], pb_m["day_zhi"])
    nf_f_d = _nianzhu_nayin(pb_f["day_gan"], pb_f["day_zhi"])
    if nf_m_d and nf_f_d:
        if nf_m_d == nf_f_d or WX_SHENG.get(nf_m_d) == nf_f_d or WX_SHENG.get(nf_f_d) == nf_m_d:
            nayin_score += 0.75; nayin_detail.append(f"日纳音合({nf_m_d}/{nf_f_d})")
        elif WX_KE.get(nf_m_d) == nf_f_d or WX_KE.get(nf_f_d) == nf_m_d:
            nayin_score += 0; nayin_detail.append(f"日纳音相克({nf_m_d}克{nf_f_d})")
        else:
            nayin_score += 0.3
    
    nayin_score = min(nayin_score, 3.0)
    total += nayin_score
    dims["纳音合"] = {"得分": round(nayin_score,1), "满分": 3, "详情": "；".join(nayin_detail) if nayin_detail else "无纳音数据"}
    
    # ===== 2. 日柱关系（3分）=====
    dz_m = pb_m["day_zhi"]
    dz_f = pb_f["day_zhi"]
    dg_m = pb_m["day_gan"]
    dg_f = pb_f["day_gan"]
    
    ri_score = 0
    ri_detail = ""
    
    # 六合
    if ZHI_LIUHE.get(dz_m) == dz_f:
        ri_score = 3.0
        ri_detail = f"日支六合({dz_m}合{dz_f})——夫妻感情深，大吉之象"
    # 三合
    elif any({dz_m, dz_f}.issubset(g) for g in ZHI_SANHE):
        ri_score = 2.5
        ri_detail = f"日支三合({dz_m}与{dz_f}三合局)——关系和谐，中吉"
    # 相冲
    elif ZHI_LIUCHONG.get(dz_m) == dz_f or ZHI_LIUCHONG.get(dz_f) == dz_m:
        ri_score = 0.5
        ri_detail = f"⚠️ 日支相冲({dz_m}冲{dz_f})——夫妻间易有争拗，需磨合"
    # 相害
    elif ZHI_LIUHAI.get(dz_m) == dz_f or ZHI_LIUHAI.get(dz_f) == dz_m:
        ri_score = 0.5
        ri_detail = f"⚠️ 日支相害({dz_m}害{dz_f})——暗中消耗，易生间隙"
    # 相刑
    elif dz_m == dz_f and dz_m in ("辰","午","酉","亥"):
        ri_score = 1.0
        ri_detail = f"日支相同({dz_m})自刑——两人性格像，容易互相消耗"
    else:
        ri_score = 1.5
        ri_detail = f"日支无特殊关系——需要靠后天经营"
    
    # 天干加分：日干相生
    if WX_SHENG.get(dg_m) == dg_f or WX_SHENG.get(dg_f) == dg_m:
        ri_score = min(ri_score + 0.5, 3.0)
        ri_detail += "；日干相生，精神层面有共鸣"
    elif dg_m == dg_f:
        ri_detail += "；日干相同，性格相似但容易固执己见"
    
    total += ri_score
    dims["日柱关系"] = {"得分": ri_score, "满分": 3, "详情": ri_detail}
    
    # ===== 3. 喜用互补（2分）=====
    xiyong_m = _rough_xiyong(bazi_male)
    xiyong_f = _rough_xiyong(bazi_female)
    
    wxf_m = _wx_count(bazi_male)
    wxf_f = _wx_count(bazi_female)
    
    bu_score = 0
    bu_detail = []
    
    # 男方的喜用神是女方的旺神？
    for wx in xiyong_m.get("喜", []):
        if wxf_f.get(wx, 0) >= 2:
            bu_score += 0.5
            bu_detail.append(f"男方喜{wx}，女方{wx}旺→互补")
    for wx in xiyong_f.get("喜", []):
        if wxf_m.get(wx, 0) >= 2:
            bu_score += 0.5
            bu_detail.append(f"女方喜{wx}，男方{wx}旺→互补")
    
    # 男方的忌神女方正好弱？
    for wx in xiyong_m.get("忌", []):
        if wxf_f.get(wx, 0) < 1:
            bu_score += 0.25
    for wx in xiyong_f.get("忌", []):
        if wxf_m.get(wx, 0) < 1:
            bu_score += 0.25
    
    bu_score = min(bu_score, 2.0)
    total += bu_score
    dims["喜用互补"] = {"得分": bu_score, "满分": 2, "详情": "；".join(bu_detail) if bu_detail else "无明显互补"}
    
    # ===== 4. 刑冲检测（2分）=====
    chong_score = 2.0
    chong_detail = []
    
    m_zhis = [pb_m["year_zhi"], pb_m["month_zhi"], pb_m["day_zhi"], pb_m["hour_zhi"]]
    f_zhis = [pb_f["year_zhi"], pb_f["month_zhi"], pb_f["day_zhi"], pb_f["hour_zhi"]]
    
    for mz in m_zhis:
        for fz in f_zhis:
            # 冲
            if ZHI_LIUCHONG.get(mz) == fz:
                chong_score -= 0.3
                chong_detail.append(f"冲：{mz}冲{fz}")
            # 害
            if ZHI_LIUHAI.get(mz) == fz:
                chong_score -= 0.2
                chong_detail.append(f"害：{mz}害{fz}")
    
    chong_score = max(chong_score, 0)
    chong_detail_str = "；无严重刑冲" if not chong_detail else "；".join(chong_detail[:4])
    
    total += chong_score
    dims["刑冲检测"] = {"得分": chong_score, "满分": 2, "详情": chong_detail_str}
    
    # ===== 5. 五行互补（1分）=====
    wx_score = 0
    wx_detail = []
    all_wx = ["木","火","土","金","水"]
    for wx in all_wx:
        m_count = wxf_m.get(wx, 0)
        f_count = wxf_f.get(wx, 0)
        if m_count >= 2.5 and f_count < 1:
            # 男多女少→女方受益
            wx_score += 0.2
            wx_detail.append(f"男方{wx}旺可补女方")
        elif f_count >= 2.5 and m_count < 1:
            wx_score += 0.2
            wx_detail.append(f"女方{wx}旺可补男方")
        elif m_count >= 2.5 and f_count >= 2.5:
            wx_score -= 0.1
            wx_detail.append(f"双方{wx}均旺→注意过犹不及")
    
    wx_score = max(0, min(wx_score, 1.0))
    total += wx_score
    dims["五行互补"] = {"得分": wx_score, "满分": 1, "详情": "；".join(wx_detail) if wx_detail else "无明显互补"}
    
    # ===== 总分+等级 =====
    total = round(total, 1)
    if total >= 8:
        level = "上婚（天作之合）"
    elif total >= 6:
        level = "中上婚（良缘可成）"
    elif total >= 4:
        level = "中婚（需经营）"
    else:
        level = "下婚（磨合期长）"
    
    # 结论叙述
    conclusion_parts = []
    if dims["日柱关系"]["得分"] >= 2.5:
        conclusion_parts.append("两人日柱相合，夫妻缘分深。")
    elif dims["日柱关系"]["得分"] < 1:
        conclusion_parts.append("日柱有冲/害，需要在沟通上多下功夫。")
    
    if dims["喜用互补"]["得分"] >= 1:
        conclusion_parts.append("喜用神互补，在一起能互相滋养。")
    else:
        conclusion_parts.append("喜用神无明显互补，相处中需彼此包容。")
    
    if dims["刑冲检测"]["得分"] < 1.5:
        conclusion_parts.append("⚠️ 八字间有较多刑冲，生活中易有摩擦，需双方有意识磨合。")
    
    return {
        "male": bazi_male,
        "female": bazi_female,
        "total": total,
        "level": level,
        "dimensions": dims,
        "conclusion": " ".join(conclusion_parts),
        "suggestions": _hehun_suggestions(dims)
    }


def _rough_xiyong(bazi_str):
    """简易喜用神判断"""
    pb = parse_bazi(bazi_str)
    if not pb:
        return {"喜": [], "忌": []}
    dm = pb["day_gan"]
    WX_MAP = {"甲乙":"木","丙丁":"火","戊己":"土","庚辛":"金","壬癸":"水"}
    dm_wx = ""
    for k, v in WX_MAP.items():
        if dm in k:
            dm_wx = v
    
    # 月令
    mz_wx = ZHI_WX_MAP.get(pb["month_zhi"], "")
    wxs = ["木","火","土","金","水"]
    
    # 简单身强/身弱判断
    # 算月令生助
    born = WX_SHENG.get(dm_wx, "")
    strong_months = {"木":["寅","卯"],"火":["巳","午"],"土":["辰","戌","丑","未"],
                     "金":["申","酉"],"水":["亥","子"]}
    weak_months = {"木":["申","酉"],"火":["亥","子"],"土":["寅","卯"],
                   "金":["巳","午"],"水":["辰","戌","丑","未"]}
    
    if pb["month_zhi"] in strong_months.get(dm_wx, []):
        # 身旺，喜克泄
        xi = [WX_KE.get(dm_wx, ""), WX_SHENG.get(dm_wx, "")]
        ji = [dm_wx, born]
    elif pb["month_zhi"] in weak_months.get(dm_wx, []):
        # 身弱，喜生助
        xi = [born, dm_wx]
        ji = [WX_KE.get(dm_wx, ""), WX_SHENG.get(dm_wx, "")]
    else:
        # 四季月，中性
        xi = [born, dm_wx]
        ji = [WX_KE.get(dm_wx, "")]
    
    return {"喜": [x for x in xi if x], "忌": [x for x in ji if x]}


def _wx_count(bazi_str):
    """简易五行计数"""
    pb = parse_bazi(bazi_str)
    if not pb:
        return {}
    CANGAN = {"子":"癸","丑":"己癸辛","寅":"甲丙戊","卯":"乙","辰":"戊乙癸",
              "巳":"丙庚戊","午":"丁己","未":"己丁乙","申":"庚壬戊",
              "酉":"辛","戌":"戊辛丁","亥":"壬甲"}
    wx = {"木":0,"火":0,"土":0,"金":0,"水":0}
    gans = [pb["year_gan"], pb["month_gan"], pb["day_gan"], pb["hour_gan"]]
    zhis = [pb["year_zhi"], pb["month_zhi"], pb["day_zhi"], pb["hour_zhi"]]
    WX_MAP = {"甲乙":"木","丙丁":"火","戊己":"土","庚辛":"金","壬癸":"水"}
    for g in gans:
        for k,v in WX_MAP.items():
            if g in k: wx[v] += 1
    for z in zhis:
        z_wx = ZHI_WX_MAP.get(z, "")
        if z_wx: wx[z_wx] += 1
        for c in CANGAN.get(z, ""):
            for k,v in WX_MAP.items():
                if c in k: wx[v] += 0.5
    return wx


def _hehun_suggestions(dims):
    """合婚建议"""
    tips = []
    
    if dims["日柱关系"]["得分"] < 1.5:
        tips.append("○ 日柱非吉配，建议婚前多相处考验，婚后多创造共同话题。")
    else:
        tips.append("○ 日柱佳配，婚后注意别因太熟而忘了经营。")
    
    if dims["喜用互补"]["得分"] < 1:
        tips.append("○ 喜用互补不足，建议在生活中寻找共同兴趣作为感情纽带。")
    
    if dims["刑冲检测"]["得分"] < 1.5:
        tips.append("○ 八字刑冲较多，适合晚婚（30岁后），心智成熟后更能包容。")
    
    if dims.get("纳音合", {}).get("得分", 1) < 0.5:
        tips.append("○ 纳音相克，需注意两个原生家庭的差异。")
    
    tips.append("○ 合婚看的是先天趋势，后天经营更重要——没有不合适的八字，只有不愿意磨合的人。")
    
    return tips


# ===== P3：职业细分映射表 =====

# 十神格局→职业方向映射（核心）
GEGE_CAREER = {
    # —— 食伤生财（技术/创意型）——
    "食神生财": {
        "tag": "技术+商业",
        "适合": ["技术型创业", "顾问/咨询", "设计师", "手工艺人", "餐饮/食品", "教育培训"],
        "不适合": ["纯行政管理", "重复性流水线", "高压谈判型销售"],
        "挣钱方式": "靠本事吃饭——你有技术/手艺/服务，客户为你的产品买单",
        "人话": "不是靠嘴皮子挣钱的人，是靠手里有活。你做的东西别人做不出来，这就是你的饭碗。"
    },
    "伤官生财": {
        "tag": "创意+营销",
        "适合": ["艺术/设计/创意行业", "营销/广告/公关", "自媒体/内容创业", "演艺/娱乐", "自由职业"],
        "不适合": ["朝九晚五坐班", "官僚体系", "被管得太死的岗位"],
        "挣钱方式": "才华变现——你的表达力/创造力/审美是你的核心资产",
        "人话": "规矩太多的地方你待不住。你需要一个能让你'做自己'的赛道，越自由你越值钱。"
    },
    # —— 杀印相生（管理型）——
    "杀印相生": {
        "tag": "管理+权威",
        "适合": ["企业高管/经理人", "公务员/事业单位", "军警/法务", "医生/工程师", "项目管理"],
        "不适合": ["完全自由的创作环境", "无规则的小生意", "单打独斗的个体户"],
        "挣钱方式": "靠职位和权力挣钱——你有权威也有人给你资源",
        "人话": "你适合在大系统里做管理者。压力对你不是坏事——压力越大你反而越稳。"
    },
    # —— 食神制杀（技术+压力型）——
    "食神制杀": {
        "tag": "技术管理",
        "适合": ["技术总监/CTO", "项目经理", "质量控制/风控", "医疗技术", "军警技术岗"],
        "不适合": ["纯销售", "完全没有技术含量的岗位", "过于安逸的闲职"],
        "挣钱方式": "用你的专业能力解决复杂问题——越难的问题你越值钱",
        "人话": "你是那种'别人搞不定的时候找你'的人。平时不起眼，关键时候显身手。"
    },
    # —— 财官相生（稳定型）——
    "财官相生": {
        "tag": "稳定+上升",
        "适合": ["金融/会计/审计", "行政管理", "国企/央企", "教育/培训", "法律"],
        "不适合": ["高风险创业", "无底薪纯提成销售", "体力劳动为主的工作"],
        "挣钱方式": "靠体系挣钱——在一个稳定的平台里一步一步往上走",
        "人话": "你不适合大起大落的生活。稳稳当当上一辈子班，你的积累会在后期爆发。"
    },
    # —— 比劫夺财（合伙型）——
    "比劫夺财": {
        "tag": "合伙+竞争",
        "适合": ["合伙创业", "销售/市场", "餐饮连锁", "社交型行业", "体育/竞技"],
        "不适合": ["独来独往的岗位", "不需要人际交往的技术岗", "被人管得太死的环境"],
        "挣钱方式": "靠人脉和圈子挣钱——你认识谁和你跟谁一起干，比你会什么更重要",
        "人话": "你不是一个人能干大事的类型，但你拉着一群人就能干成大事。你的本事不是做，是组织。"
    },
    # —— 印星护身（研究型）——
    "印星护身": {
        "tag": "研究+文职",
        "适合": ["学术研究", "教育/教学", "写作/编辑", "咨询/分析", "文秘/档案"],
        "不适合": ["高压竞争环境", "频繁出差/应酬", "需要快速变现的行业"],
        "挣钱方式": "靠知识和积累挣钱——你越老越值钱",
        "人话": "你是慢热型人才。快钱跟你无缘，但你的积累会随着时间增值。"
    },
    # —— 从格（顺势型）——
    "从格": {
        "tag": "顺势+借力",
        "适合": ["跟随大势的行业", "借平台/借资源", "配套型业务", "风口行业"],
        "不适合": ["逆势而为", "自己开创新市场", "过于保守的传统行业"],
        "挣钱方式": "不用跟命争——跟着大势走，趋势给你饭吃",
        "人话": "你不是领跑的人，你是那个踩准节奏的人。风来了你第一个起飞。"
    },
    # —— 建禄格/月刃（独立型）——
    "建禄格": {
        "tag": "独立创业",
        "适合": ["自主创业", "自由职业", "连锁加盟", "电商/个体", "专业服务"],
        "不适合": ["太依赖平台的岗位", "按部就班的流水线", "需要大量资金投入的行业"],
        "挣钱方式": "自己给自己发工资——自由越大风险也越大",
        "人话": "你天生不适合给人打工。自己干虽然累，但每一分钱都是你自己的。"
    },
}

# 日主五行→适合行业
RIZHU_WX_CAREER = {
    "木": "教育/文化/出版/环保/医疗/慈善——木主生长，适合'让人变好'的行业",
    "火": "互联网/传媒/能源/演艺/餐饮——火主传播，适合'让人看见'的行业",
    "土": "房地产/建筑/农业/仓储/金融——土主承载，适合'让人安稳'的行业",
    "金": "金融/法律/机械/汽车/军警——金主变革，适合'让人精准'的行业",
    "水": "物流/贸易/旅游/水产/IT——水主流通，适合'让人流动'的行业",
}

# 宫位+十神→职业阶段
GONG_WEI_CAREER = {
    "年": "初始/祖业/大方向——适合家族生意或早年定型的行业",
    "月": "发展/社交/主流——适合在组织/团队中发展的职业路径",
    "日": "核心/自主/专长——适合围绕自身特长打造的个性化职业",
    "时": "晚年/投资/传承——适合投资/顾问/传承性质的后期工作"
}


def career_analyze(bazi_str):
    """职业方向深度分析
    
    返回: {
        date_type: 创业/打工/混合,
        核心格局: str,
        适合职业: [str],
        不适合职业: [str],
        挣钱模式: str,
        叙事: str,
        行业建议: str,
        阶段建议: str
    }
    """
    pb = parse_bazi(bazi_str)
    if not pb:
        return {}
    
    dm = pb["day_gan"]
    gans = [pb["year_gan"], pb["month_gan"], pb["hour_gan"]]
    
    # 1. 判断核心格局
    geges = _detect_gege(bazi_str)
    primary_gege = geges[0] if geges else "财官相生"
    
    # 2. 判断创业/打工/混合
    try:
        jw = sushi_jialiwai(bazi_str)
        date_type = jw.get("模式", "混合型")
    except:
        date_type = "混合型"
    
    # 3. 获取职业映射
    career_info = GEGE_CAREER.get(primary_gege, GEGE_CAREER["财官相生"])
    
    # 4. 日主五行行业
    WX_MAP = {"甲乙":"木","丙丁":"火","戊己":"土","庚辛":"金","壬癸":"水"}
    dm_wx = ""
    for k, v in WX_MAP.items():
        if dm in k:
            dm_wx = v
    industry_tip = RIZHU_WX_CAREER.get(dm_wx, "")
    
    # 5. 宫位职业阶段
    stage_tips = []
    for pos, g in [("年", pb["year_gan"]), ("月", pb["month_gan"]), ("时", pb["hour_gan"])]:
        ss = get_shishen(dm, g)
        if ss in ("正财", "偏财", "正官", "七杀"):
            stage_info = GONG_WEI_CAREER.get(pos, "")
            stage_tips.append(f"{pos}柱{ss}: {stage_info}")
    
    # 6. 叙事体
    if date_type == "创业型" or "创业" in str(date_type):
        pattern_narrative = career_info["人话"]
    elif date_type == "财官全在家外":
        pattern_narrative = "适合在组织/公司里发展，做管理或专业岗。"
    else:
        pattern_narrative = career_info["人话"]
    
    return {
        "职业类型": date_type,
        "核心格局": primary_gege,
        "格局标签": career_info.get("tag", ""),
        "适合职业": career_info["适合"],
        "不适合职业": career_info["不适合"],
        "挣钱模式": career_info["挣钱方式"],
        "叙事": pattern_narrative,
        "行业建议": industry_tip,
        "阶段建议": "；".join(stage_tips) if stage_tips else "四柱均有事业机会"
    }


def _detect_gege(bazi_str):
    """检测八字的核心十神格局（按优先级）"""
    pb = parse_bazi(bazi_str)
    if not pb:
        return ["财官相生"]
    
    dm = pb["day_gan"]
    gans = [pb["year_gan"], pb["month_gan"], pb["hour_gan"]]
    
    # 从格优先（但继续检查具体十神组合）
    try:
        cg = is_cong_ge(bazi_str)
        if cg.get("从格", False):
            cong_wx = cg.get("类型", "").replace("格","").replace("从","") if cg.get("类型") else ""
            # 从格也是人，也有上述十神组合，继续往下检测但不返回
            # 标记从格类型后，继续看有什么具体的十神格局
    except:
        pass
    
    has_sha = any(get_shishen(dm, g) == "七杀" for g in gans)
    has_yin = any(get_shishen(dm, g) in ("正印", "偏印") for g in gans)
    has_shi = any(get_shishen(dm, g) == "食神" for g in gans)
    has_shang = any(get_shishen(dm, g) == "伤官" for g in gans)
    has_cai = any(get_shishen(dm, g) in ("正财", "偏财") for g in gans)
    has_biji = any(get_shishen(dm, g) in ("比肩", "劫财") for g in gans)
    has_guan = any(get_shishen(dm, g) in ("正官", "七杀") for g in gans)
    try:
        sw = is_shenwang(bazi_str)
        if sw.get("强弱") == "身旺" and "根" in sw.get("根类型", ""):
            if pb["month_zhi"] in ("寅","卯","巳","午","申","酉","亥","子"):
                return ["建禄格"]
    except:
        pass
    
    # 确定是否从格（给结果加前缀）
    is_cong = False
    try:
        cg = is_cong_ge(bazi_str)
        is_cong = cg.get("从格", False)
    except:
        pass
    prefix = "从格·" if is_cong else ""
    
    # 杀印相生
    if has_sha and has_yin:
        return [prefix + "杀印相生"]
    # 食神制杀
    if has_shi and has_sha:
        return [prefix + "食神制杀"]
    # 食神生财
    if has_shi and has_cai:
        return [prefix + "食神生财"]
    # 伤官生财
    if has_shang and has_cai:
        return [prefix + "伤官生财"]
    # 比劫夺财
    if has_biji and has_cai:
        return [prefix + "比劫夺财"]
    # 印星护身
    if has_yin:
        return [prefix + "印星护身"]
    # 财官相生
    if has_cai and has_guan:
        return [prefix + "财官相生"]
    
    return [prefix + "财官相生"]


# ===== 福运命理法则补充：3项翻译表 =====

# ① 十神婚姻行为模式2.0/3.0（修正闭环精华）
MARRIAGE_TRANSLATIONS = {
    "偏财透干": "把家撑起来→对老婆好是行动不是语言",
    "偏财透干·2.0": "工资卡放在桌上=他说我爱你的方式——不是不爱，是信号频率不匹配",
    "偏财透干·3.0": "行动是硬通货，语言是零钱——他从来不用零钱",
    "比肩+火": "不是不会说，是说了怕她不高兴",
    "比肩+火·2.0": "话到嘴边过三关→说出口只剩三分之一——不是不想说是被压住了",
    "正财藏": "她在暗处，做了很多但不怎么说",
    "正财藏·2.0": "正不显不等于不重要——饭是她做孩子是她管家是她收拾，外面人看不见",
    "自刑+夫妻宫": "自己给自己判了不及格",
    "自刑·2.0": "在脑子里已经离了三遍婚——她没做错什么，是他自己跟自己过不去",
    "自刑·时间累积": "不是一天拉开的——是日复一日的'算了不说了'堆出来的墙",
    "自刑·间歇模式": "热情起来比谁都上心，周期一到冷下来不解释——她困惑'是不是我做错了'",
    "自刑·知道做不到": "知道她需要什么，但知道和做到之间有断桥",
    "缺官杀": "没人管得住→骨子里不喜欢条条框框",
    "食神+财": "在外能赚钱，回家不会表达",
    "印+身弱": "需要空间恢复能量→靠近前先充满电",
    "三辰土": "表达爱的方式是：我在这里，我不走",
}

def get_marriage_translation(ten_god, bazi_str=""):
    """获取婚姻行为翻译"""
    pb = parse_bazi(bazi_str) if bazi_str else None
    dm = pb["day_gan"] if pb else ""
    gans = [pb["year_gan"], pb["month_gan"], pb["hour_gan"]] if pb else []
    CANGAN = {"子":"癸","丑":"己癸辛","寅":"甲丙戊","卯":"乙","辰":"戊乙癸",
              "巳":"丙庚戊","午":"丁己","未":"己丁乙","申":"庚壬戊",
              "酉":"辛","戌":"戊辛丁","亥":"壬甲"}
    
    # 检测特征
    has_piancai = any(get_shishen(dm, g) == "偏财" for g in gans) if dm else False
    has_bijian = any(get_shishen(dm, g) in ("比肩","劫财") for g in gans) if dm else False
    has_huo = any(GAN_WX.get(g,"") == "火" for g in gans) if dm else False
    has_zhengcai_zhi = any(any(get_shishen(dm, c) == "正财" for c in CANGAN.get(z,"")) for z in [pb.get("day_zhi",""), pb.get("month_zhi","")]) if pb else False
    has_selfxing = sum(1 for z in [pb.get("year_zhi",""),pb.get("month_zhi",""),pb.get("day_zhi",""),pb.get("hour_zhi","")] if z in ("辰","午","酉","亥") and [pb.get("year_zhi",""),pb.get("month_zhi",""),pb.get("day_zhi",""),pb.get("hour_zhi","")].count(z) >= 2) if pb else False
    has_sanchen = sum(1 for z in [pb.get("year_zhi",""),pb.get("month_zhi",""),pb.get("day_zhi",""),pb.get("hour_zhi","")] if z == "辰") >= 3 if pb else False
    
    result = []
    if has_piancai:
        result.append(MARRIAGE_TRANSLATIONS.get("偏财透干·3.0", ""))
    if has_bijian and has_huo:
        result.append(MARRIAGE_TRANSLATIONS.get("比肩+火·2.0", ""))
    if has_zhengcai_zhi:
        result.append(MARRIAGE_TRANSLATIONS.get("正财藏·2.0", ""))
    if has_selfxing:
        result.append(MARRIAGE_TRANSLATIONS.get("自刑·2.0", ""))
        result.append(MARRIAGE_TRANSLATIONS.get("自刑·时间累积", ""))
    if has_sanchen:
        result.append(MARRIAGE_TRANSLATIONS.get("三辰土", ""))
    
    return "；".join(result) if result else MARRIAGE_TRANSLATIONS.get(ten_god, "")


# ② 十神大运行为翻译表（8条）
DAYUN_NARRATIVE_MAP = {
    ("乙","any"): "想做的事一半就停——不是不想坚持，是条件不够",
    ("丙","any"): "想出去闯，脑子里很多想法，但能量不够",
    ("丁","any"): "最躁动的时候，对什么都不满",
    ("戊","any"): "想赚钱念头最强，手上过过钱但留不住",
    ("己","any"): "回归过日子状态，不再折腾",
    ("庚","any"): "第一个修剪他的东西→想自己往前走",
    ("辛","any"): "被尊重的角色",
    ("壬","any"): "水木齐来，最有福气的时候",
    ("癸","any"): "暗中蓄力，不急不躁",
}

def dayun_narrative(dayun_gan, dayun_zhi=""):
    """获取大运叙事翻译"""
    for (g, z), narr in DAYUN_NARRATIVE_MAP.items():
        if g == dayun_gan:
            return narr
    return "此运平稳过渡"


# ③ 六合→夫妻宫引动（6条）
LIUHE_HUNYIN = {
    "酉": "酉合辰→突然看见她的好",
    "未": "未合午→沟通方式明显转向",
    "申": "申合巳→关系进入新阶段",
    "亥": "亥合寅→家庭氛围转好",
    "卯": "卯合戌→关系稳定下来",
    "子": "子合丑→暗中达成共识",
}

def hehun_liuhe_translate(month_zhi_a, month_zhi_b):
    """六合婚姻引动翻译"""
    liuhe = {"子":"丑","丑":"子","寅":"亥","卯":"戌","辰":"酉","巳":"申",
             "午":"未","未":"午","申":"巳","酉":"辰","戌":"卯","亥":"寅"}
    if liuhe.get(month_zhi_a) == month_zhi_b:
        return LIUHE_HUNYIN.get(month_zhi_a, LIUHE_HUNYIN.get(month_zhi_b, "六合引动"))
    return ""


# ===== 测试 =====
if __name__ == "__main__":
    tests = [
        ("乙亥 乙酉 戊申 庚申", "韦佳幸"),
        ("丁酉 癸卯 戊戌 丙辰", "韦承凯"),
        ("乙酉 丙戌 甲戌 乙亥", "2005男"),
    ]
    for bazi, name in tests:
        r = analyze(bazi)
        print(f"\n{name} ({bazi})")
        print(f"  格局评分: {r['格局评分']['score']}分 — {r['格局评分']['level']}")
        print(f"  明细: {r['格局评分']['details']}")
        if r["相似案例"]:
            for s in r["相似案例"]:
                print(f"  相似案例: {s['案例']} ({s['相似度']}%)")

# ===== 福运法则补充：剩余4张翻译表 =====
import random

# ③ 藏干→配偶角色（5条）
CANGAN_PEIOU = {
    "辰藏戊": "管钱的人", "辰藏乙": "能干的人", "辰藏癸": "给空间的人",
    "午藏丁己": "能干但容易燥的人", "酉藏辛": "能说会道的人",
}

def get_peiou_by_canggan(zhi):
    CANGAN = {"子":"癸","丑":"己癸辛","寅":"甲丙戊","卯":"乙","辰":"戊乙癸",
              "巳":"丙庚戊","午":"丁己","未":"己丁乙","申":"庚壬戊",
              "酉":"辛","戌":"戊辛丁","亥":"壬甲"}
    result = [CANGAN_PEIOU.get(f"{zhi}藏{c}","") for c in CANGAN.get(zhi,"") if f"{zhi}藏{c}" in CANGAN_PEIOU]
    return "；".join(result) if result else ""

# ⑨ 死木人群位置翻译
SI_MU_RENQUN = {
    "内省型外向": "战壕里修工事的人——不是冲锋队长，不是躺平者，是那个在暗处把一切修好的人",
    "人群里正常": "他能融入任何场合，但他在场时别人觉得'稳'，不是觉得'亮'",
    "关系里真实": "他在外面是水泥，回家是泥——软的、塌的、需要人扶的",
}

def get_simu_renqun(level=""):
    if "下品" in level: return SI_MU_RENQUN.get("关系里真实","")
    elif "上品" in level: return SI_MU_RENQUN.get("内省型外向","")
    return SI_MU_RENQUN.get("人群里正常","")

# ⑪ 行动指南
ACTION_GUIDE_MAP = {
    "感情": {"偏财":"吵架时别讲道理，打开钱包不如开口说话——她要的不是买什么，是你在听",
             "自刑":"别让自己'想太多'变成她的负担——觉得不对就开口问，别在脑子里编剧本",
             "default":"她会记得你做了什么，但更记得你做的时候有没有看她一眼"},
    "事业": {"创业":"你不是冲锋队长的命，你是修工事的命——别跟人比快，比的是谁站得久",
             "打工":"钱从稳定渠道来——拒绝快钱诱惑，三年筑一信",
             "default":"你不是拼速度的命，你是拼耐力的命"},
    "财运": {"偏财":"钱从'你的本事'来——不是从投机来。你做的产品/服务值多少钱，你就值多少钱",
             "正财":"钱从积累来——储蓄比投资重要，稳定比暴利好",
             "default":"钱从你擅长的事来——别追风口，追你自己的本事"},
}

def action_guide(bazi_str):
    pb = parse_bazi(bazi_str)
    if not pb: return {"default":"了解自己的命才能走好自己的路"}
    dm = pb["day_gan"]
    gans = [pb["year_gan"], pb["month_gan"], pb["hour_gan"]]
    r = {}
    r["感情"] = ACTION_GUIDE_MAP["感情"]["自刑"] if any(z in ("辰","午","酉","亥") for z in [pb["year_zhi"],pb["month_zhi"],pb["day_zhi"],pb["hour_zhi"]]) and any(get_shishen(dm,g) in ("比肩","劫财") for g in gans) else \
              ACTION_GUIDE_MAP["感情"]["偏财"] if any(get_shishen(dm,g)=="偏财" for g in gans) else ACTION_GUIDE_MAP["感情"]["default"]
    r["事业"] = ACTION_GUIDE_MAP["事业"]["default"]
    r["财运"] = ACTION_GUIDE_MAP["财运"]["偏财"] if any(get_shishen(dm,g)=="偏财" for g in gans) else \
              ACTION_GUIDE_MAP["财运"]["正财"] if any(get_shishen(dm,g)=="正财" for g in gans) else ACTION_GUIDE_MAP["财运"]["default"]
    return r

# ⑫ 收尾双轨制
SHOUWEI_MAP = {
    "正向": ["死木非枯，是待春之蛰；不争不抢，只为根深",
             "他不是没运气，是运气来得慢——等得起的人，才接得住",
             "命不是用来改的，是用来懂的——懂了就不跟自己较劲了"],
    "反向": ["如果能来早一点，会更好——但人生没有如果，只有后果和结果",
             "他一直在用自己的方式爱——只是她收不到信号",
             "不是不爱，是信号频率不匹配"],
}

def shuang_gui_shouwei(score=3.5):
    return random.choice(SHOUWEI_MAP["正向"]) if score >= 3.5 else random.choice(SHOUWEI_MAP["反向"])


# ===== 扶抑病药四法：通关 + 病药 =====

WUXING_SHENG = {"木":"火","火":"土","土":"金","金":"水","水":"木"}
WUXING_KE = {"木":"土","土":"水","水":"火","火":"金","金":"木"}

def tongguan_analyze(bazi_str):
    """通关分析：五行交战→找中介
    
    逻辑：找两强五行之间的通关五行（生A又生B的中间者）
    木土战→火通关(木生火,火生土)
    水火战→木通关(水生木,木生火) 
    金木战→水通关(金生水,水生木)
    土水战→金通关(土生金,金生水)
    火金战→土通关(火生土,土生金)
    """
    pb = parse_bazi(bazi_str)
    if not pb: return {}
    
    wx_count = {"木":0,"火":0,"土":0,"金":0,"水":0}
    WX_MAP = {"甲乙":"木","丙丁":"火","戊己":"土","庚辛":"金","壬癸":"水"}
    ZHI_WXM = {"寅":"木","卯":"木","辰":"土","巳":"火","午":"火","未":"土",
               "申":"金","酉":"金","戌":"土","亥":"水","子":"水","丑":"土"}
    CANGAN = {"子":"癸","丑":"己癸辛","寅":"甲丙戊","卯":"乙","辰":"戊乙癸",
              "巳":"丙庚戊","午":"丁己","未":"己丁乙","申":"庚壬戊",
              "酉":"辛","戌":"戊辛丁","亥":"壬甲"}
    
    for g in [pb["year_gan"],pb["month_gan"],pb["day_gan"],pb["hour_gan"]]:
        for k,v in WX_MAP.items():
            if g in k: wx_count[v] += 1
    for z in [pb["year_zhi"],pb["month_zhi"],pb["day_zhi"],pb["hour_zhi"]]:
        z_wx = ZHI_WXM.get(z,"")
        if z_wx: wx_count[z_wx] += 1
        for c in CANGAN.get(z,""):
            for k,v in WX_MAP.items():
                if c in k: wx_count[v] += 0.5
    
    sorted_wx = sorted(wx_count.items(), key=lambda x: -x[1])
    strongest = sorted_wx[0]
    second = sorted_wx[1]
    
    # 如果最强两行是相克关系，找通关
    TONGGUAN = {("木","土"):{"神":"火","原理":"木生火、火生土——火是中间人"},
                ("土","木"):{"神":"火","原理":"木生火、火生土——火是中间人"},
                ("水","火"):{"神":"木","原理":"水生木、木生火——木是中间人"},
                ("火","水"):{"神":"木","原理":"水生木、木生火——木是中间人"},
                ("金","木"):{"神":"水","原理":"金生水、水生木——水是中间人"},
                ("木","金"):{"神":"水","原理":"金生水、水生木——水是中间人"},
                ("土","水"):{"神":"金","原理":"土生金、金生水——金是中间人"},
                ("水","土"):{"神":"金","原理":"土生金、金生水——金是中间人"},
                ("火","金"):{"神":"土","原理":"火生土、土生金——土是中间人"},
                ("金","火"):{"神":"土","原理":"火生土、土生金——土是中间人"},
    }
    
    key = (strongest[0], second[0])
    tg = TONGGUAN.get(key, None)
    
    if tg and wx_count.get(tg["神"], 0) > 0:
        return {"交战": f"{strongest[0]}vs{second[0]}", "通关神": tg["神"],
                "原理": tg["原理"], "通关力度": "有通关神可用",
                "叙事": f"命局{strongest[0]}与{second[0]}交战，以{tg['神']}通关。{tg['原理']}——这个{tg['神']}是你的'和事佬'，有它在就不怕两强相斗。"}
    elif tg:
        return {"交战": f"{strongest[0]}vs{second[0]}", "通关神": tg["神"],
                "原理": tg["原理"], "通关力度": "通关神不足",
                "叙事": f"命局{strongest[0]}与{second[0]}交战，按理需要{tg['神']}来通关，但{tg['神']}在原局力量不足。大运逢{tg['神']}就是转机。"}
    else:
        return {"交战": f"{strongest[0]}vs{second[0]}", "通关神": "无需通关",
                "原理": "两行不直接相克", "叙事": "五行无严重交战，无需通关。"}


def bingyao_analyze(bazi_str):
    """病药分析：找出命局最大的缺陷(病)和对应的解药(药)"""
    pb = parse_bazi(bazi_str)
    if not pb: return {}
    
    dm = pb["day_gan"]
    gans = [pb["year_gan"], pb["month_gan"], pb["hour_gan"]]
    WX_MAP = {"甲乙":"木","丙丁":"火","戊己":"土","庚辛":"金","壬癸":"水"}
    dm_wx = next(v for k,v in WX_MAP.items() if dm in k)
    
    # 十神分析
    ss_list = [get_shishen(dm, g) for g in gans]
    
    # 检测病
    diseases = []
    medicines = []
    
    # 病1：官杀混杂
    if "正官" in ss_list and "七杀" in ss_list:
        diseases.append(("官杀混杂", "事业感情两难——既想稳定又想自由"))
        medicines.append(("食神制杀/合杀留官", "用食神压制七杀，或用合的方式取清"))
    
    # 病2：财多身弱
    cai_count = ss_list.count("正财") + ss_list.count("偏财")
    bi_count = ss_list.count("比肩") + ss_list.count("劫财")
    if cai_count >= 2 and bi_count == 0:
        diseases.append(("财多身弱", "扛不动财——有机会但抓不住"))
        medicines.append(("比劫帮身", "需要有人帮你，单打独斗扛不住"))
    
    # 病3：食伤太旺
    shi_count = ss_list.count("食神") + ss_list.count("伤官")
    yin_count = ss_list.count("正印") + ss_list.count("偏印")
    if shi_count >= 2 and yin_count == 0:
        diseases.append(("食伤泄身过重", "想法太多但能量不够——脑子快身体跟不上"))
        medicines.append(("印星制食伤", "需要贵人/知识来帮你聚焦，不是少想是想对方向"))
    
    # 病4：印星太旺
    if yin_count >= 3:
        diseases.append(("印星过重", "思虑过多，行动力不足——想好了但迈不开腿"))
        medicines.append(("财星破印", "需要实际利益来推动你，光想没用"))
    
    # 病5：比劫夺财
    if bi_count >= 2 and cai_count >= 1:
        diseases.append(("比劫夺财", "朋友多但钱财也容易随朋友走"))
        medicines.append(("官杀制比劫", "需要规则/权威来约束，不然钱留不住"))
    
    # 病6：调候
    try:
        th = check_tiaohou(bazi_str)
        if th.get("降级"):
            diseases.append(("调候不足", th.get("调候","")))
            medicines.append(("大运补齐", "等大运走到调候五行就是转机"))
    except:
        pass
    
    # 没检测到病
    if not diseases:
        return {"病": "无明显缺陷", "药": "无需特别补", "药有效": True,
                "叙事": "命局相对平衡，没有特别需要修补的地方。关注大运流年的引动即可。"}
    
    # 取最严重的病（第一个）
    bing = diseases[0]
    yao = medicines[0] if medicines else ("", "")
    
    # 药是否在原局存在？
    yao_exists = False
    for g in gans:
        ss = get_shishen(dm, g)
        if yao[0] and any(k in yao[0] for k in [ss]):
            yao_exists = True
    
    return {
        "病": bing[0], "病描述": bing[1],
        "药": yao[0], "药描述": yao[1],
        "药有效": yao_exists,
        "叙事": f"【病】{bing[0]}：{bing[1]}。\n【药】{yao[0]}：{yao[1]}。\n{'✅ 药在原局中有，不需等大运。' if yao_exists else '⚠️ 药在原局不足，需等大运/流年补齐。'}"
    }

# ===== 加载反推优化参数 =====  # 反推优化v2.1
OPT_PATH = os.path.join(os.path.dirname(__file__), "params_optimized.json")
OPT_PARAMS = {}
if os.path.exists(OPT_PATH):
    with open(OPT_PATH, encoding="utf-8") as f:
        OPT_PARAMS = json.load(f).get("反推优化参数", {})
