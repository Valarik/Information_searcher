# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pandas>=2.2.0",
#   "pyyaml>=6.0.1",
#   "markdown>=3.6",
# ]
# ///
"""Universal Nosology Schema Adapter, SQLite Explorer & Print-Ready HTML/CSV Exporter (Phase 4: UI-01, D-01..D-03).

Provides a 100% disease-agnostic data layer for any nosology configured in `configs/*.yaml`.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import markdown
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = PROJECT_ROOT / "configs"
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"

REQUIRED_UNIVERSAL_KEYS = [
    "nosology_meta",
    "staging_and_classification",
    "anatomical_or_subtype_distribution",
    "etiology_and_risk_factors",
    "pathogenesis_phases",
    "natural_history_and_dynamics",
    "modalities",
    "modules",
]

REQUIRED_MODALITY_KEYS = [
    "name",
    "group",
    "target_stage",
    "primary_efficacy",
    "remission_5y_pct",
    "remission_5y_num",
    "recurrence_1_2y",
    "recurrence_3y",
    "recurrence_5y_overall",
    "recurrence_5y_num",
    "recurrence_10y",
    "recurrence_by_subtype",
    "procediv_5y",
    "procediv_5y_num",
    "reintervention_5y",
    "complications_profile",
    "recovery_time",
    "pros",
    "cons",
]


def discover_nosologies(configs_dir: Path = CONFIGS_DIR) -> list[dict[str, Any]]:
    """Scan `configs/*.yaml` and return metadata for all configured nosologies."""
    items: list[dict[str, Any]] = []
    if not configs_dir.exists():
        return items
    for cfg_path in sorted(configs_dir.glob("*.yaml")):
        try:
            raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        meta = raw.get("nosology", {})
        nos_id = meta.get("id") or cfg_path.stem
        db_path = DATA_DIR / nos_id / "literature.db"
        kb_path = REPORTS_DIR / nos_id / "knowledge_base" / "kb_index.json"
        items.append(
            {
                "id": nos_id,
                "name_ru": meta.get("name_ru", nos_id),
                "name_en": meta.get("name_en", nos_id),
                "icd10": meta.get("icd10", "—"),
                "icd11": meta.get("icd11", "—"),
                "mesh_terms": meta.get("mesh_terms", []),
                "config_path": str(cfg_path),
                "has_db": db_path.exists(),
                "has_kb_index": kb_path.exists(),
                "raw_config": raw,
            }
        )
    return items


def get_sqlite_corpus_stats(db_path: Path) -> dict[str, int]:
    """Read live row counts from `data/<nosology>/literature.db`."""
    stats = {
        "unique_articles": 0,
        "included_articles": 0,
        "excluded_articles": 0,
        "fulltext_xml_count": 0,
        "clinical_trials_nct": 0,
        "extracted_mechanisms_rows": 0,
        "extracted_clinical_rows": 0,
        "tier_1": 0,
        "tier_2": 0,
        "tier_3": 0,
        "tier_4": 0,
    }
    if not db_path.exists():
        return stats
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        stats["unique_articles"] = cur.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        stats["included_articles"] = cur.execute(
            "SELECT COUNT(*) FROM articles WHERE prisma_status = 'included'"
        ).fetchone()[0]
        stats["excluded_articles"] = cur.execute(
            "SELECT COUNT(*) FROM articles WHERE prisma_status != 'included'"
        ).fetchone()[0]
        stats["fulltext_xml_count"] = cur.execute(
            "SELECT COUNT(*) FROM articles WHERE has_fulltext_xml = 1"
        ).fetchone()[0]
        stats["clinical_trials_nct"] = cur.execute(
            "SELECT COUNT(*) FROM clinical_trials"
        ).fetchone()[0]
        stats["extracted_mechanisms_rows"] = cur.execute(
            "SELECT COUNT(*) FROM extracted_mechanisms"
        ).fetchone()[0]
        stats["extracted_clinical_rows"] = cur.execute(
            "SELECT COUNT(*) FROM extracted_clinical_evidence"
        ).fetchone()[0]
        for tier_num in (1, 2, 3, 4):
            stats[f"tier_{tier_num}"] = cur.execute(
                "SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' AND evidence_tier = ?",
                (tier_num,),
            ).fetchone()[0]
    finally:
        conn.close()
    return stats


def build_dynamic_fallback_kb(
    nosology_id: str, config: dict[str, Any], db_path: Path
) -> dict[str, Any]:
    """Construct a valid universal schema dictionary dynamically from SQLite + YAML if kb_index.json is absent."""
    meta = config.get("nosology", {})
    date_range = config.get("date_range", {})
    stats = get_sqlite_corpus_stats(db_path)

    modalities: list[dict[str, Any]] = []
    factors: list[dict[str, Any]] = []

    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            rows = cur.execute(
                """
                SELECT intervention_group, COUNT(*) as cnt
                FROM extracted_clinical_evidence
                GROUP BY intervention_group
                ORDER BY cnt DESC
                LIMIT 12
                """
            ).fetchall()
            for grp, cnt in rows:
                modalities.append(
                    {
                        "name": grp or "Группа вмешательства",
                        "group": "Извлечённые из SQLite вмешательства",
                        "target_stage": f"По данным {cnt} извлечённых клинических записей",
                        "primary_efficacy": "См. таблицу извлечённых клинических доказательств",
                        "remission_5y_pct": "—",
                        "remission_5y_num": 50.0,
                        "recurrence_1_2y": "—",
                        "recurrence_1_2y_num": 15.0,
                        "recurrence_3y": "—",
                        "recurrence_3y_num": 25.0,
                        "recurrence_5y_overall": "—",
                        "recurrence_5y_num": 35.0,
                        "recurrence_10y": "—",
                        "recurrence_10y_num": 45.0,
                        "recurrence_by_subtype": {
                            "Благоприятный подтип": "—",
                            "Тяжёлый подтип": "—",
                            "favorable_num": 25.0,
                            "unfavorable_num": 45.0,
                        },
                        "procediv_5y": "—",
                        "procediv_5y_num": 20.0,
                        "reintervention_5y": "—",
                        "reintervention_5y_num": 15.0,
                        "complications_profile": "См. колонку adverse_events в SQLite",
                        "recovery_time": "—",
                        "pros": f"Подтверждено в {cnt} записях базы данных",
                        "cons": "Требуется аналитический синтез Фазы 3 для заполнения сводных диапазонов",
                    }
                )
            m_rows = cur.execute(
                """
                SELECT category, targets_genes_pathways, mechanism_summary, pmid
                FROM extracted_mechanisms
                LIMIT 8
                """
            ).fetchall()
            for cat, tgt, desc, pmid in m_rows:
                factors.append(
                    {
                        "factor_name": f"{cat}: {tgt}",
                        "category": cat or "Механизм",
                        "direction": "Фактор риска ↑",
                        "effect_size": f"PMID: {pmid}" if pmid else "Извлечено из корпуса",
                        "clinical_notes": (desc or "")[:220],
                        "mechanism": (desc or "")[:260],
                    }
                )
        finally:
            conn.close()

    return {
        "nosology_id": nosology_id,
        "title_ru": f"{meta.get('name_ru', nosology_id)} ({meta.get('icd10', '—')})",
        "updated_at": datetime.now().strftime("%Y-%m-%d"),
        "nosology_meta": {
            "nosology_id": nosology_id,
            "title_ru": meta.get("name_ru", nosology_id),
            "title_en": meta.get("name_en", nosology_id),
            "icd10": meta.get("icd10", "—"),
            "icd11": meta.get("icd11", "—"),
            "specialty": meta.get("specialty", "Клиническая медицина"),
            "time_horizon": f"{date_range.get('start_year', 2016)}–{date_range.get('end_year', 2026)}",
            "corpus_stats": stats,
        },
        "corpus_stats": stats,
        "staging_and_classification": {
            "classification_name": "Клиническая классификация стадий тяжести",
            "metric_label": "Ведущий клинико-функциональный показатель",
            "stages": [
                {
                    "stage_code": "Ранняя / субклиническая стадия",
                    "threshold": "Начальные проявления",
                    "population_share": "—",
                    "population_share_num": 50.0,
                    "interventional_share": "—",
                    "interventional_share_num": 15.0,
                    "natural_progression": "Динамическое наблюдение и ранняя профилактика",
                    "clinical_description": "Запустите Фазу 3 пайплайна для генерации стратификации по стадиям.",
                }
            ],
        },
        "anatomical_or_subtype_distribution": {
            "dimension_name": "Распределение по анатомическим локализациям или клиническим подтипам",
            "subtypes": [
                {
                    "locus_or_subtype": "Основной клинический фенотип",
                    "category": "Подтип",
                    "share_pct": "100%",
                    "share_num": 100.0,
                    "rank": 1,
                    "prognostic_impact": "Определяется после выполнения кластерной экстракции Фазы 2.",
                }
            ],
        },
        "etiology_and_risk_factors": factors,
        "pathogenesis_phases": [
            {
                "phase_order": 1,
                "phase_name": "Фаза I — Инициация патологического процесса",
                "cellular_and_tissue_events": "Иммуно-воспалительные и молекулярные триггеры.",
                "clinical_correlate": "Ранний клинический дебют",
                "therapeutic_window": "Консервативная и таргетная профилактика",
            }
        ],
        "natural_history_and_dynamics": {
            "untreated_course_summary": "Естественное течение заболевания без лечения формируется на основе когортных исследований Фазы 2–3.",
            "definitions": {
                "natural_history": "Естественное течение — динамика заболевания без инвазивного вмешательства.",
                "primary_remission": "Первичная ремиссия — купирование ведущего синдрома после вмешательства.",
                "true_recurrence": "Истинный рецидив — возврат патологического процесса в ранее леченой зоне.",
                "procediv_progression": "Процедив — продолженный рост или распространение болезни на новые анатомические зоны.",
            },
        },
        "modules": [],
        "modalities": modalities,
    }
def load_nosology_bundle(nosology_id: str) -> dict[str, Any]:
    """Load the complete unified data bundle for any configured nosology."""
    cfg_path = CONFIGS_DIR / f"{nosology_id}.yaml"
    config: dict[str, Any] = {}
    if cfg_path.exists():
        config = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    db_path = DATA_DIR / nosology_id / "literature.db"
    rep_dir = REPORTS_DIR / nosology_id
    kb_dir = rep_dir / "knowledge_base"
    kb_index_path = kb_dir / "kb_index.json"

    if kb_index_path.exists():
        kb_data = json.loads(kb_index_path.read_text(encoding="utf-8"))
    else:
        kb_data = build_dynamic_fallback_kb(nosology_id, config, db_path)

    live_stats = get_sqlite_corpus_stats(db_path)
    if live_stats["unique_articles"] > 0:
        kb_data.setdefault("corpus_stats", {}).update(live_stats)
        kb_data.setdefault("nosology_meta", {}).setdefault("corpus_stats", {}).update(live_stats)

    dissertation_path = rep_dir / "dissertation_report.md"
    exec_summary_path = rep_dir / "executive_summary.md"
    prisma_path = rep_dir / "prisma_stats.md"
    audit_path = rep_dir / "verification_audit.md"

    kb_modules: list[dict[str, str]] = []
    for mod in kb_data.get("modules", []):
        m_file = kb_dir / mod.get("file", "")
        content = m_file.read_text(encoding="utf-8") if m_file.exists() else ""
        kb_modules.append(
            {
                "id": mod.get("id", ""),
                "title": mod.get("title", mod.get("file", "")),
                "file": mod.get("file", ""),
                "category": mod.get("category", ""),
                "content": content,
            }
        )

    if not kb_modules and kb_dir.exists():
        for md_file in sorted(kb_dir.glob("*.md")):
            kb_modules.append(
                {
                    "id": md_file.stem,
                    "title": md_file.stem,
                    "file": md_file.name,
                    "category": "general",
                    "content": md_file.read_text(encoding="utf-8"),
                }
            )

    return {
        "nosology_id": nosology_id,
        "config": config,
        "db_path": db_path,
        "reports_dir": rep_dir,
        "kb_index": kb_data,
        "dissertation_md": dissertation_path.read_text(encoding="utf-8")
        if dissertation_path.exists()
        else "",
        "executive_summary_md": exec_summary_path.read_text(encoding="utf-8")
        if exec_summary_path.exists()
        else "",
        "prisma_stats_md": prisma_path.read_text(encoding="utf-8")
        if prisma_path.exists()
        else "",
        "verification_audit_md": audit_path.read_text(encoding="utf-8")
        if audit_path.exists()
        else "",
        "kb_modules": kb_modules,
    }


def split_markdown_sections(md_text: str) -> list[dict[str, str]]:
    """Split a long Markdown document by top-level `## ` chapters for fast UI navigation."""
    if not md_text.strip():
        return []
    lines = md_text.splitlines()
    sections: list[dict[str, str]] = []
    current_title = "Титульный блок и оглавление"
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_lines:
                sections.append(
                    {"title": current_title, "content": "\n".join(current_lines).strip()}
                )
            current_title = line.removeprefix("## ").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append({"title": current_title, "content": "\n".join(current_lines).strip()})
    return sections


def render_printable_html(
    title: str, markdown_text: str, nosology_meta: dict[str, Any] | None = None
) -> str:
    """Convert Markdown report into a standalone, print-ready HTML document (`D-03`).

    Can be printed to PDF via browser (`Ctrl+P`) or opened directly in MS Word.
    """
    meta = nosology_meta or {}
    body_html = markdown.markdown(
        markdown_text,
        extensions=["tables", "fenced_code", "toc", "sane_lists"],
    )
    icd10 = meta.get("icd10", "—")
    icd11 = meta.get("icd11", "—")
    horizon = meta.get("time_horizon", "2016–2026")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    :root {{
      --text: #111827;
      --muted: #4b5563;
      --border: #d1d5db;
      --accent: #1e3a8a;
      --bg-soft: #f8fafc;
    }}
    body {{
      font-family: "Georgia", "Times New Roman", serif;
      color: var(--text);
      line-height: 1.62;
      max-width: 980px;
      margin: 28px auto;
      padding: 0 24px 48px 24px;
      background: #ffffff;
    }}
    .doc-banner {{
      border-bottom: 2px solid var(--accent);
      padding-bottom: 12px;
      margin-bottom: 24px;
      font-family: "Segoe UI", Arial, sans-serif;
      font-size: 0.9rem;
      color: var(--muted);
      display: flex;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
    }}
    h1, h2, h3, h4 {{
      font-family: "Segoe UI", Arial, sans-serif;
      color: var(--accent);
      line-height: 1.3;
      margin-top: 1.6em;
      margin-bottom: 0.6em;
    }}
    h1 {{ font-size: 1.75rem; border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
    h2 {{ font-size: 1.35rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; }}
    h3 {{ font-size: 1.12rem; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0 22px 0;
      font-family: "Segoe UI", Arial, sans-serif;
      font-size: 0.88rem;
    }}
    th, td {{
      border: 1px solid var(--border);
      padding: 8px 10px;
      vertical-align: top;
      text-align: left;
    }}
    th {{
      background: var(--bg-soft);
      font-weight: 600;
      color: var(--accent);
    }}
    tr:nth-child(even) td {{
      background: #fcfcfd;
    }}
    blockquote {{
      border-left: 4px solid var(--accent);
      background: var(--bg-soft);
      margin: 14px 0;
      padding: 10px 16px;
    }}
    code {{
      font-family: Consolas, monospace;
      background: #f1f5f9;
      padding: 1px 4px;
      border-radius: 3px;
      font-size: 0.88em;
    }}
    @media print {{
      body {{ max-width: 100%; margin: 0; padding: 0; font-size: 11pt; }}
      h2 {{ page-break-before: auto; }}
      table {{ page-break-inside: auto; }}
      tr {{ page-break-inside: avoid; page-break-after: auto; }}
    }}
  </style>
</head>
<body>
  <div class="doc-banner">
    <span><strong>Нозология:</strong> {meta.get("title_ru", title)} (МКБ-10: {icd10} | МКБ-11: {icd11})</span>
    <span><strong>Горизонт:</strong> {horizon} | <strong>Экспорт:</strong> {now_str}</span>
  </div>
  {body_html}
</body>
</html>"""


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialize DataFrame to UTF-8 with BOM (`utf-8-sig`) bytes for Russian Excel compatibility (`D-03`)."""
    return df.to_csv(index=False).encode("utf-8-sig")


def query_articles_df(db_path: Path, included_only: bool = True) -> pd.DataFrame:
    """Load articles table from SQLite with clickable PubMed and DOI URLs."""
    if not db_path.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(db_path))
    try:
        where_clause = "WHERE prisma_status = 'included'" if included_only else ""
        df = pd.read_sql_query(
            f"""
            SELECT
                id, pmid, pmcid, doi, title, authors, journal, pub_year,
                pub_types, evidence_tier, prisma_status,
                has_fulltext_xml, clusters, cited_by_count, abstract
            FROM articles
            {where_clause}
            ORDER BY evidence_tier ASC, pub_year DESC
            """,
            conn,
        )
    finally:
        conn.close()
    if not df.empty:
        df["pubmed_url"] = df["pmid"].apply(
            lambda x: f"https://pubmed.ncbi.nlm.nih.gov/{x}/" if pd.notna(x) and str(x).strip() else ""
        )
        df["doi_url"] = df["doi"].apply(
            lambda x: f"https://doi.org/{x}" if pd.notna(x) and str(x).strip() else ""
        )
    return df


def query_clinical_evidence_df(db_path: Path) -> pd.DataFrame:
    """Load `extracted_clinical_evidence` joined with article metadata."""
    if not db_path.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(db_path))
    try:
        df = pd.read_sql_query(
            """
            SELECT
                c.id,
                c.pmid,
                c.first_author_year,
                a.pub_year,
                c.evidence_tier,
                c.intervention_group,
                c.comparator_group,
                c.study_design,
                c.n_patients,
                c.followup_months,
                c.mcp_outcome,
                c.pip_outcome,
                c.recurrence_rate_overall,
                c.recurrence_rate_mcp,
                c.recurrence_rate_pip,
                c.complications_rate,
                c.complications_summary,
                c.key_conclusion,
                a.title,
                c.doi
            FROM extracted_clinical_evidence c
            LEFT JOIN articles a ON c.article_id = a.id
            ORDER BY c.evidence_tier ASC, a.pub_year DESC
            """,
            conn,
        )
    finally:
        conn.close()
    return df


def query_mechanisms_df(db_path: Path) -> pd.DataFrame:
    """Load `extracted_mechanisms` joined with article metadata."""
    if not db_path.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(db_path))
    try:
        df = pd.read_sql_query(
            """
            SELECT
                m.id,
                m.pmid,
                m.first_author_year,
                a.pub_year,
                a.evidence_tier,
                m.category,
                m.targets_genes_pathways,
                m.study_model,
                m.sample_size,
                m.quantitative_findings,
                m.mechanism_summary,
                m.therapeutic_implication,
                a.title
            FROM extracted_mechanisms m
            LEFT JOIN articles a ON m.article_id = a.id
            ORDER BY a.evidence_tier ASC, a.pub_year DESC
            """,
            conn,
        )
    finally:
        conn.close()
    return df


def query_clinical_trials_df(db_path: Path) -> pd.DataFrame:
    """Load `clinical_trials` table from SQLite with ClinicalTrials.gov URLs."""
    if not db_path.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(db_path))
    try:
        df = pd.read_sql_query(
            """
            SELECT
                nct_id, brief_title, official_title, overall_status, phase,
                study_type, enrollment, interventions, start_date,
                completion_date, has_results, summary
            FROM clinical_trials
            ORDER BY start_date DESC
            """,
            conn,
        )
    finally:
        conn.close()
    if not df.empty:
        df["ctgov_url"] = df["nct_id"].apply(
            lambda x: f"https://clinicaltrials.gov/study/{x}" if pd.notna(x) and str(x).strip() else ""
        )
    return df


def save_new_nosology_config(config_payload: dict[str, Any]) -> Path:
    """Save a new nosology configuration to `configs/<id>.yaml`."""
    nos_id = config_payload.get("nosology", {}).get("id", "").strip().lower()
    if not nos_id or not nos_id.replace("_", "").isalnum():
        raise ValueError("Идентификатор нозологии должен содержать только латинские буквы, цифры и '_'")
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CONFIGS_DIR / f"{nos_id}.yaml"
    yaml_str = yaml.safe_dump(config_payload, allow_unicode=True, sort_keys=False)
    out_path.write_text(yaml_str, encoding="utf-8")
    return out_path


def verify_universal_schema(nosology_id: str = "dupuytren") -> int:
    """Validate that `kb_index.json` and `universal_schema.py` satisfy D-01 and D-03."""
    bundle = load_nosology_bundle(nosology_id)
    kb = bundle["kb_index"]

    missing_top = [k for k in REQUIRED_UNIVERSAL_KEYS if k not in kb]
    if missing_top:
        print(f"[FAIL] Missing top-level universal keys: {missing_top}")
        return 1

    stages = kb["staging_and_classification"].get("stages", [])
    subtypes = kb["anatomical_or_subtype_distribution"].get("subtypes", [])
    factors = kb.get("etiology_and_risk_factors", [])
    phases = kb.get("pathogenesis_phases", [])
    modalities = kb.get("modalities", [])

    if len(stages) < 3 or len(subtypes) < 3 or len(factors) < 4 or len(phases) < 2 or len(modalities) < 10:
        print("[FAIL] Insufficient records in universal schema sections.")
        return 1

    for idx, mod in enumerate(modalities):
        miss_mod = [k for k in REQUIRED_MODALITY_KEYS if k not in mod]
        if miss_mod:
            print(f"[FAIL] Modality #{idx} ({mod.get('name')}) missing keys: {miss_mod}")
            return 1

    html_doc = render_printable_html(
        kb["nosology_meta"]["title_ru"],
        bundle["executive_summary_md"],
        kb["nosology_meta"],
    )
    if "<table" not in html_doc or "<!DOCTYPE html>" not in html_doc:
        print("[FAIL] Printable HTML export check failed.")
        return 1

    df_mod = pd.DataFrame(modalities)
    csv_bytes = dataframe_to_csv_bytes(df_mod)
    if not csv_bytes.startswith(b"\xef\xbb\xbf"):
        print("[FAIL] CSV UTF-8-SIG BOM check failed.")
        return 1

    df_art = query_articles_df(bundle["db_path"])
    df_clin = query_clinical_evidence_df(bundle["db_path"])
    df_mech = query_mechanisms_df(bundle["db_path"])
    df_trials = query_clinical_trials_df(bundle["db_path"])

    print(
        f"[PASS] Universal schema verified for '{nosology_id}':\n"
        f"  - Stages: {len(stages)} | Subtypes/Loci: {len(subtypes)} | Risk/Protective Factors: {len(factors)}\n"
        f"  - Pathogenesis Phases: {len(phases)} | Treatment Modalities: {len(modalities)}\n"
        f"  - SQLite rows loaded: articles={len(df_art)}, clinical={len(df_clin)}, mechanisms={len(df_mech)}, trials={len(df_trials)}\n"
        f"  - Exports verified: Printable HTML ({len(html_doc)} chars), UTF-8-SIG CSV ({len(csv_bytes)} bytes)"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Universal Nosology Schema Adapter")
    parser.add_argument("--verify", action="store_true", help="Verify universal schema & exports")
    parser.add_argument("--nosology", default="dupuytren", help="Nosology ID")
    args = parser.parse_args()
    if args.verify:
        return verify_universal_schema(args.nosology)
    return 0


if __name__ == "__main__":
    sys.exit(main())
