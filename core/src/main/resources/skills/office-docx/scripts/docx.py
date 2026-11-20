# SPDX-License-Identifier: Apache-2.0
"""Read a .docx document, or build one from a JSON spec. Standard library only.

Usage:
  docx.py read DOC.docx [--max-paragraphs N]
  docx.py write SPEC.json OUT.docx

read prints JSON: {"paragraphs":[{"style":"Normal","text":".."}],"tables":[[[cell,..],..]]}
write takes JSON:
  {"blocks":[
    {"type":"h1|h2|h3|title","text":"标题"},
    {"type":"p","text":"段落","align":"left|center|right","runs":[{"t":"加粗","b":true,"i":true,"size":14,"color":"FF0000"}]},
    {"type":"bullet","text":"要点"},
    {"type":"numbered","text":"第一条"},
    {"type":"table","header":["列1","列2"],"rows":[["a","b"]],"widths":[3000,3000]},
    {"type":"pagebreak"}
  ]}
"""
import json
import re
import sys
import zipfile

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
CT = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
      '<Default Extension="xml" ContentType="application/xml"/>'
      '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
      '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
      '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
      '</Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>')
DOC_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>'
            '</Relationships>')
STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<w:styles %s>'
          '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:eastAsia="宋体" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>'
          '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
          '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
          '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/>'
          '<w:pPr><w:jc w:val="center"/><w:spacing w:before="240" w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="44"/></w:rPr></w:style>'
          '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:qFormat/>'
          '<w:pPr><w:outlineLvl w:val="0"/><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>'
          '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:qFormat/>'
          '<w:pPr><w:outlineLvl w:val="1"/><w:spacing w:before="200" w:after="100"/></w:pPr><w:rPr><w:b/><w:sz w:val="30"/></w:rPr></w:style>'
          '<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:qFormat/>'
          '<w:pPr><w:outlineLvl w:val="2"/><w:spacing w:before="160" w:after="80"/></w:pPr><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>'
          '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/>'
          '<w:pPr><w:ind w:left="720"/></w:pPr></w:style>'
          '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr>'
          '<w:tblBorders><w:top w:val="single" w:sz="4"/><w:left w:val="single" w:sz="4"/><w:bottom w:val="single" w:sz="4"/>'
          '<w:right w:val="single" w:sz="4"/><w:insideH w:val="single" w:sz="4"/><w:insideV w:val="single" w:sz="4"/></w:tblBorders>'
          '<w:tblCellMar><w:top w:w="60" w:type="dxa"/><w:left w:w="80" w:type="dxa"/><w:bottom w:w="60" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar>'
          '</w:tblPr></w:style>'
          '</w:styles>') % W
NUMBERING = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<w:numbering %s>'
             '<w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/>'
             '<w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>'
             '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%%1."/><w:lvlJc w:val="left"/>'
             '<w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>'
             '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>'
             '<w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>'
             '</w:numbering>') % W


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def unesc(t):
    for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'"), ("&amp;", "&")):
        t = t.replace(a, b)
    return t


def run_xml(r):
    pr = []
    if r.get("b"):
        pr.append("<w:b/>")
    if r.get("i"):
        pr.append("<w:i/>")
    if r.get("u"):
        pr.append('<w:u w:val="single"/>')
    if r.get("color"):
        pr.append('<w:color w:val="%s"/>' % r["color"].lstrip("#"))
    if r.get("size"):
        pr.append('<w:sz w:val="%d"/>' % int(float(r["size"]) * 2))
    if r.get("font"):
        pr.append('<w:rFonts w:ascii="%s" w:eastAsia="%s" w:hAnsi="%s"/>' % (r["font"], r["font"], r["font"]))
    rpr = ("<w:rPr>%s</w:rPr>" % "".join(pr)) if pr else ""
    parts = str(r.get("t", "")).split("\n")
    body = "<w:br/>".join('<w:t xml:space="preserve">%s</w:t>' % esc(p) for p in parts)
    return "<w:r>%s%s</w:r>" % (rpr, body)


def para(style, runs, align=None, num_id=None):
    ppr = ['<w:pStyle w:val="%s"/>' % style] if style else []
    if num_id:
        ppr.append('<w:numPr><w:ilvl w:val="0"/><w:numId w:val="%d"/></w:numPr>' % num_id)
    if align:
        ppr.append('<w:jc w:val="%s"/>' % align)
    return "<w:p>%s%s</w:p>" % (("<w:pPr>%s</w:pPr>" % "".join(ppr)) if ppr else "", "".join(run_xml(r) for r in runs))


def table(block):
    header = block.get("header") or []
    rows = block.get("rows") or []
    widths = block.get("widths") or []
    out = ['<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/></w:tblPr>']
    if widths:
        out.append("<w:tblGrid>%s</w:tblGrid>" % "".join('<w:gridCol w:w="%d"/>' % int(w) for w in widths))
    def row_xml(cells, bold=False):
        cells_xml = "".join(
            '<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/></w:tcPr>%s</w:tc>'
            % para(None, [{"t": c, "b": bold}]) for c in cells)
        return "<w:tr>%s</w:tr>" % cells_xml
    if header:
        out.append(row_xml(header, bold=True))
    for r in rows:
        out.append(row_xml(r))
    out.append("</w:tbl>")
    return "".join(out)


def write(spec_path, out_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    blocks = spec.get("blocks") or []
    if not blocks:
        raise SystemExit("spec has no blocks")
    body = []
    for b in blocks:
        t = b.get("type", "p")
        if t == "pagebreak":
            body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
            continue
        if t == "table":
            body.append(table(b))
            body.append("<w:p/>")
            continue
        style = {"title": "Title", "h1": "Heading1", "h2": "Heading2", "h3": "Heading3"}.get(t)
        num = 1 if t == "bullet" else (2 if t == "numbered" else None)
        runs = b.get("runs") or [{"t": b.get("text", "")}]
        body.append(para(style, runs, b.get("align"), num))
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document %s><w:body>%s<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
           '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>') % (W, "".join(body))
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CT)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", doc)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/styles.xml", STYLES)
        z.writestr("word/numbering.xml", NUMBERING)
    print(json.dumps({"ok": True, "file": out_path, "blocks": len(blocks)}, ensure_ascii=False))


def read(path, max_paragraphs):
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise SystemExit("not a docx (not a zip): %s" % path)
    xml = z.read("word/document.xml").decode("utf-8", "replace")
    styles = {}
    if "word/styles.xml" in z.namelist():
        s = z.read("word/styles.xml").decode("utf-8", "replace")
        for m in re.finditer(r'<w:style [^>]*w:styleId="([^"]+)"[^>]*>(.*?)</w:style>', s, re.S):
            nm = re.search(r'<w:name w:val="([^"]*)"', m.group(2))
            styles[m.group(1)] = nm.group(1) if nm else m.group(1)
    paragraphs, tables = [], []
    for m in re.finditer(r"<w:tbl>(.*?)</w:tbl>", xml, re.S):
        rows = []
        for tr in re.finditer(r"<w:tr[ >].*?</w:tr>", m.group(1), re.S):
            cells = []
            for tc in re.finditer(r"<w:tc>(.*?)</w:tc>", tr.group(0), re.S):
                cells.append(unesc("".join(re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", tc.group(1), re.S))))
            rows.append(cells)
        tables.append(rows)
    stripped = re.sub(r"<w:tbl>.*?</w:tbl>", "", xml, flags=re.S)
    for m in re.finditer(r"<w:p[ >].*?</w:p>|<w:p/>", stripped, re.S):
        pm = re.search(r'<w:pStyle w:val="([^"]+)"', m.group(0))
        style = styles.get(pm.group(1), pm.group(1)) if pm else "Normal"
        text = unesc("".join(re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", m.group(0), re.S)))
        if text.strip() or style.lower().startswith("heading"):
            paragraphs.append({"style": style, "text": text})
        if max_paragraphs and len(paragraphs) >= max_paragraphs:
            break
    print(json.dumps({"ok": True, "file": path, "paragraphs": paragraphs, "tables": tables}, ensure_ascii=False))


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    if argv[1] == "read":
        n = 0
        if len(argv) > 3 and argv[3] == "--max-paragraphs":
            n = int(argv[4])
        read(argv[2], n)
    elif argv[1] == "write":
        write(argv[2], argv[3])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)