# SPDX-License-Identifier: Apache-2.0
"""Read a .pptx deck, or build one from a JSON spec. Standard library only.

Usage:
  pptx.py read DECK.pptx
  pptx.py write SPEC.json OUT.pptx

read prints JSON: {"slides":[{"index":1,"texts":["标题","要点1",..],"notes":".."}]}
write takes JSON:
  {"title":"演示标题","slides":[{"title":"第一页","bullets":["要点一","要点二"],"notes":"讲稿"}]}
"""
import json
import re
import sys
import zipfile

NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')
CT = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
      '<Default Extension="xml" ContentType="application/xml"/>'
      '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
      '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
      '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
      '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
      '<Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>'
      '<Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>'
      '<Override PartName="/ppt/tableStyles.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>'
      '%s</Types>')
REL_ROOT = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
            '</Relationships>')
THEME = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Mika">'
         '<a:themeElements><a:clrScheme name="Mika">'
         '<a:dk1><a:srgbClr val="000000"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
         '<a:dk2><a:srgbClr val="1F2937"/></a:dk2><a:lt2><a:srgbClr val="F3F4F6"/></a:lt2>'
         '<a:accent1><a:srgbClr val="2563EB"/></a:accent1><a:accent2><a:srgbClr val="0EA5E9"/></a:accent2>'
         '<a:accent3><a:srgbClr val="10B981"/></a:accent3><a:accent4><a:srgbClr val="F59E0B"/></a:accent4>'
         '<a:accent5><a:srgbClr val="EF4444"/></a:accent5><a:accent6><a:srgbClr val="8B5CF6"/></a:accent6>'
         '<a:hlink><a:srgbClr val="2563EB"/></a:hlink><a:folHlink><a:srgbClr val="7C3AED"/></a:folHlink>'
         '</a:clrScheme><a:fontScheme name="Mika">'
         '<a:majorFont><a:latin typeface="Calibri"/><a:ea typeface="微软雅黑"/><a:cs typeface=""/></a:majorFont>'
         '<a:minorFont><a:latin typeface="Calibri"/><a:ea typeface="微软雅黑"/><a:cs typeface=""/></a:minorFont>'
         '</a:fontScheme><a:fmtScheme name="Mika"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
         '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>'
         '<a:lnStyleLst><a:ln><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
         '<a:ln><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
         '<a:ln><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>'
         '<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle>'
         '<a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>'
         '<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
         '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>'
         '</a:fmtScheme></a:themeElements></a:theme>')
MASTER = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<p:sldMaster %s><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
          '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
          '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>'
          '<p:spPr><a:xfrm><a:off x="838200" y="365125"/><a:ext cx="10515600" cy="1325563"/></a:xfrm></p:spPr>'
          '<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>'
          '<p:sp><p:nvSpPr><p:cNvPr id="3" name="Content"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph idx="1"/></p:nvPr></p:nvSpPr>'
          '<p:spPr><a:xfrm><a:off x="838200" y="1825625"/><a:ext cx="10515600" cy="4351338"/></a:xfrm></p:spPr>'
          '<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>'
          '</p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" '
          'accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
          '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>') % NS
LAYOUT = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<p:sldLayout %s type="obj" preserve="1"><p:cSld name="Title and Content"><p:spTree>'
          '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
          '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
          '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>'
          '<p:spPr><a:xfrm><a:off x="838200" y="365125"/><a:ext cx="10515600" cy="1325563"/></a:xfrm></p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>'
          '<p:sp><p:nvSpPr><p:cNvPr id="3" name="Content"/><p:cNvSpPr/><p:nvPr><p:ph idx="1"/></p:nvPr></p:nvSpPr>'
          '<p:spPr><a:xfrm><a:off x="838200" y="1825625"/><a:ext cx="10515600" cy="4351338"/></a:xfrm></p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>'
          '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>') % NS
PRES_PROPS = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentationPr %s/>' % NS
VIEW_PROPS = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:viewPr %s/>' % NS
TABLE_STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<a:tblStyleLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" def="{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"/>')


def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def unesc(t):
    for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'"), ("&amp;", "&")):
        t = t.replace(a, b)
    return t


def run(text, size=None, bold=False, color=None):
    rpr = ""
    if size or bold or color:
        bits = []
        if bold:
            bits.append('b="1"')
        if size:
            bits.append('sz="%d"' % int(size * 100))
        fill = ('<a:solidFill><a:srgbClr val="%s"/></a:solidFill>' % color.lstrip("#")) if color else ""
        rpr = "<a:rPr %s>%s</a:rPr>" % (" ".join(bits), fill)
    return "<a:r>%s<a:t>%s</a:t></a:r>" % (rpr, esc(text))


def slide_xml(title, bullets, notes, size):
    paras = []
    if title:
        paras.append('<p:sp><p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
                     '<p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:spPr/>'
                     '<p:txBody><a:bodyPr/><a:lstStyle/><a:p>%s</a:p></p:txBody></p:sp>'
                     % run(title, size=size, bold=True))
    body = []
    for b in bullets:
        body.append("<a:p>%s</a:p>" % run(b, size=size - 2 if size else None))
    if not body:
        body.append("<a:p/>")
    paras.append('<p:sp><p:nvSpPr><p:cNvPr id="3" name="Content"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
                 '<p:nvPr><p:ph idx="1"/></p:nvPr></p:nvSpPr><p:spPr/>'
                 '<p:txBody><a:bodyPr/><a:lstStyle/>%s</p:txBody></p:sp>' % "".join(body))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:sld %s><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            '%s</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>%s</p:sld>') % (
        NS, "".join(paras), ('<p:timing/>' if notes is None else ""))


def notes_xml(text, n):
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:notes %s><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Slide Image Placeholder 1"/><p:cNvSpPr><a:spLocks noGrp="1" noRot="1" noChangeAspect="1"/></p:cNvSpPr>'
            '<p:nvPr><p:ph type="sldImg"/></p:nvPr></p:nvSpPr><p:spPr/></p:sp>'
            '<p:sp><p:nvSpPr><p:cNvPr id="3" name="Notes Placeholder 2"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
            '<p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/>'
            '<p:txBody><a:bodyPr/><a:lstStyle/><a:p>%s</a:p></p:txBody></p:sp>'
            '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>') % (NS, run(text))


def write(spec_path, out_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    slides = spec.get("slides") or []
    if not slides:
        raise SystemExit("spec has no slides")
    size = float(spec.get("font_size") or 28)
    n = len(slides)
    ct_over = "".join(
        '<Override PartName="/ppt/slides/slide%d.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>' % (i + 1)
        for i in range(n))
    with_notes = [i for i, s in enumerate(slides) if s.get("notes")]
    if with_notes:
        ct_over += "".join(
            '<Override PartName="/ppt/notesSlides/notesSlide%d.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>' % (i + 1)
            for i in with_notes)
    sld_ids = "".join('<p:sldId id="%d" r:id="rId%d"/>' % (256 + i, 10 + i) for i in range(n))
    pres = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:presentation %s saveSubsetFonts="1"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
            '<p:sldIdLst>%s</p:sldIdLst><p:sldSz cx="12192000" cy="6858000"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>') % (NS, sld_ids)
    rels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>',
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>',
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps" Target="presProps.xml"/>',
            '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps" Target="viewProps.xml"/>',
            '<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles" Target="tableStyles.xml"/>']
    for i in range(n):
        rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide%d.xml"/>' % (10 + i, i + 1))
    pres_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>') % "".join(rels)
    master_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
                   '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>'
                   '</Relationships>')
    layout_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
                   '</Relationships>')
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CT % ct_over)
        z.writestr("_rels/.rels", REL_ROOT)
        z.writestr("ppt/presentation.xml", pres)
        z.writestr("ppt/_rels/presentation.xml.rels", pres_rels)
        z.writestr("ppt/slideMasters/slideMaster1.xml", MASTER)
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", master_rels)
        z.writestr("ppt/slideLayouts/slideLayout1.xml", LAYOUT)
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", layout_rels)
        z.writestr("ppt/theme/theme1.xml", THEME)
        z.writestr("ppt/presProps.xml", PRES_PROPS)
        z.writestr("ppt/viewProps.xml", VIEW_PROPS)
        z.writestr("ppt/tableStyles.xml", TABLE_STYLES)
        for i, s in enumerate(slides, 1):
            z.writestr("ppt/slides/slide%d.xml" % i, slide_xml(s.get("title"), s.get("bullets") or [], None, size))
            srels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>']
            if s.get("notes"):
                z.writestr("ppt/notesSlides/notesSlide%d.xml" % i, notes_xml(s["notes"], i))
                srels.append('<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" Target="../notesSlides/notesSlide%d.xml"/>' % i)
            z.writestr("ppt/slides/_rels/slide%d.xml.rels" % i,
                       ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>') % "".join(srels))
    print(json.dumps({"ok": True, "file": out_path, "slides": n}, ensure_ascii=False))


def read(path):
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise SystemExit("not a pptx (not a zip): %s" % path)
    names = [n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)]
    names.sort(key=lambda s: int(re.search(r"(\d+)\.xml$", s).group(1)))
    out = []
    for idx, n in enumerate(names, 1):
        xml = z.read(n).decode("utf-8", "replace")
        texts = [unesc(t) for t in re.findall(r"<a:t>(.*?)</a:t>", xml, re.S)]
        notes_part = "ppt/notesSlides/notesSlide%d.xml" % idx
        notes = ""
        if notes_part in z.namelist():
            notes = " ".join(unesc(t) for t in re.findall(r"<a:t>(.*?)</a:t>", z.read(notes_part).decode("utf-8", "replace"), re.S))
        out.append({"index": idx, "texts": texts, "notes": notes})
    print(json.dumps({"ok": True, "file": path, "slides": out}, ensure_ascii=False))


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    if argv[1] == "read":
        read(argv[2])
    elif argv[1] == "write":
        write(argv[2], argv[3])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)