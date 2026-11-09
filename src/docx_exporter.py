"""Pure-Python OpenXML (.docx) exporter for clinical and dissertation Markdown reports.

Converts Markdown files (headings, bold/italic/code runs, clickable hyperlinks,
Markdown tables, blockquotes, lists, and ASCII clinical algorithms) into
publication-grade Microsoft Word (.docx) documents without external C/binary
dependencies.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _xml_escape(text: str) -> str:
    """Escape XML special characters and strip control characters invalid in XML 1.0."""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text or "")
    return escape(cleaned, {'"': "&quot;", "'": "&apos;"})


class _RelRegistry:
    """Tracks external hyperlink relationships for word/_rels/document.xml.rels."""

    def __init__(self) -> None:
        self._urls: Dict[str, str] = {}
        self._counter = 10  # rId1..rId9 reserved for styles/settings

    def register_url(self, url: str) -> str:
        url = url.strip()
        if url not in self._urls:
            self._counter += 1
            self._urls[url] = f"rId{self._counter}"
        return self._urls[url]

    def to_rels_xml(self) -> str:
        lines = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
            '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
        ]
        for url, rid in self._urls.items():
            lines.append(
                f'  <Relationship Id="{rid}" '
                f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
                f'Target="{_xml_escape(url)}" TargetMode="External"/>'
            )
        lines.append("</Relationships>")
        return "\n".join(lines)


def _build_content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""


def _build_root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""


def _build_styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
        <w:sz w:val="23"/>
        <w:szCs w:val="23"/>
        <w:color w:val="1E293B"/>
        <w:lang w:val="ru-RU" w:eastAsia="ru-RU" w:bidi="ar-SA"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:after="120" w:line="276" w:lineRule="auto"/>
        <w:jc w:val="both"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:keepNext/>
      <w:spacing w:before="280" w:after="160" w:line="260" w:lineRule="auto"/>
      <w:pBdr>
        <w:bottom w:val="single" w:sz="12" w:space="4" w:color="1E3A8A"/>
      </w:pBdr>
      <w:jc w:val="left"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:bCs/>
      <w:color w:val="0F172A"/>
      <w:sz w:val="32"/>
      <w:szCs w:val="32"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:keepNext/>
      <w:spacing w:before="240" w:after="120" w:line="260" w:lineRule="auto"/>
      <w:jc w:val="left"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:bCs/>
      <w:color w:val="1E3A8A"/>
      <w:sz w:val="28"/>
      <w:szCs w:val="28"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:keepNext/>
      <w:spacing w:before="180" w:after="80" w:line="260" w:lineRule="auto"/>
      <w:jc w:val="left"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:bCs/>
      <w:color w:val="1E40AF"/>
      <w:sz w:val="25"/>
      <w:szCs w:val="25"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading4">
    <w:name w:val="heading 4"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr>
      <w:keepNext/>
      <w:spacing w:before="140" w:after="60"/>
      <w:jc w:val="left"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:i/>
      <w:color w:val="334155"/>
      <w:sz w:val="23"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="CalloutQuote">
    <w:name w:val="Quote"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:pBdr>
        <w:left w:val="single" w:sz="18" w:space="10" w:color="2563EB"/>
      </w:pBdr>
      <w:shd w:val="clear" w:color="auto" w:fill="EFF6FF"/>
      <w:spacing w:before="100" w:after="120"/>
      <w:ind w:left="360" w:right="240"/>
      <w:jc w:val="left"/>
    </w:pPr>
  </w:style>
</w:styles>"""


_INLINE_TOKEN_RE = re.compile(
    r"(\[([^\]]+)\]\((https?://[^\s\)]+)\))"  # [label](url)
    r"|(\*\*\*(.+?)\*\*\*)"                   # ***bold italic***
    r"|(\*\*(.+?)\*\*)"                       # **bold**
    r"|(\*([^\*\n]+?)\*)"                     # *italic*
    r"|(`([^`\n]+?)`)"                        # `code`
)


def _render_run(
    text: str,
    bold: bool = False,
    italic: bool = False,
    code: bool = False,
    color: Optional[str] = None,
    size_half_pt: Optional[int] = None,
    underline: bool = False,
) -> str:
    if not text:
        return ""
    rpr_parts: List[str] = []
    if code:
        rpr_parts.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/>')
        rpr_parts.append('<w:b/>')
        rpr_parts.append('<w:color w:val="0F172A"/>')
        rpr_parts.append('<w:shd w:val="clear" w:color="auto" w:fill="F1F5F9"/>')
    else:
        if bold:
            rpr_parts.append("<w:b/><w:bCs/>")
        if italic:
            rpr_parts.append("<w:i/><w:iCs/>")
        if color:
            rpr_parts.append(f'<w:color w:val="{color}"/>')
        if underline:
            rpr_parts.append('<w:u w:val="single"/>')
    if size_half_pt:
        rpr_parts.append(f'<w:sz w:val="{size_half_pt}"/><w:szCs w:val="{size_half_pt}"/>')

    rpr_xml = f"<w:rPr>{''.join(rpr_parts)}</w:rPr>" if rpr_parts else ""
    return f'<w:r>{rpr_xml}<w:t xml:space="preserve">{_xml_escape(text)}</w:t></w:r>'


def _render_inline_runs(
    text: str,
    rels: _RelRegistry,
    force_bold: bool = False,
    force_color: Optional[str] = None,
    size_half_pt: Optional[int] = None,
) -> str:
    """Convert Markdown inline markup into OpenXML <w:r> and <w:hyperlink> elements."""
    out: List[str] = []
    pos = 0
    for m in _INLINE_TOKEN_RE.finditer(text):
        if m.start() > pos:
            plain = text[pos : m.start()]
            out.append(
                _render_run(
                    plain,
                    bold=force_bold,
                    color=force_color,
                    size_half_pt=size_half_pt,
                )
            )
        if m.group(1):  # [label](url)
            label, url = m.group(2), m.group(3)
            rid = rels.register_url(url)
            run_xml = _render_run(
                label,
                bold=force_bold,
                color=force_color or "1D4ED8",
                size_half_pt=size_half_pt,
                underline=True,
            )
            out.append(f'<w:hyperlink r:id="{rid}" w:history="1">{run_xml}</w:hyperlink>')
        elif m.group(4):  # ***bold italic***
            out.append(
                _render_run(
                    m.group(5),
                    bold=True,
                    italic=True,
                    color=force_color,
                    size_half_pt=size_half_pt,
                )
            )
        elif m.group(6):  # **bold**
            out.append(
                _render_run(
                    m.group(7),
                    bold=True,
                    color=force_color,
                    size_half_pt=size_half_pt,
                )
            )
        elif m.group(8):  # *italic*
            out.append(
                _render_run(
                    m.group(9),
                    bold=force_bold,
                    italic=True,
                    color=force_color,
                    size_half_pt=size_half_pt,
                )
            )
        elif m.group(10):  # `code`
            out.append(
                _render_run(
                    m.group(11),
                    bold=True,
                    code= not force_bold,
                    color=force_color,
                    size_half_pt=size_half_pt,
                )
            )
        pos = m.end()

    if pos < len(text):
        out.append(
            _render_run(
                text[pos:],
                bold=force_bold,
                color=force_color,
                size_half_pt=size_half_pt,
            )
        )
    return "".join(out)


def _split_table_row(line: str) -> List[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [c.strip() for c in stripped.split("|")]


def _is_table_separator(line: str) -> bool:
    cells = _split_table_row(line)
    if not cells:
        return False
    return all(bool(re.match(r"^:?-{2,}:?$", c)) for c in cells)


def _render_table_xml(table_lines: List[str], rels: _RelRegistry) -> str:
    rows_raw = [_split_table_row(ln) for ln in table_lines if not _is_table_separator(ln)]
    if not rows_raw:
        return ""
    num_cols = max(len(r) for r in rows_raw)
    col_pct = max(100, int(5000 / max(num_cols, 1)))

    xml_parts = [
        "<w:tbl>",
        "  <w:tblPr>",
        '    <w:tblW w:w="5000" w:type="pct"/>',
        "    <w:tblBorders>",
        '      <w:top w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>',
        '      <w:left w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>',
        '      <w:bottom w:val="single" w:sz="8" w:space="0" w:color="94A3B8"/>',
        '      <w:right w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>',
        '      <w:insideH w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>',
        '      <w:insideV w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>',
        "    </w:tblBorders>",
        "    <w:tblCellMar>",
        '      <w:top w:w="90" w:type="dxa"/>',
        '      <w:left w:w="130" w:type="dxa"/>',
        '      <w:bottom w:w="90" w:type="dxa"/>',
        '      <w:right w:w="130" w:type="dxa"/>',
        "    </w:tblCellMar>",
        "  </w:tblPr>",
    ]

    for r_idx, row in enumerate(rows_raw):
        is_header = r_idx == 0
        fill = "1E3A8A" if is_header else ("F8FAFC" if r_idx % 2 == 0 else "FFFFFF")
        tr_pr = "<w:trPr><w:tblHeader/></w:trPr>" if is_header else ""
        xml_parts.append(f"  <w:tr>{tr_pr}")

        padded_row = row + [""] * (num_cols - len(row))
        for cell_text in padded_row:
            runs = _render_inline_runs(
                cell_text,
                rels=rels,
                force_bold=is_header,
                force_color="FFFFFF" if is_header else None,
                size_half_pt=20,
            )
            xml_parts.append(
                "    <w:tc>"
                f'<w:tcPr><w:tcW w:w="{col_pct}" w:type="pct"/>'
                f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>'
                '<w:vAlign w:val="center"/></w:tcPr>'
                f'<w:p><w:pPr><w:spacing w:before="40" w:after="40" w:line="240" w:lineRule="auto"/>'
                f'<w:jc w:val="left"/></w:pPr>{runs}</w:p>'
                "</w:tc>"
            )
        xml_parts.append("  </w:tr>")

    xml_parts.append("</w:tbl>")
    xml_parts.append('<w:p><w:pPr><w:spacing w:before="60" w:after="60"/></w:pPr></w:p>')
    return "\n".join(xml_parts)


def _render_code_block_xml(code_lines: List[str]) -> str:
    runs: List[str] = []
    for idx, ln in enumerate(code_lines):
        if idx > 0:
            runs.append("<w:r><w:br/></w:r>")
        runs.append(
            '<w:r><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/>'
            '<w:sz w:val="19"/><w:szCs w:val="19"/><w:color w:val="0F172A"/></w:rPr>'
            f'<w:t xml:space="preserve">{_xml_escape(ln)}</w:t></w:r>'
        )
    return (
        "<w:p><w:pPr>"
        "<w:pBdr>"
        '<w:top w:val="single" w:sz="6" w:space="6" w:color="CBD5E1"/>'
        '<w:left w:val="single" w:sz="12" w:space="8" w:color="1E3A8A"/>'
        '<w:bottom w:val="single" w:sz="6" w:space="6" w:color="CBD5E1"/>'
        '<w:right w:val="single" w:sz="6" w:space="6" w:color="CBD5E1"/>'
        "</w:pBdr>"
        '<w:shd w:val="clear" w:color="auto" w:fill="F8FAFC"/>'
        '<w:spacing w:before="120" w:after="120" w:line="240" w:lineRule="auto"/>'
        '<w:jc w:val="left"/>'
        f"</w:pPr>{''.join(runs)}</w:p>"
    )


def _markdown_to_body_xml(md_text: str, rels: _RelRegistry) -> List[str]:
    lines = md_text.replace("\r\n", "\n").split("\n")
    body_elements: List[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Blank line
        if not stripped:
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^-{3,}$|^\*{3,}$", stripped):
            body_elements.append(
                "<w:p><w:pPr><w:pBdr>"
                '<w:bottom w:val="single" w:sz="6" w:space="1" w:color="CBD5E1"/>'
                '</w:pBdr><w:spacing w:before="80" w:after="120"/></w:pPr></w:p>'
            )
            i += 1
            continue

        # Fenced code block
        if stripped.startswith("```"):
            code_lines: List[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < n:
                i += 1
            body_elements.append(_render_code_block_xml(code_lines))
            continue

        # Markdown table
        if stripped.startswith("|") and i + 1 < n and _is_table_separator(lines[i + 1]):
            table_lines: List[str] = []
            while i < n and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            body_elements.append(_render_table_xml(table_lines, rels))
            continue

        # Headings (# .. ####)
        m_head = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if m_head:
            level = min(len(m_head.group(1)), 4)
            title_txt = m_head.group(2).strip()
            runs = _render_inline_runs(title_txt, rels=rels)
            body_elements.append(
                f'<w:p><w:pPr><w:pStyle w:val="Heading{level}"/></w:pPr>{runs}</w:p>'
            )
            i += 1
            continue

        # Blockquote (> ...)
        if stripped.startswith(">"):
            q_lines: List[str] = []
            while i < n and lines[i].strip().startswith(">"):
                q_lines.append(re.sub(r"^>\s?", "", lines[i].strip()))
                i += 1
            q_runs: List[str] = []
            for q_idx, ql in enumerate(q_lines):
                if q_idx > 0:
                    q_runs.append("<w:r><w:br/></w:r>")
                q_runs.append(_render_inline_runs(ql, rels=rels))
            body_elements.append(
                f'<w:p><w:pPr><w:pStyle w:val="CalloutQuote"/></w:pPr>{"".join(q_runs)}</w:p>'
            )
            continue

        # Bullet or numbered list item
        m_bullet = re.match(r"^(\s*)([\* \-])\s+(.+)$", line)
        m_num = re.match(r"^(\s*)(\d+\.)\s+(.+)$", line)
        if m_bullet or m_num:
            indent_spaces = len((m_bullet or m_num).group(1))
            prefix = "• " if m_bullet else f"{m_num.group(2)} "
            item_txt = (m_bullet or m_num).group(3).strip()
            left_twips = 420 + (indent_spaces // 2) * 240
            prefix_run = _render_run(prefix, bold=True, color="1E3A8A")
            item_runs = _render_inline_runs(item_txt, rels=rels)
            body_elements.append(
                f'<w:p><w:pPr><w:spacing w:before="40" w:after="80" w:line="264" w:lineRule="auto"/>'
                f'<w:ind w:left="{left_twips}" w:hanging="240"/>'
                f'<w:jc w:val="both"/></w:pPr>{prefix_run}{item_runs}</w:p>'
            )
            i += 1
            continue

        # Standard paragraph
        runs = _render_inline_runs(stripped, rels=rels)
        body_elements.append(f"<w:p>{runs}</w:p>")
        i += 1

    return body_elements


def build_docx_bytes_from_markdown_sections(sections: List[str]) -> bytes:
    """Compile one or more Markdown document sections (separated by page breaks) into a valid .docx byte stream."""
    rels = _RelRegistry()
    all_body_parts: List[str] = []

    for idx, md_sec in enumerate(sections):
        if idx > 0:
            all_body_parts.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        all_body_parts.extend(_markdown_to_body_xml(md_sec, rels))

    # A4 page setup (210 x 297 mm) with standard academic margins (left 25 mm, right 15 mm, top/bottom 20 mm)
    sect_pr = (
        "<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="850" w:bottom="1134" w:left="1417" w:header="708" w:footer="708" w:gutter="0"/>'
        "</w:sectPr>"
    )

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
        "  <w:body>\n"
        f"    {''.join(all_body_parts)}\n"
        f"    {sect_pr}\n"
        "  </w:body>\n"
        "</w:document>"
    )

    content_types_xml = _build_content_types_xml()
    root_rels_xml = _build_root_rels_xml()
    doc_rels_xml = rels.to_rels_xml()
    styles_xml = _build_styles_xml()

    # Validate XML well-formedness before packaging
    for xml_name, xml_payload in [
        ("[Content_Types].xml", content_types_xml),
        ("_rels/.rels", root_rels_xml),
        ("word/_rels/document.xml.rels", doc_rels_xml),
        ("word/styles.xml", styles_xml),
        ("word/document.xml", document_xml),
    ]:
        try:
            ET.fromstring(xml_payload.encode("utf-8"))
        except ET.ParseError as exc:
            raise RuntimeError(f"Invalid OpenXML in {xml_name}: {exc}") from exc

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml.encode("utf-8"))
        zf.writestr("_rels/.rels", root_rels_xml.encode("utf-8"))
        zf.writestr("word/_rels/document.xml.rels", doc_rels_xml.encode("utf-8"))
        zf.writestr("word/styles.xml", styles_xml.encode("utf-8"))
        zf.writestr("word/document.xml", document_xml.encode("utf-8"))
    return buf.getvalue()


def build_docx_bytes_from_markdown(md_text: str) -> bytes:
    """Convert a single Markdown string into a valid .docx byte stream."""
    return build_docx_bytes_from_markdown_sections([md_text])


def export_nosology_docx_files(nosology_slug: str, base_dir: Optional[Path] = None) -> Dict[str, Path]:
    """Generate .docx reports for a given nosology in reports/<nosology>/:
      1. dissertation_report.docx (Диссертационная монография)
      2. executive_summary.docx (Краткое клиническое руководство)
      3. full_clinical_dossier.docx (Полное клиническое досье: Краткое руководство + Диссертация + 5 модулей БЗ)
    """
    root = base_dir or Path(__file__).resolve().parent.parent
    rep_dir = root / "reports" / nosology_slug
    if not rep_dir.exists():
        raise FileNotFoundError(f"Reports directory not found: {rep_dir}")

    diss_md_path = rep_dir / "dissertation_report.md"
    exec_md_path = rep_dir / "executive_summary.md"
    kb_dir = rep_dir / "knowledge_base"

    diss_text = diss_md_path.read_text(encoding="utf-8")
    exec_text = exec_md_path.read_text(encoding="utf-8")

    diss_docx_path = rep_dir / "dissertation_report.docx"
    exec_docx_path = rep_dir / "executive_summary.docx"
    full_docx_path = rep_dir / "full_clinical_dossier.docx"

    diss_docx_path.write_bytes(build_docx_bytes_from_markdown(diss_text))
    exec_docx_path.write_bytes(build_docx_bytes_from_markdown(exec_text))

    kb_sections: List[str] = [exec_text, diss_text]
    if kb_dir.exists():
        for md_file in sorted(kb_dir.glob("*.md")):
            kb_sections.append(md_file.read_text(encoding="utf-8"))
    full_docx_path.write_bytes(build_docx_bytes_from_markdown_sections(kb_sections))

    return {
        "dissertation_docx": diss_docx_path,
        "executive_docx": exec_docx_path,
        "full_dossier_docx": full_docx_path,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export Markdown medical reports to .docx")
    parser.add_argument("--nosology", type=str, default="all", help="Nosology slug or 'all'")
    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parent.parent
    configs_dir = root_dir / "configs"
    slugs = (
        [p.stem for p in sorted(configs_dir.glob("*.yaml"))]
        if args.nosology == "all"
        else [args.nosology]
    )

    for slug in slugs:
        paths = export_nosology_docx_files(slug, root_dir)
        print(f"[DOCX Exporter: {slug}] Generated 3 Word documents:")
        for k, p in paths.items():
            print(f"  - {k}: {p.relative_to(root_dir)} ({p.stat().st_size:,} bytes)")
