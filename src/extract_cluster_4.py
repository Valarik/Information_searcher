# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = []
# ///
"""Cluster 4 Structured Extractor: Surgical Treatments, Complications & Long-Term Outcomes (Phase 2, Plan 02-04).

Populates `extracted_clinical_evidence` with `[Cluster4]` rows (including the 23 Tier 4
Rare Severe Complication cases kept distinct per D-05), exports
`data/dupuytren/extractions/cluster_4_rows.json`, and validates
`data/dupuytren/extractions/cluster_4_surgical_and_outcomes.md`.
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

CLUSTER4_INTERVENTIONS = (
    "[Cluster4] Limited / Selective Fasciectomy (LF)",
    "[Cluster4] Dermofasciectomy (DF) & Skin Grafting",
    "[Cluster4] Open Palm (McCash) & Z-Plasty/Brunner",
    "[Cluster4] WALANT Hand Surgery",
    "[Cluster4] Percutaneous Aponeurotomy + Lipofilling (PALF/SVF)",
    "[Cluster4] Skeletal Traction / Digit Widget & Salvage",
    "[Cluster4] Comparative Surgery vs PNF/CCH Long-Term",
    "[Cluster4] Rare Severe Complication [D-05]",
)


def classify_c4_intervention(title: str, abstract: str, pub_types: str) -> tuple[str, str]:
    if "Rare Complication" in (pub_types or ""):
        return "[Cluster4] Rare Severe Complication [D-05]", "Case report / Rare adverse event [D-05]"

    t = f"{title} {abstract}".lower()
    if any(k in t for k in ("walant", "wide awake", "wide-awake", "no tourniquet")):
        return "[Cluster4] WALANT Hand Surgery", "Tourniquet + General/Regional Anesthesia"
    if any(k in t for k in ("lipofill", "fat graft", "adipose", "stromal vascular", "palf")):
        return "[Cluster4] Percutaneous Aponeurotomy + Lipofilling (PALF/SVF)", "Limited Fasciectomy / PNF alone"
    if any(k in t for k in ("digit widget", "external fixat", "skeletal traction", "distraction", "arthrodes", "amputat", "osteotom", "salvage")):
        return "[Cluster4] Skeletal Traction / Digit Widget & Salvage", "Single-stage Fasciectomy / Salvage cohort"
    if any(k in t for k in ("dermofasciectom", "skin graft", "full-thickness graft", "ftsg", "firebreak")):
        return "[Cluster4] Dermofasciectomy (DF) & Skin Grafting", "Limited Fasciectomy without graft"
    if any(k in t for k in ("mccash", "open palm", "open-palm", "z-plast", "bruner", "brunner")):
        return "[Cluster4] Open Palm (McCash) & Z-Plasty/Brunner", "Primary skin closure / Alternative incision"

    has_cch_or_pnf = any(k in t for k in ("collagenase", "cch", "xiapex", "xiaflex", "needle fasciotomy", "needle aponeurotomy", "pnf"))
    has_surg = any(k in t for k in ("fasciectomy", "surgery", "surgical", "aponeurectomy"))
    if has_cch_or_pnf and has_surg:
        return "[Cluster4] Comparative Surgery vs PNF/CCH Long-Term", "PNF and/or Collagenase (CCH)"
    if any(k in t for k in ("5-year", "five-year", "10-year", "ten-year", "long-term", "recurrence", "uram", "quickdash", "dash", "southampton")):
        return "[Cluster4] Comparative Surgery vs PNF/CCH Long-Term", "Long-term Outcomes / PROM Cohort"

    return "[Cluster4] Limited / Selective Fasciectomy (LF)", "Standard Limited Fasciectomy Cohort"


def detect_c4_design(title: str, abstract: str, tier: int, pub_types: str) -> str:
    if "Rare Complication" in (pub_types or ""):
        return "Clinical Case Report — Rare Complication [D-05]"
    combined = f"{title} {abstract}".lower()
    if "network meta-analysis" in combined:
        return "Systematic Review & Network Meta-Analysis"
    if "meta-analysis" in combined or "systematic review" in combined:
        return "Systematic Review / Meta-Analysis"
    if "randomized" in combined or "randomised" in combined or "rct" in combined or "disc trial" in combined:
        return "Randomized Controlled Trial (RCT)"
    if "prospective" in combined or tier == 2:
        return "Prospective Surgical Cohort / National Registry"
    return "Retrospective Surgical Series / Comparative Cohort"


def extract_c4_details(text: str) -> tuple[str, str, str, str, str]:
    if not text:
        return ("Tubiana II–IV / Severe contracture", "Postoperative surgical morbidity profile", "Not quantified", "Not reported", "See text")

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]
    sev_sents = [s for s in sentences if any(k in s.lower() for k in ("tubiana", "baseline", "preoperative", "contracture", "extension deficit", "pip", "mcp", "recurrent"))]
    baseline_sev = sev_sents[0][:250] if sev_sents else "Primary or recurrent Dupuytren contracture (MCP/PIP)"

    comp_sents = [s for s in sentences if any(k in s.lower() for k in ("complication", "nerve injury", "digital nerve", "artery", "ischemia", "ischaemia", "necrosis", "crps", "complex regional pain", "infection", "hematoma", "stiffness", "amputation", "pseudoaneurysm", "tendon rupture"))]
    comp_sum = " | ".join(comp_sents[:2])[:400] if comp_sents else "Standard surgical morbidity (wound healing, transient paresthesia, stiffness)"

    comp_rates = re.findall(r"\b\d+(?:\.\d+)?%\b", comp_sum)
    comp_rate_str = "; ".join(comp_rates[:3]) if comp_rates else "See summary"

    prom_sents = [s for s in sentences if any(k in s.lower() for k in ("dash", "quickdash", "uram", "southampton", "pem", "mhq", "vas", "satisfaction"))]
    prom_str = " | ".join(prom_sents[:2])[:350] if prom_sents else "Not reported in abstract"

    concl_sents = [s for s in sentences if any(k in s.lower() for k in ("conclu", "effective", "recurrence", "recommend", "demonstrat", "showed", "outcome"))]
    key_concl = (concl_sents[-1] if concl_sents else sentences[-1])[:450]
    return baseline_sev, comp_sum, comp_rate_str, prom_str, key_concl


def run_extraction() -> int:
    conn = get_db_connection("data/dupuytren/literature.db")
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT id, pmid, pmcid, doi, title, abstract, authors, pub_year,
               evidence_tier, pub_types, cited_by_count, has_fulltext_xml, fulltext_path, clusters
        FROM articles
        WHERE prisma_status = 'included'
          AND (
            pub_types LIKE '%Rare Complication%'
            OR (
              (clusters LIKE '%"surgical"%' OR clusters LIKE '%"outcomes"%')
              AND (pub_types IS NULL OR pub_types NOT LIKE '%Narrative Review%')
            )
          )
        ORDER BY evidence_tier ASC, has_fulltext_xml DESC, cited_by_count DESC
        """
    ).fetchall()

    extracted_rows: list[dict[str, Any]] = []
    for r in rows:
        tier = int(r["evidence_tier"] or 3)
        has_xml = int(r["has_fulltext_xml"] or 0)
        title = r["title"] or ""
        abstract = r["abstract"] or ""
        pub_types = r["pub_types"] or ""
        is_rare = "Rare Complication" in pub_types

        if tier == 4 and not is_rare:
            continue
        if tier == 3 and not has_xml and len(abstract) < 120:
            continue

        xml_data = parse_jats_xml(r["fulltext_path"]) if has_xml else {"results_text": "", "tables": []}
        xml_results = xml_data.get("results_text", "")
        xml_tables = "\n".join(xml_data.get("tables", [])[:2])
        combined_text = f"{title}. {abstract} {xml_results} {xml_tables}"

        fay = format_first_author_year(r["authors"], r["pub_year"])
        design = detect_c4_design(title, abstract, tier, pub_types)
        n_pat, n_jnt, _ = extract_sample_size(combined_text)
        if is_rare and n_pat is None:
            n_pat = 1
        interv, comp = classify_c4_intervention(title, abstract, pub_types)
        fup_mo = extract_followup_months(combined_text)
        rec_def = detect_recurrence_definition(combined_text)
        j_out = extract_joint_outcomes(combined_text)
        b_sev, c_sum, c_rate, proms, k_concl = extract_c4_details(combined_text)

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

    cur.execute("DELETE FROM extracted_clinical_evidence WHERE intervention_group LIKE '[Cluster4]%'")
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
    json_path = out_dir / "cluster_4_rows.json"
    json_path.write_text(json.dumps(extracted_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Cluster 4] Inserted {len(extracted_rows)} rows into extracted_clinical_evidence and saved {json_path}")
    return len(extracted_rows)


def verify_extraction() -> None:
    conn = get_db_connection("data/dupuytren/literature.db")
    cur = conn.cursor()
    total = cur.execute(
        "SELECT COUNT(*) FROM extracted_clinical_evidence WHERE intervention_group LIKE '[Cluster4]%'"
    ).fetchone()[0]
    grp_rows = cur.execute(
        "SELECT intervention_group, COUNT(*) as cnt FROM extracted_clinical_evidence WHERE intervention_group LIKE '[Cluster4]%' GROUP BY intervention_group"
    ).fetchall()
    grp_map = {r["intervention_group"]: r["cnt"] for r in grp_rows}
    print(f"[Verify Cluster 4] Total [Cluster4] rows in extracted_clinical_evidence: {total}")
    for g in CLUSTER4_INTERVENTIONS:
        cnt = grp_map.get(g, 0)
        print(f"  - {g}: {cnt}")
        assert cnt > 0, f"Intervention group {g} has 0 rows!"

    assert grp_map.get("[Cluster4] Rare Severe Complication [D-05]", 0) == 23, "Expected exactly 23 Rare Severe Complication [D-05] rows!"
    assert total >= 220, f"Expected >= 220 rows for Cluster 4, got {total}"

    orphan_cnt = cur.execute(
        "SELECT COUNT(*) FROM extracted_clinical_evidence ece LEFT JOIN articles a ON ece.article_id = a.id WHERE a.id IS NULL"
    ).fetchone()[0]
    assert orphan_cnt == 0, f"Found {orphan_cnt} orphan article_id references!"

    md_path = Path("data/dupuytren/extractions/cluster_4_surgical_and_outcomes.md")
    assert md_path.exists() and md_path.stat().st_size > 5000, f"Dossier {md_path} missing or too small!"
    print("[Verify Cluster 4] ALL CHECKS PASSED.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster 4 Surgical Treatments, Complications & Long-Term Outcomes Extractor")
    parser.add_argument("--verify", action="store_true", help="Verify Cluster 4 SQLite rows and dossier")
    args = parser.parse_args()
    if args.verify:
        verify_extraction()
    else:
        run_extraction()


if __name__ == "__main__":
    main()
