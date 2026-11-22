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
import copy
import json
import math
import os
import re
import sqlite3
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

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
    resolve_treatment_profile_and_focus,
    table_exists,
    validate_nosology_id,
)

CONFIGS_DIR = PROJECT_ROOT / "configs"
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"

FROZEN_V1_NOSOLOGIES = frozenset({"prom", "metroplasty_pregnancy", "trigger_finger"})


def get_active_project_root() -> Path:
    """Return active workspace root (INFO_SEARCHER_ROOT env override or repository root) (T-19-05)."""
    env_root = os.environ.get("INFO_SEARCHER_ROOT", "").strip()
    if env_root:
        return Path(env_root).resolve()
    return PROJECT_ROOT.resolve()


def _get_configs_dir() -> Path:
    env_root = os.environ.get("INFO_SEARCHER_ROOT", "").strip()
    if env_root:
        return Path(env_root).resolve() / "configs"
    return CONFIGS_DIR


def _get_data_dir() -> Path:
    env_root = os.environ.get("INFO_SEARCHER_ROOT", "").strip()
    if env_root:
        return Path(env_root).resolve() / "data"
    return DATA_DIR


def _get_reports_dir() -> Path:
    env_root = os.environ.get("INFO_SEARCHER_ROOT", "").strip()
    if env_root:
        return Path(env_root).resolve() / "reports"
    return REPORTS_DIR

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

REQUIRED_CLINICAL_NUANCE_SECTIONS = (
    "universal_workhorse_modalities",
    "overlapping_indications_and_gray_zones",
    "strict_niche_or_salvage_indications",
)

REQUIRED_WORKHORSE_KEYS = (
    "modality",
    "applicable_spectrum",
    "practical_nuances",
    "surgeon_and_equipment_factors",
    "patient_tradeoffs",
    "evidence_pmids",
)

REQUIRED_OVERLAP_KEYS = (
    "clinical_scenario",
    "competing_modalities",
    "why_no_single_winner",
    "decisive_practical_factors",
    "evidence_pmids",
)

REQUIRED_NICHE_KEYS = (
    "modality",
    "narrow_indication_or_salvage_role",
    "why_not_first_line_for_all",
    "evidence_pmids",
)


def _default_clinical_decision_nuances() -> dict[str, list[Any]]:
    """Return a fresh empty v2.0 clinical_decision_nuances structure (in-memory safe default)."""
    return {
        "universal_workhorse_modalities": [],
        "overlapping_indications_and_gray_zones": [],
        "strict_niche_or_salvage_indications": [],
    }

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
    """Open an existing SQLite DB strictly read-only without ever falling back to RW mode (CR-02, T-17-02, D-09)."""
    resolved = db_path.resolve()
    encoded_path = quote(resolved.as_posix(), safe="/:")
    try:
        conn = sqlite3.connect(f"file:{encoded_path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        conn = sqlite3.connect(f"file:{encoded_path}?mode=ro&immutable=1", uri=True)
    conn.execute("PRAGMA query_only = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def discover_nosologies(configs_dir: Path | None = None) -> list[dict[str, Any]]:
    """Scan `configs/*.yaml` and return metadata for all configured nosologies (CR-01, WR-08, T-19-05)."""
    items: list[dict[str, Any]] = []
    active_configs = configs_dir if configs_dir is not None else _get_configs_dir()
    if not active_configs.exists():
        return items
    data_dir = _get_data_dir()
    reports_dir = _get_reports_dir()
    data_root = data_dir.resolve()
    reports_root = reports_dir.resolve()
    for cfg_path in sorted(active_configs.glob("*.yaml")):
        try:
            raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        meta = raw.get("nosology") if isinstance(raw.get("nosology"), dict) else {}
        raw_nos_id = meta.get("id") or raw.get("nosology_id") or cfg_path.stem
        try:
            nos_id = validate_nosology_id(raw_nos_id)
        except ValueError:
            continue
        db_path = (data_dir / nos_id / "literature.db").resolve()
        kb_path = (reports_dir / nos_id / "knowledge_base" / "kb_index.json").resolve()
        if not db_path.is_relative_to(data_root) or not kb_path.is_relative_to(reports_root):
            continue

        treatment_profile, surgical_focus = resolve_treatment_profile_and_focus(raw)

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
                    COALESCE(c.pmid, a.pmid) AS pmid,
                    COALESCE(c.doi, a.doi) AS doi,
                    c.first_author_year,
                    COALESCE(c.evidence_tier, a.evidence_tier) AS evidence_tier,
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
        qualitative_cohort_rows: list[sqlite3.Row] = []
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
            elif (
                tier in (1, 2, 3)
                and n_val is not None
                and int(n_val) >= 20
                and is_cas == 0
                and freq_num is None
            ):
                qualitative_cohort_rows.append(r)
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
                # D-09 red-flag schema invariant: frequency_max_num < 1.0; if single outlier cohort reached >=1% while median < 1%, label median explicitly
                if f_max < 1.0:
                    rf_pct = freq_pct
                    rf_num = f_max
                else:
                    rf_pct = f"медиана {med:g}% (разброс когорт {f_min:g}–{f_max:g}%)"
                    rf_num = med
                rare_critical_red_flags.append(
                    {
                        "modality": rep["modality"],
                        "complication_name": rep["complication_name"],
                        "clavien_dindo_grade": rep["clavien_dindo_grade"],
                        "reversibility": rep["reversibility"],
                        "frequency_pct": rf_pct,
                        "frequency_max_num": rf_num,
                        "anatomical_substrate": rep["anatomical_substrate"],
                        "prevention_and_management": rep["prevention_and_management"],
                        "evidence_pmids": rep["evidence_pmids"],
                    }
                )
        elif qualitative_cohort_rows or casuistry_rows:
            fallback_rows = qualitative_cohort_rows if qualitative_cohort_rows else casuistry_rows
            rep = _pick_representative(fallback_rows)
            if rep["clavien_dindo_grade"] in ("IIIa", "IIIb", "IV", "V") or rep["reversibility"] in (
                "requires_reoperation",
                "permanent_deficit",
            ):
                explicit_low = [
                    float(r["frequency_num"])
                    for r in fallback_rows
                    if r["frequency_num"] is not None and 0.0 <= float(r["frequency_num"]) < 1.0
                ]
                if explicit_low:
                    freq_max_num = round(max(explicit_low), 2)
                    freq_pct = f"{freq_max_num:g}% (единичные клинические наблюдения Tier 4)"
                elif qualitative_cohort_rows:
                    freq_max_num = 0.49
                    freq_pct = "< 1% (качественное упоминание в когорте Tier 1–3 без точного %)"
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
        key=lambda item: (item["modality"].lower(), -float(item["frequency_median_num"]), item["complication_name"])
    )
    rare_critical_red_flags.sort(
        key=lambda item: (item["modality"].lower(), -float(item["frequency_max_num"]), item["complication_name"])
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
        "clinical_decision_nuances": _default_clinical_decision_nuances(),
    }


def load_nosology_bundle(nosology_id: str) -> dict[str, Any]:
    """Load the complete unified data bundle for any configured nosology (CR-03, T-18-02, T-19-05)."""
    nosology_id = validate_nosology_id(nosology_id)
    configs_root = _get_configs_dir().resolve()
    data_root = _get_data_dir().resolve()
    reports_root = _get_reports_dir().resolve()

    cfg_path = (configs_root / f"{nosology_id}.yaml").resolve()
    db_path = (data_root / nosology_id / "literature.db").resolve()
    rep_dir = (reports_root / nosology_id).resolve()
    kb_dir = (rep_dir / "knowledge_base").resolve()
    kb_index_path = (kb_dir / "kb_index.json").resolve()
    if (
        not cfg_path.is_relative_to(configs_root)
        or not db_path.is_relative_to(data_root)
        or not rep_dir.is_relative_to(reports_root)
        or not kb_dir.is_relative_to(reports_root)
        or not kb_index_path.is_relative_to(kb_dir)
    ):
        raise ValueError(f"Path traversal blocked for nosology_id={nosology_id!r}")

    config: dict[str, Any] = {}
    if cfg_path.exists():
        config = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    if kb_index_path.exists():
        kb_data = json.loads(kb_index_path.read_text(encoding="utf-8"))
        if not isinstance(kb_data, dict):
            raise ValueError(f"kb_index.json must be a JSON object: {kb_index_path}")
    else:
        kb_data = build_dynamic_fallback_kb(nosology_id, config, db_path)

    # T-18-02 & IN-02: In-memory only normalization for legacy v1.x corpora (never writes to disk).
    # For schema_version == '2.0', preserve missing/malformed clinical_decision_nuances intact so validation reports the exact error.
    if str(kb_data.get("schema_version", "")) != "2.0":
        nuances_val = kb_data.get("clinical_decision_nuances")
        if not isinstance(nuances_val, dict):
            kb_data["clinical_decision_nuances"] = _default_clinical_decision_nuances()
        else:
            for section_key in REQUIRED_CLINICAL_NUANCE_SECTIONS:
                if not isinstance(nuances_val.get(section_key), list):
                    nuances_val[section_key] = []

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
        if not isinstance(mod, dict):
            continue
        raw_mod_file = str(mod.get("file") or "").strip()
        if not raw_mod_file:
            continue
        m_file = (kb_dir / raw_mod_file).resolve()
        if not m_file.is_relative_to(kb_dir):
            raise ValueError(f"KB module path escapes knowledge_base dir: {raw_mod_file!r}")
        content = m_file.read_text(encoding="utf-8") if m_file.exists() else ""
        kb_modules.append(
            {
                "id": mod.get("id", ""),
                "title": mod.get("title", raw_mod_file),
                "file": raw_mod_file,
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
    """Load `extracted_complications` joined with article metadata safely (empty DataFrame if table absent, D-09/T-17-02/IN-04)."""
    if not db_path.exists():
        return pd.DataFrame()
    conn = _connect_sqlite_readonly(db_path)
    try:
        if not table_exists(conn, "extracted_complications"):
            return pd.DataFrame()
        where_clause = "WHERE COALESCE(c.is_rare_casuistry, 0) = 0" if not include_casuistry else ""
        if table_exists(conn, "articles"):
            sql = f"""
            SELECT
                c.id,
                c.article_id,
                COALESCE(c.pmid, a.pmid) AS pmid,
                COALESCE(c.doi, a.doi) AS doi,
                c.first_author_year,
                a.pub_year,
                COALESCE(c.evidence_tier, a.evidence_tier) AS evidence_tier,
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
            ORDER BY c.modality ASC, COALESCE(c.frequency_num, -1.0) DESC, COALESCE(c.evidence_tier, a.evidence_tier) ASC
            """
        else:
            sql = f"""
            SELECT
                c.id,
                c.article_id,
                c.pmid,
                c.doi,
                c.first_author_year,
                NULL AS pub_year,
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
                NULL AS title
            FROM extracted_complications c
            {where_clause}
            ORDER BY c.modality ASC, COALESCE(c.frequency_num, -1.0) DESC, c.evidence_tier ASC
            """
        df = pd.read_sql_query(sql, conn)
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


def save_new_nosology_config(
    config_payload: dict[str, Any],
    *,
    allow_frozen_overwrite: bool = False,
) -> Path:
    """Save a new nosology configuration to `configs/<id>.yaml` with normalized surgical_focus, query keys, and frozen v1.x guard (T-17-05, T-19-01, D-05.3)."""
    payload = copy.deepcopy(config_payload)
    nos_meta = payload.get("nosology")
    if not isinstance(nos_meta, dict):
        nos_meta = {}
        payload["nosology"] = nos_meta

    raw_nos_id = nos_meta.get("id") or payload.get("nosology_id") or ""
    try:
        nos_id = validate_nosology_id(raw_nos_id)
    except ValueError as exc:
        raise ValueError(
            "Идентификатор нозологии должен содержать только латинские буквы, цифры и '_'"
        ) from exc
    nos_meta["id"] = nos_id

    treatment_profile, surgical_focus = resolve_treatment_profile_and_focus(payload)
    nos_meta["surgical_focus"] = surgical_focus
    if "treatment_profile" in payload or "treatment_profile" in nos_meta or not surgical_focus:
        nos_meta["treatment_profile"] = treatment_profile

    queries_dict = payload.get("queries")
    if isinstance(queries_dict, dict):
        if "openalex" in queries_dict:
            legacy_openalex = queries_dict.pop("openalex")
            if not str(queries_dict.get("openalex_search") or "").strip() and legacy_openalex not in (None, ""):
                queries_dict["openalex_search"] = legacy_openalex
        if "clinicaltrials" in queries_dict:
            legacy_ct = queries_dict.pop("clinicaltrials")
            if not str(queries_dict.get("clinical_trials_condition") or "").strip() and legacy_ct not in (None, ""):
                queries_dict["clinical_trials_condition"] = legacy_ct

    comp_queries = payload.get("complications_queries")
    if isinstance(comp_queries, dict):
        cleaned_queries = {
            k: v
            for k, v in comp_queries.items()
            if k in ("pubmed", "europepmc", "max_results", "pubmed_max_results", "europepmc_max_results")
            and v not in (None, "")
        }
        if cleaned_queries:
            payload["complications_queries"] = cleaned_queries
        else:
            payload.pop("complications_queries", None)

    target_configs = _get_configs_dir()
    target_configs_resolved = target_configs.resolve()
    out_path = (target_configs_resolved / f"{nos_id}.yaml").resolve()
    if out_path.parent != target_configs_resolved:
        raise ValueError("Недопустимый путь сохранения конфигурации нозологии")
    frozen_repo_cfg = (PROJECT_ROOT / "configs" / f"{nos_id}.yaml").resolve()
    if out_path == frozen_repo_cfg and nos_id in FROZEN_V1_NOSOLOGIES and not allow_frozen_overwrite:
        raise PermissionError(
            f"Замороженная конфигурация v1.x '{nos_id}' защищена от перезаписи ({out_path}). "
            "Для явной перезаписи передайте allow_frozen_overwrite=True."
        )
    target_configs.mkdir(parents=True, exist_ok=True)
    yaml_str = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    out_path.write_text(yaml_str, encoding="utf-8")
    return out_path


_PMID_STR_RE = re.compile(r"^[1-9]\d{0,8}$")


def _is_nonempty_str(value: Any) -> bool:
    """Return True strictly for non-blank strings."""
    return isinstance(value, str) and bool(value.strip())


def _has_valid_evidence_pmids(pmids: Any) -> bool:
    """Validate non-empty evidence_pmids array containing strictly numeric positive PMIDs (CR-02, T-18-01)."""
    if not isinstance(pmids, list) or len(pmids) == 0:
        return False
    return all(
        p is not None
        and not isinstance(p, bool)
        and isinstance(p, (str, int))
        and bool(_PMID_STR_RE.fullmatch(str(p).strip()))
        for p in pmids
    )


def validate_kb_complications_v2(kb: dict[str, Any]) -> list[str]:
    """Validate schema_version '2.0' frequent_complications and rare_critical_red_flags contract (COMP-04, D-07..D-09, CR-02, CR-05, WR-06)."""
    if not isinstance(kb, dict):
        return ["Knowledge base payload must be a dict"]
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

            mod = str(entry.get("modality") or "").strip()
            if not mod:
                errors.append(f"frequent_complications[{idx}] has empty modality")

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
            if (
                isinstance(med_raw, bool)
                or not isinstance(med_raw, (int, float))
                or not math.isfinite(float(med_raw))
            ):
                errors.append(f"frequent_complications[{idx}] frequency_median_num must be a finite number")
            else:
                med_val = float(med_raw)
                if med_val < 1.0:
                    errors.append(
                        f"frequent_complications[{idx}] frequency_median_num must be >= 1.0, got {med_val}"
                    )
                elif med_val > 100.0:
                    errors.append(
                        f"frequent_complications[{idx}] frequency_median_num must be <= 100.0, got {med_val}"
                    )
                elif mod:
                    mod_key = mod.lower()
                    if mod_key in last_median_by_modality and med_val > last_median_by_modality[mod_key]:
                        errors.append(
                            f"frequent_complications[{idx}] for modality '{mod}' is not sorted descending "
                            f"by frequency_median_num ({med_val} > {last_median_by_modality[mod_key]})"
                        )
                    last_median_by_modality[mod_key] = med_val

            n_raw = entry.get("sample_size_total")
            if (
                isinstance(n_raw, bool)
                or not isinstance(n_raw, (int, float))
                or not math.isfinite(float(n_raw))
            ):
                errors.append(
                    f"frequent_complications[{idx}] sample_size_total must be a finite number, got {n_raw!r}"
                )
            elif int(n_raw) < 20:
                errors.append(
                    f"frequent_complications[{idx}] sample_size_total must be >= 20, got {n_raw!r}"
                )

            if not _has_valid_evidence_pmids(entry.get("evidence_pmids")):
                errors.append(f"frequent_complications[{idx}] evidence_pmids must be a non-empty list of valid PMIDs")

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

            mod = str(entry.get("modality") or "").strip()
            if not mod:
                errors.append(f"rare_critical_red_flags[{idx}] has empty modality")

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
            if (
                isinstance(max_raw, bool)
                or not isinstance(max_raw, (int, float))
                or not math.isfinite(float(max_raw))
            ):
                errors.append(f"rare_critical_red_flags[{idx}] frequency_max_num must be a finite number")
            elif float(max_raw) >= 1.0 or float(max_raw) < 0.0:
                errors.append(
                    f"rare_critical_red_flags[{idx}] frequency_max_num must be in [0.0, 1.0), got {max_raw}"
                )

            if not _has_valid_evidence_pmids(entry.get("evidence_pmids")):
                errors.append(f"rare_critical_red_flags[{idx}] evidence_pmids must be a non-empty list of valid PMIDs")

    return errors


def validate_kb_clinical_nuances_v2(kb: dict[str, Any]) -> list[str]:
    """Validate schema_version '2.0' clinical_decision_nuances contract (HUM2-02, CR-02, T-18-01, IN-01)."""
    errors: list[str] = []
    if not isinstance(kb, dict):
        return ["Knowledge base payload must be a dict"]

    nuances = kb.get("clinical_decision_nuances")
    if not isinstance(nuances, dict):
        return [
            "Field 'clinical_decision_nuances' must be an object containing "
            "universal_workhorse_modalities, overlapping_indications_and_gray_zones, "
            "and strict_niche_or_salvage_indications"
        ]

    # 1. universal_workhorse_modalities (>= 1 entry)
    if "universal_workhorse_modalities" not in nuances:
        errors.append("clinical_decision_nuances missing required section 'universal_workhorse_modalities'")
    else:
        workhorses = nuances.get("universal_workhorse_modalities")
        if not isinstance(workhorses, list) or len(workhorses) == 0:
            errors.append(
                "clinical_decision_nuances.universal_workhorse_modalities must be a non-empty list (>= 1 workhorse modality)"
            )
        else:
            for idx, entry in enumerate(workhorses):
                prefix = f"clinical_decision_nuances.universal_workhorse_modalities[{idx}]"
                if not isinstance(entry, dict):
                    errors.append(f"{prefix} must be an object")
                    continue
                missing = [k for k in REQUIRED_WORKHORSE_KEYS if k not in entry]
                if missing:
                    errors.append(f"{prefix} missing keys: {missing}")
                for str_field in (
                    "modality",
                    "applicable_spectrum",
                    "practical_nuances",
                    "surgeon_and_equipment_factors",
                    "patient_tradeoffs",
                ):
                    if str_field in entry and not _is_nonempty_str(entry.get(str_field)):
                        errors.append(f"{prefix} has invalid or empty '{str_field}'")
                if "evidence_pmids" in entry and not _has_valid_evidence_pmids(entry.get("evidence_pmids")):
                    errors.append(f"{prefix} evidence_pmids must be a non-empty list of valid PMIDs")

    # 2. overlapping_indications_and_gray_zones (>= 1 entry, >= 2 distinct competing_modalities)
    if "overlapping_indications_and_gray_zones" not in nuances:
        errors.append(
            "clinical_decision_nuances missing required section 'overlapping_indications_and_gray_zones'"
        )
    else:
        overlaps = nuances.get("overlapping_indications_and_gray_zones")
        if not isinstance(overlaps, list) or len(overlaps) == 0:
            errors.append(
                "clinical_decision_nuances.overlapping_indications_and_gray_zones must be a non-empty list"
            )
        else:
            for idx, entry in enumerate(overlaps):
                prefix = f"clinical_decision_nuances.overlapping_indications_and_gray_zones[{idx}]"
                if not isinstance(entry, dict):
                    errors.append(f"{prefix} must be an object")
                    continue
                missing = [k for k in REQUIRED_OVERLAP_KEYS if k not in entry]
                if missing:
                    errors.append(f"{prefix} missing keys: {missing}")
                for str_field in (
                    "clinical_scenario",
                    "why_no_single_winner",
                    "decisive_practical_factors",
                ):
                    if str_field in entry and not _is_nonempty_str(entry.get(str_field)):
                        errors.append(f"{prefix} has invalid or empty '{str_field}'")
                if "competing_modalities" in entry:
                    comp_mods = entry.get("competing_modalities")
                    if not isinstance(comp_mods, list):
                        errors.append(f"{prefix} competing_modalities must be a list of >= 2 distinct modalities")
                    elif not all(_is_nonempty_str(m) for m in comp_mods):
                        errors.append(
                            f"{prefix} competing_modalities must contain only non-empty strings"
                        )
                    else:
                        distinct_mods = {m.strip().lower() for m in comp_mods}
                        if len(distinct_mods) < 2:
                            errors.append(
                                f"{prefix} competing_modalities must contain >= 2 distinct modalities"
                            )
                if "evidence_pmids" in entry and not _has_valid_evidence_pmids(entry.get("evidence_pmids")):
                    errors.append(f"{prefix} evidence_pmids must be a non-empty list of valid PMIDs")

    # 3. strict_niche_or_salvage_indications (>= 0 entries; each present entry strictly validated)
    if "strict_niche_or_salvage_indications" not in nuances:
        errors.append(
            "clinical_decision_nuances missing required section 'strict_niche_or_salvage_indications'"
        )
    else:
        niches = nuances.get("strict_niche_or_salvage_indications")
        if not isinstance(niches, list):
            errors.append(
                "clinical_decision_nuances.strict_niche_or_salvage_indications must be a list"
            )
        else:
            for idx, entry in enumerate(niches):
                prefix = f"clinical_decision_nuances.strict_niche_or_salvage_indications[{idx}]"
                if not isinstance(entry, dict):
                    errors.append(f"{prefix} must be an object")
                    continue
                missing = [k for k in REQUIRED_NICHE_KEYS if k not in entry]
                if missing:
                    errors.append(f"{prefix} missing keys: {missing}")
                for str_field in (
                    "modality",
                    "narrow_indication_or_salvage_role",
                    "why_not_first_line_for_all",
                ):
                    if str_field in entry and not _is_nonempty_str(entry.get(str_field)):
                        errors.append(f"{prefix} has invalid or empty '{str_field}'")
                if "evidence_pmids" in entry and not _has_valid_evidence_pmids(entry.get("evidence_pmids")):
                    errors.append(f"{prefix} evidence_pmids must be a non-empty list of valid PMIDs")

    return errors


def validate_kb_v2(kb: dict[str, Any]) -> list[str]:
    """Validate full schema_version '2.0' KB contract (complications + clinical_decision_nuances, WR-06)."""
    if not isinstance(kb, dict):
        return ["Knowledge base payload must be a dict"]
    return validate_kb_complications_v2(kb) + validate_kb_clinical_nuances_v2(kb)


def verify_universal_schema(nosology_id: str | None = None, schema_version: str = "auto") -> int:
    """Validate that `kb_index.json` and `universal_schema.py` satisfy D-01, D-03, COMP-04/D-09, and HUM2-02."""
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
        v2_errors = validate_kb_v2(kb)
        if v2_errors:
            print(f"[FAIL] Schema v2.0 validation failed for '{nosology_id}':")
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

    from src.docx_exporter import build_executive_docx_bytes

    docx_bytes = build_executive_docx_bytes(bundle["executive_summary_md"], kb)
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
        help="Schema validation mode: auto (detect), v1 (legacy compat), or v2 (strict complications + clinical nuances)",
    )
    args = parser.parse_args()
    if args.verify:
        return verify_universal_schema(args.nosology, schema_version=args.schema_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
