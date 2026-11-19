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
import re
import sqlite3
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import markdown
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.extractor_common import (
    DEFAULT_SEQUELA_TIME_WINDOW,
    VALID_CLAVIEN_DINDO,
    VALID_EVENT_CLASS,
    VALID_REVERSIBILITY,
    is_excluded_recurrence_event,
    table_exists,
)

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

REQUIRED_COMPLICATION_ENTRY_KEYS = [
    "modality",
    "complication_name",
    "event_class",
    "clavien_dindo_grade",
    "reversibility",
    "frequency_pct",
    "frequency_median_num",
    "sample_size_total",
    "time_window",
    "anatomical_substrate",
    "prevention_and_management",
    "evidence_pmids",
]

REQUIRED_RED_FLAG_KEYS = [
    "modality",
    "complication_name",
    "clavien_dindo_grade",
    "reversibility",
    "frequency_pct",
    "frequency_max_num",
    "anatomical_substrate",
    "prevention_and_management",
    "evidence_pmids",
]

_CLAVIEN_SEVERITY_RANK: dict[str, int] = {
    "I": 1,
    "II": 2,
    "IIIa": 3,
    "IIIb": 4,
    "IV": 5,
    "V": 6,
}

_REVERSIBILITY_SEVERITY_RANK: dict[str, int] = {
    "transient_self_limiting": 1,
    "requires_conservative_therapy": 2,
    "requires_reoperation": 3,
    "permanent_deficit": 4,
}


def _connect_sqlite_readonly(db_path: Path) -> sqlite3.Connection:
    """Open an existing SQLite DB in strict read-only URI mode without creating/mutating files (T-17-02, D-09)."""
    resolved = db_path.resolve()
    try:
        conn = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


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
        meta = raw.get("nosology", {}) or {}
        nos_id = meta.get("id") or raw.get("nosology_id") or cfg_path.stem
        db_path = DATA_DIR / nos_id / "literature.db"
        kb_path = REPORTS_DIR / nos_id / "knowledge_base" / "kb_index.json"

        raw_profile = raw.get("treatment_profile") or meta.get("treatment_profile")
        treatment_profile = str(raw_profile).strip().lower() if raw_profile else None
        if treatment_profile == "conservative":
            surgical_focus = False
        elif "surgical_focus" in raw and raw["surgical_focus"] is False:
            surgical_focus = False
        elif "surgical_focus" in meta and meta["surgical_focus"] is False:
            surgical_focus = False
        else:
            surgical_focus = True
        if treatment_profile is None:
            treatment_profile = "conservative" if not surgical_focus else "surgical"

        items.append(
            {
                "id": nos_id,
                "name_ru": meta.get("name_ru") or raw.get("name_ru") or nos_id,
                "name_en": meta.get("name_en") or raw.get("name_en") or nos_id,
                "icd10": meta.get("icd10") or raw.get("icd10") or "—",
                "icd11": meta.get("icd11") or raw.get("icd11") or "—",
                "mesh_terms": meta.get("mesh_terms") or raw.get("mesh_terms") or [],
                "surgical_focus": surgical_focus,
                "treatment_profile": treatment_profile,
                "config_path": str(cfg_path),
                "has_db": db_path.exists(),
                "has_kb_index": kb_path.exists(),
                "raw_config": raw,
            }
        )
    return items


def get_sqlite_corpus_stats(db_path: Path) -> dict[str, int]:
    """Read live row counts from `data/<nosology>/literature.db` in read-only mode."""
    stats = {
        "unique_articles": 0,
        "included_articles": 0,
        "excluded_articles": 0,
        "fulltext_xml_count": 0,
        "clinical_trials_nct": 0,
        "extracted_mechanisms_rows": 0,
        "extracted_clinical_rows": 0,
        "extracted_complications_rows": 0,
        "tier_1": 0,
        "tier_2": 0,
        "tier_3": 0,
        "tier_4": 0,
    }
    if not db_path.exists():
        return stats
    conn = _connect_sqlite_readonly(db_path)
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
        if table_exists(conn, "extracted_complications"):
            stats["extracted_complications_rows"] = cur.execute(
                "SELECT COUNT(*) FROM extracted_complications"
            ).fetchone()[0]
        for tier_num in (1, 2, 3, 4):
            stats[f"tier_{tier_num}"] = cur.execute(
                "SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' AND evidence_tier = ?",
                (tier_num,),
            ).fetchone()[0]
    finally:
        conn.close()
    return stats


def aggregate_complications_from_sqlite(
    db_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Aggregate extracted_complications into (frequent_complications, rare_critical_red_flags) (COMP-04, D-04, D-08, D-09)."""
    if not db_path.exists():
        return [], []

    conn = _connect_sqlite_readonly(db_path)
    try:
        if not table_exists(conn, "extracted_complications"):
            return [], []

        if table_exists(conn, "articles"):
            rows = conn.execute(
                """
                SELECT
                    c.id,
                    c.article_id,
                    c.pmid,
                    c.doi,
                    c.first_author_year,
                    c.evidence_tier,
                    c.modality,
                    c.complication_name,
                    c.event_class,
                    c.timing_category,
                    c.clavien_dindo_grade,
                    c.ctcae_grade,
                    c.frequency_pct,
                    c.frequency_num,
                    c.reversibility,
                    c.time_window,
                    c.anatomical_substrate,
                    c.prevention_and_management,
                    c.sample_size,
                    c.is_rare_casuistry
                FROM extracted_complications c
                LEFT JOIN articles a ON c.article_id = a.id
                WHERE a.id IS NULL OR a.prisma_status = 'included'
                ORDER BY c.id ASC
                """
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM extracted_complications ORDER BY id ASC").fetchall()
    finally:
        conn.close()

    groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for row in rows:
        mod = str(row["modality"] or "").strip()
        comp = str(row["complication_name"] or "").strip()
        if not mod or not comp:
            continue
        if is_excluded_recurrence_event(comp):
            continue
        key = (mod.lower(), comp.lower())
        groups.setdefault(key, []).append(row)

    frequent_complications: list[dict[str, Any]] = []
    rare_critical_red_flags: list[dict[str, Any]] = []

    def _pick_representative(subset: list[sqlite3.Row]) -> dict[str, Any]:
        display_modality = str(subset[0]["modality"]).strip()
        display_name = str(subset[0]["complication_name"]).strip()

        valid_cds = [str(r["clavien_dindo_grade"]).strip() for r in subset if str(r["clavien_dindo_grade"] or "").strip() in VALID_CLAVIEN_DINDO]
        cd_grade = max(valid_cds, key=lambda g: _CLAVIEN_SEVERITY_RANK[g]) if valid_cds else "I"

        valid_revs = [str(r["reversibility"]).strip() for r in subset if str(r["reversibility"] or "").strip() in VALID_REVERSIBILITY]
        reversibility = max(valid_revs, key=lambda v: _REVERSIBILITY_SEVERITY_RANK[v]) if valid_revs else "transient_self_limiting"

        valid_classes = [str(r["event_class"]).strip() for r in subset if str(r["event_class"] or "").strip() in VALID_EVENT_CLASS]
        event_class = "true_complication" if "true_complication" in valid_classes else (valid_classes[0] if valid_classes else "true_complication")

        time_window = next((str(r["time_window"]).strip() for r in subset if str(r["time_window"] or "").strip()), "")
        if event_class == "transient_postop_sequela" and not time_window:
            time_window = DEFAULT_SEQUELA_TIME_WINDOW

        anatomical_substrate = next(
            (str(r["anatomical_substrate"]).strip() for r in subset if str(r["anatomical_substrate"] or "").strip()),
            "—",
        )
        prevention_and_management = next(
            (str(r["prevention_and_management"]).strip() for r in subset if str(r["prevention_and_management"] or "").strip()),
            "—",
        )
        evidence_pmids = list(
            dict.fromkeys(str(r["pmid"]).strip() for r in subset if r["pmid"] is not None and str(r["pmid"]).strip())
        )

        return {
            "modality": display_modality,
            "complication_name": display_name,
            "event_class": event_class,
            "clavien_dindo_grade": cd_grade,
            "reversibility": reversibility,
            "time_window": time_window,
            "anatomical_substrate": anatomical_substrate,
            "prevention_and_management": prevention_and_management,
            "evidence_pmids": evidence_pmids,
        }

    for group_rows in groups.values():
        cohort_rows: list[sqlite3.Row] = []
        casuistry_rows: list[sqlite3.Row] = []

        for r in group_rows:
            tier = r["evidence_tier"]
            n_val = r["sample_size"]
            is_cas = int(r["is_rare_casuistry"] or 0)
            freq_num = r["frequency_num"]

            if (
                tier in (1, 2, 3)
                and n_val is not None
                and int(n_val) >= 20
                and is_cas == 0
                and freq_num is not None
            ):
                cohort_rows.append(r)
            elif tier == 4 or n_val is None or int(n_val) < 20 or is_cas == 1:
                casuistry_rows.append(r)

        if cohort_rows:
            rep = _pick_representative(cohort_rows)
            freqs = [float(r["frequency_num"]) for r in cohort_rows]
            med = round(float(statistics.median(freqs)), 2)
            f_min = round(float(min(freqs)), 2)
            f_max = round(float(max(freqs)), 2)
            freq_pct = f"{med:g}%" if f_min == f_max else f"{med:g}% ({f_min:g}–{f_max:g}%)"

            seen_articles: dict[tuple[str, int], int] = {}
            for r in cohort_rows:
                art_key = (
                    ("article", int(r["article_id"]))
                    if r["article_id"] is not None
                    else ("row", int(r["id"]))
                )
                n_int = int(r["sample_size"])
                if art_key not in seen_articles or n_int > seen_articles[art_key]:
                    seen_articles[art_key] = n_int
            sample_size_total = sum(seen_articles.values())

            if med >= 1.0:
                frequent_complications.append(
                    {
                        "modality": rep["modality"],
                        "complication_name": rep["complication_name"],
                        "event_class": rep["event_class"],
                        "clavien_dindo_grade": rep["clavien_dindo_grade"],
                        "reversibility": rep["reversibility"],
                        "frequency_pct": freq_pct,
                        "frequency_median_num": med,
                        "sample_size_total": sample_size_total,
                        "time_window": rep["time_window"],
                        "anatomical_substrate": rep["anatomical_substrate"],
                        "prevention_and_management": rep["prevention_and_management"],
                        "evidence_pmids": rep["evidence_pmids"],
                    }
                )
            elif rep["clavien_dindo_grade"] in ("IIIa", "IIIb", "IV", "V") or rep["reversibility"] in (
                "requires_reoperation",
                "permanent_deficit",
            ):
                rare_critical_red_flags.append(
                    {
                        "modality": rep["modality"],
                        "complication_name": rep["complication_name"],
                        "clavien_dindo_grade": rep["clavien_dindo_grade"],
                        "reversibility": rep["reversibility"],
                        "frequency_pct": freq_pct,
                        "frequency_max_num": f_max if f_max < 1.0 else med,
                        "anatomical_substrate": rep["anatomical_substrate"],
                        "prevention_and_management": rep["prevention_and_management"],
                        "evidence_pmids": rep["evidence_pmids"],
                    }
                )
        elif casuistry_rows:
            rep = _pick_representative(casuistry_rows)
            if rep["clavien_dindo_grade"] in ("IIIa", "IIIb", "IV", "V") or rep["reversibility"] in (
                "requires_reoperation",
                "permanent_deficit",
            ):
                explicit_low = [
                    float(r["frequency_num"])
                    for r in casuistry_rows
                    if r["frequency_num"] is not None and 0.0 <= float(r["frequency_num"]) < 1.0
                ]
                if explicit_low:
                    freq_max_num = round(max(explicit_low), 2)
                    freq_pct = f"{freq_max_num:g}% (единичные клинические наблюдения Tier 4)"
                else:
                    freq_max_num = 0.49
                    freq_pct = "< 0.5% (единичные клинические наблюдения Tier 4)"

                rare_critical_red_flags.append(
                    {
                        "modality": rep["modality"],
                        "complication_name": rep["complication_name"],
                        "clavien_dindo_grade": rep["clavien_dindo_grade"],
                        "reversibility": rep["reversibility"],
                        "frequency_pct": freq_pct,
                        "frequency_max_num": freq_max_num,
                        "anatomical_substrate": rep["anatomical_substrate"],
                        "prevention_and_management": rep["prevention_and_management"],
                        "evidence_pmids": rep["evidence_pmids"],
                    }
                )

    frequent_complications.sort(
        key=lambda item: (item["modality"], -float(item["frequency_median_num"]), item["complication_name"])
    )
    rare_critical_red_flags.sort(
        key=lambda item: (item["modality"], -float(item["frequency_max_num"]), item["complication_name"])
    )
    return frequent_complications, rare_critical_red_flags


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
        conn = _connect_sqlite_readonly(db_path)
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

    freq_comps, red_flags = aggregate_complications_from_sqlite(db_path)

    return {
        "schema_version": "2.0",
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
        "frequent_complications": freq_comps,
        "rare_critical_red_flags": red_flags,
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
    conn = _connect_sqlite_readonly(db_path)
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
    conn = _connect_sqlite_readonly(db_path)
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
    conn = _connect_sqlite_readonly(db_path)
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
    conn = _connect_sqlite_readonly(db_path)
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


def query_complications_df(db_path: Path, *, include_casuistry: bool = True) -> pd.DataFrame:
    """Load `extracted_complications` joined with article metadata safely (empty DataFrame if table absent, D-09/T-17-02)."""
    if not db_path.exists():
        return pd.DataFrame()
    conn = _connect_sqlite_readonly(db_path)
    try:
        if not table_exists(conn, "extracted_complications"):
            return pd.DataFrame()
        where_clause = "WHERE COALESCE(c.is_rare_casuistry, 0) = 0" if not include_casuistry else ""
        df = pd.read_sql_query(
            f"""
            SELECT
                c.id,
                c.article_id,
                c.pmid,
                c.doi,
                c.first_author_year,
                a.pub_year,
                c.evidence_tier,
                c.modality,
                c.complication_name,
                c.event_class,
                c.timing_category,
                c.clavien_dindo_grade,
                c.ctcae_grade,
                c.frequency_pct,
                c.frequency_num,
                c.reversibility,
                c.time_window,
                c.anatomical_substrate,
                c.prevention_and_management,
                c.sample_size,
                c.is_rare_casuistry,
                a.title
            FROM extracted_complications c
            LEFT JOIN articles a ON c.article_id = a.id
            {where_clause}
            ORDER BY c.modality ASC, COALESCE(c.frequency_num, -1.0) DESC, c.evidence_tier ASC
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


def save_new_nosology_config(config_payload: dict[str, Any]) -> Path:
    """Save a new nosology configuration to `configs/<id>.yaml` with normalized surgical_focus & YAML safety (T-17-05)."""
    nos_meta = config_payload.setdefault("nosology", {})
    nos_id = str(nos_meta.get("id") or config_payload.get("nosology_id") or "").strip().lower()
    if not nos_id or not re.fullmatch(r"[a-z0-9_]+", nos_id):
        raise ValueError("Идентификатор нозологии должен содержать только латинские буквы, цифры и '_'")
    nos_meta["id"] = nos_id

    raw_profile = config_payload.get("treatment_profile") or nos_meta.get("treatment_profile")
    treatment_profile = str(raw_profile).strip().lower() if raw_profile else ""
    if (
        treatment_profile == "conservative"
        or config_payload.get("surgical_focus") is False
        or nos_meta.get("surgical_focus") is False
    ):
        nos_meta["surgical_focus"] = False
    else:
        nos_meta["surgical_focus"] = True
    if treatment_profile:
        nos_meta["treatment_profile"] = treatment_profile

    comp_queries = config_payload.get("complications_queries")
    if isinstance(comp_queries, dict):
        cleaned_queries = {
            k: v
            for k, v in comp_queries.items()
            if k in ("pubmed", "europepmc", "max_results") and v not in (None, "")
        }
        if cleaned_queries:
            config_payload["complications_queries"] = cleaned_queries

    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = (CONFIGS_DIR / f"{nos_id}.yaml").resolve()
    if out_path.parent != CONFIGS_DIR.resolve():
        raise ValueError("Недопустимый путь сохранения конфигурации нозологии")
    yaml_str = yaml.safe_dump(config_payload, allow_unicode=True, sort_keys=False)
    out_path.write_text(yaml_str, encoding="utf-8")
    return out_path


def validate_kb_complications_v2(kb: dict[str, Any]) -> list[str]:
    """Validate schema_version '2.0' frequent_complications and rare_critical_red_flags contract (COMP-04, D-07..D-09)."""
    errors: list[str] = []
    if str(kb.get("schema_version", "")) != "2.0":
        errors.append(f"Expected schema_version == '2.0', got {kb.get('schema_version')!r}")

    freq_list = kb.get("frequent_complications")
    if not isinstance(freq_list, list) or len(freq_list) == 0:
        errors.append("Field 'frequent_complications' must be a non-empty list for schema_version '2.0'")
    else:
        last_median_by_modality: dict[str, float] = {}
        for idx, entry in enumerate(freq_list):
            if not isinstance(entry, dict):
                errors.append(f"frequent_complications[{idx}] must be an object")
                continue
            missing = [k for k in REQUIRED_COMPLICATION_ENTRY_KEYS if k not in entry]
            if missing:
                errors.append(f"frequent_complications[{idx}] missing keys: {missing}")

            comp_name = str(entry.get("complication_name") or "").strip()
            if not comp_name:
                errors.append(f"frequent_complications[{idx}] has empty complication_name")
            elif is_excluded_recurrence_event(comp_name):
                errors.append(
                    f"frequent_complications[{idx}] contains excluded recurrence/incomplete-release event: {comp_name!r}"
                )

            cd_grade = entry.get("clavien_dindo_grade")
            if cd_grade not in VALID_CLAVIEN_DINDO:
                errors.append(f"frequent_complications[{idx}] invalid clavien_dindo_grade: {cd_grade!r}")

            reversibility = entry.get("reversibility")
            if reversibility not in VALID_REVERSIBILITY:
                errors.append(f"frequent_complications[{idx}] invalid reversibility: {reversibility!r}")

            event_class = entry.get("event_class")
            if event_class not in VALID_EVENT_CLASS:
                errors.append(f"frequent_complications[{idx}] invalid event_class: {event_class!r}")
            elif event_class == "transient_postop_sequela" and not str(entry.get("time_window") or "").strip():
                errors.append(
                    f"frequent_complications[{idx}] transient_postop_sequela requires non-empty time_window"
                )

            med_raw = entry.get("frequency_median_num")
            if isinstance(med_raw, bool) or not isinstance(med_raw, (int, float)):
                errors.append(f"frequent_complications[{idx}] frequency_median_num must be numeric")
            else:
                med_val = float(med_raw)
                if med_val < 1.0:
                    errors.append(
                        f"frequent_complications[{idx}] frequency_median_num must be >= 1.0, got {med_val}"
                    )
                mod = str(entry.get("modality") or "").strip()
                if mod:
                    if mod in last_median_by_modality and med_val > last_median_by_modality[mod]:
                        errors.append(
                            f"frequent_complications[{idx}] for modality '{mod}' is not sorted descending "
                            f"by frequency_median_num ({med_val} > {last_median_by_modality[mod]})"
                        )
                    last_median_by_modality[mod] = med_val

            n_raw = entry.get("sample_size_total")
            if isinstance(n_raw, bool) or not isinstance(n_raw, (int, float)) or int(n_raw) < 20:
                errors.append(
                    f"frequent_complications[{idx}] sample_size_total must be >= 20, got {n_raw!r}"
                )

            pmids = entry.get("evidence_pmids")
            if not isinstance(pmids, list) or not any(str(p).strip() for p in pmids):
                errors.append(f"frequent_complications[{idx}] evidence_pmids must be a non-empty list")

    red_flags = kb.get("rare_critical_red_flags")
    if not isinstance(red_flags, list):
        errors.append("Field 'rare_critical_red_flags' must be a list for schema_version '2.0'")
    else:
        for idx, entry in enumerate(red_flags):
            if not isinstance(entry, dict):
                errors.append(f"rare_critical_red_flags[{idx}] must be an object")
                continue
            missing = [k for k in REQUIRED_RED_FLAG_KEYS if k not in entry]
            if missing:
                errors.append(f"rare_critical_red_flags[{idx}] missing keys: {missing}")

            comp_name = str(entry.get("complication_name") or "").strip()
            if not comp_name:
                errors.append(f"rare_critical_red_flags[{idx}] has empty complication_name")
            elif is_excluded_recurrence_event(comp_name):
                errors.append(
                    f"rare_critical_red_flags[{idx}] contains excluded recurrence/incomplete-release event: {comp_name!r}"
                )

            cd_grade = entry.get("clavien_dindo_grade")
            if cd_grade not in VALID_CLAVIEN_DINDO:
                errors.append(f"rare_critical_red_flags[{idx}] invalid clavien_dindo_grade: {cd_grade!r}")

            reversibility = entry.get("reversibility")
            if reversibility not in VALID_REVERSIBILITY:
                errors.append(f"rare_critical_red_flags[{idx}] invalid reversibility: {reversibility!r}")

            max_raw = entry.get("frequency_max_num")
            if isinstance(max_raw, bool) or not isinstance(max_raw, (int, float)):
                errors.append(f"rare_critical_red_flags[{idx}] frequency_max_num must be numeric")
            elif float(max_raw) >= 1.0 or float(max_raw) < 0.0:
                errors.append(
                    f"rare_critical_red_flags[{idx}] frequency_max_num must be in [0.0, 1.0), got {max_raw}"
                )

            pmids = entry.get("evidence_pmids")
            if not isinstance(pmids, list) or not any(str(p).strip() for p in pmids):
                errors.append(f"rare_critical_red_flags[{idx}] evidence_pmids must be a non-empty list")

    return errors


def verify_universal_schema(nosology_id: str | None = None, schema_version: str = "auto") -> int:
    """Validate that `kb_index.json` and `universal_schema.py` satisfy D-01, D-03, and COMP-04/D-09."""
    if not nosology_id:
        discovered = discover_nosologies()
        nosology_id = discovered[0]["id"] if discovered else "prom"
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

    if len(stages) < 3 or len(subtypes) < 3 or len(factors) < 4 or len(phases) < 2 or len(modalities) < 8:
        print("[FAIL] Insufficient records in universal schema sections.")
        return 1

    for idx, mod in enumerate(modalities):
        miss_mod = [k for k in REQUIRED_MODALITY_KEYS if k not in mod]
        if miss_mod:
            print(f"[FAIL] Modality #{idx} ({mod.get('name')}) missing keys: {miss_mod}")
            return 1

    enforce_v2 = (schema_version == "v2") or (
        schema_version == "auto" and str(kb.get("schema_version", "")) == "2.0"
    )
    if enforce_v2:
        v2_errors = validate_kb_complications_v2(kb)
        if v2_errors:
            print(f"[FAIL] Schema v2.0 complications validation failed for '{nosology_id}':")
            for err in v2_errors:
                print(f"  - {err}")
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

    from src.docx_exporter import build_docx_bytes_from_markdown

    docx_bytes = build_docx_bytes_from_markdown(bundle["executive_summary_md"])
    if not docx_bytes.startswith(b"PK") or len(docx_bytes) < 2048:
        print("[FAIL] DOCX OpenXML export check failed.")
        return 1

    df_art = query_articles_df(bundle["db_path"])
    df_clin = query_clinical_evidence_df(bundle["db_path"])
    df_mech = query_mechanisms_df(bundle["db_path"])
    df_trials = query_clinical_trials_df(bundle["db_path"])
    df_comp = query_complications_df(bundle["db_path"])

    schema_label = "v2.0" if enforce_v2 else "v1.x (compat)"
    print(
        f"[PASS] Universal schema verified for '{nosology_id}' [{schema_label}]:\n"
        f"  - Stages: {len(stages)} | Subtypes/Loci: {len(subtypes)} | Risk/Protective Factors: {len(factors)}\n"
        f"  - Pathogenesis Phases: {len(phases)} | Treatment Modalities: {len(modalities)}\n"
        f"  - SQLite rows loaded: articles={len(df_art)}, clinical={len(df_clin)}, "
        f"mechanisms={len(df_mech)}, trials={len(df_trials)}, complications={len(df_comp)}\n"
        f"  - Exports verified: DOCX ({len(docx_bytes)} bytes), Printable HTML ({len(html_doc)} chars), UTF-8-SIG CSV ({len(csv_bytes)} bytes)"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Universal Nosology Schema Adapter")
    parser.add_argument("--verify", action="store_true", help="Verify universal schema & exports")
    parser.add_argument("--nosology", default=None, help="Nosology ID")
    parser.add_argument(
        "--schema-version",
        choices=["auto", "v1", "v2"],
        default="auto",
        help="Schema validation mode: auto (detect), v1 (legacy compat), or v2 (strict complications)",
    )
    args = parser.parse_args()
    if args.verify:
        return verify_universal_schema(args.nosology, schema_version=args.schema_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
