# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = []
# ///
"""Cluster 1 Structured Extractor: Etiology, Epidemiology & Genetics (Phase 2, Plan 02-01).

Populates `extracted_mechanisms` across the 7 Cluster 1 categories, exports
`data/dupuytren/extractions/cluster_1_rows.json`, and validates the analytical dossier
`data/dupuytren/extractions/cluster_1_etiology_genetics.md`.
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
    extract_sample_size,
    extract_statistical_metrics,
    format_first_author_year,
    get_db_connection,
    parse_jats_xml,
)

CLUSTER1_CATEGORIES = (
    "Epidemiology & Prevalence",
    "Genetics & GWAS",
    "Wnt Signaling Genetics",
    "Metabolic & Lifestyle Risk Factors",
    "Occupational & Vibration Exposure",
    "Dupuytren Diathesis & Associated Fibromatoses",
    "Epigenetics & Non-coding RNA",
)

CATEGORY_PATTERNS = {
    "Wnt Signaling Genetics": r"\b(wnt\w*|sfrp4|wnt7b|wnt2|wnt4|rspo2|ctnnb1|beta-catenin|β-catenin|dkk\d?|fzd\d?|axin2|lef1|tcf\w*)\b",
    "Epigenetics & Non-coding RNA": r"\b(epigenet\w*|methylat\w*|histone|h3k27\w*|crebbp|ep300|bromodomain|micro-?rna|mirna|mir-\d+|lncrna|non-coding\s+rna|meg3|telomer\w*)\b",
    "Genetics & GWAS": r"\b(gwas|genome-wide|polygenic|prs\b|heritabil\w*|snp\b|rs\d{4,}|neandertal\w*|epdr1|mmp14|chst6|mafb|nedd4|raly|lmna|exome|mendelian\s+randomization|twin\w*|familial|susceptibil\w*)\b",
    "Occupational & Vibration Exposure": r"\b(vibrat\w*|havs\b|manual\s+labou?r\w*|occupational|workplace|heavy\s+work|climber\w*|rock\s+climbing|trauma\w*|hand\s+injury| biomechanical\s+exposure)\b",
    "Dupuytren Diathesis & Associated Fibromatoses": r"\b(diathesis|ledderhose|plantar\s+fibromatosis|peyronie|garrod\w*|knuckle\s+pad\w*|frozen\s+shoulder|adhesive\s+capsulitis|trigger\s+finger|ectopic\s+fibromatosis|abe\s+score)\b",
    "Metabolic & Lifestyle Risk Factors": r"\b(diabet\w*|glycem\w*|hba1c|alcohol\w*|smoking|smoker\w*|tobacco|body\s+mass\s+index|bmi\b|obes\w*|adipos\w*|hyperlipid\w*|cholesterol|statin\w*|epileps\w*|anticonvulsant\w*|liver\s+disease|mortality|life\s+expectancy)\b",
    "Epidemiology & Prevalence": r"\b(prevalence|incidence|epidemiolog\w*|population-based|nationwide|global\s+prevalence|worldwide|demograph\w*|geographic\w*|ethnic\w*|african|asian|nordic|scandinavian)\b",
}

GENE_TARGET_RE = re.compile(
    r"\b(WNT7B|WNT2|WNT4|WNT3A|SFRP4|RSPO2|EPDR1|CTNNB1|DKK1|MAFB|MMP14|MMP8|CHST6|NEDD4|RALY|LMNA|ZBTB40|IGF2|CREBBP|EP300|MEG3|TGFB1|TNF|COL1A1|COL3A1|ACTA2|miR-\d+[a-z]?|rs\d{4,})\b"
)


def detect_study_model(title: str, abstract: str, tier: int) -> str:
    combined = f"{title} {abstract}".lower()
    if "mendelian randomization" in combined:
        return "Two-sample Mendelian Randomization / GWAS summary stats"
    if "genome-wide association" in combined or "gwas" in combined:
        return "Genome-Wide Association Study (GWAS) / Biobank Meta-Analysis"
    if "meta-analysis" in combined or "systematic review" in combined:
        return "Systematic Review & Meta-Analysis"
    if "twin" in combined:
        return "Population-based Twin / Heritability Cohort"
    if "biobank" in combined or "nationwide" in combined or "national database" in combined or "registry" in combined:
        return "Large Population Biobank / National Registry Cohort"
    if "exome" in combined or "pedigree" in combined or "family" in combined:
        return "Familial Pedigree / Whole-Exome Sequencing"
    if "methylation" in combined or "mirna" in combined or "rna-seq" in combined or "fibroblast" in combined:
        return "Patient Tissue / Primary Fibroblast Functional Genomics"
    if tier in (1, 2):
        return "Prospective / Case-Control Clinical Cohort"
    return "Observational Clinical Series / Case-Control Study"


def assign_cluster1_categories(title: str, abstract: str, xml_text: str) -> list[str]:
    primary_text = f"{title} {abstract}"
    full_text = f"{primary_text} {xml_text[:3000]}"
    matched: list[str] = []
    for cat, pat in CATEGORY_PATTERNS.items():
        if re.search(pat, primary_text, flags=re.IGNORECASE):
            matched.append(cat)
    if not matched:
        for cat, pat in CATEGORY_PATTERNS.items():
            if re.search(pat, full_text, flags=re.IGNORECASE):
                matched.append(cat)
                break
    if not matched:
        matched.append("Epidemiology & Prevalence")
    return matched[:2]


def extract_targets(text: str, cat: str) -> str:
    found: list[str] = []
    for m in GENE_TARGET_RE.finditer(text):
        tok = m.group(1)
        if tok not in found:
            found.append(tok)
    tl = text.lower()
    pathway_map = [
        ("wnt", "Canonical/Non-canonical Wnt signaling"),
        ("diabetes", "Hyperglycemia / AGE-RAGE axis"),
        ("bmi", "Adiposity / BMI inverse genetic correlation"),
        ("obesity", "Adipose-fibroblast metabolic axis"),
        ("alcohol", "Alcohol intake / hepatic metabolic toxicity"),
        ("smoking", "Microvascular hypoxia / tobacco exposure"),
        ("vibration", "Hand-Arm Vibration (HAV) mechanotransduction"),
        ("manual", "Cumulative mechanical palmar load"),
        ("ledderhose", "Palmoplantar fibromatosis shared diathesis"),
        ("peyronie", "Peyronie-Dupuytren shared WNT2/WNT7B susceptibility"),
        ("frozen shoulder", "Fibroproliferative shoulder-hand shared loci"),
        ("methylation", "DNA CpG methylation / epigenetic remodeling"),
        ("microrna", "Post-transcriptional miRNA-ECM regulation"),
    ]
    for kw, label in pathway_map:
        if kw in tl and label not in found:
            found.append(label)
    if not found:
        return cat
    return "; ".join(found[:6])


def build_mechanism_summary(title: str, abstract: str, results_text: str) -> tuple[str, str]:
    combined = f"{abstract or ''} {results_text or ''}".strip()
    if not combined:
        return title, "Supports epidemiological risk stratification in Dupuytren disease."
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", combined) if len(s.strip()) > 30]
    mech_sents = [
        s for s in sentences
        if any(k in s.lower() for k in ("associated", "identified", "demonstrated", "showed", "increased", "decreased", "prevalence", "risk", "locus", "loci", "expression", "variant", "protective", "correlation"))
    ]
    summary = " ".join((mech_sents[:2] if mech_sents else sentences[:2]))[:550]
    impl_sents = [
        s for s in sentences
        if any(k in s.lower() for k in ("conclude", "suggest", "implication", "target", "screening", "counseling", "prevention", "recurrence", "stratification", "treatment", "therapy"))
    ]
    implication = (impl_sents[-1] if impl_sents else sentences[-1])[:400]
    return summary or title, implication


def run_extraction() -> int:
    conn = get_db_connection("data/dupuytren/literature.db")
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT id, pmid, pmcid, doi, title, abstract, authors, pub_year,
               evidence_tier, pub_types, cited_by_count, has_fulltext_xml, fulltext_path
        FROM articles
        WHERE prisma_status = 'included'
          AND clusters LIKE '%"etiology"%'
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

        # D-01: Include all Tier 1-2, all Full-Text XML, and targeted Tier 3 original studies with substantive abstracts
        if tier > 3:
            continue
        if tier == 3 and not has_xml and len(abstract) < 120:
            continue

        xml_data = parse_jats_xml(r["fulltext_path"]) if has_xml else {"results_text": "", "methods_text": "", "tables": []}
        xml_results = xml_data.get("results_text", "")
        xml_tables = "\n".join(xml_data.get("tables", [])[:2])
        combined_text = f"{title}. {abstract} {xml_results} {xml_tables}"

        categories = assign_cluster1_categories(title, abstract, xml_results)
        fay = format_first_author_year(r["authors"], r["pub_year"])
        study_model = detect_study_model(title, abstract, tier)
        _, _, sample_desc = extract_sample_size(combined_text)
        quant_metrics = extract_statistical_metrics(combined_text)
        if not quant_metrics:
            quant_metrics = (abstract[:280] + "...") if len(abstract) > 280 else (abstract or title)
        mech_sum, ther_impl = build_mechanism_summary(title, abstract, xml_results)

        for cat in categories:
            targets = extract_targets(combined_text, cat)
            extracted_rows.append(
                {
                    "article_id": r["id"],
                    "pmid": r["pmid"],
                    "doi": r["doi"],
                    "first_author_year": fay,
                    "category": cat,
                    "targets_genes_pathways": targets,
                    "study_model": study_model,
                    "sample_size": sample_desc[:200],
                    "quantitative_findings": quant_metrics[:600],
                    "mechanism_summary": mech_sum,
                    "therapeutic_implication": ther_impl,
                }
            )

    placeholders = ",".join("?" for _ in CLUSTER1_CATEGORIES)
    cur.execute(f"DELETE FROM extracted_mechanisms WHERE category IN ({placeholders})", CLUSTER1_CATEGORIES)

    cur.executemany(
        """
        INSERT INTO extracted_mechanisms (
            article_id, pmid, doi, first_author_year, category,
            targets_genes_pathways, study_model, sample_size,
            quantitative_findings, mechanism_summary, therapeutic_implication
        ) VALUES (
            :article_id, :pmid, :doi, :first_author_year, :category,
            :targets_genes_pathways, :study_model, :sample_size,
            :quantitative_findings, :mechanism_summary, :therapeutic_implication
        )
        """,
        extracted_rows,
    )
    conn.commit()

    out_dir = Path("data/dupuytren/extractions")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "cluster_1_rows.json"
    json_path.write_text(json.dumps(extracted_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Cluster 1] Inserted {len(extracted_rows)} rows into extracted_mechanisms and saved {json_path}")
    return len(extracted_rows)


def verify_extraction() -> None:
    conn = get_db_connection("data/dupuytren/literature.db")
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in CLUSTER1_CATEGORIES)
    total = cur.execute(
        f"SELECT COUNT(*) FROM extracted_mechanisms WHERE category IN ({placeholders})",
        CLUSTER1_CATEGORIES,
    ).fetchone()[0]

    cat_rows = cur.execute(
        f"SELECT category, COUNT(*) as cnt FROM extracted_mechanisms WHERE category IN ({placeholders}) GROUP BY category",
        CLUSTER1_CATEGORIES,
    ).fetchall()
    cat_map = {r["category"]: r["cnt"] for r in cat_rows}
    print(f"[Verify Cluster 1] Total rows in extracted_mechanisms: {total}")
    for c in CLUSTER1_CATEGORIES:
        cnt = cat_map.get(c, 0)
        print(f"  - {c}: {cnt}")
        assert cnt > 0, f"Category {c} has 0 rows!"

    assert total >= 120, f"Expected >= 120 rows for Cluster 1, got {total}"

    orphan_cnt = cur.execute(
        "SELECT COUNT(*) FROM extracted_mechanisms em LEFT JOIN articles a ON em.article_id = a.id WHERE a.id IS NULL"
    ).fetchone()[0]
    assert orphan_cnt == 0, f"Found {orphan_cnt} orphan article_id references!"

    md_path = Path("data/dupuytren/extractions/cluster_1_etiology_genetics.md")
    assert md_path.exists() and md_path.stat().st_size > 5000, f"Dossier {md_path} missing or too small!"
    print("[Verify Cluster 1] ALL CHECKS PASSED.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster 1 Etiology, Epidemiology & Genetics Extractor")
    parser.add_argument("--verify", action="store_true", help="Verify Cluster 1 SQLite rows and dossier")
    args = parser.parse_args()
    if args.verify:
        verify_extraction()
    else:
        run_extraction()


if __name__ == "__main__":
    main()
