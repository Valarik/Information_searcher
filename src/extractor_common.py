"""Shared utilities for Phase 2 Swarm Structured Extraction (Clusters 1-4).

Provides:
- Safe SQLite WAL connection with 30s busy timeout
- JATS XML parser for Europe PMC full-text XMLs (data/dupuytren/raw/fulltext_xml/*.xml)
- Helper regex extractors for sample sizes, statistical metrics (OR/HR/CI/p-value),
  joint contracture angles (MCP/PIP), follow-up duration, and recurrence definitions.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


NOSOLOGY_ID_RE = re.compile(r"^[a-z0-9_]+$")


def validate_nosology_id(raw_id: Any) -> str:
    """Validate and normalize a nosology identifier against path traversal (CR-01, T-17-03/T-17-05)."""
    nos_id = str(raw_id or "").strip().lower()
    if not NOSOLOGY_ID_RE.fullmatch(nos_id):
        raise ValueError(
            f"Invalid nosology_id {raw_id!r}: must match ^[a-z0-9_]+$ (lowercase ASCII letters, digits, underscores)"
        )
    return nos_id


def resolve_treatment_profile_and_focus(cfg: dict[str, Any] | None) -> tuple[str, bool]:
    """Resolve mutually consistent (treatment_profile, surgical_focus) with top-level override precedence (D-01, WR-08).

    Top-level keys take precedence over nested `nosology.*` keys:
    - Explicit `treatment_profile == 'conservative'` -> ('conservative', False)
    - Explicit `surgical_focus` (`cfg['surgical_focus']` if key present, else `meta['surgical_focus']`):
      - `False` -> ('conservative', False)
      - `True`  -> (explicit non-conservative profile or 'surgical', True)
    - Default when omitted -> ('surgical', True)
    """
    cfg_dict = cfg if isinstance(cfg, dict) else {}
    meta = cfg_dict.get("nosology")
    meta_dict = meta if isinstance(meta, dict) else {}

    if "treatment_profile" in cfg_dict and cfg_dict["treatment_profile"] not in (None, ""):
        raw_profile = cfg_dict["treatment_profile"]
    elif "treatment_profile" in meta_dict and meta_dict["treatment_profile"] not in (None, ""):
        raw_profile = meta_dict["treatment_profile"]
    else:
        raw_profile = None
    explicit_profile = str(raw_profile).strip().lower() if raw_profile is not None else ""

    if "surgical_focus" in cfg_dict and cfg_dict["surgical_focus"] is not None:
        explicit_focus: bool | None = bool(cfg_dict["surgical_focus"])
    elif "surgical_focus" in meta_dict and meta_dict["surgical_focus"] is not None:
        explicit_focus = bool(meta_dict["surgical_focus"])
    else:
        explicit_focus = None

    if explicit_profile == "conservative" or explicit_focus is False:
        return "conservative", False

    profile = explicit_profile if explicit_profile in ("surgical", "mixed") else "surgical"
    return profile, True


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
        if any(
            k in sec_title
            for k in (
                "result",
                "finding",
                "outcome",
                "complication",
                "recurrence",
                "efficacy",
                "adverse",
                "safety",
                "morbidity",
                "side effect",
                "sequela",
                "harms",
            )
        ):
            results_parts.append(sec_text[:5000])
        elif any(k in sec_title for k in ("method", "material", "patient", "study design", "cohort", "population")):
            methods_parts.append(sec_text[:4000])
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


# ---------------------------------------------------------------------------
# Phase 17 (COMP-03, D-04, D-07, D-08): Complications Extraction & Validation
# ---------------------------------------------------------------------------

VALID_CLAVIEN_DINDO: tuple[str, ...] = ("I", "II", "IIIa", "IIIb", "IV", "V")

VALID_REVERSIBILITY: tuple[str, ...] = (
    "transient_self_limiting",
    "requires_conservative_therapy",
    "requires_reoperation",
    "permanent_deficit",
)

VALID_EVENT_CLASS: tuple[str, ...] = (
    "true_complication",
    "transient_postop_sequela",
)

CTCAE_TO_CLAVIEN_MAP: dict[str, str] = {
    "1": "I",
    "2": "II",
    "3": "IIIa",
    "4": "IV",
    "5": "V",
}

RECURRENCE_EXCLUSION_PATTERNS: tuple[str, ...] = (
    r"\btrue\s+recurrence\b",
    r"\bdisease\s+recurrence\b",
    r"\brelapse\b",
    r"\bincomplete\s+(?:release|(?:division|transection)(?!\s+of\s+(?:the\s+)?(?:[\w-]+\s+){0,3}(?:nerve|artery|vessel|tendon|organ|bowel|bladder|ureter)))\b",
    r"\bpersistent\s+triggering\b",
    r"истинн\w*\s+рецидив",
    r"рецидив\s+заболеван",
    r"неполн\w*\s+(?:релиз|рассечен(?!\w*\s+(?:[\w-]+\s+){0,3}(?:нерв|артери|сосуд|сухожил|орган|киш|мочев)))",
)

DEFAULT_SEQUELA_TIME_WINDOW = "Фаза послеоперационного ремоделирования (срок требует уточнения)"


def _parse_bool_flag(value: Any) -> bool:
    """Safely parse boolean flags without treating string '0'/'false' as truthy (WR-05)."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    low = str(value).strip().lower()
    if low in ("", "0", "false", "no", "off", "none", "null"):
        return False
    if low in ("1", "true", "yes", "on"):
        return True
    raise ValueError(f"Invalid boolean flag value: {value!r}")


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Return True if a SQLite table exists (parameterized sqlite_master lookup, T-17-01/T-17-02)."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def is_excluded_recurrence_event(complication_name: str) -> bool:
    """Return True if event is disease recurrence or technical incomplete release (D-08)."""
    text = (complication_name or "").strip()
    if not text:
        return False
    return any(re.search(pat, text, flags=re.IGNORECASE) for pat in RECURRENCE_EXCLUSION_PATTERNS)


def normalize_clavien_dindo(
    grade: str | int | None = None,
    ctcae_grade: str | int | None = None,
    requires_reoperation: bool = False,
) -> tuple[str, str | None]:
    """Normalize Clavien-Dindo (I..V) and/or CTCAE Grade 1-5 to canonical (clavien_dindo_grade, ctcae_grade) (D-07, CR-04, WR-05)."""
    normalized_ctcae: str | None = None
    ctcae_mapped: str | None = None

    if ctcae_grade is not None and str(ctcae_grade).strip():
        ctcae_raw = str(ctcae_grade).strip()
        m_ctcae = re.fullmatch(
            r"(?:(?:nci[\s\-–—]*)?ctcae(?:\s+v?\d+(?:\.\d+)?)?\s*(?:(?:grade|gr\.?|g)\s*[:\-–—]?|[:\-–—])\s*|"
            r"(?:grade|gr\.?|g)\s*[:\-–—]?\s*)?([1-5])(?!\.\d)",
            ctcae_raw,
            flags=re.IGNORECASE,
        )
        if not m_ctcae:
            raise ValueError(f"Invalid CTCAE grade: {ctcae_grade!r}")
        digit = m_ctcae.group(1)
        normalized_ctcae = f"Grade {digit}"
        ctcae_mapped = CTCAE_TO_CLAVIEN_MAP[digit]

    grade_str = str(grade).strip() if grade is not None else ""
    if grade_str:
        if "ctcae" in grade_str.lower():
            m_inline_ctcae = re.fullmatch(
                r"(?:nci[\s\-–—]*)?ctcae(?:\s+v?\d+(?:\.\d+)?)?\s*"
                r"(?:(?:grade|gr\.?|g)\s*[:\-–—]?|[:\-–—])\s*([1-5])(?!\.\d)",
                grade_str,
                flags=re.IGNORECASE,
            )
            if not m_inline_ctcae:
                raise ValueError(f"Invalid CTCAE grade in Clavien-Dindo field: {grade!r}")
            digit = m_inline_ctcae.group(1)
            if normalized_ctcae is None:
                normalized_ctcae = f"Grade {digit}"
            return CTCAE_TO_CLAVIEN_MAP[digit], normalized_ctcae

        cleaned = re.sub(
            r"^(?:clavien[\s\-–—]+dindo|clavien|cd)\s*(?:classification\s*)?[:\-–—]?\s*",
            "",
            grade_str,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"^(?:grade|class|type)\s*[:\-–—]?\s*", "", cleaned, flags=re.IGNORECASE).strip()
        compact = re.sub(r"[\s\-–—]+", "", cleaned).upper()

        mapping = {
            "I": "I",
            "II": "II",
            "III": "IIIb" if requires_reoperation else "IIIa",
            "IIIA": "IIIa",
            "IIIB": "IIIb",
            "IV": "IV",
            "IVA": "IV",
            "IVB": "IV",
            "V": "V",
        }
        if compact not in mapping:
            raise ValueError(f"Invalid Clavien-Dindo grade: {grade!r}")
        resolved = mapping[compact]
        if resolved not in VALID_CLAVIEN_DINDO:
            raise ValueError(f"Invalid Clavien-Dindo grade: {grade!r}")
        return resolved, normalized_ctcae

    if ctcae_mapped is not None:
        return ctcae_mapped, normalized_ctcae

    raise ValueError("Either Clavien-Dindo grade or CTCAE grade (1-5) must be provided")


def extract_complication_frequency(text: str) -> tuple[str | None, float | None, int | None]:
    """Parse '14/76 (18.4%)', '18.4% (14/76)', '15-32%', or '3.2%' while ignoring '95% CI' (WR-02)."""
    if not text:
        return None, None, None

    # (a) n/N (X.Y%)
    for m in re.finditer(
        r"\b(\d{1,5})\s*/\s*(\d{1,6})\s*\(\s*(\d{1,2}(?:[.,]\d+)?|100(?:[.,]0+)?)\s*%\s*\)",
        text,
    ):
        num, denom = int(m.group(1)), int(m.group(2))
        pct = float(m.group(3).replace(",", "."))
        if denom > 0 and num <= denom and 0.0 <= pct <= 100.0:
            return f"{pct:g}% ({num}/{denom})", pct, denom

    # (b) X.Y% (n/N)
    for m in re.finditer(
        r"\b(\d{1,2}(?:[.,]\d+)?|100(?:[.,]0+)?)\s*%\s*\(\s*(\d{1,5})\s*/\s*(\d{1,6})\s*\)",
        text,
    ):
        pct = float(m.group(1).replace(",", "."))
        num, denom = int(m.group(2)), int(m.group(3))
        if denom > 0 and num <= denom and 0.0 <= pct <= 100.0:
            return f"{pct:g}% ({num}/{denom})", pct, denom

    # Strip explicit CI clauses (parenthesized, bracketed, and AMA/JAMA comma-delimited) before scanning percentages
    cleaned = re.sub(
        r"[\(\[]\s*(?:90|95|99)\s*%\s*(?:CI|ДИ|confidence\s+interval)[^\)\]]*[\)\]]",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:90|95|99)\s*%\s*(?:CI|ДИ|confidence\s+interval)\s*[,;:=]?\s*"
        r"\d+(?:[.,]\d+)?\s*%?\s*(?:–|-|—|to|,)\s*\d+(?:[.,]\d+)?\s*%?",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )

    # (c) Range X–Y% / X-Y% / X to Y%
    for m in re.finditer(
        r"\b(\d{1,2}(?:[.,]\d+)?|100(?:[.,]0+)?)\s*%?\s*(?:–|-|—|to)\s*"
        r"(\d{1,2}(?:[.,]\d+)?|100(?:[.,]0+)?)\s*%(?!\s*(?:CI|ДИ|confidence))",
        cleaned,
        flags=re.IGNORECASE,
    ):
        lo = float(m.group(1).replace(",", "."))
        hi = float(m.group(2).replace(",", "."))
        if 0.0 <= lo <= hi <= 100.0:
            mid = round((lo + hi) / 2.0, 2)
            return f"{lo:g}–{hi:g}%", mid, None

    # (d) Single X.Y% (ignoring 95% CI)
    for m in re.finditer(
        r"\b(\d{1,2}(?:[.,]\d+)?|100(?:[.,]0+)?)\s*%(?!\s*(?:CI|ДИ|confidence))",
        cleaned,
        flags=re.IGNORECASE,
    ):
        pct = float(m.group(1).replace(",", "."))
        if 0.0 <= pct <= 100.0:
            return f"{pct:g}%", pct, None

    return None, None, None


def extract_clavien_dindo_grade(text: str) -> tuple[str | None, str | None]:
    """Extract (clavien_dindo_grade, ctcae_grade) mentions from text and normalize via normalize_clavien_dindo (CR-04)."""
    if not text:
        return None, None

    cd_raw: str | None = None
    ctcae_raw: str | None = None

    m_cd = re.search(
        r"\bclavien[\s\-–—]+dindo\s*(?:classification\s*)?(?:grade|class|type)?\s*[:\-–—]?\s*"
        r"(III[ab]|IV[ab]|III|II|IV|I|V)\b",
        text,
        flags=re.IGNORECASE,
    )
    if not m_cd:
        m_cd = re.search(
            r"\b(?:grade|class)\s+(III[ab]|IV[ab]|III|II|IV|I|V)\b[^.]{0,40}\bclavien[\s\-–—]+dindo\b",
            text,
            flags=re.IGNORECASE,
        )
    if m_cd:
        cd_raw = m_cd.group(1)

    # Require explicit grade marker (grade/gr/g) and reject CTCAE version numbers such as 'CTCAE 4.0' / 'CTCAE 5.0' (CR-04)
    m_ctcae = re.search(
        r"\b(?:nci[\s\-–—]*)?ctcae(?:\s+v?\d+(?:\.\d+)?)?\s*"
        r"(?:grade|gr\.?|g)\s*[:\-–—]?\s*([1-5])(?!\.\d)\b",
        text,
        flags=re.IGNORECASE,
    )
    if not m_ctcae:
        m_ctcae = re.search(
            r"\bgrade\s+([1-5])(?!\.\d)\b[^.]{0,30}\bctcae\b",
            text,
            flags=re.IGNORECASE,
        )
    if m_ctcae:
        ctcae_raw = m_ctcae.group(1)

    if cd_raw is None and ctcae_raw is None:
        return None, None

    requires_reop = bool(re.search(r"\b(?:reoperat\w*|revision\s+surg\w*|general\s+anesthe\w*)\b", text, re.IGNORECASE))
    return normalize_clavien_dindo(cd_raw, ctcae_raw, requires_reoperation=requires_reop)


def extract_resolution_time_window(text: str) -> str | None:
    """Extract clinical resolution/remodeling time window in English or Russian, or None."""
    if not text:
        return None

    prefixed_patterns = (
        r"\b(?:within|over|during|after|by|for|up\s+to)\s+"
        r"\d+(?:\.\d+)?(?:\s*(?:–|-|—|to)\s*\d+(?:\.\d+)?)?\s*"
        r"(?:days?|weeks?|wks?|months?|mos?|years?|yrs?)\b",
        r"(?<!\w)(?:в\s+течение|через|до|на\s+протяжении|за)\s+"
        r"\d+(?:[.,]\d+)?(?:\s*(?:–|-|—|до)\s*\d+(?:[.,]\d+)?)?\s*"
        r"(?:дн(?:я|ей)|суток|сут\.?|недел[ьию]|нед\.?|месяц(?:а|ев)?|мес\.?|год(?:а)?|лет)(?!\w)",
    )
    for pat in prefixed_patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return " ".join(m.group(0).split()).strip()

    standalone_patterns = (
        r"\b\d+(?:\.\d+)?(?:\s*(?:–|-|—|to)\s*\d+(?:\.\d+)?)?\s*"
        r"(?:days?|weeks?|wks?|months?|mos?|years?|yrs?)\b",
        r"(?<!\w)\d+(?:[.,]\d+)?(?:\s*(?:–|-|—|до)\s*\d+(?:[.,]\d+)?)?\s*"
        r"(?:дн(?:я|ей)|суток|сут\.?|недел[ьию]|нед\.?|месяц(?:а|ев)?|мес\.?|год(?:а)?|лет)(?!\w)",
    )
    for pat in standalone_patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return " ".join(m.group(0).split()).strip()

    return None


def insert_extracted_complication(
    conn: sqlite3.Connection,
    record: dict[str, Any],
    *,
    skip_recurrence: bool = False,
    commit: bool = True,
) -> int | None:
    """Validate and insert one complication row into extracted_complications (COMP-03, D-04, D-07, D-08, T-17-01)."""
    modality = str(record.get("modality") or "").strip()
    complication_name = str(record.get("complication_name") or "").strip()
    if not modality:
        raise ValueError("Field 'modality' must be a non-empty string")
    if not complication_name:
        raise ValueError("Field 'complication_name' must be a non-empty string")

    if is_excluded_recurrence_event(complication_name):
        if skip_recurrence:
            return None
        raise ValueError(
            f"Excluded disease recurrence / incomplete release event (D-08): {complication_name!r}"
        )

    raw_event_class = record.get("event_class")
    event_class = "true_complication" if raw_event_class is None else str(raw_event_class).strip()
    if event_class not in VALID_EVENT_CLASS:
        raise ValueError(f"Invalid event_class: {event_class!r}. Allowed: {VALID_EVENT_CLASS}")

    reversibility = str(record.get("reversibility") or "").strip()
    if reversibility not in VALID_REVERSIBILITY:
        raise ValueError(f"Invalid reversibility: {reversibility!r}. Allowed: {VALID_REVERSIBILITY}")

    clavien_grade, ctcae_grade = normalize_clavien_dindo(
        record.get("clavien_dindo_grade"),
        record.get("ctcae_grade"),
        requires_reoperation=(reversibility == "requires_reoperation"),
    )

    time_window_raw = str(record.get("time_window") or "").strip()
    if event_class == "transient_postop_sequela":
        if not time_window_raw:
            search_blob = " ".join(
                str(record.get(k) or "")
                for k in ("complication_name", "timing_category", "prevention_and_management")
            )
            time_window_raw = extract_resolution_time_window(search_blob) or DEFAULT_SEQUELA_TIME_WINDOW
        time_window: str | None = time_window_raw
    else:
        time_window = time_window_raw or None

    raw_tier = record.get("evidence_tier")
    if isinstance(raw_tier, bool):
        raise ValueError(f"Invalid evidence_tier: {raw_tier!r}")
    evidence_tier = int(raw_tier) if raw_tier is not None and str(raw_tier).strip() != "" else None
    if evidence_tier is not None and evidence_tier not in (1, 2, 3, 4):
        raise ValueError(f"Invalid evidence_tier: {evidence_tier!r} (expected 1..4)")

    raw_sample_size = record.get("sample_size")
    if isinstance(raw_sample_size, bool):
        raise ValueError(f"Invalid sample_size: {raw_sample_size!r}")
    if raw_sample_size is not None and str(raw_sample_size).strip() != "":
        sample_size_f = float(raw_sample_size)
        if not math.isfinite(sample_size_f) or sample_size_f <= 0:
            raise ValueError(f"Invalid sample_size: {raw_sample_size!r} (must be finite and > 0)")
        sample_size: int | None = int(sample_size_f)
    else:
        sample_size = None

    raw_freq_num = record.get("frequency_num")
    if isinstance(raw_freq_num, bool):
        raise ValueError(f"Invalid frequency_num: {raw_freq_num!r}")
    if raw_freq_num is not None and str(raw_freq_num).strip() != "":
        frequency_num: float | None = float(raw_freq_num)
        if not math.isfinite(frequency_num) or frequency_num < 0.0 or frequency_num > 100.0:
            raise ValueError(f"Invalid frequency_num: {raw_freq_num!r} (must be finite in [0.0, 100.0])")
    else:
        frequency_num = None

    is_rare_casuistry = (
        1
        if (
            _parse_bool_flag(record.get("is_rare_casuistry"))
            or evidence_tier == 4
            or (sample_size is not None and sample_size < 20)
        )
        else 0
    )

    if (
        is_rare_casuistry == 1
        and (sample_size is None or sample_size < 20)
        and frequency_num is not None
        and frequency_num >= 50.0
    ):
        frequency_num = None

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO extracted_complications (
            article_id,
            pmid,
            doi,
            first_author_year,
            evidence_tier,
            modality,
            complication_name,
            event_class,
            timing_category,
            clavien_dindo_grade,
            ctcae_grade,
            frequency_pct,
            frequency_num,
            reversibility,
            time_window,
            anatomical_substrate,
            prevention_and_management,
            sample_size,
            is_rare_casuistry
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.get("article_id"),
            record.get("pmid"),
            record.get("doi"),
            record.get("first_author_year"),
            evidence_tier,
            modality,
            complication_name,
            event_class,
            record.get("timing_category"),
            clavien_grade,
            ctcae_grade,
            record.get("frequency_pct"),
            frequency_num,
            reversibility,
            time_window,
            record.get("anatomical_substrate"),
            record.get("prevention_and_management"),
            sample_size,
            is_rare_casuistry,
        ),
    )
    if commit:
        conn.commit()
    return int(cur.lastrowid)


def fetch_extracted_complications(
    conn: sqlite3.Connection,
    *,
    modality: str | None = None,
    include_casuistry: bool = True,
) -> list[dict[str, Any]]:
    """Fetch rows from extracted_complications safely (returns [] if table absent, T-17-01/T-17-02)."""
    if not table_exists(conn, "extracted_complications"):
        return []

    clauses: list[str] = []
    params: list[Any] = []
    if modality is not None:
        clauses.append("modality = ?")
        params.append(modality)
    if not include_casuistry:
        clauses.append("COALESCE(is_rare_casuistry, 0) = 0")

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = (
        f"SELECT * FROM extracted_complications {where_sql} "
        "ORDER BY modality ASC, COALESCE(frequency_num, -1.0) DESC, id ASC"
    )
    cur = conn.execute(sql, tuple(params))
    columns = [desc[0] for desc in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]
