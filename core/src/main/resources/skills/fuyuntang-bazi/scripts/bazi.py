#!/usr/bin/env python3
"""八字排盘工具 — 基于 lunar-python，含真太阳时校正"""
from lunar_python import Solar, Lunar
import json, math, os

# 城市经度表
CITIES_PATH = os.path.join(os.path.dirname(__file__), "cities.json")
CITY_LON = {}
if os.path.exists(CITIES_PATH):
    with open(CITIES_PATH, encoding="utf-8") as f:
        CITY_LON = json.load(f)

def get_city_lon(city_name):
    """根据城市名获取经度"""
    if not city_name:
        return None
    # 尝试直接匹配
    if city_name in CITY_LON:
        return CITY_LON[city_name]
    # 尝试模糊匹配(城市名可能包含"市")
    for name, lon in CITY_LON.items():
        if name in city_name or city_name in name:
            return lon
    return None

GAN = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
ZHI = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]

TIMEZONE_LON = 120.0  # 东八区基准经度

def sun_correction(lon, hour, minute):
    """真太阳时校正：每偏离1度±4分钟"""
    if lon is None:
        return hour, minute
    offset_minutes = (lon - TIMEZONE_LON) * 4
    total = hour * 60 + minute + offset_minutes
    if total < 0:
        total += 1440
    elif total >= 1440:
        total -= 1440
    return int(total // 60), int(total % 60)

def get_shichen(hour, minute, lon=None):
    """获取时辰（支持真太阳时）"""
    h, m = sun_correction(lon, hour, minute) if lon else (hour, minute)
    val = h + m / 60
    if val >= 23 or val < 1: return "子", h, m
    if 1 <= val < 3: return "丑", h, m
    if 3 <= val < 5: return "寅", h, m
    if 5 <= val < 7: return "卯", h, m
    if 7 <= val < 9: return "辰", h, m
    if 9 <= val < 11: return "巳", h, m
    if 11 <= val < 13: return "午", h, m
    if 13 <= val < 15: return "未", h, m
    if 15 <= val < 17: return "申", h, m
    if 17 <= val < 19: return "酉", h, m
    if 19 <= val < 21: return "戌", h, m
    return "亥", h, m

def shizhu(day_gan, sc):
    """计算时柱。day_gan: 日干(如'甲'), sc: 时辰(如'辰')"""
    # 五鼠遁
    map_start = {"甲":"甲","乙":"丙","丙":"戊","丁":"庚","戊":"壬","己":"甲","庚":"丙","辛":"戊","壬":"庚","癸":"壬"}
    start = map_start[day_gan]
    idx = GAN.index(start)
    for i in range(12):
        if ZHI[i] == sc:
            return GAN[(idx + i) % 10] + ZHI[i]
    return "??"

def bazi_from_solar(year, month, day, hour, minute, lon=None):
    """从公历排盘（支持真太阳时：传入经度lon）"""
    s = Solar.fromYmd(year, month, day)
    l = Lunar.fromSolar(s)
    yg = l.getYearInGanZhiExact()  # 立春法
    mg = l.getMonthInGanZhiExact()  # 立春法
    dg = l.getDayInGanZhi()
    sc = get_shichen(hour, minute, lon)
    sg = shizhu(dg[0], sc[0])
    return yg, mg, dg, sg, sc, l

def bazi_from_lunar(year, month, day, hour, minute, lon=None):
    """从农历排盘（支持真太阳时：传入经度lon）"""
    l = Lunar.fromYmd(year, month, day)
    s = l.getSolar()
    yg = l.getYearInGanZhi()
    mg = l.getMonthInGanZhi()
    dg = l.getDayInGanZhi()
    sc = get_shichen(hour, minute, lon)
    sg = shizhu(dg[0], sc[0])
    return yg, mg, dg, sg, sc, s, l

def print_bazi(name, yg, mg, dg, sg, sc):
    print(f"{name}")
    print(f"  八字: {yg} {mg} {dg} {sg}")
    print(f"  时辰: {sc}时")

# ===== 大运推算（lunar-python节气法） =====
YANG_GAN = {"甲","丙","戊","庚","壬"}
GAN = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
ZHI = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]

def calc_dayun(solar_year, solar_month, solar_day, hour, minute, is_male):
    """
    根据公历出生日期推算大运
    阳男阴女→顺排，阴男阳女→逆排
    返回：起运岁数, 大运列表[(干,支,起始年龄,结束年龄)]
    """
    s = Solar(solar_year, solar_month, solar_day, hour, minute, 0)
    l = s.getLunar()
    
    # 年干决定阴阳
    year_gan = l.getYearInGanZhiExact()[0]
    is_yang = year_gan in YANG_GAN
    
    # 顺排还是逆排
    forward = (is_yang and is_male) or (not is_yang and not is_male)
    
    l_month = l.getMonth()
    
    # 月柱
    mg = l.getMonthInGanZhiExact()
    m_gan = mg[0]
    m_zhi = mg[1]
    
    # 找下一个或上一个节（用lunar-python的节气功能）
    # JieQi表：立春、惊蛰、清明、立夏、芒种、小暑、立秋、白露、寒露、立冬、大雪、小寒
    jie_names = ["立春", "惊蛰", "清明", "立夏", "芒种", "小暑", "立秋", "白露", "寒露", "立冬", "大雪", "小寒"]
    
    # 获取当前农历月份对应的节
    # 农历月份对应的节：正月立春、二月惊蛰、三月清明、四月立夏、五月芒种、六月小暑
    # 七月立秋、八月白露、九月寒露、十月立冬、冬月大雪、腊月小寒
    
    if forward:
        # 顺排：找下一个节气
        next_jie = None
        for days_offset in range(1, 60):
            from datetime import datetime, timedelta
            dt = datetime(solar_year, solar_month, solar_day, hour, minute) + timedelta(days=days_offset)
            test_s = Solar(dt.year, dt.month, dt.day, 0, 0, 0)
            test_l = test_s.getLunar()
            jq = test_l.getJieQi()
            if jq and jq in jie_names:
                next_jie = (dt.year, dt.month, dt.day, jq)
                break
        
        if next_jie:
            from datetime import datetime, timedelta
            start_dt = datetime(solar_year, solar_month, solar_day, hour, minute)
            end_dt = datetime(next_jie[0], next_jie[1], next_jie[2], 0, 0)
            diff_seconds = (end_dt - start_dt).total_seconds()
            diff_days = diff_seconds / 86400.0  # 精确到秒
            qiyun_years = int(diff_days // 3)
            remainder_days = (diff_days / 3 - qiyun_years) * 3
            extra_months = int((diff_days % 3) * 4)
        else:
            qiyun_years, extra_months = 10, 0  # 找不到节时给默认值(极罕见)
    else:
        # 逆排：找上一个节气
        prev_jie = None
        for days_offset in range(1, 60):
            from datetime import datetime, timedelta
            dt = datetime(solar_year, solar_month, solar_day, hour, minute) - timedelta(days=days_offset)
            test_s = Solar(dt.year, dt.month, dt.day, 0, 0, 0)
            test_l = test_s.getLunar()
            jq = test_l.getJieQi()
            if jq and jq in jie_names:
                prev_jie = (dt.year, dt.month, dt.day, jq)
                break
        
        if prev_jie:
            from datetime import datetime, timedelta
            end_dt = datetime(solar_year, solar_month, solar_day, hour, minute)
            start_dt = datetime(prev_jie[0], prev_jie[1], prev_jie[2], 0, 0)
            diff_seconds = (end_dt - start_dt).total_seconds()
            diff_days = diff_seconds / 86400.0  # 精确到秒
            qiyun_years = int(diff_days // 3)
            extra_months = int((diff_days % 3) * 4)
        else:
            qiyun_years, extra_months = 10, 0  # 找不到节时给默认值(极罕见)
    
    # 月柱干支索引
    m_gan_idx = GAN.index(m_gan)
    m_zhi_idx = ZHI.index(m_zhi)
    
    # 大运排列
    dayun_list = []
    for step in range(8):
        if forward:
            g_idx = (m_gan_idx + step + 1) % 10
            z_idx = (m_zhi_idx + step + 1) % 12
        else:
            g_idx = (m_gan_idx - step - 1) % 10
            z_idx = (m_zhi_idx - step - 1) % 12
        
        dg = GAN[g_idx]
        dz = ZHI[z_idx]
        start_age = qiyun_years + step * 10
        end_age = start_age + 9
        dayun_list.append((dg, dz, start_age, end_age))
    
    return {
        "起运": f"{qiyun_years}岁{extra_months}个月",
        "起运年龄": qiyun_years,
        "顺逆": "顺排" if forward else "逆排",
        "大运": dayun_list
    }

# ===== 测试 =====
if __name__ == "__main__":
    # 已知锚点
    y,m,d,hh,mm,__ = bazi_from_solar(1900,1,1,12,0)
    print_bazi("1900-01-01 午时", y,m,d,hh,mm)
    
    y,m,d,hh,mm,__ = bazi_from_solar(2000,1,1,12,0)
    print_bazi("2000-01-01 午时", y,m,d,hh,mm)
    
    # 孙中山
    y,m,d,hh,mm,__ = bazi_from_solar(1866,11,12,8,0)
    print_bazi("孙中山 1866-11-12 辰时", y,m,d,hh,mm)
    
    # 2005年10月17日亥时（跟用户争论过的）
    y,m,d,hh,mm,__ = bazi_from_solar(2005,10,17,21,48)
    print_bazi("2005-10-17 21:48 亥时", y,m,d,hh,mm)
    
    # 韦承凯 农历2017-02-15 辰时
    y,m,d,hh,mm,s,__ = bazi_from_lunar(2017,2,15,8,0)
    print_bazi(f"韦承凯 农历2017-02-15 辰时 (公历{s.getYear()}-{s.getMonth()}-{s.getDay()})", y,m,d,hh,mm)
    
    # 韦佳幸 农历1995-08-20 申时(16:40)
    y,m,d,hh,mm,s,__ = bazi_from_lunar(1995,8,20,16,40)
    print_bazi(f"韦佳幸 农历1995-08-20 16:40 申时 (公历{s.getYear()}-{s.getMonth()}-{s.getDay()})", y,m,d,hh,mm)
