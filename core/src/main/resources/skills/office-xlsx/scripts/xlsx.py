# SPDX-License-Identifier: Apache-2.0
"""Read an .xlsx workbook, or build one from a JSON spec. Standard library only.

Usage:
  xlsx.py read WORKBOOK.xlsx [--sheet NAME] [--max-rows N]
  xlsx.py write SPEC.json OUT.xlsx

read prints JSON: {"sheets":[{"name":..,"rows":[[cell,..],..]}]}
write takes JSON:
  {"sheets":[{"name":"Sheet1",
              "columns":[{"width":18},..],          # optional
              "rows":[[{"v":"Name","b":true},{"v":12.5,"fmt":"0.00"},{"v":"2026-11-20","fmt":"date"}], ..]}]}
  cell may also be a bare string/number/bool instead of an object.
"""
import json
import re
import sys
import zipfile

CT = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>{sheets}</Types>'
RELS = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
STYLES = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="2"><numFmt numFmtId="164" formatCode="0.00"/><numFmt numFmtId="165" formatCode="yyyy-mm-dd"/></numFmts><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'



def unesc(t):
    for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#10;", "\n"), ("&amp;", "&")):
        t = t.replace(a, b)
    return t

def col_name(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("\n", "&#10;"))


def cell_xml(ref, cell):
    if isinstance(cell, dict):
        v = cell.get("v")
        bold = bool(cell.get("b"))
        fmt = cell.get("fmt")
        f = cell.get("f")
    else:
        v, bold, fmt, f = cell, False, None, None
    style = 1 if bold else (2 if fmt == "0.00" else (3 if fmt == "date" else 0))
    if f:
        return '<c r="%s" s="%d"><f>%s</f></c>' % (ref, style, esc(f))
    if v is None or v == "":
        return '<c r="%s" s="%d"/>' % (ref, style)
    if isinstance(v, bool):
        return '<c r="%s" s="%d" t="b"><v>%d</v></c>' % (ref, style, 1 if v else 0)
    if isinstance(v, (int, float)):
        return '<c r="%s" s="%d"><v>%s</v></c>' % (ref, style, repr(v))
    return '<c r="%s" s="%d" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>' % (ref, style, esc(v))


def write(spec_path, out_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    sheets = spec.get("sheets") or []
    if not sheets:
        raise SystemExit("spec has no sheets")
    overrides, sheet_parts, wb_sheets, rels = [], [], [], []
    for i, sh in enumerate(sheets, 1):
        name = sh.get("name") or ("Sheet%d" % i)
        rows = sh.get("rows") or []
        cols = sh.get("columns") or []
        body = []
        for r, row in enumerate(rows, 1):
            cells = "".join(cell_xml(col_name(c) + str(r), v) for c, v in enumerate(row))
            body.append('<row r="%d">%s</row>' % (r, cells))
        colxml = ""
        if cols:
            colxml = "<cols>%s</cols>" % "".join(
                '<col min="%d" max="%d" width="%s" customWidth="1"/>' % (j, j, c.get("width", 10))
                for j, c in enumerate(cols, 1))
        sheet_parts.append(('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                            '%s<sheetData>%s</sheetData></worksheet>') % (colxml, "".join(body)))
        wb_sheets.append('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (esc(name)[:31], i, i))
        rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i, i))
        overrides.append('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % i)
    n = len(sheets)
    wb = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
          '<sheets>%s</sheets></workbook>') % "".join(wb_sheets)
    wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s'
               '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
               '</Relationships>') % ("".join(rels), n + 1)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CT.format(sheets="".join(overrides)))
        z.writestr("_rels/.rels", RELS)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", STYLES)
        for i, part in enumerate(sheet_parts, 1):
            z.writestr("xl/worksheets/sheet%d.xml" % i, part)
    print(json.dumps({"ok": True, "file": out_path, "sheets": n}, ensure_ascii=False))


def read_sheet(xml, shared, max_rows):
    rows = []
    for rm in re.finditer(r"<row[^>]*>(.*?)</row>", xml, re.S):
        cells, last = [], -1
        for cm in re.finditer(r'<c r="([A-Z]+)\d+"([^>]*)>(.*?)</c>|<c r="([A-Z]+)\d+"([^>]*)/>', rm.group(1), re.S):
            ref = cm.group(1) or cm.group(4)
            attrs = (cm.group(2) or cm.group(5) or "")
            inner = cm.group(3) or ""
            idx = 0
            for ch in ref:
                idx = idx * 26 + (ord(ch) - 64)
            idx -= 1
            t = re.search(r't="([^"]+)"', attrs)
            t = t.group(1) if t else "n"
            if t == "inlineStr":
                val = "".join(re.findall(r"<t[^>]*>(.*?)</t>", inner, re.S))
                val = unesc(val)
            elif t == "s":
                m = re.search(r"<v>(\d+)</v>", inner)
                val = shared[int(m.group(1))] if m else ""
            elif t == "str":
                m = re.search(r"<v>(.*?)</v>", inner, re.S)
                val = unesc(m.group(1)) if m else ""
            elif t == "b":
                m = re.search(r"<v>(\d)</v>", inner)
                val = bool(int(m.group(1))) if m else None
            else:
                m = re.search(r"<v>(.*?)</v>", inner, re.S)
                if not m:
                    continue
                raw = m.group(1)
                try:
                    val = float(raw)
                    val = int(val) if val == int(val) and "." not in raw and "E" not in raw.upper() else val
                except ValueError:
                    val = raw
            while len(cells) < idx:
                cells.append(None)
            cells.append(val)
            last = idx
        rows.append(cells[: last + 1])
        if max_rows and len(rows) >= max_rows:
            break
    return rows


def read(path, only, max_rows):
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise SystemExit("not an xlsx (not a zip): %s" % path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        s = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
        for si in re.finditer(r"<si>(.*?)</si>", s, re.S):
            shared.append(unesc("".join(re.findall(r"<t[^>]*>(.*?)</t>", si.group(1), re.S))))
    wb = z.read("xl/workbook.xml").decode("utf-8", "replace")
    sheets = []
    for i, m in enumerate(re.finditer(r'<sheet [^>]*name="([^"]*)"', wb), 1):
        name = m.group(1)
        if only and name != only:
            continue
        part = "xl/worksheets/sheet%d.xml" % i
        if part not in z.namelist():
            continue
        sheets.append({"name": name, "rows": read_sheet(z.read(part).decode("utf-8", "replace"), shared, max_rows)})
    if only and not sheets:
        raise SystemExit("no sheet named %s" % only)
    print(json.dumps({"ok": True, "file": path, "sheets": sheets}, ensure_ascii=False))


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    cmd = argv[1]
    if cmd == "read":
        path = argv[2]
        only = None
        max_rows = 0
        rest = argv[3:]
        i = 0
        while i < len(rest):
            if rest[i] == "--sheet":
                only = rest[i + 1]
                i += 2
            elif rest[i] == "--max-rows":
                max_rows = int(rest[i + 1])
                i += 2
            else:
                raise SystemExit("unknown option " + rest[i])
        read(path, only, max_rows)
    elif cmd == "write":
        write(argv[2], argv[3])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)