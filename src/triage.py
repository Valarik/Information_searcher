# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = [
#   "pyyaml",
#   "polite-http",
#   "pip-system-certs",
#   "truststore",
# ]
# ///
"""PRISMA screening, Evidence Tier classification (Tier 1-4), 5-cluster tagging,
and Europe PMC full-text XML retrieval (Phase 1, Plan 01-02).

Implements locked decisions D-01 through D-07 from 01-CONTEXT.md.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import truststore
truststore.inject_into_ssl()

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.schema import init_db

SKILLS_ROOT = Path.home() / ".gemini" / "config" / "plugins" / "science" / "skills"
EPMC_SCRIPT = SKILLS_ROOT / "literature_search_europepmc" / "scripts" / "europepmc_api.py"

PMCID_RE = re.compile(r"^PMC\d+$")

ANKLE_FRACTURE_TERMS = (
    "ankle",
    "malleol",
    "bimalleolar",
    "trimalleolar",
    "fibula",
    "fibular",
    "tibiofibular",
    "syndesmosis",
    "syndesmot",
    "talus",
    "talar",
    "pott's fracture",
    "pott fracture",
    "maisoneuve",
    "lower leg fracture",
    "distal tibia",
)

HAND_PALMAR_TERMS = (
    "palmar",
    "hand",
    "finger",
    "digit",
    "metacarpophalangeal",
    "mcp",
    "proximal interphalangeal",
    "pip",
    "aponeurosis",
    "aponeurotomy",
    "fasciectomy",
    "fasciotomy",
    "dermofasciectomy",
    "collagenase",
    "clostridium histolyticum",
    "xiapex",
    "xiaflex",
    "myofibroblast",
    "nodule",
    "cord",
)

DUPUYTREN_CORE_TERMS = (
    "dupuytren",
    "palmar fibromatosis",
    "viking disease",
    "viking's disease",
    "morbus dupuytren",
    "maladie de dupuytren",
)

ISOLATED_OTHER_FIBROMATOSIS_TERMS = (
    "peyronie",
    "penile curvature",
    "tunica albuginea",
    "corpora cavernosa",
    "ledderhose",
    "plantar fibromatosis",
    "plantar fascia",
    "garrod",
    "knuckle pad",
)

RARE_COMPLICATION_TERMS = (
    "necrosis",
    "gangrene",
    "amputation",
    "tendon rupture",
    "flexor tendon",
    "pulley rupture",
    "pseudoaneurysm",
    "false aneurysm",
    "arterial injury",
    "digital ischemia",
    "ischaemia",
    "nerve injury",
    "digital nerve",
    "crps",
    "complex regional pain",
    "anaphylaxis",
    "deep infection",
    "compartment syndrome",
)

UNIVERSAL_SURGICAL_COMPLICATION_TERMS = (
    "postoperative complication",
    "intraoperative complication",
    "surgical complication",
    "iatrogenic",
    "clavien-dindo",
    "clavien–dindo",
    "surgical site infection",
    "wound infection",
    "wound dehiscence",
    "hematoma",
    "seroma",
    "nerve injury",
    "neuropraxia",
    "paresthesia",
    "numbness",
    "bowstringing",
    "tendon rupture",
    "pulley rupture",
    "scar tenderness",
    "scar pain",
    "complex regional pain",
    "crps",
    "algodystrophy",
    "postoperative stiffness",
    "extension lag",
    "extension deficit",
    "vascular injury",
    "ischemia",
    "necrosis",
    "reoperation",
    "revision surgery",
)

UNIVERSAL_CONSERVATIVE_ADVERSE_TERMS = (
    "adverse event",
    "adverse effect",
    "side effect",
    "drug-related",
    "treatment-related adverse",
    "treatment-emergent",
    "ctcae",
    "toxicity",
    "skin atrophy",
    "hypopigmentation",
    "fat necrosis",
    "flare reaction",
    "steroid flare",
    "hyperglycemia",
    "anaphylaxis",
)

BASIC_SCIENCE_MARKERS = (
    "in vitro",
    "ex vivo",
    "cell line",
    "animal model",
    "mouse",
    "mice",
    "rat ",
    "cadaver",
    "scrna-seq",
    "single-cell",
    "rna-seq",
    "gwas",
)

CLINICAL_SAMPLE_SIZE_PATTERNS = (
    r"\b(\d[\d,]{0,6})\s+(?:consecutive\s+)?(?:patients?|subjects?|participants?|individuals?|cases?|wom[ae]n|pregnanc(?:y|ies)|deliver(?:y|ies)|mothers?|adults?|child(?:ren)?)\b",
    r"\b(?:n|N)\s*=\s*(\d[\d,]{0,6})\b",
    r"\b(?:cohort|series|total|study|review)\s+of\s+(\d[\d,]{0,6})\b",
    r"\b(\d[\d,]{0,6})\s+(?:consecutive\s+)?(?:hands?|digits?|fingers?|thumbs?|rays?|joints?|pulleys?|tendons?|trigger\s+fingers?|trigger\s+digits?|trigger\s+thumbs?|wrists?|elbows?|shoulders?|knees?|hips?|ankles?|procedures?|operations?|releases?|interventions?)\b",
)


def _parse_sources_list(sources: list[str] | str | None) -> list[str]:
    if not sources:
        return []
    if isinstance(sources, str):
        try:
            parsed = json.loads(sources)
            if isinstance(parsed, list):
                return [str(s) for s in parsed if s is not None]
            if parsed is not None:
                return [str(parsed)]
        except Exception:
            return [sources]
        return []
    if isinstance(sources, (list, tuple, set)):
        return [str(s) for s in sources if s is not None]
    return [str(sources)]


def should_tag_complications_safety(
    title: str,
    abstract: str | None,
    sources: list[str] | str | None = None,
    triage_rules: dict[str, Any] | None = None,
) -> bool:
    """Return True when an article triggers any of the 3 D-05 complications_safety signals."""
    src_list = _parse_sources_list(sources)
    if any(
        s in ("PubMed:Complications", "EuropePMC:Complications") or s.endswith(":Complications")
        for s in src_list
    ):
        return True

    combined = f"{title or ''}\n{abstract or ''}".lower()
    if any(
        term in combined
        for term in (
            *UNIVERSAL_SURGICAL_COMPLICATION_TERMS,
            *UNIVERSAL_CONSERVATIVE_ADVERSE_TERMS,
            *RARE_COMPLICATION_TERMS,
        )
    ):
        return True

    if triage_rules:
        yaml_terms = list(triage_rules.get("complication_terms") or []) + list(
            triage_rules.get("rare_complication_terms") or []
        )
        if any(str(t).lower() in combined for t in yaml_terms if t):
            return True

    return False


def _extract_clinical_sample_size(text: str) -> int | None:
    """Extract maximum clinical patient/joint/digit sample size while filtering calendar years."""
    if not text:
        return None
    max_n: int | None = None
    for pat in CLINICAL_SAMPLE_SIZE_PATTERNS:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            val_str = m.group(1).replace(",", "")
            if val_str.isdigit():
                val = int(val_str)
                if 1 <= val <= 1_000_000 and not (1990 <= val <= 2030):
                    if max_n is None or val > max_n:
                        max_n = val
    return max_n


def _is_basic_science_study(text: str) -> bool:
    """Return True for in vitro / ex vivo / animal / cadaver / omics studies."""
    low = (text or "").lower()
    return any(marker in low for marker in BASIC_SCIENCE_MARKERS)


def get_uv_bin() -> str:
    uv_in_path = shutil.which("uv")
    if uv_in_path:
        return uv_in_path
    local_uv = Path.home() / ".local" / "bin" / ("uv.exe" if os.name == "nt" else "uv")
    if local_uv.exists():
        return str(local_uv)
    raise RuntimeError("uv executable not found")


def has_english_or_russian_text(text: str | None) -> bool:
    if not text or len(text.strip()) < 40:
        return False
    return bool(re.search(r"[a-zA-Zа-яА-ЯёЁ]{4,}", text))


def classify_prisma_status(
    title: str,
    abstract: str | None,
    pub_year: int | None,
    language: str | None,
    start_year: int,
    end_year: int,
    triage_rules: dict[str, Any] | None = None,
    sources: list[str] | str | None = None,
) -> str:
    """Apply nosology-agnostic PRISMA inclusion/exclusion filters from `triage_rules`."""
    if pub_year is not None and (pub_year < start_year or pub_year > end_year):
        return "excluded_out_of_date_range"

    combined = f"{title}\n{abstract or ''}".lower()

    if triage_rules:
        for rule in triage_rules.get("exclusion_rules", []):
            triggers = [t.lower() for t in rule.get("trigger_terms", [])]
            unless = [u.lower() for u in rule.get("unless_terms", [])]
            if any(t in combined for t in triggers) and not any(u in combined for u in unless):
                return rule.get("status", "excluded_custom_rule")

        core_terms = [t.lower() for t in triage_rules.get("core_terms", [])]
        ctx_terms = [t.lower() for t in triage_rules.get("context_terms", [])]
        has_core = any(t in combined for t in core_terms) if core_terms else True
        has_ctx = any(t in combined for t in ctx_terms) if ctx_terms else True
        if not has_ctx and ctx_terms:
            has_ctx = should_tag_complications_safety(
                title, abstract, sources=sources, triage_rules=triage_rules
            )
        if not has_core or not has_ctx:
            return "excluded_offtopic"
    else:
        has_ankle = any(t in combined for t in ANKLE_FRACTURE_TERMS)
        has_hand = any(t in combined for t in HAND_PALMAR_TERMS)
        if has_ankle and not has_hand:
            return "excluded_ankle_fracture"
        has_dupuytren = any(t in combined for t in DUPUYTREN_CORE_TERMS)
        has_other_fibro = any(t in combined for t in ISOLATED_OTHER_FIBROMATOSIS_TERMS)
        if has_other_fibro and not has_dupuytren:
            return "excluded_isolated_peyronie_ledderhose"
        if not has_dupuytren and not ("fibromatosis" in combined and has_hand):
            return "excluded_offtopic"

    # Foreign language without English/Russian abstract
    lang = (language or "eng").lower()
    is_en_ru = lang.startswith(("en", "ru", "und"))
    if not is_en_ru and not has_english_or_russian_text(abstract):
        return "excluded_foreign_no_abstract"

    return "included"


def classify_evidence_tier(
    title: str,
    abstract: str | None,
    pub_types: list[str],
    rare_complication_terms: tuple[str, ...] | list[str] = RARE_COMPLICATION_TERMS,
    complication_terms: tuple[str, ...] | list[str] = (),
) -> tuple[int, list[str]]:
    """Classify included articles into Tier 1-4 per D-04, D-05 and D-06."""
    t_lower = title.lower()
    abs_lower = (abstract or "").lower()
    combined = f"{t_lower}\n{abs_lower}"
    pt_lower = [p.lower() for p in pub_types]
    updated_types = list(pub_types)

    def _append_tier4_comp_markers() -> None:
        has_rare = any(str(rc).lower() in combined for rc in (rare_complication_terms or ()) if rc)
        has_any_comp = has_rare or any(
            str(term).lower() in combined
            for term in (
                *(complication_terms or ()),
                *UNIVERSAL_SURGICAL_COMPLICATION_TERMS,
                *UNIVERSAL_CONSERVATIVE_ADVERSE_TERMS,
            )
            if term
        )
        if has_rare and "Rare Complication Case [D-05]" not in updated_types:
            updated_types.append("Rare Complication Case [D-05]")
        if has_any_comp and "rare_catastrophic_case" not in updated_types:
            updated_types.append("rare_catastrophic_case")

    # Check Tier 4 first for obvious letters/errata/comments/case reports (D-04, D-05)
    tier4_pt_markers = (
        "case reports",
        "letter",
        "comment",
        "editorial",
        "published erratum",
        "erratum",
        "corrigendum",
        "news",
        "historical article",
        "biography",
        "portrait",
        "retracted publication",
    )
    if any(m in pt_lower for m in tier4_pt_markers):
        _append_tier4_comp_markers()
        return 4, updated_types

    tier4_title_markers = (
        "case report",
        "a case of",
        "two cases of",
        "letter to the editor",
        "reply to",
        "response to",
        "comment on:",
        "erratum",
        "corrigendum",
        "author response",
    )
    if any(m in t_lower for m in tier4_title_markers):
        _append_tier4_comp_markers()
        return 4, updated_types

    # Tier 1: Meta-Analysis, Systematic Review, RCT, Clinical Practice Guideline
    tier1_pt_markers = (
        "meta-analysis",
        "systematic review",
        "randomized controlled trial",
        "controlled clinical trial",
        "practice guideline",
        "guideline",
        "consensus development conference",
    )
    if any(m in pt_lower for m in tier1_pt_markers):
        return 1, updated_types

    tier1_text_markers = (
        "systematic review",
        "meta-analysis",
        "network meta-analysis",
        "prisma",
        "randomized controlled trial",
        "randomised controlled trial",
        "randomized clinical trial",
        "randomised clinical trial",
        "prospectively randomized",
        "double-blind randomized",
    )
    if any(m in combined for m in tier1_text_markers):
        return 1, updated_types

    # D-06: Separate Narrative Reviews into Tier 3 so they don't pollute primary stats
    is_review = ("review" in pt_lower) or ("review" in t_lower)
    if is_review:
        if "Narrative Review [D-06]" not in updated_types:
            updated_types.append("Narrative Review [D-06]")
        return 3, updated_types

    # If abstract is completely missing and not Tier 1, place in Tier 4 (D-05)
    if not abstract or len(abstract.strip()) < 60:
        return 4, updated_types

    # D-04: Two-contour separation — small clinical series (1 <= N < 20) go to Tier 4 casuistry
    eff_n = _extract_clinical_sample_size(combined)
    if eff_n is not None and 1 <= eff_n < 20 and not _is_basic_science_study(combined):
        _append_tier4_comp_markers()
        return 4, updated_types

    # Tier 2: Prospective/Comparative cohorts, registries, GWAS, scRNA-seq/multi-omics, >=3yr follow-up
    tier2_pt_markers = (
        "comparative study",
        "clinical trial",
        "clinical trial, phase ii",
        "clinical trial, phase iii",
        "clinical trial, phase iv",
        "multicenter study",
        "observational study",
    )
    tier2_text_markers = (
        "prospective cohort",
        "prospective study",
        "prospectively collected",
        "multicenter",
        "multi-center",
        "national registry",
        "population-based",
        "5-year",
        "10-year",
        "long-term follow-up",
        "long-term outcome",
        "gwas",
        "genome-wide association",
        "mendelian randomization",
        "uk biobank",
        "finngen",
        "single-cell",
        "scrna-seq",
        "scrnaseq",
        "spatial transcriptom",
        "rna-seq",
        "transcriptom",
        "proteom",
        "epigenom",
        "methylation array",
    )
    if any(m in pt_lower for m in tier2_pt_markers) or any(m in combined for m in tier2_text_markers):
        return 2, updated_types

    # Default for remaining original clinical series and in vitro/ex vivo studies: Tier 3
    return 3, updated_types


def assign_clusters(
    title: str,
    abstract: str | None,
    clusters_cfg: dict[str, Any],
    *,
    sources: list[str] | str | None = None,
    triage_rules: dict[str, Any] | None = None,
) -> list[str]:
    combined = f"{title}\n{abstract or ''}".lower()
    matched: list[str] = []
    for c_key, c_info in (clusters_cfg or {}).items():
        keywords = c_info.get("keywords") or []
        if any(kw.lower() in combined for kw in keywords):
            matched.append(c_key)
    if should_tag_complications_safety(title, abstract, sources=sources, triage_rules=triage_rules):
        if "complications_safety" not in matched:
            matched.append("complications_safety")
    return matched


def load_epmc_module():
    spec = importlib.util.spec_from_file_location("europepmc_api", str(EPMC_SCRIPT))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {EPMC_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _has_epmc_source(raw_sources: str | None) -> bool:
    """Return True if parsed JSON sources contain 'EuropePMC' or 'EuropePMC:Complications'."""
    if not raw_sources:
        return False
    try:
        parsed = json.loads(raw_sources)
        if isinstance(parsed, list):
            return any(str(s).startswith("EuropePMC") for s in parsed)
    except Exception:
        pass
    return "EuropePMC" in str(raw_sources)


def download_fulltexts_tier1_to_3(
    conn: sqlite3.Connection,
    fulltext_dir: Path,
    max_downloads: int = 1200,
) -> int:
    """Download open-access full-text XML from Europe PMC for Tier 1-3 articles (D-06, D-07, T-17-04)."""
    fulltext_dir.mkdir(parents=True, exist_ok=True)
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT id, pmcid, sources, clusters, is_open_access, evidence_tier, cited_by_count
        FROM articles
        WHERE prisma_status = 'included'
          AND evidence_tier IN (1, 2, 3, 4)
          AND pmcid IS NOT NULL
          AND pmcid != ''
        ORDER BY
          CASE WHEN evidence_tier IN (1, 2, 3) THEN 0 ELSE 1 END ASC,
          CASE
            WHEN evidence_tier IN (1, 2, 3)
                 AND (clusters LIKE '%"complications_safety"%' OR sources LIKE '%:Complications"%')
            THEN 0
            ELSE 1
          END ASC,
          evidence_tier ASC,
          cited_by_count DESC
        """
    ).fetchall()

    # Prioritize records confirmed in EuropePMC Open Access first while preserving SQL priority order
    epmc_rows = []
    other_pmc_rows = []
    for r in rows:
        pmcid_chk = str(r["pmcid"] or "").strip()
        if not PMCID_RE.match(pmcid_chk):
            continue
        if _has_epmc_source(r["sources"]):
            epmc_rows.append(r)
        else:
            other_pmc_rows.append(r)

    candidates = (epmc_rows + other_pmc_rows)[:max_downloads]
    print(f"[Full-Text XML] Checking/downloading up to {len(candidates)} Tier 1-3 PMC articles (D-06, D-07)...", flush=True)

    success_count = 0
    to_fetch: list[tuple[int, str, Path]] = []
    for r in candidates:
        row_id = r["id"]
        pmcid = str(r["pmcid"]).strip()
        # T-17-04: Strict regex validation against path traversal
        if not PMCID_RE.match(pmcid):
            continue

        xml_file = fulltext_dir / f"{pmcid}.xml"
        if xml_file.exists() and xml_file.stat().st_size > 200:
            cur.execute(
                "UPDATE articles SET has_fulltext_xml = 1, fulltext_path = ? WHERE id = ?",
                (str(xml_file), row_id),
            )
            success_count += 1
            continue

        # Only fetch from EuropePMC REST endpoint if indexed in EuropePMC OA (incl. EuropePMC:Complications)
        if not _has_epmc_source(r["sources"]):
            continue

        to_fetch.append((row_id, pmcid, xml_file))

    conn.commit()

    def _fetch_one(item: tuple[int, str, Path]) -> tuple[int, Path] | None:
        r_id, p_id, x_file = item
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{p_id}/fullTextXML"
        req = urllib.request.Request(url, headers={"User-Agent": "InformationSearcher/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                xml_bytes = resp.read()
                if xml_bytes and len(xml_bytes) > 200 and b"<article" in xml_bytes[:2000]:
                    x_file.write_bytes(xml_bytes)
                    return (r_id, x_file)
        except Exception:
            pass
        return None

    if to_fetch:
        print(f"  -> Remaining uncached EuropePMC OA XMLs to fetch: {len(to_fetch)}", flush=True)
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(_fetch_one, item) for item in to_fetch]
            for idx, fut in enumerate(as_completed(futures), 1):
                res = fut.result()
                if res is not None:
                    r_id, x_file = res
                    cur.execute(
                        "UPDATE articles SET has_fulltext_xml = 1, fulltext_path = ? WHERE id = ?",
                        (str(x_file), r_id),
                    )
                    success_count += 1
                if idx % 25 == 0:
                    conn.commit()
                    print(f"  -> Processed {idx}/{len(to_fetch)} XML requests (total XMLs: {success_count})...", flush=True)

    conn.commit()
    print(f"  -> Total Tier 1-3 articles with local Full-Text XML: {success_count}", flush=True)
    return success_count


def generate_prisma_report(
    conn: sqlite3.Connection,
    cfg: dict[str, Any],
    raw_dir: Path,
    report_path: Path,
) -> None:
    """Generate reports/<id>/prisma_stats.md with full PRISMA flow and breakdowns."""
    cur = conn.cursor()
    cfg = cfg or {}
    meta = cfg.get("nosology") or {}
    nosology_id = cfg.get("nosology_id") or meta.get("id") or "unknown"
    name_ru = cfg.get("name_ru") or meta.get("name_ru") or nosology_id
    date_range = cfg.get("date_range") or {}
    start_year = date_range.get("start_year", 2016)
    end_year = date_range.get("end_year", 2026)

    # Count raw records per source
    raw_pubmed = 0
    pmids_file = raw_dir / "pubmed_pmids.json"
    if pmids_file.exists():
        raw_pubmed = len(json.loads(pmids_file.read_text(encoding="utf-8")))

    raw_epmc = 0
    for f in sorted(raw_dir.glob("europepmc_page_*.json")):
        try:
            raw_epmc += len(json.loads(f.read_text(encoding="utf-8")).get("results") or [])
        except Exception:
            pass

    raw_oa = 0
    for f in sorted(raw_dir.glob("openalex_page_*.json")):
        try:
            raw_oa += len(json.loads(f.read_text(encoding="utf-8")).get("results") or [])
        except Exception:
            pass

    raw_pubmed_comp = 0
    pm_comp_file = raw_dir / "pubmed_complications.json"
    if pm_comp_file.exists():
        try:
            pm_comp_data = json.loads(pm_comp_file.read_text(encoding="utf-8"))
            if isinstance(pm_comp_data, dict):
                raw_pubmed_comp = len(pm_comp_data.get("pmids") or pm_comp_data.get("records") or [])
            elif isinstance(pm_comp_data, list):
                raw_pubmed_comp = len(pm_comp_data)
        except Exception:
            pass

    raw_epmc_comp = 0
    epmc_comp_file = raw_dir / "europepmc_complications.json"
    if epmc_comp_file.exists():
        try:
            epmc_comp_data = json.loads(epmc_comp_file.read_text(encoding="utf-8"))
            if isinstance(epmc_comp_data, dict):
                raw_epmc_comp = len(epmc_comp_data.get("results") or [])
            elif isinstance(epmc_comp_data, list):
                raw_epmc_comp = len(epmc_comp_data)
        except Exception:
            pass

    total_raw = raw_pubmed + raw_epmc + raw_oa + raw_pubmed_comp + raw_epmc_comp
    total_unique = cur.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    duplicates_removed = max(0, total_raw - total_unique)

    status_rows = cur.execute(
        "SELECT prisma_status, COUNT(*) as cnt FROM articles GROUP BY prisma_status ORDER BY cnt DESC"
    ).fetchall()
    status_map = {r["prisma_status"]: r["cnt"] for r in status_rows}
    included_total = status_map.get("included", 0)
    excluded_total = total_unique - included_total

    tier_rows = cur.execute(
        """
        SELECT evidence_tier, COUNT(*) as cnt,
               SUM(has_fulltext_xml) as ft_cnt,
               SUM(is_open_access) as oa_cnt
        FROM articles
        WHERE prisma_status = 'included'
        GROUP BY evidence_tier
        ORDER BY evidence_tier ASC
        """
    ).fetchall()

    narrative_reviews_cnt = cur.execute(
        "SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' AND pub_types LIKE '%Narrative Review%'"
    ).fetchone()[0]
    rare_comp_cnt = cur.execute(
        "SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' "
        "AND (pub_types LIKE '%rare_catastrophic_case%' OR pub_types LIKE '%Rare Complication%')"
    ).fetchone()[0]
    preprints_cnt = cur.execute(
        "SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' AND is_preprint = 1"
    ).fetchone()[0]
    fulltext_total = cur.execute(
        "SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' AND has_fulltext_xml = 1"
    ).fetchone()[0]

    year_rows = cur.execute(
        """
        SELECT pub_year,
               COUNT(*) as total,
               SUM(CASE WHEN evidence_tier = 1 THEN 1 ELSE 0 END) as t1,
               SUM(CASE WHEN evidence_tier = 2 THEN 1 ELSE 0 END) as t2,
               SUM(CASE WHEN evidence_tier = 3 THEN 1 ELSE 0 END) as t3,
               SUM(CASE WHEN evidence_tier = 4 THEN 1 ELSE 0 END) as t4
        FROM articles
        WHERE prisma_status = 'included' AND pub_year IS NOT NULL
        GROUP BY pub_year
        ORDER BY pub_year ASC
        """
    ).fetchall()

    clusters_cfg = cfg.get("clusters") or {}
    cluster_stats: list[tuple[str, str, int, int, int]] = []
    for c_key, c_info in clusters_cfg.items():
        c_name = c_info.get("name_ru", c_key)
        c_total = cur.execute(
            "SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' AND clusters LIKE ?",
            (f'%"{c_key}"%',),
        ).fetchone()[0]
        c_t12 = cur.execute(
            "SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' AND evidence_tier IN (1, 2) AND clusters LIKE ?",
            (f'%"{c_key}"%',),
        ).fetchone()[0]
        c_ft = cur.execute(
            "SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' AND has_fulltext_xml = 1 AND clusters LIKE ?",
            (f'%"{c_key}"%',),
        ).fetchone()[0]
        cluster_stats.append((c_key, c_name, c_total, c_t12, c_ft))

    if "complications_safety" not in clusters_cfg:
        c_key = "complications_safety"
        c_name = "Безопасность лечения и хирургические осложнения (D-05)"
        c_total = cur.execute(
            "SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' AND clusters LIKE ?",
            (f'%"{c_key}"%',),
        ).fetchone()[0]
        c_t12 = cur.execute(
            "SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' AND evidence_tier IN (1, 2) AND clusters LIKE ?",
            (f'%"{c_key}"%',),
        ).fetchone()[0]
        c_ft = cur.execute(
            "SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' AND has_fulltext_xml = 1 AND clusters LIKE ?",
            (f'%"{c_key}"%',),
        ).fetchone()[0]
        cluster_stats.append((c_key, c_name, c_total, c_t12, c_ft))

    ct_total = cur.execute("SELECT COUNT(*) FROM clinical_trials").fetchone()[0]
    ct_status_rows = cur.execute(
        "SELECT overall_status, COUNT(*) as cnt FROM clinical_trials GROUP BY overall_status ORDER BY cnt DESC"
    ).fetchall()

    excl_breakdown = "<br/>".join(
        f"- {k}: {v}" for k, v in sorted(status_map.items()) if k != "included"
    ) or "- Нет исключённых"

    comp_raw_suffix = ""
    if raw_pubmed_comp > 0 or raw_epmc_comp > 0:
        comp_raw_suffix = (
            f"<br/>PubMed:Complications: {raw_pubmed_comp} | EuropePMC:Complications: {raw_epmc_comp}"
        )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# PRISMA-статистика и карта корпуса: {name_ru}",
        "",
        f"**Временной срез:** {start_year}–{end_year} гг.",
        f"**База данных:** `data/{nosology_id}/literature.db`",
        "",
        "## 1. Воронка отбора публикаций (PRISMA 2020)",
        "",
        "```mermaid",
        "flowchart TD",
        f'    A["Первичная выгрузка из баз (N = {total_raw})<br/>PubMed: {raw_pubmed} | Europe PMC: {raw_epmc} | OpenAlex: {raw_oa}{comp_raw_suffix}"] --> B["После дедупликации по PMID / DOI / Заголовку<br/>Уникальных записей: N = {total_unique}<br/>(Удалено дублей: {duplicates_removed})"]',
        f'    B --> C["PRISMA-скрининг заголовков и абстрактов (N = {total_unique})"]',
        f'    C --> D["Исключено по критериям PRISMA (N = {excluded_total})<br/>{excl_breakdown}"]',
        f'    C --> E["Включено в итоговый корпус ({name_ru})<br/>N = {included_total} статей (+ {ct_total} записей ClinicalTrials.gov)"]',
        f'    E --> F["Полнотекстовые XML (Europe PMC OA, Tier 1-3): N = {fulltext_total}"]',
        "```",
        "",
        "## 2. Стратификация по уровням доказательности (`Tier 1–4`)",
        "",
        "| Уровень доказательности | Описание категории | Число статей | Открытый доступ (OA) | Скачано Full-Text XML |",
        "|-------------------------|--------------------|-------------:|---------------------:|----------------------:|",
    ]

    tier_descriptions = {
        1: "**Tier 1** (Метаанализы, систематические обзоры, РКИ, гайдлайны)",
        2: "**Tier 2** (Проспективные/сравнительные когорты, GWAS, scRNA-seq, наблюдение ≥3 лет)",
        3: f"**Tier 3** (Ретроспективные серии, работы *in vitro*/*ex vivo*, нарративные обзоры [{narrative_reviews_cnt}])",
        4: f"**Tier 4** (Case reports, малые серии N<20, письма, комментарии; из них редкие осложнения: {rare_comp_cnt})",
    }
    for r in tier_rows:
        t = int(r["evidence_tier"])
        desc = tier_descriptions.get(t, f"Tier {t}")
        lines.append(
            f"| Tier {t} | {desc} | {r['cnt']} | {r['oa_cnt'] or 0} | {r['ft_cnt'] or 0} |"
        )

    lines.extend(
        [
            "",
            f"- **Включено препринтов (2023–2026, метка `[Preprint]`, D-02):** {preprints_cnt}",
            f"- **Нарративных обзоров в Tier 3 (`D-06`, используются только для проверки полноты ссылок):** {narrative_reviews_cnt}",
            f"- **Клинических случаев редких осложнений в Tier 4 (`D-04`/`D-05`):** {rare_comp_cnt}",
            "",
            "## 3. Распределение по 5 тематическим кластерам",
            "",
            "| Кластер | Название кластера | Всего статей | Ядро доказательности (Tier 1–2) | Доступно Full-Text XML |",
            "|---------|-------------------|-------------:|--------------------------------:|-----------------------:|",
        ]
    )

    for c_key, c_name, c_total, c_t12, c_ft in cluster_stats:
        lines.append(f"| `{c_key}` | {c_name} | {c_total} | {c_t12} | {c_ft} |")

    lines.extend(
        [
            "",
            "## 4. Динамика публикаций по годам (2016–2026)",
            "",
            "| Год | Всего включено | Tier 1 (РКИ/Мета) | Tier 2 (Когорты/Омики) | Tier 3 (Серии/In vitro/Обзоры) | Tier 4 (Кейсы/Письма) |",
            "|----:|---------------:|------------------:|-----------------------:|-------------------------------:|----------------------:|",
        ]
    )

    for yr in year_rows:
        lines.append(
            f"| {yr['pub_year']} | {yr['total']} | {yr['t1']} | {yr['t2']} | {yr['t3']} | {yr['t4']} |"
        )

    lines.extend(
        [
            "",
            f"## 5. Реестр клинических исследований ClinicalTrials.gov (N = {ct_total})",
            "",
            "| Статус исследования | Количество |",
            "|---------------------|-----------:|",
        ]
    )
    for csr in ct_status_rows:
        lines.append(f"| `{csr['overall_status']}` | {csr['cnt']} |")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[PRISMA Report] Written to {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="PRISMA triage, Evidence Tier classification, and Full-Text XML fetcher.")
    parser.add_argument("--config", type=str, default="configs/prom.yaml", help="Path to nosology YAML config")
    parser.add_argument("--verify-only", action="store_true", help="Run verification checks without re-downloading XMLs")
    parser.add_argument("--max-xml", type=int, default=200, help="Max full-text XMLs to download from Europe PMC")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    meta = cfg.get("nosology") or {}
    nosology_id = cfg.get("nosology_id") or meta.get("id") or cfg_path.stem
    date_range = cfg.get("date_range") or {}
    start_year = int(date_range.get("start_year") or 2016)
    end_year = int(date_range.get("end_year") or 2026)
    clusters_cfg = cfg.get("clusters") or {}
    triage_rules = cfg.get("triage_rules")
    rare_comp_terms = (
        triage_rules.get("rare_complication_terms", RARE_COMPLICATION_TERMS)
        if triage_rules
        else RARE_COMPLICATION_TERMS
    )
    comp_terms = (triage_rules or {}).get("complication_terms") or ()

    data_dir = Path("data") / nosology_id
    raw_dir = data_dir / "raw"
    fulltext_dir = raw_dir / "fulltext_xml"
    db_path = data_dir / "literature.db"
    report_path = Path("reports") / nosology_id / "prisma_stats.md"

    conn = init_db(db_path)
    cur = conn.cursor()

    rows = cur.execute(
        "SELECT id, title, abstract, pub_year, language, pub_types, sources FROM articles"
    ).fetchall()
    print(f"[Triage] Screening and classifying {len(rows)} unique records for '{nosology_id}'...")

    for r in rows:
        row_id = r["id"]
        title = r["title"] or ""
        abstract = r["abstract"]
        pub_year = r["pub_year"]
        lang = r["language"]
        try:
            pub_types = json.loads(r["pub_types"] or "[]")
        except Exception:
            pub_types = []
        sources_list = _parse_sources_list(r["sources"])

        p_status = classify_prisma_status(
            title,
            abstract,
            pub_year,
            lang,
            start_year,
            end_year,
            triage_rules=triage_rules,
            sources=sources_list,
        )
        if p_status == "included":
            tier, updated_types = classify_evidence_tier(
                title,
                abstract,
                pub_types,
                rare_complication_terms=rare_comp_terms,
                complication_terms=comp_terms,
            )
            matched_clusters = assign_clusters(
                title,
                abstract,
                clusters_cfg,
                sources=sources_list,
                triage_rules=triage_rules,
            )
        else:
            tier = 4
            updated_types = pub_types
            matched_clusters = []

        cur.execute(
            """
            UPDATE articles
            SET prisma_status = ?, evidence_tier = ?, pub_types = ?, clusters = ?
            WHERE id = ?
            """,
            (
                p_status,
                tier,
                json.dumps(updated_types, ensure_ascii=False),
                json.dumps(matched_clusters, ensure_ascii=False),
                row_id,
            ),
        )
    conn.commit()

    if not args.verify_only:
        download_fulltexts_tier1_to_3(conn, fulltext_dir, max_downloads=args.max_xml)

    generate_prisma_report(conn, cfg, raw_dir, report_path)

    # Final verification assertions
    inc_cnt = cur.execute("SELECT COUNT(*) FROM articles WHERE prisma_status = 'included'").fetchone()[0]
    t1_cnt = cur.execute("SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' AND evidence_tier = 1").fetchone()[0]
    t2_cnt = cur.execute("SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' AND evidence_tier = 2").fetchone()[0]
    t3_cnt = cur.execute("SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' AND evidence_tier = 3").fetchone()[0]
    t4_cnt = cur.execute("SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' AND evidence_tier = 4").fetchone()[0]
    print(f"[Triage Complete] Included: {inc_cnt} (Tier 1: {t1_cnt}, Tier 2: {t2_cnt}, Tier 3: {t3_cnt}, Tier 4: {t4_cnt})")


if __name__ == "__main__":
    main()
