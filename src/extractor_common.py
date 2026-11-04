"""Shared utilities for Phase 2 Swarm Structured Extraction (Clusters 1-4).

Provides:
- Safe SQLite WAL connection with 30s busy timeout
- JATS XML parser for Europe PMC full-text XMLs (data/dupuytren/raw/fulltext_xml/*.xml)
- Helper regex extractors for sample sizes, statistical metrics (OR/HR/CI/p-value),
  joint contracture angles (MCP/PIP), follow-up duration, and recurrence definitions.
"""

from __future__ import annotations

import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def get_db_connection(db_path: str | Path = "data/dupuytren/literature.db") -> sqlite3.Connection:
    """Open SQLite connection with WAL mode and 30-second busy timeout for safe concurrent access."""
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def format_first_author_year(authors_str: str | None, pub_year: int | None) -> str:
    """Format 'FirstAuthor et al., YYYY' from authors string (JSON list or delimited) and publication year."""
    yr = str(pub_year) if pub_year else "n.d."
    if not authors_str or not authors_str.strip():
        return f"Anonymous, {yr}"
    raw = authors_str.strip()
    parts: list[str] = []
    if raw.startswith("["):
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, list):
                parts = [str(x).strip() for x in loaded if str(x).strip()]
        except Exception:
            pass
    if not parts:
        cleaned = raw.strip("[]\"'")
        parts = [a.strip().strip("\"'") for a in re.split(r"[;,]", cleaned) if a.strip().strip("\"'")]
    if not parts:
        return f"Anonymous, {yr}"
    first = parts[0]
    tokens = first.split()
    surname = tokens[0] if tokens else first
    # If formatted like 'Jeremiah D. Johnson' (full given name first), take last token if first is not surname+initials
    if len(tokens) >= 2 and len(tokens[-1]) > 2 and not re.match(r"^[A-Z]{1,3}$", tokens[-1]):
        surname = tokens[-1]
    if len(parts) > 1:
        return f"{surname} et al., {yr}"
    return f"{surname}, {yr}"


def _iter_text(elem: ET.Element | None) -> str:
    if elem is None:
        return ""
    return " ".join("".join(elem.itertext()).split())


def parse_jats_xml(xml_path: str | Path | None) -> dict[str, Any]:
    """Parse Europe PMC JATS XML file into structured sections and tables."""
    result: dict[str, Any] = {
        "has_xml": False,
        "abstract_text": "",
        "methods_text": "",
        "results_text": "",
        "discussion_text": "",
        "tables": [],
        "full_text_snippet": "",
    }
    if not xml_path:
        return result
    path = Path(xml_path)
    if not path.exists() or path.stat().st_size < 200:
        return result

    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception:
        return result

    result["has_xml"] = True

    # Abstract
    abs_elems = root.findall(".//abstract")
    result["abstract_text"] = " ".join(_iter_text(a) for a in abs_elems if _iter_text(a))

    # Sections
    methods_parts: list[str] = []
    results_parts: list[str] = []
    discussion_parts: list[str] = []

    for sec in root.findall(".//body//sec"):
        title_elem = sec.find("title")
        sec_title = _iter_text(title_elem).lower()
        sec_text = _iter_text(sec)
        if not sec_text:
            continue
        if any(k in sec_title for k in ("method", "material", "patient", "study design", "cohort", "population")):
            methods_parts.append(sec_text[:4000])
        elif any(k in sec_title for k in ("result", "finding", "outcome", "complication", "recurrence", "efficacy")):
            results_parts.append(sec_text[:5000])
        elif any(k in sec_title for k in ("discussion", "conclusion")):
            discussion_parts.append(sec_text[:3000])

    result["methods_text"] = " ".join(methods_parts)[:8000]
    result["results_text"] = " ".join(results_parts)[:10000]
    result["discussion_text"] = " ".join(discussion_parts)[:5000]

    # Tables
    tables_out: list[str] = []
    for tw in root.findall(".//table-wrap"):
        label = _iter_text(tw.find("label"))
        caption = _iter_text(tw.find("caption"))
        rows_str: list[str] = []
        for tr in tw.findall(".//tr")[:25]:
            cells = [_iter_text(c) for c in list(tr) if c.tag in ("th", "td")]
            if cells:
                rows_str.append(" | ".join(cells))
        t_summary = f"{label}: {caption}\n" + "\n".join(rows_str[:15])
        if t_summary.strip():
            tables_out.append(t_summary[:2500])

    result["tables"] = tables_out
    body_elem = root.find(".//body")
    result["full_text_snippet"] = _iter_text(body_elem)[:12000] if body_elem is not None else ""
    return result


def extract_sample_size(text: str) -> tuple[int | None, int | None, str]:
    """Extract (n_patients, n_rays_or_joints, sample_description) from abstract/results text."""
    if not text:
        return None, None, "Not specified"

    n_patients: int | None = None
    n_joints: int | None = None
    matches_desc: list[str] = []

    # Patterns for patients / cases / controls / samples
    pat_regexes = [
        r"\b(\d[\d,]{0,6})\s+(?:patients|subjects|participants|individuals|cases|men and women|adults)\b",
        r"\b(?:n|N)\s*=\s*(\d[\d,]{0,6})\s*(?:patients|cases|subjects|samples)?\b",
        r"\bcohort of\s+(\d[\d,]{0,6})\b",
        r"\b(\d[\d,]{0,6})\s+Dupuytren(?:'s)?\s+(?:patients|cases|samples|nodules|tissues)\b",
    ]
    for rgx in pat_regexes:
        for m in re.finditer(rgx, text, flags=re.IGNORECASE):
            val_str = m.group(1).replace(",", "")
            if val_str.isdigit():
                val = int(val_str)
                if 1 <= val <= 1000000 and (val < 1990 or val > 2030):
                    if n_patients is None or val > n_patients:
                        n_patients = val
                    matches_desc.append(m.group(0).strip())

    # Patterns for hands / fingers / rays / digits / joints / cords
    joint_regexes = [
        r"\b(\d[\d,]{0,5})\s+(?:joints|fingers|digits|rays|hands|cords|contractures|treated joints)\b",
    ]
    for rgx in joint_regexes:
        for m in re.finditer(rgx, text, flags=re.IGNORECASE):
            val_str = m.group(1).replace(",", "")
            if val_str.isdigit():
                val = int(val_str)
                if 1 <= val <= 50000 and (val < 1990 or val > 2030):
                    if n_joints is None or val > n_joints:
                        n_joints = val
                    matches_desc.append(m.group(0).strip())

    dedup_desc: list[str] = []
    for d in matches_desc:
        if d not in dedup_desc:
            dedup_desc.append(d)
    summary_str = "; ".join(dedup_desc[:4]) if dedup_desc else (f"N={n_patients}" if n_patients else "See text")
    return n_patients, n_joints, summary_str


def extract_statistical_metrics(text: str) -> str:
    """Extract quantitative sentences containing OR, HR, RR, CI, p-values, fold-change, percentages, or rsIDs."""
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    quant_sentences: list[str] = []
    metric_re = re.compile(
        r"(\b(?:OR|HR|RR|IRR|PR|aOR|aHR)\s*[=:<>]\s*\d+|\b95%\s*CI\b|\bp\s*[<=>]\s*0\.\d+|\bp\s*[<=>]\s*10|\brs\d{4,}|\b\d+(?:\.\d+)?%\b|\b\d+(?:\.\d+)?-fold\b|\b\d+(?:\.\d+)?°)",
        flags=re.IGNORECASE,
    )
    for s in sentences:
        s_clean = s.strip()
        if 25 <= len(s_clean) <= 450 and metric_re.search(s_clean):
            quant_sentences.append(s_clean)
        if len(quant_sentences) >= 5:
            break
    return " | ".join(quant_sentences)


def extract_followup_months(text: str) -> float | None:
    """Extract follow-up duration in months from text."""
    if not text:
        return None
    # Match years first
    yr_matches = re.findall(
        r"\b(\d+(?:\.\d+)?)\s*(?:-|\s+to\s+)?(?:year|yr)s?\s+(?:follow-up|followup|after|outcomes?|postoperatively)",
        text,
        flags=re.IGNORECASE,
    )
    if not yr_matches:
        yr_matches = re.findall(
            r"(?:follow-up|followed(?:\s+up)?)\s+(?:of|for|was|mean|median)?\s*(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:year|yr)s?",
            text,
            flags=re.IGNORECASE,
        )
    if yr_matches:
        try:
            vals = [float(x) for x in yr_matches if 0.2 <= float(x) <= 30.0]
            if vals:
                return round(max(vals) * 12.0, 1)
        except Exception:
            pass

    mo_matches = re.findall(
        r"\b(\d+(?:\.\d+)?)\s*(?:-|\s+to\s+)?(?:month|mo)s?\s+(?:follow-up|followup|after|postoperatively)",
        text,
        flags=re.IGNORECASE,
    )
    if not mo_matches:
        mo_matches = re.findall(
            r"(?:follow-up|followed(?:\s+up)?)\s+(?:of|for|was|mean|median)?\s*(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:month|mo)s?",
            text,
            flags=re.IGNORECASE,
        )
    if mo_matches:
        try:
            vals = [float(x) for x in mo_matches if 0.5 <= float(x) <= 240.0]
            if vals:
                return round(max(vals), 1)
        except Exception:
            pass

    wk_matches = re.findall(
        r"\b(\d+(?:\.\d+)?)\s*(?:-|\s+to\s+)?weeks?\s+(?:follow-up|followup|after)",
        text,
        flags=re.IGNORECASE,
    )
    if wk_matches:
        try:
            vals = [float(x) for x in wk_matches if 1.0 <= float(x) <= 104.0]
            if vals:
                return round(max(vals) / 4.33, 1)
        except Exception:
            pass
    return None


def detect_recurrence_definition(text: str) -> str:
    """Detect recurrence definition per D-02."""
    if not text:
        return "Not reported"
    tl = text.lower()
    if "20°" in tl or "20 degrees" in tl or "20-degree" in tl or "kan " in tl or "consensus" in tl:
        return "≥20° contracture increase (Kan consensus)"
    if "30°" in tl or "30 degrees" in tl or "30-degree" in tl:
        return "≥30° contracture increase"
    if "reoperation" in tl or "re-intervention" in tl or "repeat surgery" in tl or "retreatment" in tl:
        return "Re-intervention / repeat procedure in treated ray"
    if "0 to 5" in tl or "0-5°" in tl or "≤5°" in tl or "clinical success" in tl:
        return "Loss of clinical success (>5°–20° residual/recurrent deficit)"
    if "recurrence" in tl or "recurrent" in tl:
        return "Clinical recurrence (threshold not standardized in abstract)"
    return "Not applicable / primary endpoint non-recurrence"


def extract_joint_outcomes(text: str) -> dict[str, str]:
    """Extract separate MCP and PIP outcomes and recurrence rates from text (D-02)."""
    res = {
        "mcp_outcome": "Not stratified in abstract",
        "pip_outcome": "Not stratified in abstract",
        "recurrence_rate_overall": "Not reported",
        "recurrence_rate_mcp": "Not stratified",
        "recurrence_rate_pip": "Not stratified",
    }
    if not text:
        return res

    sentences = re.split(r"(?<=[.!?])\s+", text)
    mcp_sents: list[str] = []
    pip_sents: list[str] = []
    rec_sents: list[str] = []

    for s in sentences:
        sl = s.lower()
        s_clean = s.strip()
        if any(k in sl for k in ("mcp", "metacarpophalangeal", "mp joint")):
            mcp_sents.append(s_clean)
        if any(k in sl for k in ("pip", "proximal interphalangeal")):
            pip_sents.append(s_clean)
        if any(k in sl for k in ("recurrence", "recurred", "recurrent", "relapse", "reoperation")):
            rec_sents.append(s_clean)

    if mcp_sents:
        res["mcp_outcome"] = " | ".join(mcp_sents[:2])[:400]
        for ms in mcp_sents:
            if "recur" in ms.lower():
                res["recurrence_rate_mcp"] = ms[:300]
                break

    if pip_sents:
        res["pip_outcome"] = " | ".join(pip_sents[:2])[:400]
        for ps in pip_sents:
            if "recur" in ps.lower():
                res["recurrence_rate_pip"] = ps[:300]
                break

    if rec_sents:
        res["recurrence_rate_overall"] = " | ".join(rec_sents[:2])[:400]

    return res
