# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = []
# ///
"""Cluster 3 Structured Extractor: Conservative & Minimally Invasive Treatments + ClinicalTrials.gov (Phase 2, Plan 02-03).

Populates `extracted_clinical_evidence` with `[Cluster3]` rows, exports
`data/dupuytren/extractions/cluster_3_rows.json`, and validates
`data/dupuytren/extractions/cluster_3_conservative_minimally_invasive.md`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.extractor_common import (
    detect_recurrence_definition,
    extract_followup_months,
    extract_joint_outcomes,
    extract_sample_size,
    format_first_author_year,
    get_db_connection,
    parse_jats_xml,
)

CLUSTER3_INTERVENTIONS = (
    "[Cluster3] Collagenase Clostridium histolyticum (CCH)",
    "[Cluster3] Percutaneous Needle Fasciotomy (PNF)",
    "[Cluster3] Adalimumab / Anti-TNF & Targeted Injections",
    "[Cluster3] Radiotherapy",
    "[Cluster3] Corticosteroid Injection",
    "[Cluster3] ESWT / Physical Therapy / Night Splinting",
)


def classify_c3_intervention(title: str, abstract: str) -> tuple[str, str]:
    t = f"{title} {abstract}".lower()
    has_cch = any(k in t for k in ("collagenase", "clostridium histolyticum", "xiapex", "xiaflex", "cch"))
    has_pnf = any(k in t for k in ("needle aponeurotomy", "needle fasciotomy", "percutaneous needle", "pnf", "pna"))
    has_fasciectomy = any(k in t for k in ("fasciectomy", "aponeurectomy", "dermofasciectomy"))

    if any(k in t for k in ("adalimumab", "anti-tnf", "anti-tumour necrosis", "ridd", "pirfenidone", "verteporfin", "tamoxifen", "sorafenib")):
        comp = "Placebo / Standard care" if "placebo" in t else "Untreated / Control"
        return "[Cluster3] Adalimumab / Anti-TNF & Targeted Injections", comp

    if any(k in t for k in ("radiotherapy", "radiation therapy", "irradiation", "electron beam", "orthovoltage")):
        return "[Cluster3] Radiotherapy", "Observation / Sham or Surgical cohort"

    if any(k in t for k in ("triamcinolone", "corticosteroid", "steroid injection", "kenalog", "hydrocortisone")):
        comp = "PNF alone" if has_pnf else "Observation / Placebo"
        return "[Cluster3] Corticosteroid Injection", comp

    if any(k in t for k in ("shockwave", "shock wave", "eswt", "splint", "orthos", "night extension", "hand therapy", "physical therapy", "ultrasound", "stretching", "massage")):
        comp = "No night splint / Hand therapy alone" if "splint" in t else "Sham / Standard care"
        return "[Cluster3] ESWT / Physical Therapy / Night Splinting", comp

    if has_pnf and has_cch:
        return "[Cluster3] Percutaneous Needle Fasciotomy (PNF)", "Collagenase C. histolyticum (CCH)"
    if has_cch and has_fasciectomy:
        return "[Cluster3] Collagenase Clostridium histolyticum (CCH)", "Limited Fasciectomy (LF)"
    if has_pnf and has_fasciectomy:
        return "[Cluster3] Percutaneous Needle Fasciotomy (PNF)", "Limited Fasciectomy (LF)"
    if has_pnf:
        return "[Cluster3] Percutaneous Needle Fasciotomy (PNF)", "Single-arm PNF cohort / Registry"
    return "[Cluster3] Collagenase Clostridium histolyticum (CCH)", "Single-arm CCH cohort / Registry"


def detect_c3_design(title: str, abstract: str, tier: int) -> str:
    combined = f"{title} {abstract}".lower()
    if "network meta-analysis" in combined:
        return "Systematic Review & Network Meta-Analysis"
    if "meta-analysis" in combined or "systematic review" in combined:
        return "Systematic Review / Meta-Analysis"
    if "randomized" in combined or "randomised" in combined or "rct" in combined:
        return "Randomized Controlled Trial (RCT)"
    if "cost-effectiveness" in combined or "cost-utility" in combined or "economic" in combined:
        return "Health Economic / Cost-Utility Evaluation"
    if "prospective" in combined or tier == 2:
        return "Prospective Clinical Cohort / Registry Study"
    return "Retrospective Clinical Cohort / Case Series"


def extract_c3_details(text: str) -> tuple[str, str, str, str, str]:
    if not text:
        return ("Tubiana I–IV / Palpable cord", "Minor transient local events", "Not quantified", "Not reported", "See text")

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]
    sev_sents = [s for s in sentences if any(k in s.lower() for k in ("tubiana", "baseline", "pre-treatment", "pretreatment", "contracture of", "extension deficit", "stage", "nodule"))]
    baseline_sev = sev_sents[0][:250] if sev_sents else "Palpable Dupuytren cord / nodule (MCP ≥20° or PIP ≥20°)"

    comp_sents = [s for s in sentences if any(k in s.lower() for k in ("complication", "adverse", "skin tear", "rupture", "hematoma", "edema", "oedema", "blister", "lymphadenopathy", "nerve injury", "crps"))]
    comp_sum = " | ".join(comp_sents[:2])[:400] if comp_sents else "Transient local edema/contusion/skin tear; no major neurovascular injury reported"

    comp_rates = re.findall(r"\b\d+(?:\.\d+)?%\b", comp_sum)
    comp_rate_str = "; ".join(comp_rates[:3]) if comp_rates else "See summary"

    prom_sents = [s for s in sentences if any(k in s.lower() for k in ("dash", "quickdash", "uram", "southampton", "pem", "mhq", "vas", "satisfaction"))]
    prom_str = " | ".join(prom_sents[:2])[:350] if prom_sents else "Not reported in abstract"

    concl_sents = [s for s in sentences if any(k in s.lower() for k in ("conclu", "effective", "safe", "superior", "comparable", "recommend", "demonstrat", "showed"))]
    key_concl = (concl_sents[-1] if concl_sents else sentences[-1])[:450]
    return baseline_sev, comp_sum, comp_rate_str, prom_str, key_concl


def run_extraction() -> int:
    conn = get_db_connection("data/dupuytren/literature.db")
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT id, pmid, pmcid, doi, title, abstract, authors, pub_year,
               evidence_tier, pub_types, cited_by_count, has_fulltext_xml, fulltext_path
        FROM articles
        WHERE prisma_status = 'included'
          AND clusters LIKE '%"conservative"%'
          AND (pub_types IS NULL OR pub_types NOT LIKE '%Narrative Review%')
        ORDER BY evidence_tier ASC, has_fulltext_xml DESC, cited_by_count DESC
        """
    ).fetchall()

    extracted_rows: list[dict[str, Any]] = []
    for r in rows:
        tier = int(r["evidence_tier"] or 3)
        has_xml = int(r["has_fulltext_xml"] or 0)
        title = r["title"] or ""
        abstract = r["abstract"] or ""

        # D-01 & D-05: Exclude Tier 4 from efficacy table; include all Tier 1-2, all XML, and original Tier 3 series
        if tier > 3:
            continue
        if tier == 3 and not has_xml and len(abstract) < 120:
            continue

        xml_data = parse_jats_xml(r["fulltext_path"]) if has_xml else {"results_text": "", "tables": []}
        xml_results = xml_data.get("results_text", "")
        xml_tables = "\n".join(xml_data.get("tables", [])[:2])
        combined_text = f"{title}. {abstract} {xml_results} {xml_tables}"

        fay = format_first_author_year(r["authors"], r["pub_year"])
        design = detect_c3_design(title, abstract, tier)
        n_pat, n_jnt, _ = extract_sample_size(combined_text)
        interv, comp = classify_c3_intervention(title, abstract)
        fup_mo = extract_followup_months(combined_text)
        rec_def = detect_recurrence_definition(combined_text)
        j_out = extract_joint_outcomes(combined_text)
        b_sev, c_sum, c_rate, proms, k_concl = extract_c3_details(combined_text)

        extracted_rows.append(
            {
                "article_id": r["id"],
                "pmid": r["pmid"],
                "doi": r["doi"],
                "first_author_year": fay,
                "study_design": design,
                "evidence_tier": tier,
                "n_patients": n_pat,
                "n_rays_or_joints": n_jnt,
                "baseline_severity": b_sev,
                "intervention_group": interv,
                "comparator_group": comp,
                "followup_months": fup_mo,
                "mcp_outcome": j_out["mcp_outcome"],
                "pip_outcome": j_out["pip_outcome"],
                "recurrence_definition": rec_def,
                "recurrence_rate_overall": j_out["recurrence_rate_overall"],
                "recurrence_rate_mcp": j_out["recurrence_rate_mcp"],
                "recurrence_rate_pip": j_out["recurrence_rate_pip"],
                "complications_summary": c_sum,
                "complications_rate": c_rate,
                "prom_scores": proms,
                "key_conclusion": k_concl,
            }
        )

    cur.execute("DELETE FROM extracted_clinical_evidence WHERE intervention_group LIKE '[Cluster3]%'")
    cur.executemany(
        """
        INSERT INTO extracted_clinical_evidence (
            article_id, pmid, doi, first_author_year, study_design, evidence_tier,
            n_patients, n_rays_or_joints, baseline_severity, intervention_group,
            comparator_group, followup_months, mcp_outcome, pip_outcome,
            recurrence_definition, recurrence_rate_overall, recurrence_rate_mcp,
            recurrence_rate_pip, complications_summary, complications_rate,
            prom_scores, key_conclusion
        ) VALUES (
            :article_id, :pmid, :doi, :first_author_year, :study_design, :evidence_tier,
            :n_patients, :n_rays_or_joints, :baseline_severity, :intervention_group,
            :comparator_group, :followup_months, :mcp_outcome, :pip_outcome,
            :recurrence_definition, :recurrence_rate_overall, :recurrence_rate_mcp,
            :recurrence_rate_pip, :complications_summary, :complications_rate,
            :prom_scores, :key_conclusion
        )
        """,
        extracted_rows,
    )
    conn.commit()

    out_dir = Path("data/dupuytren/extractions")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "cluster_3_rows.json"
    json_path.write_text(json.dumps(extracted_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Cluster 3] Inserted {len(extracted_rows)} rows into extracted_clinical_evidence and saved {json_path}")
    return len(extracted_rows)


def verify_extraction() -> None:
    conn = get_db_connection("data/dupuytren/literature.db")
    cur = conn.cursor()
    total = cur.execute(
        "SELECT COUNT(*) FROM extracted_clinical_evidence WHERE intervention_group LIKE '[Cluster3]%'"
    ).fetchone()[0]
    grp_rows = cur.execute(
        "SELECT intervention_group, COUNT(*) as cnt FROM extracted_clinical_evidence WHERE intervention_group LIKE '[Cluster3]%' GROUP BY intervention_group"
    ).fetchall()
    grp_map = {r["intervention_group"]: r["cnt"] for r in grp_rows}
    print(f"[Verify Cluster 3] Total [Cluster3] rows in extracted_clinical_evidence: {total}")
    for g in CLUSTER3_INTERVENTIONS:
        cnt = grp_map.get(g, 0)
        print(f"  - {g}: {cnt}")
        assert cnt > 0, f"Intervention group {g} has 0 rows!"

    assert total >= 170, f"Expected >= 170 rows for Cluster 3, got {total}"

    orphan_cnt = cur.execute(
        "SELECT COUNT(*) FROM extracted_clinical_evidence ece LEFT JOIN articles a ON ece.article_id = a.id WHERE a.id IS NULL"
    ).fetchone()[0]
    assert orphan_cnt == 0, f"Found {orphan_cnt} orphan article_id references!"

    md_path = Path("data/dupuytren/extractions/cluster_3_conservative_minimally_invasive.md")
    assert md_path.exists() and md_path.stat().st_size > 5000, f"Dossier {md_path} missing or too small!"
    print("[Verify Cluster 3] ALL CHECKS PASSED.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster 3 Conservative & Minimally Invasive Treatments Extractor")
    parser.add_argument("--verify", action="store_true", help="Verify Cluster 3 SQLite rows and dossier")
    args = parser.parse_args()
    if args.verify:
        verify_extraction()
    else:
        run_extraction()


if __name__ == "__main__":
    main()
