# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = []
# ///
"""Cluster 2 Structured Extractor: Molecular & Cellular Pathogenesis (Phase 2, Plan 02-02).

Populates `extracted_mechanisms` across the 6 Cluster 2 categories, exports
`data/dupuytren/extractions/cluster_2_rows.json`, and validates the analytical dossier
`data/dupuytren/extractions/cluster_2_pathogenesis.md`.
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

CLUSTER2_CATEGORIES = (
    "Myofibroblast Biology & Cellular Origin",
    "TGF-beta / Smad Canonical & Non-canonical Signaling",
    "Mechanotransduction & YAP/TAZ",
    "Immune Microenvironment, Macrophages & TNF",
    "Extracellular Matrix, Collagen III/I & MMPs/TIMPs",
    "Single-Cell & Spatial Multi-Omics",
)

CATEGORY_PATTERNS = {
    "Single-Cell & Spatial Multi-Omics": r"\b(single-cell|scrna-seq|snrna-seq|rna-seq|transcriptom\w*|spatial\s+transcriptom\w*|proteom\w*|mass\s+spectrom\w*|cytof|mass\s+cytometry|multi-omic\w*|microarray|wgcna)\b",
    "Mechanotransduction & YAP/TAZ": r"\b(mechanotransduct\w*|mechanosens\w*|yap1?|taz|wwtr1|hippo|verteporfin|stiffness|mechanical\s+stress|mechanical\s+tension|traction|integrin\w*|focal\s+adhesion|fak\b|rhoa|rock\d?|piezo\d?|trpv4|rheolog\w*)\b",
    "TGF-beta / Smad Canonical & Non-canonical Signaling": r"\b(tgf-?β\w*|tgf-?beta\w*|tgfb\d?|smad\d?|alk5|tgfbr\d?|p38|mapk|erk1/2|erk\b|jnk|pi3k|akt\b|mtor|pirfenidone|nintedanib|ctgf|ccn2|pdgf\w*)\b",
    "Immune Microenvironment, Macrophages & TNF": r"\b(tnf-?α|tnf-?alpha|tumor\s+necrosis\s+factor|adalimumab|anti-tnf|macrophage\w*|cd68|cd163|mast\s+cell\w*|t-cell\w*|lymphocyte\w*|il-1\b|il-1β|il-6|il-13|il-4|il-17|cytokine\w*|chemokine\w*|cxcl\w*|ccl\w*)\b",
    "Extracellular Matrix, Collagen III/I & MMPs/TIMPs": r"\b(collagen\s+(?:type\s+)?(?:i|iii|iv|v|vi|1|3|homotrimer)\b|col1a1|col1a2|col3a1|col6a\d|mmp-?\d+|matrix\s+metalloproteinase\w*|timp-?\d+|lysyl\s+oxidase|lox\w*|plod\w*|periostin|postn|tenascin|tnc\b|fibronectin|fn1|extracellular\s+matrix|decellularized)\b",
    "Myofibroblast Biology & Cellular Origin": r"\b(myofibroblast\w*|alpha-sma|α-sma|acta2|pericyte\w*|fibroblast\w*|cd34|cd90|thy1|pdpn|podoplanin|icam1|contractil\w*|nodule\w*|cord\w*|apopto\w*|proliferat\w*)\b",
}

MOL_TARGET_RE = re.compile(
    r"\b(TGF-?β1?|TGFB1|SMAD2|SMAD3|SMAD4|SMAD7|YAP1?|TAZ|WWTR1|TNF-?α?|TNFR1|TNFR2|IL-6|IL-13|IL-1β|CXCL14|CCL2|ACTA2|α-SMA|COL1A1|COL1A2|COL3A1|COL6A1|MMP1|MMP2|MMP9|MMP13|MMP14|TIMP1|TIMP2|LOX|LOXL2|POSTN|TNC|FN1|ICAM1|PDPN|CD34|CD90|THY1|CD68|CD163|PDGFRB|SFRP4|WNT7B|CTNNB1|ERK1/2|p38|AKT|ROCK1/2)\b"
)


def detect_exp_model(title: str, abstract: str, tier: int) -> str:
    combined = f"{title} {abstract}".lower()
    if "single-cell" in combined or "scrna" in combined or "cytof" in combined:
        return "Single-cell RNA-seq / CyTOF Atlas of Human Nodule & Cord"
    if "3d " in combined or "decellularized" in combined or "collagen lattice" in combined or "hydrogel" in combined:
        return "3D Biomimetic / Decellularized ECM & Collagen Lattice Model"
    if "bioreactor" in combined or "traction" in combined or "atomic force" in combined or "rheolog" in combined:
        return "Biomechanical Traction / AFM Stiffness Assay on Primary Cells"
    if "rna-seq" in combined or "transcriptom" in combined or "proteom" in combined or "microarray" in combined:
        return "Bulk Transcriptomic / Proteomic Profiling (Patient Tissue)"
    if "immunohistochem" in combined or "histolog" in combined or "electron microscop" in combined:
        return "Human Surgical Explant Histopathology / IHC (Nodule vs Cord)"
    if "randomised" in combined or "randomized" in combined or "phase 2" in combined:
        return "Translational Biomarker / Window-of-Opportunity Clinical Trial"
    return "Primary Human Dupuytren Myofibroblast / Ex Vivo Tissue Culture"


def assign_cluster2_categories(title: str, abstract: str, xml_text: str) -> list[str]:
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
        matched.append("Myofibroblast Biology & Cellular Origin")
    return matched[:2]


def extract_mol_targets(text: str, cat: str) -> str:
    found: list[str] = []
    for m in MOL_TARGET_RE.finditer(text):
        tok = m.group(1)
        if tok not in found:
            found.append(tok)
    if not found:
        return cat
    return "; ".join(found[:7])


def build_mol_summary(title: str, abstract: str, results_text: str) -> tuple[str, str]:
    combined = f"{abstract or ''} {results_text or ''}".strip()
    if not combined:
        return title, "Identifies molecular regulator of myofibroblast contractility and ECM deposition."
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", combined) if len(s.strip()) > 30]
    mech_sents = [
        s for s in sentences
        if any(k in s.lower() for k in ("myofibroblast", "fibroblast", "expression", "signaling", "inhibited", "induced", "collagen", "contractil", "nodule", "cord", "macrophage", "tnf", "tgf", "yap", "matrix"))
    ]
    summary = " ".join((mech_sents[:2] if mech_sents else sentences[:2]))[:550]
    impl_sents = [
        s for s in sentences
        if any(k in s.lower() for k in ("target", "therap", "inhibit", "attenuat", "prevent", "adalimumab", "pirfenidone", "verteporfin", "nintedanib", "treatment", "antifibrotic"))
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
          AND clusters LIKE '%"pathogenesis"%'
          AND (pub_types IS NULL OR pub_types NOT LIKE '%Narrative Review%')
        ORDER BY has_fulltext_xml DESC, evidence_tier ASC, cited_by_count DESC
        """
    ).fetchall()

    extracted_rows: list[dict[str, Any]] = []
    for r in rows:
        tier = int(r["evidence_tier"] or 3)
        has_xml = int(r["has_fulltext_xml"] or 0)
        title = r["title"] or ""
        abstract = r["abstract"] or ""

        if tier > 3:
            continue
        if tier == 3 and not has_xml and len(abstract) < 120:
            continue

        xml_data = parse_jats_xml(r["fulltext_path"]) if has_xml else {"results_text": "", "tables": []}
        xml_results = xml_data.get("results_text", "")
        xml_tables = "\n".join(xml_data.get("tables", [])[:2])
        combined_text = f"{title}. {abstract} {xml_results} {xml_tables}"

        categories = assign_cluster2_categories(title, abstract, xml_results)
        fay = format_first_author_year(r["authors"], r["pub_year"])
        study_model = detect_exp_model(title, abstract, tier)
        _, _, sample_desc = extract_sample_size(combined_text)
        quant_metrics = extract_statistical_metrics(combined_text)
        if not quant_metrics:
            quant_metrics = (abstract[:280] + "...") if len(abstract) > 280 else (abstract or title)
        mech_sum, ther_impl = build_mol_summary(title, abstract, xml_results)

        for cat in categories:
            targets = extract_mol_targets(combined_text, cat)
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

    placeholders = ",".join("?" for _ in CLUSTER2_CATEGORIES)
    cur.execute(f"DELETE FROM extracted_mechanisms WHERE category IN ({placeholders})", CLUSTER2_CATEGORIES)

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
    json_path = out_dir / "cluster_2_rows.json"
    json_path.write_text(json.dumps(extracted_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Cluster 2] Inserted {len(extracted_rows)} rows into extracted_mechanisms and saved {json_path}")
    return len(extracted_rows)


def verify_extraction() -> None:
    conn = get_db_connection("data/dupuytren/literature.db")
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in CLUSTER2_CATEGORIES)
    total = cur.execute(
        f"SELECT COUNT(*) FROM extracted_mechanisms WHERE category IN ({placeholders})",
        CLUSTER2_CATEGORIES,
    ).fetchone()[0]

    cat_rows = cur.execute(
        f"SELECT category, COUNT(*) as cnt FROM extracted_mechanisms WHERE category IN ({placeholders}) GROUP BY category",
        CLUSTER2_CATEGORIES,
    ).fetchall()
    cat_map = {r["category"]: r["cnt"] for r in cat_rows}
    print(f"[Verify Cluster 2] Total rows in extracted_mechanisms: {total}")
    for c in CLUSTER2_CATEGORIES:
        cnt = cat_map.get(c, 0)
        print(f"  - {c}: {cnt}")
        assert cnt > 0, f"Category {c} has 0 rows!"

    assert total >= 160, f"Expected >= 160 rows for Cluster 2, got {total}"

    orphan_cnt = cur.execute(
        "SELECT COUNT(*) FROM extracted_mechanisms em LEFT JOIN articles a ON em.article_id = a.id WHERE a.id IS NULL"
    ).fetchone()[0]
    assert orphan_cnt == 0, f"Found {orphan_cnt} orphan article_id references!"

    md_path = Path("data/dupuytren/extractions/cluster_2_pathogenesis.md")
    assert md_path.exists() and md_path.stat().st_size > 5000, f"Dossier {md_path} missing or too small!"
    print("[Verify Cluster 2] ALL CHECKS PASSED.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster 2 Molecular & Cellular Pathogenesis Extractor")
    parser.add_argument("--verify", action="store_true", help="Verify Cluster 2 SQLite rows and dossier")
    args = parser.parse_args()
    if args.verify:
        verify_extraction()
    else:
        run_extraction()


if __name__ == "__main__":
    main()
