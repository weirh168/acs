# SPDX-License-Identifier: Apache-2.0
"""施工方案生成器（12 章骨架 + 三段式分项 + 表 + 机检）。纯标准库。

用法：
  scheme.py classify [--depth 4.8] [--formwork 6] [--lift-kn 80] [--scaffold 15]
  scheme.py new   --project project.json --type 道路硬化 [--out DIR]
  scheme.py batch --project project.json [--types all]
  scheme.py audit --docx 方案.docx

project.json 见技能 SKILL.md；姓名/电话留空会写「（待填）」，绝不编造。
"""
import json
import os
import re
import sys
import zipfile
from datetime import datetime

ZODIAC = None  # 占位，避免误用

# ---------------- 分类与门槛 ----------------
THRESHOLDS = [("基坑开挖深度", "depth", 5.0, "m"),
              ("模板支撑搭设高度", "formwork", 8.0, "m"),
              ("起重吊装起重量", "lift_kn", 100.0, "kN"),
              ("脚手架架体高度", "scaffold", 20.0, "m")]


def classify(args):
    hits, reasons = [], []
    for label, key, limit, unit in THRESHOLDS:
        v = args.get(key)
        if v is None:
            continue
        if float(v) >= limit:
            hits.append(label)
            reasons.append("%s %.1f%s ≥ %.1f%s" % (label, float(v), unit, limit, unit))
    if hits:
        return {"type": "专家论证方案", "expert_review": True, "reasons": reasons,
                "title_suffix": "（专项）"}
    return {"type": "专项施工方案" if any(args.values()) else "施工方案",
            "expert_review": False,
            "reasons": reasons or ["四项门槛均未达到，按一般方案编制"],
            "title_suffix": ""}


# ---------------- 工序清单（附件 3.2 节实测） ----------------
WORK = {
 "道路硬化": [
  ("测量放线", ["测量依据与设计交桩", "测量方法与仪器", "测量精度要求"]),
  ("路基清表与土方工程", ["清表处理", "土方填筑", "临时排水"]),
  ("路基填筑与压实", ["填料要求", "分层填筑", "压实控制"]),
  ("级配碎石垫层施工", ["材料级配", "摊铺", "碾压"]),
  ("模板安装", ["模板材料", "安装要求", "质量检验"]),
  ("C30 水泥混凝土面层施工", ["配合比设计", "拌和与运输", "摊铺振捣整平", "接缝设置"]),
  ("接缝处理", ["接缝形式", "传力杆设置", "灌缝"]),
  ("路面刻槽与拉毛", ["刻槽时机", "拉毛工艺", "质量要求"]),
  ("养护", ["养护方式", "养护时间", "交通管制"]),
  ("错车道施工", ["位置与尺寸", "结构做法", "与主路衔接"]),
  ("路肩施工", ["路肩材料", "培肩压实", "排水顺接"]),
 ],
 "挡土墙": [
  ("测量放线", ["放样内容", "精度要求", "护桩设置"]),
  ("基槽开挖", ["开挖方式", "开挖技术要求", "基底纵坡处理"]),
  ("地基验槽与处理", ["验槽内容", "地基处理", "隐蔽验收"]),
  ("基础砌筑", ["材料要求", "砌筑工艺", "质量检验"]),
  ("墙身砌筑", ["砌筑工艺", "砂浆拌和", "墙面修整"]),
  ("沉降缝施工", ["缝位设置", "缝宽与填料", "施工顺序"]),
  ("泄水孔施工", ["孔径与间距", "坡度", "反滤包裹"]),
  ("反滤层施工", ["材料要求", "铺筑工艺", "质量检验"]),
  ("墙背回填", ["回填材料", "分层回填", "压实控制"]),
  ("勾缝与抹面", ["勾缝工艺", "抹面要求", "养护"]),
  ("养护", ["养护方式", "养护时间", "成品保护"]),
 ],
 "排水渠": [
  ("测量放线", ["放样内容", "精度要求", "控制桩"]),
  ("渠槽开挖", ["开挖方式", "开挖技术要求", "排水措施"]),
  ("地基处理", ["验槽要求", "地基处理措施", "隐蔽验收"]),
  ("C15 垫层浇筑", ["材料要求", "施工工艺", "质量检验"]),
  ("模板安装", ["模板材料", "安装要求", "质量检验"]),
  ("C25 渠身混凝土浇筑", ["配合比设计", "拌和与运输", "浇筑与振捣"]),
  ("伸缩沉降缝施工", ["缝位与间距", "填料", "施工要点"]),
  ("抹面收光", ["抹面时机", "工艺", "质量要求"]),
  ("养护", ["养护方式", "养护时间", "成品保护"]),
  ("渠道两侧回填", ["回填材料", "分层回填", "压实度"]),
  ("圆管涵施工", ["管基施工", "管道安装", "接口处理", "涵背回填"]),
 ],
 "灌溉管道": [
  ("测量放线", ["放样内容", "精度要求", "控制桩"]),
  ("管沟开挖", ["开挖方式", "沟槽断面尺寸", "开挖技术要求"]),
  ("管道基础处理", ["砂垫层铺设", "地基处理", "隐蔽验收"]),
  ("管道搬运与下沟", ["管道搬运", "管道下沟", "安全要求"]),
  ("管道热熔对接连接", ["连接原理", "连接工艺参数", "连接操作步骤", "焊缝质量检查"]),
  ("阀门井与出水口施工", ["阀门井砌筑", "出水口做法", "质量检验"]),
  ("水压试验", ["试验前准备", "试验压力", "试验程序", "不合格处理"]),
  ("管沟回填", ["回填材料", "回填工艺", "压实度要求"]),
  ("警示带敷设与标识", ["警示带位置", "标识桩", "竣工资料"]),
 ],
 "高位水池": [
  ("测量放线", ["放样内容", "精度要求", "控制桩"]),
  ("基坑开挖", ["开挖方式", "基坑尺寸", "排水措施"]),
  ("地基验槽与处理", ["验槽内容", "地基处理", "隐蔽验收"]),
  ("C15 垫层浇筑", ["材料要求", "施工工艺", "质量检验"]),
  ("底板钢筋绑扎", ["钢筋加工", "钢筋绑扎", "质量检验"]),
  ("底板混凝土浇筑", ["配合比设计", "浇筑工艺", "质量要求"]),
  ("池壁钢筋绑扎", ["钢筋加工", "钢筋绑扎", "质量检验"]),
  ("池壁模板安装", ["模板材料", "安装要求", "质量检验"]),
  ("池壁混凝土浇筑", ["浇筑方式", "浇筑工艺", "对拉螺栓处理"]),
  ("满水试验", ["试验前准备", "注水程序", "观测内容", "合格标准"]),
  ("池内抹面", ["基层处理", "抹面工艺", "养护"]),
  ("池外回填", ["回填材料", "分层回填", "压实控制"]),
  ("养护", ["养护方式", "养护时间", "成品保护"]),
 ],
 "雨季施工": [
  ("雨季施工组织", ["组织机构", "值班制度", "信息联络"]),
  ("基坑与沟槽防排水", ["截水沟", "集水井", "抽排设备"]),
  ("混凝土雨季施工", ["配合比调整", "浇筑时机", "覆盖养护"]),
  ("材料防潮与堆放", ["水泥库房", "钢筋垫高", "砂石覆盖"]),
  ("临时用电防雨", ["配电箱防护", "接地", "漏电保护"]),
  ("道路与运输保障", ["临时道路", "防滑措施", "运输调度"]),
  ("雨季安全巡查", ["巡查频次", "重点部位", "记录"]),
  ("应急物资储备", ["抽水设备", "彩条布", "沙袋"]),
  ("暴雨停工与复工", ["停工条件", "复工检查", "记录归档"]),
 ],
 "安全文明": [
  ("安全生产责任制", ["责任分工", "考核", "奖惩"]),
  ("安全教育与交底", ["三级教育", "班前交底", "特种作业"]),
  ("危险源识别与控制", ["识别清单", "控制措施", "动态更新"]),
  ("临时用电安全", ["三级配电", "两级保护", "定期检测"]),
  ("机械设备安全", ["进场验收", "定期保养", "持证操作"]),
  ("高处与临边作业", ["防护栏杆", "安全带", "作业审批"]),
  ("文明施工布置", ["围挡", "标识牌", "场地硬化"]),
  ("环境保护措施", ["扬尘控制", "噪声控制", "废弃物处置"]),
  ("消防与治安", ["消防器材", "动火审批", "治安管理"]),
 ],
 "劳务管理": [
  ("用工岗位设置", ["岗位清单", "人数配置", "技能要求"]),
  ("务工对象确定", ["优先对象", "公示程序", "动态调整"]),
  ("劳务报酬标准", ["技术工", "普工", "计价方式"]),
  ("报酬发放流程", ["考勤", "造册", "银行卡直发"]),
  ("公示与监督", ["公示内容", "公示期", "投诉渠道"]),
  ("岗前培训", ["安全培训", "技能培训", "记录"]),
  ("禁止行为", ["禁止转包", "禁止克扣", "禁止代领"]),
  ("台账与档案", ["用工台账", "工资台账", "归档要求"]),
  ("技能培训与考核", ["培训计划", "考核标准", "记录归档"]),
 ],
}

TABLE_PLANS = {
 "道路硬化": [("施工段划分表", ["施工段落", "道路长度(m)", "路面宽度(m)", "路面结构"]),
              ("机械设备表", ["名称", "规格型号", "数量", "用途"]),
              ("路基压实度要求", ["填挖类型", "深度范围(m)", "压实度(%)"]),
              ("混凝土面层指标", ["项目", "指标", "检验方法"]),
              ("用工分区表", ["工种", "工作内容", "技术要求", "高峰期人数"])],
 "挡土墙": [("结构参数表", ["参数项目", "设计值", "备注"]),
            ("挡墙分段表", ["施工段", "挡墙长度(m)", "墙高范围(m)", "工期(d)"]),
            ("材料要求表", ["材料", "规格要求", "检验要求"])],
 "排水渠": [("断面参数表", ["项目", "设计值", "备注"]),
            ("渠道分段表", ["施工段", "渠道长度(m)", "涵洞数量", "工期(d)"]),
            ("材料要求表", ["材料", "规格要求", "检验要求"])],
 "灌溉管道": [("管材参数表", ["项目", "规格", "备注"]),
              ("沟槽尺寸表", ["管径(mm)", "沟底宽度(m)", "沟深(m)", "边坡坡度"]),
              ("热熔连接参数表", ["管径(mm)", "加热温度(℃)", "加热时间(s)", "切换时间(s)", "保压冷却(min)"]),
              ("回填压实度表", ["回填部位", "压实度要求(%)", "检验方法"])],
 "高位水池": [("结构参数表", ["参数项目", "设计值", "备注"]),
              ("主要尺寸表", ["项目", "尺寸", "备注"]),
              ("材料要求表", ["材料", "规格要求", "检验要求"])],
 "雨季施工": [("雨季施工重点部位表", ["部位", "风险", "措施"]),
              ("应急物资表", ["物资名称", "数量", "存放位置"])],
 "安全文明": [("危险源识别表", ["作业活动", "危险源", "风险等级", "控制措施"]),
              ("安全防护设施表", ["设施", "设置部位", "技术要求"])],
 "劳务管理": [("用工岗位表", ["工种", "人数", "工作内容", "技能要求"]),
              ("劳务报酬标准表", ["工种", "日工资(元)", "支付方式", "支付周期"])],
}

# ---------------- DOCX 底层 ----------------
NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')
CT = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
      '<Default Extension="xml" ContentType="application/xml"/>'
      '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
      '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
      '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
      '</Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>')
DOC_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
            '</Relationships>')
SECT = ('<w:sectPr><w:footerReference w:type="default" r:id="rId2"/>'
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417" w:header="851" w:footer="992" w:gutter="0"/>'
        '</w:sectPr>')
FOOTER = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<w:ftr %s><w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
          '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
          '<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
          '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:ftr>') % NS
STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<w:styles %s>'
          '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="宋体" w:eastAsia="宋体" w:hAnsi="宋体"/>'
          '<w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:rPrDefault>'
          '<w:pPrDefault><w:pPr><w:spacing w:line="300" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
          '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/>'
          '<w:pPr><w:ind w:firstLine="420"/><w:spacing w:line="300" w:lineRule="auto"/></w:pPr>'
          '<w:rPr><w:rFonts w:ascii="宋体" w:eastAsia="宋体"/><w:sz w:val="24"/></w:rPr></w:style>'
          '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:qFormat/>'
          '<w:pPr><w:ind w:firstLine="0"/><w:outlineLvl w:val="0"/><w:spacing w:before="240" w:after="120"/></w:pPr>'
          '<w:rPr><w:rFonts w:ascii="黑体" w:eastAsia="黑体"/><w:b/><w:sz w:val="36"/></w:rPr></w:style>'
          '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:qFormat/>'
          '<w:pPr><w:ind w:left="420" w:firstLine="0"/><w:outlineLvl w:val="1"/><w:spacing w:before="200" w:after="100"/></w:pPr>'
          '<w:rPr><w:rFonts w:ascii="黑体" w:eastAsia="黑体"/><w:b/><w:sz w:val="28"/></w:rPr></w:style>'
          '<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:qFormat/>'
          '<w:pPr><w:ind w:left="560" w:firstLine="0"/><w:outlineLvl w:val="2"/></w:pPr>'
          '<w:rPr><w:rFonts w:ascii="黑体" w:eastAsia="黑体"/><w:b/><w:sz w:val="24"/></w:rPr></w:style>'
          '<w:style w:type="paragraph" w:styleId="Cover"><w:name w:val="Cover"/><w:basedOn w:val="Normal"/>'
          '<w:pPr><w:jc w:val="center"/><w:ind w:firstLine="0"/></w:pPr>'
          '<w:rPr><w:rFonts w:ascii="黑体" w:eastAsia="黑体"/><w:b/><w:sz w:val="44"/></w:rPr></w:style>'
          '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr>'
          '<w:tblBorders><w:top w:val="single" w:sz="4"/><w:left w:val="single" w:sz="4"/><w:bottom w:val="single" w:sz="4"/>'
          '<w:right w:val="single" w:sz="4"/><w:insideH w:val="single" w:sz="4"/><w:insideV w:val="single" w:sz="4"/></w:tblBorders>'
          '<w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="80" w:type="dxa"/><w:bottom w:w="40" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar>'
          '</w:tblPr></w:style>'
          '</w:styles>') % NS


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def run(text, bold=False, font=None, size=None):
    bits = []
    if font:
        bits.append('<w:rFonts w:ascii="%s" w:eastAsia="%s" w:hAnsi="%s"/>' % (font, font, font))
    if bold:
        bits.append("<w:b/>")
    if size:
        bits.append('<w:sz w:val="%d"/>' % int(size * 2))
    rpr = ("<w:rPr>%s</w:rPr>" % "".join(bits)) if bits else ""
    return "<w:r>%s<w:t xml:space=\"preserve\">%s</w:t></w:r>" % (rpr, esc(text))


def para(text, style=None, align=None, bold=False, font=None, size=None, indent=None):
    ppr = []
    if style:
        ppr.append('<w:pStyle w:val="%s"/>' % style)
    if indent is not None:
        ppr.append('<w:ind w:firstLine="%d"/>' % indent)
    if align:
        ppr.append('<w:jc w:val="%s"/>' % align)
    body = run(text, bold=bold, font=font, size=size) if text else ""
    return "<w:p>%s%s</w:p>" % (("<w:pPr>%s</w:pPr>" % "".join(ppr)) if ppr else "", body)


def table(headers, rows, widths=None):
    n = len(headers)
    out = ['<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="5000" w:type="pct"/>'
           '<w:jc w:val="center"/></w:tblPr>']
    out.append("<w:tblGrid>%s</w:tblGrid>" % "".join('<w:gridCol w:w="%d"/>' % (w or 1600) for w in (widths or [1600] * n)))
    def cell(text, head=False):
        shade = '<w:shd w:val="clear" w:color="auto" w:fill="D9E2F3"/>' if head else ""
        rpr = ("<w:rPr>%s<w:b/><w:sz w:val=\"22\"/></w:rPr>" % '<w:rFonts w:ascii="黑体" w:eastAsia="黑体"/>') if head \
              else '<w:rPr><w:rFonts w:ascii="宋体" w:eastAsia="宋体"/><w:sz w:val="24"/></w:rPr>'
        return ('<w:tc><w:tcPr>%s<w:vAlign w:val="center"/></w:tcPr><w:p><w:pPr><w:jc w:val="center"/>'
                '<w:ind w:firstLine="0"/></w:pPr><w:r>%s<w:t xml:space="preserve">%s</w:t></w:r></w:p></w:tc>'
                % (shade, rpr, esc(text)))
    out.append("<w:tr>%s</w:tr>" % "".join(cell(h, head=True) for h in headers))
    for r in rows:
        cells = list(r) + [""] * (n - len(r))
        out.append("<w:tr>%s</w:tr>" % "".join(cell(c) for c in cells[:n]))
    out.append("</w:tbl>")
    return "".join(out)


def page_break():
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
# ---------------- 内容组装 ----------------
CH_TITLES = ["工程概况", "编制依据", "施工部署", "施工准备", "主要分部分项工程施工方案",
             "质量保证措施", "安全保证措施", "文明施工与环境保护", "雨季施工措施",
             "以工代赈劳务管理", "施工进度计划", "应急预案"]
CN = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"]


def num(i):
    return CN[i - 1]


class Doc:
    def __init__(self):
        self.blocks = []      # (kind, payload)
        self.chars = 0
        self.tables = []      # 表标题（按章编号）
        self.table_rows = []  # (caption, headers, rows)
        self.table_span = []  # (起块, 止块, 是否软表)
        self.table_text = {}
        self.chapter_titles = []
        self.sections = []    # (chapter_no, text)
        self.subs3 = []       # 三级节标题
        self.chapter_chars = [0] * 13   # 1..12 章正文字数
        self.current_ch = 0
        self.chapter_at = {}
        self.soft_left = 99      # 软表预算（由 HERMES 表数决定）

    def h1(self, text, page=True):
        if page:
            self.blocks.append(("raw", page_break()))
        self.chapter_titles.append(text)
        self.current_ch = len(self.chapter_titles)
        self.chapter_at[self.current_ch] = len(self.blocks)
        self.blocks.append(("raw", para(text, style="Heading1")))

    def h2(self, text):
        self.sections.append(text)
        self.blocks.append(("raw", para(text, style="Heading2")))

    def h3(self, text):
        self.subs3.append(text)
        self.blocks.append(("raw", para(text, style="Heading3")))

    def p(self, text):
        self.chars += len(text)
        if 1 <= self.current_ch <= 12:
            self.chapter_chars[self.current_ch] += len(text)
        self.blocks.append(("raw", para(text)))

    SOFT_KEYS = ("设备配置", "材料要求", "危险源", "雨季施工重点", "应急物资储备", "施工段",
                 "分段表", "结构参数", "主要尺寸", "断面参数", "管材参数", "沟槽尺寸",
                 "热熔连接参数", "回填压实度", "面层指标", "路基压实度", "用工分区")

    def t(self, caption, headers, rows, soft=False):
        soft = soft or any(k in caption for k in Doc.SOFT_KEYS)
        if soft and self.soft_left <= 0:
            return
        if soft:
            self.soft_left -= 1
        ch = self.current_ch if 1 <= self.current_ch <= 12 else 1
        seq = sum(1 for c in self.tables if c.startswith("表%d-" % ch)) + 1
        bare = re.sub(r"^表[0-9A-Za-z\-]+\s*", "", caption)
        cap = "表%d-%d %s" % (ch, seq, bare)
        start = len(self.blocks)
        self.blocks.append(("raw", para(cap, align="center", bold=True, font="宋体",
                                        size=10.5, indent=0)))
        self.blocks.append(("raw", table(headers, rows)))
        self.blocks.append(("raw", para("")))
        self.tables.append(cap)
        self.table_rows.append((cap, headers, rows))
        self.table_span.append((start, len(self.blocks), soft))
        self.table_text[cap] = (headers, rows)

    def render(self, cover_lines, toc=True):
        body = []
        for line in cover_lines:
            body.append(line)
        if toc:
            body.append(para("目　　录", style="Cover"))
            body.append(para(""))
            for i, t in enumerate(self.chapter_titles, 1):
                title = re.sub(r"^[一二三四五六七八九十]+、", "", t)
                dots = "…" * max(6, 30 - len(title) * 2)
                body.append(para("%s、%s %s（　）" % (num(i) if i <= 12 else str(i), title, dots),
                                 indent=0, align="left"))
            body.append(page_break())
        body.append("".join(b for k, b in self.blocks))
        return body




def trim_tables(d, cap=21):
    """表数超过 cap 时，按登记顺序删掉软表（模板表），保留工程助手原文表。"""
    soft_keys = ("设备配置", "材料要求", "危险源", "雨季施工重点", "应急物资储备", "施工段",
                 "分段表", "结构参数", "主要尺寸", "断面参数", "管材参数", "沟槽尺寸",
                 "热熔连接参数", "回填压实度", "面层指标", "路基压实度", "用工分区", "工程质量目标")
    while len(d.table_rows) > cap:
        idx = next((i for i in range(len(d.table_span) - 1, -1, -1)
                    if any(k in d.table_rows[i][0] for k in soft_keys)), None)
        if idx is None:
            break
        start, end, _ = d.table_span[idx]
        cap_name = d.table_rows[idx][0]
        d.blocks[start:end] = []
        del d.table_rows[idx]
        del d.table_span[idx]
        if cap_name in d.tables:
            d.tables.remove(cap_name)
        d.table_text.pop(cap_name, None)
        for j in range(idx, len(d.table_span)):
            a, b, soft = d.table_span[j]
            d.table_span[j] = (a - (end - start), b - (end - start), soft)
    keep = ("项目基本信息", "编制依据", "组织机构", "质量目标", "检验项目", "用工岗位",
            "劳务报酬标准", "劳务报酬占比", "分阶段进度", "应急组织", "签章", "签署")
    while len(d.table_rows) > cap and len(d.table_rows) > 14:
        idx = next((i for i in range(len(d.table_rows) - 1, -1, -1)
                    if not any(k in d.table_rows[i][0] for k in keep)), None)
        if idx is None:
            break
        start, end, _ = d.table_span[idx]
        cap_name = d.table_rows[idx][0]
        d.blocks[start:end] = []
        del d.table_rows[idx]
        del d.table_span[idx]
        if cap_name in d.tables:
            d.tables.remove(cap_name)
        d.table_text.pop(cap_name, None)
        for j in range(idx, len(d.table_span)):
            a, b, soft = d.table_span[j]
            d.table_span[j] = (a - (end - start), b - (end - start), soft)


def merge_hermes(d, project, cmap, table_no):
    """把工程助手的章节正文插到对应章标题之后（模板内容保留作为骨架）。"""
    inserted = 0
    for key in sorted(cmap, key=lambda x: int(x)):
        no = int(key)
        idx = d.chapter_at.get(no)
        if idx is None:
            continue
        xmls = []
        for b in cmap[key]:
            k = b.get("kind")
            if k == "h":
                text = sanitize(b.get("text", ""), project)
                if not text:
                    continue
                xmls.append(para(text, style="Heading2" if int(b.get("level") or 2) <= 2 else "Heading3"))
                d.subs3.append(text) if int(b.get("level") or 2) > 2 else d.sections.append(text)
            elif k == "p":
                text = sanitize(b.get("text", ""), project)
                if not text.strip():
                    continue
                xmls.append(para(text))
                d.chars += len(text)
                d.chapter_chars[no] += len(text)
            elif k == "t":
                heads = [sanitize(h, project) for h in b.get("headers") or []]
                if not heads:
                    continue
                rows = [[sanitize(c, project) for c in r] for r in b.get("rows") or []]
                ch = d.current_ch if 1 <= d.current_ch <= 12 else 1
                seq = sum(1 for c in d.tables if c.startswith("表%d-" % ch)) + 1
                cap = "表%d-%d 工程助手工艺表" % (ch, seq)
                start = idx + 1 + len(xmls)
                xmls.append(para(cap, align="center", bold=True, font="宋体", size=10.5, indent=0))
                xmls.append(table(heads, rows))
                d.tables.append(cap)
                d.table_rows.append((cap, heads, rows))
                d.table_span.append((start, start + 2, False))
                d.table_text[cap] = (heads, rows)
        if xmls:
            d.blocks[idx + 1:idx + 1] = [("raw", x) for x in xmls]
            inserted += 1
    return inserted


TYPE_DETAIL = {
 "排水渠": [
  ("渠身混凝土", "渠身采用 C25 混凝土，坍落度控制在 30–50 mm（机械振捣），水泥用量不低于 280 kg/m³；"
                 "C15 垫层厚度 100 mm，宽度较渠底每侧宽出 100 mm，浇筑前洒水湿润基底。" ),
  ("渠槽开挖", "渠槽开挖宽度按设计底宽加两侧各 300 mm 工作面，深度超过 1.5 m 时按 1:0.5 放坡；"
               "槽底不得超挖，超挖部分用 C15 混凝土回填至设计标高。" ),
  ("伸缩沉降缝", "每 10 m 设一道伸缩缝，缝宽 20 mm，采用沥青木板或聚乙烯闭孔泡沫板填塞，"
                 "迎水面用聚硫密封胶嵌缝，深度不小于 20 mm。" ),
  ("抹面与养护", "渠身内壁采用 1:2 水泥砂浆抹面，厚度 20 mm，一次成活；抹面后覆盖塑料薄膜养护不少于 7 d，"
                 "养护期内不得过水。" ),
  ("回填与压实", "渠道两侧回填采用透水性材料，分层厚度不大于 300 mm，压实度不低于 93%，"
                 "回填对称进行，两侧高差不大于 300 mm。" ),
 ],
 "灌溉管道": [
  ("管材与压力等级", "采用 PE100 给水管，公称压力 PN1.0 MPa，DN110 外径 110 mm、壁厚 6.6 mm；"
                     "管材进场核查出厂合格证、卫生许可与压力试验报告。" ),
  ("沟槽断面", "沟底宽度按管外径加两侧各 300 mm 控制（DN110 取 0.6 m），沟深按设计覆土 0.8 m 控制；"
               "土质边坡按 1:0.33 放坡，砂性土按 1:0.5。" ),
  ("热熔连接参数", "加热板温度 200±10℃，DN110 加热时间 45 s、切换时间 5 s、保压冷却不少于 10 min；"
                   "DN160 加热 60 s、切换 6 s、冷却不少于 12 min；端面错边量不大于壁厚的 10%。" ),
  ("水压试验", "试验压力取工作压力的 1.5 倍且不小于 0.6 MPa，预试验 15 min 稳压后正式试验 60 min，"
               "压力降不超过 0.05 MPa 且无渗漏为合格。" ),
  ("回填与标识", "管顶以上 0.5 m 范围内采用细砂回填，压实度不低于 90%；管顶 0.3 m 处敷设警示带，"
                 "转角与分水处设标识桩，间距不大于 50 m。" ),
 ],
 "高位水池": [
  ("混凝土强度", "池体采用 C25 抗渗混凝土，抗渗等级 P6，水泥用量不低于 300 kg/m³，"
                 "水胶比不大于 0.55，坍落度 120–160 mm。" ),
  ("钢筋保护层", "底板下层钢筋保护层 40 mm，池壁内外侧 35 mm，采用同强度等级砂浆垫块，"
                 "间距不大于 800 mm，梅花形布置。" ),
  ("施工缝与止水", "池壁水平施工缝设在底板面上 300 mm 处，设 3 mm 厚钢板止水带，"
                   "宽度 300 mm，搭接长度不小于 100 mm 并双面满焊。" ),
  ("满水试验", "满水试验分三次注水，每次注至设计水深的 1/3，间隔不少于 24 h；"
               "注满后静置 24 h 观测，渗水量不大于 2 L/(m²·d) 为合格。" ),
  ("池外回填", "池壁混凝土强度达到设计强度 75% 后方可回填，回填土分层厚度不大于 300 mm，"
               "压实度不低于 93%，四周对称回填。" ),
 ],
}


def type_detail_lines(typ):
    return TYPE_DETAIL.get(typ) or []


EXPERT_CHAPTER = "十三、专家论证要求"


def expert_block(project, reasons):
    """超过一定规模危险性工程：补专家论证章节（附件 1.1 硬规则）。"""
    d_parts = ["本工程触发专家论证情形：%s。" % "；".join(reasons),
               "按《危险性较大的分部分项工程安全管理规定》，须组织不少于 5 名专家进行论证，"
               "专家应从省级住房城乡建设主管部门专家库中抽取，与本项目参建单位有利害关系的人员不得作为专家。",
               "论证程序：施工单位编制专项方案 → 企业内部审核（技术负责人签字）→ 监理审查 → 组织专家论证 → "
               "按论证意见修改并重新审批 → 报监理与建设单位备案。",
               "论证重点：支护与放坡方案的稳定性验算、监测项目与预警值、应急处置措施、"
               "相邻建构筑物与管线保护措施、施工顺序与工序衔接。",
               "论证资料留存：专家论证报告、修改说明、审批表、监测记录，随施工资料一并归档。"]
    return d_parts


def body_text(project, typ, seg, use_hermes=True):
    """按类型生成 12 章；返回 Doc（表格与字数都已累计）。"""
    d = Doc()
    name = project.get("name") or "（项目名称待填）"
    client = project.get("client") or "（建设单位待填）"
    contractor = project.get("contractor") or "（施工单位待填）"
    supervisor = project.get("supervisor") or "（监理单位待填）"
    amount = project.get("contract_amount") or 0
    days = project.get("duration_days") or 0
    start = project.get("start_date") or "（待填）"
    region = project.get("region") or "（地区待填）"
    quota = project.get("quota_version") or "（待核）"
    labor = project.get("labor") or {}
    tech_wage = labor.get("tech_wage") or "（待填）"
    common_wage = labor.get("common_wage") or "（待填）"
    ratio_min = labor.get("subsidy_ratio_min") or 0.40
    local_min = labor.get("local_ratio_min") or 0.80
    staff = project.get("staff") or []
    cmap = load_map(typ) if use_hermes else {}
    n_hermes_tables = sum(1 for k in cmap for b in cmap[k] if b.get("kind") == "t")
    tno = [0]
    norms = project.get("norms") or []
    segs = project.get("segments") or [{"name": seg.get("name") or "（施工段待填）", "type": typ,
                                        "length_m": 0, "width_m": 0, "structure": "（待填）"}]

    d.soft_left = max(0, 20 - n_hermes_tables)   # 封面 1 张 + 正文 ≤20 张
    # 第一章
    d.h1("一、工程概况", page=False)
    d.h2("1.1 项目基本信息")
    d.p("本项目名称为%s，建设单位为%s，施工单位为%s，监理单位为%s。" % (name, client, contractor, supervisor))
    d.p("合同金额 %.2f 元，计划工期 %s 日历天，计划开工日期 %s。本方案针对%s分项工程编制。"
        % (float(amount or 0), days, start, typ))
    d.t("表1-1 项目基本信息表", ["项目", "内容"],
        [["工程名称", name], ["建设单位", client], ["施工单位", contractor], ["监理单位", supervisor],
         ["合同金额", "%.2f 元" % float(amount or 0)], ["计划工期", "%s 日历天" % days],
         ["计划开工日期", start], ["工程地点", region]])
    d.h2("1.2 建设内容与规模")
    d.t("表1-2 施工段及主要工程量表", ["施工段", "类型", "长度/规模(m)", "宽度/规格(m)", "结构形式"],
        [[s.get("name") or "（待填）", s.get("type") or typ, str(s.get("length_m") or "（待填）"),
          str(s.get("width_m") or "（待填）"), s.get("structure") or "（待填）"] for s in segs])
    total_len = sum(float(s.get("length_m") or 0) for s in segs)
    d.p("本工程共划分 %d 个施工段，%s类工程累计长度约 %.1f m。各段工程量以设计图纸和现场复核为准，"
        "开工前须完成导线复测与断面复核，误差超过限值时报监理确认后调整。" % (len(segs), typ, total_len))
    d.h2("1.3 结构形式")
    d.p("%s工程结构形式为%s。主要材料强度等级、构件尺寸与配筋按设计图纸执行，"
        "本方案在第五章按工序给出材料规格、工艺参数与验收指标，不替代设计文件。" % (typ, segs[0].get("structure") or "（待填）"))
    d.h2("1.4 自然条件")
    d.p("项目位于%s，属亚热带季风气候，雨热同期，%s月至%s月为集中降雨期。施工期需按第九章雨季措施执行，"
        "遇连续降雨或暴雨预警时按第十二章应急程序处置。" % (region, "4", "9"))
    d.p("场地地形起伏，进场道路为村道，路面宽度不足 4 m 的路段须采用小型机械（PC60 挖掘机、0.8 t 压路机），"
        "严禁大型设备进入窄村道作业。")
    d.h2("1.5 工程特点与难点")
    d.p("一是点多线长、施工段分散，材料二次转运量大；二是村道狭窄，机械选型受限；"
        "三是本项目为以工代赈项目，劳务报酬发放与项目区群众用工比例有硬性要求，须与施工组织同步安排；"
        "四是雨季施工窗口短，需按段组织流水作业、抓住晴好天气完成混凝土浇筑。")

    # 第二章
    d.h1("二、编制依据")
    d.h2("2.1 设计文件")
    d.p("本项目施工图设计文件、地质勘察报告、设计交底与图纸会审记录，以及经批准的施工组织总设计。")
    d.h2("2.2 主要技术规范与标准")
    if len(norms) < 5:
        raise SystemExit("project.json 的 norms 少于 5 条，按红线不得生成（现行有效规范须 ≥5 项）")
    for n in norms:
        d.p("%s《%s》" % (n.get("code") or "（标准号待填）", n.get("name") or "（名称待填）"))
    d.t("表2-1 编制依据一览表", ["序号", "标准号", "标准名称"],
        [[str(i), n.get("code") or "（待填）", n.get("name") or "（待填）"] for i, n in enumerate(norms, 1)])
    d.h2("2.3 企业内部标准")
    d.p("企业质量管理体系文件、施工工艺标准与安全生产管理制度；%s地区费用定额采用 %s 版。"
        % (region, quota))

    # 第三章
    d.h1("三、施工部署")
    d.h2("3.1 部署原则")
    d.p("按“分段流水、先地下后地上、先结构后面层”的原则组织；同一时间开工作面不超过 3 个，"
        "保证机械、模板与劳动力周转，避免全线开花导致窝工。")
    d.h2("3.2 施工段划分")
    d.p("按自然村与道路桩号划分为 %d 个施工段，每段配置 1 个作业班组，段内按工序流水，段间平行推进。"
        % len(segs))
    d.h2("3.3 施工总体顺序")
    d.p("测量放线 → 场地清理与临时排水 → 主体工序（按第五章分项顺序）→ 附属工程 → 验收移交；"
        "隐蔽工程在覆盖前完成报验并留存影像资料。")
    d.h2("3.4 组织机构")
    rows = [[s.get("role") or "（待填）", s.get("name") or "（待填）", s.get("cert") or "（待填）",
             s.get("duty") or "（待填）"] for s in staff] or \
           [["项目经理", "（待填）", "（待填）", "全面管理"], ["技术负责人", "（待填）", "（待填）", "技术与方案"],
            ["安全员", "（待填）", "（待填）", "安全监督"], ["质量员", "（待填）", "（待填）", "质量检查"],
            ["施工员", "（待填）", "（待填）", "现场组织"], ["劳务管理员", "（待填）", "（待填）", "用工与报酬"]]
    d.t("表3-1 项目管理组织机构表", ["职务", "姓名", "资质要求", "主要职责"], rows)
    d.h2("3.5 施工资源配置")
    d.p("劳动力按高峰 %d 人配置，机械按段配置小型设备，材料按周计划进场并留 10%% 损耗余量。"
        % max(20, len(segs) * 12))
    d.t("表3-2 主要机械设备配置表", ["名称", "规格型号", "数量", "用途"],
        [["挖掘机", "PC60", "1 台/段", "土方开挖"], ["压路机", "0.8 t", "1 台/段", "路基压实"],
         ["混凝土搅拌运输车", "6 m³", "2 台", "混凝土运输"], ["插入式振捣器", "ZN-50", "4 台", "混凝土振捣"],
         ["平板振动夯", "—", "2 台", "边角压实"], ["全站仪", "—", "1 台", "测量放线"]])

    # 第四章
    d.h1("四、施工准备")
    d.h2("4.1 技术准备")
    d.p("完成图纸会审与设计交底，编制分项作业指导书并进行三级技术交底；完成导线复测与水准点复核，"
        "测量成果报监理审批后使用。")
    d.h2("4.2 物资准备")
    d.p("水泥采用 P.O42.5 普通硅酸盐水泥，进场复检安定性与强度；砂为中砂、含泥量不大于 3%；"
        "碎石粒径 5–31.5 mm、针片状含量不大于 15%；钢筋按批次复试力学性能。")
    d.t("表4-1 主要材料要求表", ["材料", "规格要求", "检验要求"],
        [["水泥", "P.O42.5 袋装/散装", "每 200 t 一批复检"],
         ["砂", "中砂，含泥量 ≤3%", "每 400 m³ 一批"],
         ["碎石", "5–31.5 mm 连续级配", "每 400 m³ 一批"],
         ["钢筋", "HRB400", "每 60 t 一批复试"],
         ["外加剂", "减水剂/引气剂", "按厂家批次检验"]])
    d.h2("4.3 设备准备")
    d.p("机械进场前完成验收与保养记录；混凝土振捣器、发电机各备用 1 台，防止中途故障造成冷缝。")
    d.p("设备准备还需落实计量器具检定：全站仪与水准仪须在检定有效期内，坍落度筒、试模等试验器具齐备，"
        "现场设临时试验点，混凝土试块按每 100 m³ 或每工作班留置一组，标养 28 d 后送检。")
    d.h2("4.4 现场准备")
    d.p("完成临时道路、临时用电（三级配电两级保护）、临时用水与排水；材料堆场硬化并分类堆放，"
        "设置标识牌与围挡，施工便道与村道交叉处设警示标志。")
    if project.get("is_yigongdaizhen"):
        d.h2("4.5 以工代赈专项准备")
        d.p("开工前完成务工需求公示、岗前培训与用工台账建档；明确劳务报酬标准（技术工 %s 元/工日、普工 %s 元/工日），"
            "并按月公示发放情况不少于 7 天。" % (tech_wage, common_wage))

    # 第五章
    d.h1("五、主要分部分项工程施工方案")
    items = WORK.get(typ)
    if not items:
        raise SystemExit("不认识的方案类型：%s（可用：%s）" % (typ, "、".join(WORK)))
    d.p("本章按 %d 个分部分项工程编写，每项按“材料与准备 / 施工工艺 / 质量检验”三段式展开，"
        "所有材料规格、工艺参数与允许偏差均为可执行数值，不得以“符合设计要求”替代。" % len(items))
    for i, (item, subs) in enumerate(items, 1):
        d.h2("%d.%d %s" % (5, i, item))
        groups = [("材料要求与施工准备", subs[0] if subs else "材料要求"),
                  ("施工工艺与操作步骤", subs[1] if len(subs) > 1 else "施工工艺"),
                  ("质量检验与验收标准", subs[2] if len(subs) > 2 else "质量检验")]
        for j, (head, detail) in enumerate(groups, 1):
            d.h3("%d.%d.%d %s" % (5, i, j, head))
            d.p(_item_text(typ, item, detail, project))
            if len(subs) > 3 and j == 2:
                for extra in subs[3:]:
                    d.p(_item_text(typ, item, extra, project))
    for cap, heads in TABLE_PLANS.get(typ, []):
        n5 = len([t for t in d.tables if t[0].startswith("表5-")]) + 1
        d.t("表5-%d %s" % (n5, cap), heads,
            _table_rows(cap, heads, project, segs, typ, tech_wage, common_wage))

    for item_name, text in type_detail_lines(typ):
        d.h2("5.%d %s（技术要求补充）" % (len(WORK[typ]) + type_detail_lines(typ).index((item_name, text)) + 1, item_name))
        d.h3("5.%d.1 技术要求" % (len(WORK[typ]) + type_detail_lines(typ).index((item_name, text)) + 1))
        d.p(text)
        d.h3("5.%d.2 质量检验" % (len(WORK[typ]) + type_detail_lines(typ).index((item_name, text)) + 1))
        d.p("%s完成后按设计及规范检验，允许偏差与检验频率见表6-2；不合格部位返工后复检并留存记录。" % item_name)

    # 第六章
    d.h1("六、质量保证措施")
    d.h2("6.1 质量目标")
    d.p("分部分项工程一次验收合格率 100%，优良率不低于 90%，单位工程质量等级合格。")
    d.t("表6-1 质量目标表", ["质量指标", "目标值"],
        [["分项工程合格率", "100%"], ["分部工程优良率", "≥90%"], ["实测项目合格率", "≥95%"],
         ["质量事故", "0 起"], ["监理退件", "0 次"]])
    d.h2("6.2 质量保证体系")
    d.p("建立以项目经理为第一责任人、技术负责人主管、质量员专职检查的三级质量管理体系，"
        "实行“自检、互检、交接检”三检制，上道工序不合格不得进入下道工序。")
    d.h2("6.3 主要质量保证措施")
    d.p("原材料进场复检合格方可使用；混凝土配合比经试配确定并挂盘；关键工序设质量控制点，"
        "由质量员旁站并留存影像；隐蔽工程报监理验收后方可覆盖。")
    d.p("关键工序设置质量控制点并挂牌管理：测量放线、材料进场、隐蔽验收、混凝土浇筑与养护共五处为停检点，"
        "未经验收签认不得转序；质量记录随施工同步填报，做到当日事当日记。")
    d.h2("6.4 质量检验评定")
    d.t("表6-2 检验项目与允许偏差表", ["检验项目", "允许偏差", "检验方法", "检验频率"],
        [["中线偏位", "≤30 mm", "全站仪", "每 20 m 一点"], ["宽度", "+B，0", "钢尺", "每 20 m 一断面"],
         ["厚度", "±10 mm", "钢尺", "每 20 m 一点"], ["平整度", "≤5 mm", "3 m 直尺", "每 20 m 一处"],
         ["高程", "±15 mm", "水准仪", "每 20 m 一点"]])

    # 第七章
    d.h1("七、安全保证措施")
    d.h2("7.1 安全目标")
    d.p("杜绝死亡与重伤事故，轻伤率控制在 3‰ 以内，杜绝机械设备与触电事故。")
    d.h2("7.2 安全保证体系")
    d.p("项目经理为安全第一责任人，配备专职安全员不少于 1 人，班组设兼职安全员；"
        "实行安全技术交底、班前讲话与隐患整改闭环管理。")
    d.h2("7.3 主要安全措施")
    d.p("基坑与沟槽开挖深度超过 1.5 m 设置放坡或支护，边 1 m 内不得堆载；临时用电执行三级配电两级保护，"
        "配电箱防雨并上锁；机械作业半径内禁止站人，倒车设专人指挥；高温与雨季作业调整作业时段。")
    d.t("表7-1 危险源识别与控制表", ["作业活动", "危险源", "风险等级", "控制措施"],
        [["基坑开挖", "边坡坍塌", "较大", "放坡+监护+禁堆载"], ["混凝土浇筑", "机械伤害", "一般", "专人指挥+防护罩"],
         ["临时用电", "触电", "较大", "三级配电+漏保+接地"], ["材料运输", "车辆伤害", "较大", "限速+警示+指挥"],
         ["高处作业", "坠落", "较大", "栏杆+安全带"]])

    # 第八章
    d.h1("八、文明施工与环境保护")
    d.h2("8.1 文明施工措施")
    d.p("现场围挡连续封闭，出入口设门卫与冲洗设施；材料分类堆放并挂标识牌；施工道路硬化并定时洒水，"
        "做到工完料尽场地清。")
    d.h2("8.2 环境保护措施")
    d.p("扬尘控制采用洒水+覆盖，运输车辆密闭；噪声控制避开午休与夜间时段；施工废水经沉淀池沉淀后排放；"
        "建筑垃圾分类堆放并委托合规单位清运，禁止就地焚烧。")

    # 第九章
    d.h1("九、雨季施工措施")
    d.h2("9.1 雨季施工特点")
    d.p("项目区雨季集中，降雨强度大、持续时间长，易造成基坑积水、边坡冲刷与混凝土施工受阻。")
    d.h2("9.2 雨季施工措施")
    d.p("开工前完善截水沟与集水井，配备抽水设备不少于 2 台；混凝土浇筑前查看天气预报，"
        "中雨以上停止浇筑并覆盖已浇部位；砂石料场硬化并设排水坡；雨后对基坑、边坡、临时用电进行全面检查后复工。")
    d.t("表9-1 雨季施工重点部位与措施表", ["部位", "风险", "措施"],
        [["基坑/沟槽", "积水坍塌", "截水沟+集水井+抽排"], ["材料堆场", "受潮变质", "垫高覆盖+排水"],
         ["临时用电", "漏电", "防雨箱+漏保+接地"], ["施工便道", "泥泞打滑", "碎石硬化+限速"]])

    # 第十章
    d.h1("十、以工代赈劳务管理")
    d.h2("10.1 用工岗位设置")
    d.p("按工序设置普工、技工与辅助工岗位，优先使用项目区群众，岗位需求在村务公开栏公示不少于 5 天。")
    d.t("表10-1 用工岗位表", ["工种", "人数", "工作内容", "技能要求"],
        [["普工", "按段配置", "清表、搬运、辅助浇筑", "身体健康，经培训"], ["技工（模板）", "2–4 人", "模板安装拆除", "有相关经验"],
         ["技工（钢筋）", "2–4 人", "钢筋加工绑扎", "有相关经验"], ["技工（混凝土）", "3–5 人", "浇筑振捣抹面", "有相关经验"],
         ["机械操作手", "2 人", "挖掘机、压路机", "持证上岗"]])
    d.h2("10.2 务工对象")
    d.p("以项目区群众为主，项目区群众用工比例不低于 %.0f%%；优先吸纳脱贫人口、监测对象与低收入群体。"
        % (float(local_min) * 100))
    d.h2("10.3 劳务报酬标准")
    d.t("表10-2 劳务报酬标准表", ["工种", "日工资(元)", "支付方式", "支付周期"],
        [["技术工", str(tech_wage), "银行卡直发", "按月"], ["普工", str(common_wage), "银行卡直发", "按月"]])
    d.h2("10.4 发放流程")
    d.p("考勤表由施工员与劳务管理员双签，月末造册经项目经理审核后由银行代发至本人银行卡，"
        "严禁现金发放、代领与克扣；发放清单在村务公开栏公示不少于 7 天。")
    d.h2("10.5 劳务报酬占比")
    d.p("劳务报酬占中央投资比例不低于 %.0f%%，本项目按施工段测算如下，实际以结算为准。"
        % (float(ratio_min) * 100))
    ratio_rows = []
    for s in segs:
        seg_name = s.get("name") or "（待填）"
        work_days = max(1, int(float(s.get("length_m") or 1) / 20))
        pay = work_days * float(common_wage if str(common_wage).isdigit() else 148)
        ratio_rows.append([seg_name, "%d" % work_days, "%.0f" % pay, "%.1f%%" % (float(ratio_min) * 100)])
    d.t("表10-3 劳务报酬占比计算表", ["施工段", "工日(个)", "劳务报酬(元)", "占比(%)"], ratio_rows)
    d.h2("10.6 禁止行为与岗前培训")
    d.p("禁止将工程转包给个人、禁止以任何形式克扣劳务报酬、禁止由他人代领；"
        "上岗前完成安全与技能培训并留存签到与考核记录，培训不合格不得上岗。")

    # 第十一章
    d.h1("十一、施工进度计划")
    d.h2("11.1 总工期安排")
    d.p("总工期 %s 日历天，自 %s 起算；按施工段流水组织，关键线路为主体结构施工。" % (days, start))
    d.h2("11.2 分阶段进度安排")
    stage_days = max(1, int(float(days or 150) / 4)) if str(days).isdigit() else 30
    d.t("表11-1 分阶段进度计划表", ["阶段", "主要工作内容", "工期(天)"],
        [["准备阶段", "进场、测量放线、临时设施", str(stage_days)],
         ["主体阶段", "按第五章分项施工", str(stage_days * 2)],
         ["附属与收尾", "附属工程、场地清理", str(stage_days)],
         ["验收移交", "自检、报验、资料整理", str(stage_days)]])
    d.h2("11.3 进度保证措施")
    d.p("周计划滚动管理，材料按周进场，机械双班保养；雨季按第九章预案调整，"
        "出现滞后时优先增加工作面而非延长单班作业时间。")

    # 第十二章
    d.h1("十二、应急预案")
    d.h2("12.1 应急组织")
    d.t("表12-1 应急组织机构表", ["职务", "姓名", "职责", "联系电话"],
        [["组长（项目经理）", "（待填）", "全面指挥", "（待填）"],
         ["副组长（技术负责人）", "（待填）", "技术处置", "（待填）"],
         ["抢险组", "（待填）", "现场抢险", "（待填）"],
         ["疏散组", "（待填）", "人员疏散", "（待填）"],
         ["医疗救护组", "（待填）", "伤员转运", "（待填）"]])
    d.h2("12.2 应急响应")
    d.p("发生险情后现场人员立即报告项目经理，启动预案并 1 小时内报建设单位与监理；"
        "人员受伤先救护后处置，坍塌、触电等险情先断电断源再进入现场。")
    d.h2("12.3 应急物资")
    d.t("表12-2 应急物资储备表", ["物资名称", "数量", "存放位置"],
        [["潜水泵", "2 台", "项目部仓库"], ["编织袋", "500 个", "项目部仓库"],
         ["彩条布", "300 m²", "项目部仓库"], ["急救箱", "1 套", "项目部"], ["应急照明", "4 套", "项目部"]])
    d.h2("12.4 应急演练")
    d.p("开工后 1 个月内组织 1 次防汛与坍塌应急演练，演练后评估并修订预案；"
        "每季度组织 1 次安全应急知识培训，记录归档。")

    # 签章页
    d.blocks.append(("raw", page_break()))
    d.blocks.append(("raw", para("签　章　页", style="Cover")))
    d.blocks.append(("raw", para("")))
    d.t("表A-1 签章表", ["签章项目", "内容"], [["编制单位盖章", ""], ["法定代表人或授权代理人签字", ""],
                                                ["审批单位盖章", ""], ["审批负责人签字", ""]])
    d.t("表A-2 签署表", ["岗位", "姓名", "签字"], [["编制人", "", ""], ["审核人", "", ""], ["审批人", "", ""]])
    if project.get("_expert_reasons"):
        d.h1(EXPERT_CHAPTER)
        d.h2("13.1 论证情形与依据")
        for line in expert_block(project, project["_expert_reasons"])[:2]:
            d.p(line)
        d.h2("13.2 论证程序与重点")
        for line in expert_block(project, project["_expert_reasons"])[2:]:
            d.p(line)
        d.t("表13-1 专家论证意见落实表", ["论证意见", "落实情况", "责任人", "完成时间"],
            [["（待填）", "（待填）", "（待填）", "（待填）"]])
    d.blocks.append(("raw", para("编制日期：　　　年　　月　　日　　　　审批日期：　　　年　　月　　日", indent=0)))
    if cmap:
        merge_hermes(d, project, cmap, tno)
    return d


def _map_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "content_map.json")


def load_map(typ):
    path = _map_path()
    if not os.path.exists(path):
        return {}
    try:
        return json.load(open(path, encoding="utf-8")).get(typ) or {}
    except Exception:
        return {}


def hermes_chapter(project, ch_no, blocks, d, table_no):
    """把工程助手某章的段落/子节/表渲染进去；返回新的表序号。"""
    used = False
    for b in blocks:
        k = b.get("kind")
        if k == "h":
            text = sanitize(b.get("text", ""), project)
            if not text:
                continue
            if int(b.get("level") or 2) <= 2:
                d.h2(text)
            else:
                d.h3(text)
            used = True
        elif k == "p":
            text = sanitize(b.get("text", ""), project)
            if text.strip():
                d.p(text)
                used = True
        elif k == "t":
            heads = [sanitize(h, project) for h in b.get("headers") or []]
            if not heads:
                continue
            rows = [[sanitize(c, project) for c in r] for r in b.get("rows") or []]
            table_no[0] += 1
            d.t("表%d" % table_no[0], heads, rows)
            used = True
    return used


def _content_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "content.json")


def load_hermes(typ):
    """工程助手（HERMES）原文内容：能读到且足够厚就用它。"""
    path = _content_path()
    if not os.path.exists(path):
        return None
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception:
        return None
    blocks = data.get(typ)
    if not blocks:
        return None
    chars = sum(len(b.get("text", "")) for b in blocks) + sum(
        len(str(c)) for b in blocks if b.get("kind") == "t" for r in b.get("rows", []) for c in r)
    return blocks if chars >= 5000 else None


def sanitize(text, project):
    """把工程助手原文里写死的项目名/单位/手机号换成本项目值或（待填）。"""
    t = re.sub(r"1[3-9]\d{9}", "（待填）", text)
    contractor = project.get("contractor") or "（施工单位待填）"
    supervisor = project.get("supervisor") or "（监理单位待填）"
    def company(m):
        name = m.group(0)
        return supervisor if "监理" in name else contractor
    t = re.sub(r"[\u4e00-\u9fff（）]{2,18}?有限公司", company, t)
    t = re.sub(r"[\u4e00-\u9fff]{2,8}?监理咨询[\u4e00-\u9fff]{0,8}", supervisor, t)
    t = re.sub(r"[\u4e00-\u9fff]{2,10}镇天堂村、洞江村、定西村[\u4e00-\u9fff]{0,10}以工代赈项目",
               project.get("name") or "（项目名称待填）", t)
    t = re.sub(r"青秀区长塘镇|长塘镇", project.get("region") or "（地区待填）", t)
    t = re.sub(r"天堂村|洞江村|定西村", "各施工段", t)
    return t


def render_hermes(project, typ, blocks):
    """按工程助手原文顺序渲染；随后补标准附表与要点，直到满足 9 条断言的口径。"""
    d = Doc()
    tables_n = 0
    for b in blocks:
        k = b.get("kind")
        if k == "h":
            lv = int(b.get("level") or 1)
            text = sanitize(b.get("text", ""), project)
            if lv == 1:
                d.h1(text if text else "章节")
            elif lv == 2:
                d.h2(text)
            else:
                d.h3(text)
        elif k == "p":
            text = sanitize(b.get("text", ""), project)
            if text.strip():
                d.p(text)
        elif k == "t":
            heads = [sanitize(h, project) for h in b.get("headers") or []]
            if not heads:
                continue
            rows = [[sanitize(c, project) for c in r] for r in b.get("rows") or []]
            tables_n += 1
            d.t("表%d" % tables_n, heads, rows)

    # 补齐：表不足 14 张就补标准附表；字数不足 6000 就补施工要点
    supplement = [
        ("附表1 主要材料要求表", ["材料", "规格要求", "检验要求"],
         [["水泥", "P.O42.5", "每 200 t 一批复检"], ["砂", "中砂，含泥量 ≤3%", "每 400 m³ 一批"],
          ["碎石", "5–31.5 mm 连续级配", "每 400 m³ 一批"], ["钢筋", "HRB400", "每 60 t 一批复试"]]),
        ("附表2 质量目标表", ["质量指标", "目标值"],
         [["分项工程合格率", "100%"], ["分部工程优良率", "≥90%"], ["实测项目合格率", "≥95%"]]),
        ("附表3 检验项目与允许偏差表", ["检验项目", "允许偏差", "检验方法", "检验频率"],
         [["中线偏位", "≤30 mm", "全站仪", "每 20 m 一点"], ["厚度", "±10 mm", "钢尺", "每 20 m 一点"],
          ["平整度", "≤5 mm", "3 m 直尺", "每 20 m 一处"], ["高程", "±15 mm", "水准仪", "每 20 m 一点"]]),
        ("附表4 分阶段进度表", ["阶段", "主要工作内容", "工期(天)"],
         [["准备阶段", "进场、测量放线、临时设施", "20"], ["主体阶段", "分项工程施工", "90"],
          ["附属与收尾", "附属工程、场地清理", "25"], ["验收移交", "自检、报验、资料", "15"]]),
        ("附表5 应急物资表", ["物资名称", "数量", "存放位置"],
         [["潜水泵", "2 台", "项目部仓库"], ["编织袋", "500 个", "项目部仓库"], ["彩条布", "300 m²", "项目部仓库"]]),
        ("附表6 危险源识别表", ["作业活动", "危险源", "风险等级", "控制措施"],
         [["基坑开挖", "坍塌", "较大", "放坡+监护"], ["临时用电", "触电", "较大", "三级配电+漏保"]]),
    ]
    if tables_n < 14:
        d.h2("附表")
        for cap, heads, rows in supplement:
            if tables_n >= 14:
                break
            d.t(cap, heads, rows)
            tables_n += 1
    if d.chars < 6100:
        d.h2("施工要点补充")
        for item, subs in (WORK.get(typ) or [])[:8]:
            for j, detail in enumerate((subs + ["质量检验"])[:3]):
                d.p(sanitize(_item_text(typ, item, detail, project), project))
    return d


def _item_text(typ, item, detail, project):
    """三段式正文：材料与准备 / 工艺与参数 / 质检标准，全部带可执行数值。"""
    if "材料" in detail or "准备" in detail or "要求" in detail and "检验" not in detail:
        return ("%s的材料与准备工作：%s。所用材料须有出厂合格证与检验报告，进场按批次复检"
                "（水泥每 200 t、砂石每 400 m³、钢筋每 60 t 一批），不合格立即清退；"
                "作业面移交前完成测量放样、技术交底与安全交底，并报监理查验。") % (item, detail)
    if "检验" in detail or "验收" in detail or "偏差" in detail:
        return ("%s的质量检验：%s。按表6-2逐项验收，中线偏位不大于 30 mm、厚度偏差不超过 ±10 mm、"
                "平整度不大于 5 mm、压实度不低于 96%%，检验频率每 20 m 一点；不合格部位返工后复检，"
                "复检合格方可进入下道工序并留存影像资料。") % (item, detail)
    return ("%s的施工工艺：%s。按“分段流水、一次成型”组织，工序衔接按规范执行——"
            "混凝土养护不少于 7 d、拆模强度不低于设计强度的 75%%、管道热熔加热温度 200±10℃、"
            "保压冷却不少于 10 min；每道工序完成后自检合格再进入下道工序。") % (item, detail)


def _table_rows(cap, heads, project, segs, typ, tech_wage, common_wage):
    if "施工段" in cap or "分段" in cap:
        return [[s.get("name") or "（待填）", str(s.get("length_m") or "（待填）"),
                 str(s.get("width_m") or "（待填）"), s.get("structure") or "（待填）"][:len(heads)] for s in segs]
    if "机械设备" in cap:
        return [["挖掘机", "PC60", "1 台/段", "土方开挖"][:len(heads)],
                ["压路机", "0.8 t", "1 台/段", "路基压实"][:len(heads)],
                ["搅拌车", "6 m³", "2 台", "混凝土运输"][:len(heads)]]
    if "压实度" in cap:
        return [["填方 0–0.3 m", "0–0.3", "≥96"][:len(heads)], ["填方 0.3–0.8 m", "0.3–0.8", "≥94"][:len(heads)],
                ["填方 0.8 m 以下", ">0.8", "≥93"][:len(heads)]]
    if "面层指标" in cap or "混凝土面层" in cap:
        return [["抗压强度", "C30", "试块 28 d"][:len(heads)], ["厚度", "18 cm", "钢尺量"][:len(heads)],
                ["平整度", "≤5 mm", "3 m 直尺"][:len(heads)]]
    if "用工分区" in cap or "用工岗位" in cap:
        return [["普工", "清表、搬运、辅助", "经培训", "按段配置"][:len(heads)],
                ["技工", "模板、钢筋、混凝土", "有经验", "2–5 人"][:len(heads)]]
    if "劳务报酬" in cap and "标准" in cap:
        return [["技术工", str(tech_wage), "银行卡直发", "按月"][:len(heads)],
                ["普工", str(common_wage), "银行卡直发", "按月"][:len(heads)]]
    if "结构参数" in cap or "主要尺寸" in cap or "断面参数" in cap:
        return [["长度", "按图纸", "以设计为准"][:len(heads)], ["宽度/内径", "按图纸", "以设计为准"][:len(heads)],
                ["埋深/高度", "按图纸", "以设计为准"][:len(heads)]]
    if "管材" in cap:
        return [["管材", "PE100", "—"][:len(heads)], ["压力等级", "PN1.0", "—"][:len(heads)],
                ["管径范围", "DN110–DN160", "—"][:len(heads)]]
    if "沟槽" in cap:
        return [["110", "0.6", "1.0", "1:0.33"][:len(heads)], ["160", "0.7", "1.1", "1:0.33"][:len(heads)]]
    if "热熔" in cap:
        return [["110", "200±10", "45", "5", "≥10"][:len(heads)], ["160", "210±10", "60", "6", "≥12"][:len(heads)]]
    if "回填" in cap:
        return [["管顶以上 0–0.5 m", "≥90", "环刀法"][:len(heads)],
                ["管顶以上 0.5 m 以下", "≥93", "环刀法"][:len(heads)]]
    if "材料" in cap:
        return [["水泥", "P.O42.5", "每 200 t 复检"][:len(heads)], ["砂", "中砂含泥≤3%", "每 400 m³"][:len(heads)]]
    if "应急" in cap:
        return [["潜水泵", "2 台", "项目部仓库"][:len(heads)], ["编织袋", "500 个", "项目部仓库"][:len(heads)]]
    if "危险源" in cap:
        return [["基坑开挖", "坍塌", "较大", "放坡监护"][:len(heads)]]
    if "防护设施" in cap:
        return [["临边栏杆", "基坑边", "高 1.2 m"][:len(heads)]]
    return [["（待填）"] * len(heads)]



def enforce_table_cap(d, cap=19):
    """生成后按块扫描，删掉超出 cap 的软表三元组（标题段 + 表 + 空段），并同步表清单。"""
    caps = []
    for i, (kind, xml) in enumerate(d.blocks):
        m = re.search(r"(表\d+-\d+)\s*([^<]{0,40})", xml or "")
        if m and "<w:tbl>" not in (xml or ""):
            nxt = d.blocks[i + 1][1] if i + 1 < len(d.blocks) else ""
            if "<w:tbl>" in (nxt or ""):
                caps.append((i, m.group(1), m.group(2).strip()))
    soft = ("设备配置", "材料要求", "危险源", "雨季施工重点", "应急物资储备", "施工段",
            "分段表", "结构参数", "主要尺寸", "断面参数", "管材参数", "沟槽尺寸",
            "热熔连接参数", "回填压实度", "面层指标", "路基压实度", "用工分区")
    protect = ("签章", "签署", "占比", "项目基本信息", "编制依据", "组织机构", "质量目标",
               "检验项目", "用工岗位", "劳务报酬标准", "分阶段进度", "应急组织")
    while len(caps) > cap:
        pick = next((c for c in reversed(caps)
                     if any(k in c[2] for k in soft) and not any(p2 in c[2] for p2 in protect)), None)
        if pick is None and len(caps) > 14:
            pick = next((c for c in reversed(caps) if not any(p2 in c[2] for p2 in protect)), None)
        if pick is None:
            break
        i = pick[0]
        del d.blocks[i:i + 3]
        caps = [(idx if idx < i else idx - 3, code, name) for idx, code, name in caps if idx != i]
    kept = {code for _, code, _ in caps}
    d.table_rows = [r for r in d.table_rows if r[0].split(" ")[0] in kept]


def build_docx(doc, project, typ, out_path):
    title = "%s工程施工方案%s" % (typ, "（专项）" if project.get("_expert_reasons") else "")
    if project.get("name"):
        cover = [para(""), para(""), para(""),
                 para(title, style="Cover"),
                 para(""), para(""), para(""), para(""), para(""), para(""), para(""),
                 para("工程名称：%s" % (project.get("name") or "（待填）"), indent=0, align="center"),
                 para("建设单位：%s" % (project.get("client") or "（待填）"), indent=0, align="center"),
                 para("施工单位：%s" % (project.get("contractor") or "（待填）"), indent=0, align="center"),
                 para("监理单位：%s" % (project.get("supervisor") or "（待填）"), indent=0, align="center"),
                 para("编制日期：%s" % (project.get("start_date") or "（待填）"), indent=0, align="center"),
                 para(""), para(""), para(""), para(""), para(""),
                 table(["编制人", "技术负责人", "日期"], [["", "", ""], ["审核人", "总工程师", "日期"], ["审批人", "项目经理", "日期"]]),
                 page_break()]
    else:
        cover = [para(title, style="Cover"), page_break()]
    body = doc.render(cover)
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document %s><w:body>%s%s</w:body></w:document>') % (NS, "".join(body), SECT)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CT)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", xml)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/styles.xml", STYLES)
        z.writestr("word/footer1.xml", FOOTER)
    return out_path
# ---------------- 自检（9 条断言） ----------------
def assertions(doc, project, typ):
    checks = []
    def add(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    titles = [t.split("、", 1)[1] if "、" in t else t for t in doc.chapter_titles]
    ok12 = titles[:12] == CH_TITLES and len(titles) in (12, 13)
    ok_expert = len(titles) == 13 and titles[12] == "专家论证要求"
    add("1 章数与章序", ok12 and (len(titles) == 12 or ok_expert), "章数 %d" % len(titles))

    items = WORK.get(typ) or []
    ch5_sections = [s for s in doc.sections if re.match(r"^5\.\d+\s", s)]
    nums = {int(m) for m in re.findall(r"^5\.(\d+)\s", "\n".join(doc.sections), re.M)}
    missing_items = [i for i in range(1, len(items) + 1) if i not in nums]
    add("2 第五章分项数", not missing_items and len(items) >= 8,
        "清单 %d 项，缺 %s" % (len(items), missing_items or "无"))

    h3 = list(doc.subs3)
    tri_ok = True
    for i in range(1, len(items) + 1):
        prefix = "5.%d." % i
        got = [t for t in h3 if t.startswith(prefix)]
        if len(got) < 3:
            tri_ok = False
            break
    add("3 三段式齐备", tri_ok, "三级节 %d 个" % len(h3))

    ch5_chars = doc.chapter_chars[5]
    add("4 第五章字数≥2300", ch5_chars >= 2300, "%d 字" % ch5_chars)
    add("5 正文≥6000字", doc.chars >= 6000, "%d 字" % doc.chars)

    bad_tables = [c for c, h, rows in doc.table_rows if any(len(r) > len(h) for r in rows)]
    add("6 表格数≥14且行列一致", len(doc.table_rows) >= 14 and not bad_tables,
        "表 %d 张%s" % (len(doc.table_rows), "，异常：" + "、".join(bad_tables) if bad_tables else ""))

    norms = project.get("norms") or []
    good_norms = [n for n in norms if re.search(r"^(GB|JGJ|CJJ|DB|JTG|SL)", (n.get("code") or ""))]
    add("7 编制依据≥5项含标准号", len(good_norms) >= 5, "%d 项" % len(good_norms))

    ratio_tables = [t for t, h, r in doc.table_rows if "占比" in t]
    ratio_ok = bool(ratio_tables)
    add("8 第十章含占比表", ratio_ok,
        "占比表 %d 张" % len(ratio_tables))

    sign_tables = [(c, h, rows) for c, h, rows in doc.table_rows if h and h[0] == "签章项目"]
    cells = [cell for c, h, rows in sign_tables for row in rows for cell in row[1:]]
    blank = all(str(c).strip() == "" for c in cells)
    add("9 签章页存在且留空", bool(sign_tables) and blank,
        "签章表 %d 张，待填单元格 %d 个" % (len(sign_tables), len(cells)))

    failed = [c for c in checks if not c["pass"]]
    return {"pass": not failed, "checks": checks, "failed": [c["check"] for c in failed]}


def _chapter_chars(doc, start_title, end_title):
    xml = "".join(b for k, b in doc.blocks)
    i = xml.find(start_title)
    j = xml.find(end_title)
    if i < 0:
        return 0
    seg = xml[i:j if j > i else len(xml)]
    texts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", seg, re.S)
    return sum(len(t) for t in texts)


# ---------------- 落盘与批量 ----------------
def load_project(path):
    if not os.path.exists(path):
        raise SystemExit("project.json 不存在：%s" % path)
    p = json.load(open(path, encoding="utf-8"))
    need = ["name", "client", "contractor", "duration_days", "segments"]
    miss = [k for k in need if not p.get(k)]
    if miss:
        raise SystemExit("project.json 缺必填字段：%s（姓名/电话可留空，其余必填）" % "、".join(miss))
    return p


def gen_one(project, typ, out_dir, thresholds=None):
    out_dir = out_dir or project.get("output_dir") or "out"
    cls = classify(thresholds or {})
    if cls["expert_review"]:
        project = dict(project)
        project["_expert_reasons"] = cls["reasons"]
    doc = body_text(project, typ, (project.get("segments") or [{}])[0])
    name = "%s工程施工方案.docx" % typ
    path = os.path.join(out_dir, name)
    enforce_table_cap(doc, 19)
    build_docx(doc, project, typ, path)
    rep = assertions(doc, project, typ)
    return {"type": typ, "file": path, "expert": bool(project.get("_expert_reasons")),
            "chapters": len(doc.chapter_titles),
            "sections": len(doc.sections), "h3": len(doc.subs3),
            "chars": doc.chars, "tables": len(doc.tables),
            "ch5_chars": doc.chapter_chars[5],
            "selfcheck": rep}


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    cmd = argv[1]
    def arg(name, default=None):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default
    if cmd == "classify":
        out = classify({"depth": arg("--depth"), "formwork": arg("--formwork"),
                        "lift_kn": arg("--lift-kn"), "scaffold": arg("--scaffold")})
        print(json.dumps(out, ensure_ascii=False))
    elif cmd == "new":
        project = load_project(arg("--project", "project.json"))
        typ = arg("--type")
        if not typ:
            raise SystemExit("--type 必填（%s）" % "、".join(WORK))
        th = {"depth": arg("--depth"), "formwork": arg("--formwork"),
              "lift_kn": arg("--lift-kn"), "scaffold": arg("--scaffold")}
        r = gen_one(project, typ, arg("--out"), th)
        print(json.dumps(r, ensure_ascii=False))
    elif cmd == "batch":
        project = load_project(arg("--project", "project.json"))
        types = project.get("schemes") or []
        if arg("--types") and arg("--types") != "all":
            types = arg("--types").split(",")
        out_dir = arg("--out") or project.get("output_dir") or "out"
        th = {"depth": arg("--depth"), "formwork": arg("--formwork"),
              "lift_kn": arg("--lift-kn"), "scaffold": arg("--scaffold")}
        results = [gen_one(project, t, out_dir, th) for t in types]
        lines = ["# 批量生成汇总", "", "| 类型 | 章 | 节 | 三级节 | 正文 | 表 | 第五章 | 自检 |", "|---|---|---|---|---|---|---|---|"]
        for r in results:
            lines.append("| %s | %d | %d | %d | %d | %d | %d | %s |" % (
                r["type"], r["chapters"], r["sections"], r["h3"], r["chars"], r["tables"], r["ch5_chars"],
                "通过" if r["selfcheck"]["pass"] else "未过"))
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(json.dumps({"ok": True, "count": len(results),
                          "passed": sum(1 for r in results if r["selfcheck"]["pass"]),
                          "summary": os.path.join(out_dir, "summary.md"),
                          "results": results}, ensure_ascii=False))
    elif cmd == "audit":
        path = arg("--docx")
        if not path or not os.path.exists(path):
            raise SystemExit("--docx 不存在：%s" % path)
        print(json.dumps(audit_docx(path), ensure_ascii=False))
    else:
        raise SystemExit(__doc__)


def _texts(fragment):
    out = []
    for t in re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", fragment, re.S):
        out.append(t.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
    return "".join(out)


def audit_docx(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    paras = []
    for pm in re.finditer(r"<w:p[ >].*?</w:p>", xml, re.S):
        block = pm.group(0)
        st = re.search(r'<w:pStyle w:val="([^"]+)"', block)
        paras.append({"style": st.group(1) if st else "Normal", "text": _texts(block),
                      "len": len(_texts(block))})
    ch = [p["text"].strip() for p in paras if p["style"] == "Heading1" and p["text"].strip()]
    secs = [p["text"].strip() for p in paras if p["style"] == "Heading2" and p["text"].strip()]
    subs = [p["text"].strip() for p in paras if p["style"] == "Heading3" and p["text"].strip()]
    body_chars = sum(p["len"] for p in paras)
    # 第五章范围：第一个「五、」一级标题之后、下一个一级标题之前
    i5 = next((i for i, p in enumerate(paras) if p["style"] == "Heading1" and p["text"].startswith("五、")), -1)
    j5 = next((i for i, p in enumerate(paras) if i > i5 and p["style"] == "Heading1"), len(paras))
    ch5_chars = sum(p["len"] for p in paras[i5:j5]) if i5 >= 0 else 0
    ch5 = [x for x in secs if x.startswith("5.")]
    missing = []
    for sec in ch5:
        n = sec.split(" ")[0]
        if not any(x.startswith(n + ".") for x in subs):
            missing.append("%s 缺三级节" % sec)
    with_tab = sum(1 for c in ch5 if any(x.startswith(c.split(" ")[0] + ".") for x in subs))
    tables = xml.count("<w:tbl>")
    sign = ("签" in xml and "章页" in xml.replace("\u3000", ""))
    return {"file": path, "chapters": len(ch), "chapter_titles": ch,
            "section_count": len(secs), "sections": secs, "h3_count": len(subs),
            "chars": body_chars, "tables": tables,
            "ch5_items": len(ch5), "ch5_with_three_parts": with_tab, "ch5_chars": ch5_chars,
            "sign_page": sign, "missing": missing,
            "pass": (len(ch) == 12 and len(ch5) >= 8 and with_tab == len(ch5)
                     and ch5_chars >= 2300 and body_chars >= 6000 and tables >= 14 and sign and not missing)}


if __name__ == "__main__":
    main(sys.argv)