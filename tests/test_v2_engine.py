"""Comprehensive offline E2E v2.0 engine test suite, OpenXML DOM audit, security guards, and Streamlit AppTest.

Covers Phase 19 (UI-02, EXPORT-02, D-01..D-08, T-19-01..T-19-05):
1. Full offline synthetic 6-module v2.0 nosology pipeline in tmp_path:
   harvester.build_complications_queries -> SQLite (5 tables) ->
   aggregate_complications_from_sqlite -> kb_index.json v2.0 ->
   verify_universal_schema(v2) -> verify_reports(v2, read-only).
2. OpenXML (.docx) DOM verification of word/document.xml:
   <w:cantSplit/> before <w:tblHeader/>, single <w:shd>, scoped Clavien-Dindo
   IIIb (FFEDD5/FED7AA) and IV/V/Red Flags (FEE2E2/FECACA) shading with zero
   false positives on staging tables ("Стадия IV"), XML/Markdown escaping of
   <rare> & "pain" | pipe, Appendix A/B presence in executive_summary.docx &
   full_clinical_dossier.docx, clean dissertation_report.docx, and CSV BOM.
3. Security guards (T-19-01..T-19-05):
   path traversal rejection (ValueError), frozen v1.x repo-root overwrite
   protection (PermissionError), and tmp_path isolation.
4. Isolated headless Streamlit AppTest (INFO_SEARCHER_ROOT=tmp_path):
   Sidebar "Строк осложнений" KPI, dynamic 6-module Mode C, Tab 2 subtabs 2.5
   (Plotly charts, color switch, Red Flags) & 2.6 (all 3 nuance blocks),
   Tab 3 option 5 + Tier 4 casuistry toggle, Tab 4 reactive surgical_focus live
   preview & YAML save (openalex_search / clinical_trials_condition), and
   read-only btn_run_verify subprocess verification (--verify --read-only,
   shell=False, 0 file mutations).
5. Frozen v1.x immutability & backward-compatibility regression suite:
   all 3 frozen nosologies (prom, metroplasty_pregnancy, trigger_finger) with
   recursive SHA-256 + st_mtime_ns + st_size + no -wal/-shm + git status gate.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import streamlit as st
import yaml
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.docx_exporter as docx_exporter
import src.extractor_common as extractor_common
import src.harvester as harvester
import src.schema as schema
import src.universal_schema as universal_schema
import src.verify_reports as verify_reports


W_NS = docx_exporter.W_NS
W = f"{{{W_NS}}}"
SPECIAL_COMPLICATION_NAME = 'Глубокая адгезия с ревизией <rare> & "pain" | pipe'


# ===========================================================================
# Synthetic 6-module v2.0 workspace builder (100% offline, isolated tmp_path)
# ===========================================================================


def _build_synthetic_v2_dissertation_md() -> str:
    """Return de-AI-ized Russian dissertation prose compliant with Humanizer v2.0 (>3500 bytes, 36 refs)."""
    body = """# Клинико-хирургический синтез лечения стенозирующего лигаментита кисти (v2.0)

## Глава 1. Методология систематического отбора и доказательная структура корпуса

Систематический анализ рандомизированных контролируемых исследований, проспективных когорт и реестров хирургии кисти за 2016–2026 годы объединяет 36 верифицированных публикаций и два завершённых клинических протокола [1–6]. Раздельная стратификация исходов позволяет чётко отличать истинный рецидив в зоне первичного вмешательства, продолженное поражение соседних пальцев и послеоперационные осложнения, кодируемые по шкале Clavien–Dindo [7–11]. Такое разграничение устраняет методическую путаницу между технически неполным рассечением кольцевидной связки и ятрогенным повреждением мягких тканей или нервно-сосудистых структур.

Сравнительная оценка вмешательств опирается на анатомический статус кисти, компенсацию сопутствующего сахарного диабета, антикоагулянтную нагрузку и функциональные приоритеты пациента [12–17]. Плюсы и Минусы каждого доступа целесообразно сопоставлять не по одному раннему проценту исчезновения щелчка, а по совокупности раневой морбидности, темпов возврата к ручному труду и частоты повторных ревизий на пятилетнем горизонте [18–22].

## Глава 2. Профиль осложнений лечения и профилактика ятрогенных повреждений

Послеоперационные реакции и истинные хирургические осложнения принципиально различаются по клинической тяжести, срокам регресса и потребности в ревизии [23–26]. После открытого рассечения связки A1 ведущим транзиторным явлением выступает болезненность ладонного рубца (медиана 14,5%, Clavien–Dindo I), которая самостоятельно стихает за 2–8 недель при щадящем уходе за швом и раннем массаже [27–29]. Поверхностные инфекции раны (Clavien–Dindo II) регистрируются примерно у 3,2% пациентов после чрескожного доступа под ультразвуковым контролем и купируются коротким курсом пероральной антибактериальной терапии без ревизии раны [30, 31]. Более тяжёлые рубцовые адгезии сухожильного аппарата (Clavien–Dindo IIIb, 1,8%) требуют повторного вмешательства и ранней кистевой терапии для восстановления скольжения сгибателей [32].

Редкие критические осложнения класса Clavien–Dindo IV (< 1%) вынесены в отдельный контур красных флагов [33, 34]. Наиболее опасным ятрогенным событием при чрескожных и эндоскопических техниках остаётся стойкое повреждение собственного ладонного пальцевого нерва или сосудистого пучка, особенно на первом луче с косым ходом нерва. Профилактика необратимого дефицита строится на непрерывной динамической сонографической визуализации либо конверсии в открытый доступ при малейшей анатомической неопределённости.

- **Маркер клинической безопасности:** раздельная регистрация транзиторной болезненности рубца (Clavien–Dindo I) и истинных хирургических осложнений (Clavien–Dindo II–IV) предотвращает искусственное завышение риска открытого доступа [34].
- **Контроль ятрогении:** отказ от «слепой» чрескожной методики при отсутствии высокочастотного датчика снижает вероятность травмы пальцевого нерва и сухожилий сгибателей [35].

## Глава 3. Заключение и практическая тактика выбора метода

При первичных формах заболевания стадий I–III открытый релиз связки A1 и УЗ-контролируемый чрескожный релиз не делят пациентов по жёстким ступеням классификации — обе сквозные конкурирующие методики охватывают практически весь амбулаторный поток и обеспечивают сопоставимую стойкую пятилетнюю ремиссию свыше 92% [35, 36]. Реальная развилка проходит через практические компромиссы, оснащение операционной и профиль осложнений, а не формальный номер стадии.

Открытый доступ воспроизводим без специализированного УЗИ-датчика, гарантирует прямой визуальный контроль сосудисто-нервных пучков и опирается на короткую кривую обучения, но связан с временной болезненностью ладонного рубца в ранней реабилитации. УЗ-контролируемый чрескожный релиз сокращает восстановление бытового захвата до 1–2 недель и минимизирует кожную травму, однако критически зависит от опыта хирурга, владения динамической соноанатомией и наличия линейного датчика. Выбор между этими равноценными подходами определяется оснащением клиники, антикоагулянтным фоном и предпочтениями пациента относительно сроков возврата к нагрузке.

В отдельную узкую резервную нишу выносятся эндоскопическая декомпрессия и ревизионный открытый тенолиз при рецидивных рубцовых сращениях и стойкой контрактуре проксимального межфалангового сустава, когда стандартное первичное рассечение не устраняет вторичные адгезии [36].
"""
    bib_lines = [
        f"{i}. Author{i} A. Synthetic hand surgery outcomes study #{i} // Hand Surgery Review. — {2016 + (i % 10)}. — PMID: {88000000 + i}."
        for i in range(1, 37)
    ]
    return body + "\n---\n\n## Список литературы\n\n" + "\n".join(bib_lines) + "\n"


def _build_synthetic_v2_executive_summary_md() -> str:
    """Return de-AI-ized v2.0 Executive Summary (>3500 bytes) with a staging table containing 'Стадия IV'."""
    text = (
        "# Краткое клиническое руководство: стенозирующий лигаментит кисти (v2.0)\n\n"
        "## 1. Клиническая классификация стадий и профиль осложнений\n\n"
        "Сравнительная оценка Плюсы и Минусы основных методик подтверждена в проспективных когортах "
        "[PMID: 88000001; PMID: 88000002; PMID: 88000003] и клинических протоколах NCT05123456 и NCT05123457. "
        "Таблица ниже отражает распределение пациентов по клиническим стадиям тяжести (включая Стадия IV с "
        "фиксированной контрактурой); обратите внимание, что стадия служит анатомическим описанием, а не жёстким "
        "запретом на сквозные методики.\n\n"
        "| Стадия | Пороговый критерий | Доля в популяции | Клиническое описание |\n"
        "| :--- | :---: | :---: | :--- |\n"
        "| Стадия I | Пальпируемый узел | 22% | Локальная болезненность в проекции связки A1 без защёлкивания |\n"
        "| Стадия II | Активное разгибание | 38% | Воспроизводимый щелчок с самостоятельным разгибанием пальца |\n"
        "| Стадия III | Пассивная коррекция | 28% | Фиксация в сгибании, требующая пассивного расправления другой рукой |\n"
        "| Стадия IV | > 90° | 12% | Фиксированная сгибательная контрактура ПМФС с вторичным укорочением капсулы |\n\n"
        "Профиль безопасности вмешательств стратифицирован по Clavien–Dindo: транзиторная болезненность рубца "
        "(Clavien–Dindo I, 14,5%) проходит самостоятельно за 2–8 недель, поверхностная инфекция раны "
        "(Clavien–Dindo II, 3,2%) купируется консервативно, а рубцовая адгезия (Clavien–Dindo IIIb, 1,8%) "
        "требует ревизии [PMID: 88000001; PMID: 88000002; PMID: 88000003]. Редкие критические повреждения "
        "нервно-сосудистого пучка (Clavien–Dindo IV, < 1%) контролируются строгой профилактикой и динамической "
        "визуализацией [PMID: 88000004; PMID: 88000005].\n\n"
        "| Методика | 5-летняя ремиссия | Профиль осложнений | Плюсы и Минусы |\n"
        "| :--- | :---: | :--- | :--- |\n"
        "| Открытый релиз связки A1 | 94% | Рубцовая боль 14,5%, ревизионная адгезия 1,8% | Плюсы: прямой обзор; Минусы: рубец |\n"
        "| УЗ-контролируемый чрескожный релиз | 92% | Поверхностная инфекция 3,2%, травма нерва 0,4% | Плюсы: ранняя нагрузка; Минусы: кривая обучения |\n\n"
        "## 2. Практическая тактика и клинические компромиссы\n\n"
        "Обе сквозные операции — открытый релиз связки A1 и УЗ-контролируемый чрескожный релиз — конкурируют "
        "на одних и тех же первичных пациентах и показывают равноценную отдалённую стойкость ремиссии "
        "[PMID: 88000006; PMID: 88000007]. В повседневной клинике выбор опирается на оснащение кабинета "
        "высокочастотным УЗИ-датчиком, опыт хирурга, антикоагулянтный статус и предпочтения пациента по "
        "срокам возврата к работе и терпимости к послеоперационному рубцу. Эндоскопическая декомпрессия и "
        "расширенный открытый тенолиз занимают узкую резервную нишу для рецидивных и фиксированных "
        "контрактур [PMID: 88000008].\n\n"
        + (
            "Долговременное наблюдение проспективных хирургических серий подтверждает стабильность захвата "
            "кисти при соблюдении протоколов асептики, гликемического контроля и ранней функциональной "
            "мобилизации сухожилий сгибателей [PMID: 88000009; PMID: 88000010]. "
            * 7
        )
    )
    return text


def _build_synthetic_v2_workspace(
    base_dir: Path,
    nosology_id: str = "synthetic_hand_v2",
) -> dict[str, Any]:
    """Create a complete, self-contained 6-module v2.0 nosology workspace under base_dir."""
    cfg_dir = base_dir / "configs"
    data_dir = base_dir / "data" / nosology_id
    rep_dir = base_dir / "reports" / nosology_id
    kb_dir = rep_dir / "knowledge_base"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    kb_dir.mkdir(parents=True, exist_ok=True)

    cfg_dict: dict[str, Any] = {
        "nosology": {
            "id": nosology_id,
            "name_ru": "Синтетический стенозирующий лигаментит кисти (v2.0)",
            "name_en": "Synthetic Trigger Finger Condition",
            "icd10": "M65.3",
            "icd11": "FB40.2",
            "specialty": "Хирургия кисти",
            "surgical_focus": True,
            "treatment_profile": "surgical",
            "mesh_terms": ["Trigger Finger Disorder", "Hand Surgery"],
        },
        "date_range": {"start_year": 2016, "end_year": 2026},
        "queries": {
            "pubmed": '("Trigger Finger Disorder"[MeSH] OR "A1 pulley release"[tiab])',
            "europepmc": '("trigger finger" OR "A1 pulley release")',
            "openalex_search": "Trigger Finger Disorder",
            "clinical_trials_condition": "Trigger Finger",
        },
        "triage_rules": {
            "core_terms": ["trigger finger", "A1 pulley release", "stenosing tenosynovitis"],
        },
        "verification_rules": {
            "required_terms": ["Плюсы", "Минусы"],
        },
    }
    cfg_path = cfg_dir / f"{nosology_id}.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg_dict, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # 1. Populate SQLite (all 5 tables)
    db_path = data_dir / "literature.db"
    conn = schema.init_db(db_path)
    try:
        article_ids: dict[int, int] = {}
        for i in range(1, 37):
            pmid = str(88000000 + i)
            pmcid = f"PMC88000{i:02d}" if i <= 10 else None
            has_xml = 1 if i <= 10 else 0
            # Explicit tier mapping for first 5 articles linked to complications; cycle 1..4 for rest
            if i == 5:
                tier = 4
            elif i in (1, 2, 3, 4):
                tier = 2
            else:
                tier = ((i - 1) % 4) + 1
            nct_ref = "NCT05123456" if i % 2 == 1 else "NCT05123457"
            cur = conn.execute(
                """
                INSERT INTO articles (
                    pmid, pmcid, doi, title, norm_title, abstract, authors, journal,
                    pub_year, pub_types, prisma_status, evidence_tier, clusters,
                    cited_by_count, is_open_access, has_fulltext_xml, sources
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pmid,
                    pmcid,
                    f"10.1000/v2synth.{i}",
                    f"Synthetic hand surgery cohort #{i} evaluating Clavien-Dindo safety",
                    f"synthetichandsurgerycohort{i}",
                    f"Prospective evaluation referencing {nct_ref} with Clavien-Dindo outcomes and safety endpoints.",
                    json.dumps([f"Author{i} A", "Coauthor B"]),
                    "Hand Surgery Review",
                    2016 + (i % 10),
                    json.dumps(["Case Reports"] if tier == 4 else ["Journal Article"]),
                    "included",
                    tier,
                    json.dumps(["surgical_outcomes", "complications_safety"]),
                    10 + i,
                    1 if pmcid else 0,
                    has_xml,
                    json.dumps(["PubMed", "EuropePMC:Complications"]),
                ),
            )
            article_ids[i] = int(cur.lastrowid)

        conn.execute(
            """
            INSERT INTO clinical_trials (
                nct_id, brief_title, official_title, overall_status, phase,
                study_type, interventions, enrollment, start_date, completion_date,
                has_results, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "NCT05123456",
                "Open vs Ultrasound-Guided A1 Pulley Release",
                "Randomized Trial Comparing Open and US-Guided Release",
                "COMPLETED",
                "PHASE3",
                "INTERVENTIONAL",
                "Open A1 pulley release | Ultrasound-guided percutaneous release",
                240,
                "2021-01-15",
                "2024-06-30",
                1,
                "Comparable 5-year remission rates with distinct scar vs nerve safety profiles.",
            ),
        )
        conn.execute(
            """
            INSERT INTO clinical_trials (
                nct_id, brief_title, official_title, overall_status, phase,
                study_type, interventions, enrollment, start_date, completion_date,
                has_results, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "NCT05123457",
                "Postoperative Complication Surveillance Registry",
                "Prospective Clavien-Dindo Registry in Hand Surgery",
                "ACTIVE_NOT_RECRUITING",
                "NA",
                "OBSERVATIONAL",
                "Standardized open and percutaneous hand procedures",
                450,
                "2022-03-01",
                "2026-01-01",
                0,
                "Longitudinal tracking of transient sequelae versus true reoperation complications.",
            ),
        )

        # >= 2 rows extracted_clinical_evidence
        conn.execute(
            """
            INSERT INTO extracted_clinical_evidence (
                article_id, pmid, doi, first_author_year, study_design, evidence_tier,
                n_patients, intervention_group, comparator_group, followup_months,
                mcp_outcome, pip_outcome, recurrence_rate_overall, recurrence_rate_mcp,
                recurrence_rate_pip, complications_summary, complications_rate, key_conclusion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article_ids[1],
                "88000001",
                "10.1000/v2synth.1",
                "Author1 2023",
                "RCT",
                2,
                120,
                "Открытый релиз связки A1",
                "УЗ-контролируемый чрескожный релиз",
                60.0,
                "95% полное купирование",
                "91% без контрактуры",
                "4.2%",
                "3.1%",
                "5.4%",
                "Транзиторная болезненность рубца 14.5% (Clavien-Dindo I)",
                "14.5%",
                "Высокая стойкость ремиссии при минимальном риске травмы нерва.",
            ),
        )
        conn.execute(
            """
            INSERT INTO extracted_clinical_evidence (
                article_id, pmid, doi, first_author_year, study_design, evidence_tier,
                n_patients, intervention_group, comparator_group, followup_months,
                mcp_outcome, pip_outcome, recurrence_rate_overall, recurrence_rate_mcp,
                recurrence_rate_pip, complications_summary, complications_rate, key_conclusion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article_ids[2],
                "88000002",
                "10.1000/v2synth.2",
                "Author2 2024",
                "Prospective Cohort",
                2,
                210,
                "УЗ-контролируемый чрескожный релиз",
                "Открытый релиз связки A1",
                48.0,
                "93% полное купирование",
                "89% восстановление объёма",
                "5.8%",
                "4.0%",
                "7.1%",
                "Поверхностная инфекция 3.2% (Clavien-Dindo II)",
                "3.2%",
                "Быстрая реабилитация при условии достаточного сонографического опыта.",
            ),
        )

        # >= 2 rows extracted_mechanisms
        conn.execute(
            """
            INSERT INTO extracted_mechanisms (
                article_id, pmid, doi, first_author_year, category,
                targets_genes_pathways, study_model, sample_size,
                quantitative_findings, mechanism_summary, therapeutic_implication
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article_ids[3],
                "88000003",
                "10.1000/v2synth.3",
                "Author3 2023",
                "Фиброз и ремоделирование матрикса",
                "TGF-beta1 / COL1A1 / COL3A1",
                "Human pulley biopsy",
                "48 specimens",
                "COL3A1 expression +2.4-fold (p < 0.01)",
                "Хондроидная метаплазия и утолщение кольцевидной связки A1 под механическим сдвигом.",
                "Обоснование раннего механического или хирургического устранения конфликта скольжения.",
            ),
        )
        conn.execute(
            """
            INSERT INTO extracted_mechanisms (
                article_id, pmid, doi, first_author_year, category,
                targets_genes_pathways, study_model, sample_size,
                quantitative_findings, mechanism_summary, therapeutic_implication
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article_ids[4],
                "88000004",
                "10.1000/v2synth.4",
                "Author4 2024",
                "Метаболическая гликация",
                "AGEs / RAGE / MMP-2",
                "Diabetic vs control cohort",
                "64 specimens",
                "Cross-link density +1.9-fold in HbA1c > 7.5%",
                "Накопление конечных продуктов гликирования повышает жёсткость сухожильного влагалища и риск раневых осложнений.",
                "Предоперационная коррекция гликемии снижает частоту раневой инфекции и адгезий.",
            ),
        )

        # 5 diverse rows in extracted_complications via extractor_common.insert_extracted_complication
        complication_rows = [
            {
                "article_id": article_ids[1],
                "pmid": "88000001",
                "doi": "10.1000/v2synth.1",
                "first_author_year": "Author1 2023",
                "evidence_tier": 2,
                "modality": "Открытый релиз связки A1",
                "complication_name": "Транзиторная болезненность ладонного рубца",
                "event_class": "transient_postop_sequela",
                "timing_category": "early_postop",
                "clavien_dindo_grade": "I",
                "frequency_pct": "14.5% (17/120)",
                "frequency_num": 14.5,
                "reversibility": "transient_self_limiting",
                "time_window": "2–8 недель",
                "anatomical_substrate": "Ладонный кожно-подкожный рубец над связкой A1",
                "prevention_and_management": "Щадящий разрез по кожным складкам, силиконовые пластины и ранний массаж",
                "sample_size": 120,
                "is_rare_casuistry": 0,
            },
            {
                "article_id": article_ids[2],
                "pmid": "88000002",
                "doi": "10.1000/v2synth.2",
                "first_author_year": "Author2 2024",
                "evidence_tier": 2,
                "modality": "УЗ-контролируемый чрескожный релиз",
                "complication_name": "Поверхностная раневая инфекция",
                "event_class": "true_complication",
                "timing_category": "early_postop",
                "clavien_dindo_grade": "II",
                "frequency_pct": "3.2% (7/210)",
                "frequency_num": 3.2,
                "reversibility": "requires_conservative_therapy",
                "time_window": "до 14 суток",
                "anatomical_substrate": "Кожный прокол и подкожная клетчатка ладони",
                "prevention_and_management": "Стерильный чехол УЗИ-датчика, контроль HbA1c, короткий курс пероральных антибиотиков",
                "sample_size": 210,
                "is_rare_casuistry": 0,
            },
            {
                "article_id": article_ids[3],
                "pmid": "88000003",
                "doi": "10.1000/v2synth.3",
                "first_author_year": "Author3 2023",
                "evidence_tier": 2,
                "modality": "Открытый релиз связки A1",
                "complication_name": SPECIAL_COMPLICATION_NAME,
                "event_class": "true_complication",
                "timing_category": "late_postop",
                "clavien_dindo_grade": "IIIb",
                "frequency_pct": "1.8% (4/240)",
                "frequency_num": 1.8,
                "reversibility": "requires_reoperation",
                "time_window": "3–6 месяцев",
                "anatomical_substrate": "Сухожилие глубокого сгибателя и влагалище в зоне A1–A2",
                "prevention_and_management": "Ранняя активная мобилизация с первых суток; при стойком блоке — открытый тенолиз",
                "sample_size": 240,
                "is_rare_casuistry": 0,
            },
            {
                "article_id": article_ids[4],
                "pmid": "88000004",
                "doi": "10.1000/v2synth.4",
                "first_author_year": "Author4 2024",
                "evidence_tier": 2,
                "modality": "УЗ-контролируемый чрескожный релиз",
                "complication_name": "Стойкое повреждение лучевого пальцевого нерва",
                "event_class": "true_complication",
                "timing_category": "intraop",
                "clavien_dindo_grade": "IV",
                "frequency_pct": "0.4% (2/450)",
                "frequency_num": 0.4,
                "reversibility": "permanent_deficit",
                "time_window": "стойкий неврологический дефицит",
                "anatomical_substrate": "Собственный ладонный пальцевой нерв первого луча",
                "prevention_and_management": "Непрерывная динамическая сонографическая визуализация нерва; при травме — микрохирургический шов",
                "sample_size": 450,
                "is_rare_casuistry": 0,
            },
            {
                "article_id": article_ids[5],
                "pmid": "88000005",
                "doi": "10.1000/v2synth.5",
                "first_author_year": "Author5 2024",
                "evidence_tier": 4,
                "modality": "Эндоскопическая декомпрессия",
                "complication_name": "Ятрогенный тромбоз пальцевой артерии с ишемией (казуистика Tier 4)",
                "event_class": "true_complication",
                "timing_category": "intraop",
                "clavien_dindo_grade": "IV",
                "frequency_pct": "1/1 (100%)",
                "frequency_num": 100.0,
                "reversibility": "permanent_deficit",
                "time_window": "экстренная ревизия в 24 ч",
                "anatomical_substrate": "Ладонный сосудисто-нервный пучок пальца",
                "prevention_and_management": "Строгий визуальный контроль до пересечения тканей; экстренная сосудистая ревизия",
                "sample_size": 1,
                "is_rare_casuistry": 1,
            },
        ]
        for row_payload in complication_rows:
            inserted_id = extractor_common.insert_extracted_complication(conn, row_payload)
            assert inserted_id is not None
        conn.commit()
    finally:
        conn.close()

    # 2. Aggregate complications from SQLite
    freq_comps, red_flags = universal_schema.aggregate_complications_from_sqlite(db_path)
    assert len(freq_comps) >= 3, f"Expected >= 3 frequent complications, got {len(freq_comps)}"
    assert len(red_flags) >= 1, f"Expected >= 1 rare critical red flag, got {len(red_flags)}"

    # 3. Build complete schema_version '2.0' kb_index.json with all 8 REQUIRED_UNIVERSAL_KEYS & 6 modules
    kb_module_specs = [
        ("01_epidemiology_and_staging", "Модуль 1. Эпидемиология и классификация стадий", "01_epidemiology_and_staging.md", "epidemiology"),
        ("02_etiology_and_pathogenesis", "Модуль 2. Этиология и молекулярный патогенез", "02_etiology_and_pathogenesis.md", "pathogenesis"),
        ("03_treatment_modalities", "Модуль 3. Хирургические и консервативные методики", "03_treatment_modalities.md", "clinical"),
        ("04_long_term_outcomes", "Модуль 4. Отдалённые исходы, рецидив и процедив", "04_long_term_outcomes.md", "outcomes"),
        ("05_clinical_decision_nuances", "Модуль 5. Клинические компромиссы и серые зоны", "05_clinical_decision_nuances.md", "decision"),
        ("06_complications_and_safety", "Модуль 6. Осложнения лечения и безопасность (Clavien–Dindo)", "06_complications_and_safety.md", "safety"),
    ]
    modules_index = [
        {"id": mid, "title": mtitle, "file": mfile, "category": mcat}
        for mid, mtitle, mfile, mcat in kb_module_specs
    ]

    modality_names = [
        ("Открытый релиз связки A1", "Хирургические вмешательства"),
        ("УЗ-контролируемый чрескожный релиз", "Малоинвазивные вмешательства"),
        ("Эндоскопическая декомпрессия", "Малоинвазивные вмешательства"),
        ("Локальная инъекция кортикостероида под УЗИ", "Консервативная терапия"),
        ("Ортезирование ПМФС/ПФС", "Консервативная терапия"),
        ("Комбинированная инъекция + кистевая реабилитация", "Консервативная терапия"),
        ("Открытый ревизионный тенолиз", "Ревизионная хирургия"),
        ("Резекция ножки поверхностного сгибателя (FDS)", "Ревизионная хирургия"),
    ]
    modalities = []
    for idx, (m_name, m_grp) in enumerate(modality_names, start=1):
        modalities.append(
            {
                "name": m_name,
                "group": m_grp,
                "target_stage": "Стадии I–IV" if idx <= 2 else "Стадии I–III",
                "primary_efficacy": f"{96 - idx}%",
                "remission_5y_pct": f"{94 - idx * 2}%",
                "remission_5y_num": float(94 - idx * 2),
                "recurrence_1_2y": f"{2 + idx}%",
                "recurrence_1_2y_num": float(2 + idx),
                "recurrence_3y": f"{4 + idx}%",
                "recurrence_3y_num": float(4 + idx),
                "recurrence_5y_overall": f"{5 + idx * 2}%",
                "recurrence_5y_num": float(5 + idx * 2),
                "recurrence_10y": f"{8 + idx * 2}%",
                "recurrence_10y_num": float(8 + idx * 2),
                "recurrence_by_subtype": {
                    "Идиопатический": f"{4 + idx}%",
                    "Диабетический": f"{9 + idx}%",
                    "favorable_num": float(4 + idx),
                    "unfavorable_num": float(9 + idx),
                },
                "procediv_5y": f"{6 + idx}%",
                "procediv_5y_num": float(6 + idx),
                "reintervention_5y": f"{3 + idx}%",
                "reintervention_5y_num": float(3 + idx),
                "complications_profile": "См. структурированный профиль Clavien–Dindo в Приложении А и подвкладке 2.5",
                "recovery_time": "1–4 недели",
                "pros": "Воспроизводимый функциональный результат и документированная безопасность",
                "cons": "Зависимость профиля осложнений от коморбидности и оснащения клиники",
            }
        )

    corpus_stats = universal_schema.get_sqlite_corpus_stats(db_path)
    kb_index: dict[str, Any] = {
        "schema_version": "2.0",
        "nosology_id": nosology_id,
        "title_ru": f"{cfg_dict['nosology']['name_ru']} (M65.3)",
        "updated_at": "2026-11-22",
        "nosology_meta": {
            "nosology_id": nosology_id,
            "title_ru": cfg_dict["nosology"]["name_ru"],
            "title_en": cfg_dict["nosology"]["name_en"],
            "icd10": "M65.3",
            "icd11": "FB40.2",
            "specialty": "Хирургия кисти",
            "time_horizon": "2016–2026",
            "corpus_stats": corpus_stats,
        },
        "corpus_stats": corpus_stats,
        "staging_and_classification": {
            "classification_name": "Клиническая шкала стадий Green (I–IV)",
            "metric_label": "Механический блок скольжения сухожилия и дефицит разгибания",
            "stages": [
                {
                    "stage_code": "Стадия I",
                    "threshold": "Локальная боль без щелчка",
                    "population_share": "22%",
                    "population_share_num": 22.0,
                    "interventional_share": "8%",
                    "interventional_share_num": 8.0,
                    "natural_progression": "Стабилизация или переход в стадию II за 6–12 мес",
                    "clinical_description": "Пальпаторная болезненность в проекции связки A1",
                },
                {
                    "stage_code": "Стадия II",
                    "threshold": "Щелчок с активным разгибанием",
                    "population_share": "38%",
                    "population_share_num": 38.0,
                    "interventional_share": "32%",
                    "interventional_share_num": 32.0,
                    "natural_progression": "Волнообразное течение с эпизодами утренней фиксации",
                    "clinical_description": "Воспроизводимое защёлкивание при сгибании и активном разгибании",
                },
                {
                    "stage_code": "Стадия III",
                    "threshold": "Требуется пассивное разгибание",
                    "population_share": "28%",
                    "population_share_num": 28.0,
                    "interventional_share": "42%",
                    "interventional_share_num": 42.0,
                    "natural_progression": "Риск перехода во вторичную контрактуру ПМФС",
                    "clinical_description": "Стойкий механический блок скольжения сухожилия сгибателя",
                },
                {
                    "stage_code": "Стадия IV",
                    "threshold": "> 90° фиксированной контрактуры",
                    "population_share": "12%",
                    "population_share_num": 12.0,
                    "interventional_share": "18%",
                    "interventional_share_num": 18.0,
                    "natural_progression": "Фиксация капсулы ПМФС без спонтанного регресса",
                    "clinical_description": "Фиксированная сгибательная деформация сустава",
                },
            ],
        },
        "anatomical_or_subtype_distribution": {
            "dimension_name": "Распределение по лучам кисти и фенотипам",
            "subtypes": [
                {
                    "rank": 1,
                    "category": "Анатомический луч",
                    "locus_or_subtype": "IV палец (безымянный)",
                    "share_pct": "34%",
                    "share_num": 34.0,
                    "prognostic_impact": "Типичный амбулаторный профиль для сквозных методик",
                },
                {
                    "rank": 2,
                    "category": "Анатомический луч",
                    "locus_or_subtype": "I палец (большой)",
                    "share_pct": "30%",
                    "share_num": 30.0,
                    "prognostic_impact": "Близкое косое прохождение лучевого пальцевого нерва требует УЗ-визуализации или открытого обзора",
                },
                {
                    "rank": 3,
                    "category": "Метаболический фенотип",
                    "locus_or_subtype": "Диабетический многолучевой фенотип",
                    "share_pct": "21%",
                    "share_num": 21.0,
                    "prognostic_impact": "Повышенный риск раневой инфекции Clavien–Dindo II и продолженного поражения соседних лучей",
                },
            ],
        },
        "etiology_and_risk_factors": [
            {
                "factor_name": "Сахарный диабет 1–2 типа",
                "category": "Метаболический",
                "direction": "Фактор риска ↑",
                "effect_size": "OR 3.1 (95% CI 2.4–4.0)",
                "clinical_notes": "Повышает вероятность двустороннего поражения и раневой инфекции",
                "mechanism": "Неферментативное гликирование коллагена связки A1",
            },
            {
                "factor_name": "Повторяющаяся силовая нагрузка хвата",
                "category": "Механический",
                "direction": "Фактор риска ↑",
                "effect_size": "OR 1.8",
                "clinical_notes": "Провоцирует гипертрофию фиброхряща в зоне контакта",
                "mechanism": "Хронический сдвиговый стресс и хондроидная метаплазия",
            },
            {
                "factor_name": "Ревматоидный артрит",
                "category": "Иммуновоспалительный",
                "direction": "Фактор риска ↑",
                "effect_size": "OR 2.5",
                "clinical_notes": "Требует бережного обращения с теносиновием и контроля активности",
                "mechanism": "Пролиферативный теносиновит сгибателей",
            },
            {
                "factor_name": "Ранняя контролируемая кистевая мобилизация",
                "category": "Реабилитационный",
                "direction": "Протективный ↓",
                "effect_size": "RR 0.52 для адгезий",
                "clinical_notes": "Снижает частоту послеоперационной тугоподвижности ПМФС",
                "mechanism": "Предупреждение спаек сухожильного влагалища",
            },
        ],
        "pathogenesis_phases": [
            {
                "phase_order": 1,
                "phase_name": "Фаза I — Микротравматизация и отёк влагалища",
                "cellular_and_tissue_events": "Активация фибробластов и локальная экспрессия TGF-beta1.",
                "clinical_correlate": "Локальная болезненность и утренняя скованность",
                "therapeutic_window": "Консервативная разгрузка и таргетное купирование воспаления",
            },
            {
                "phase_order": 2,
                "phase_name": "Фаза II — Фиброхрящевая метаплазия связки A1",
                "cellular_and_tissue_events": "Утолщение кольцевидной связки и сужение канала скольжения сухожилия.",
                "clinical_correlate": "Стойкое защёлкивание и блок разгибания",
                "therapeutic_window": "Открытый либо УЗ-контролируемый релиз связки A1",
            },
        ],
        "natural_history_and_dynamics": {
            "untreated_course_summary": "Без лечения у части пациентов с ранней стадией возможна стабилизация, но при стойком блоке возрастает риск вторичной контрактуры ПМФС.",
            "definitions": {
                "natural_history": "Динамика симптомов без инвазивного вмешательства.",
                "primary_remission": "Полное восстановление безболезненного скольжения сухожилия.",
                "true_recurrence": "Возврат механического защёлкивания в оперированном луче.",
                "procediv_progression": "Последовательное вовлечение ранее интактных пальцев кисти.",
            },
        },
        "modules": modules_index,
        "modalities": modalities,
        "frequent_complications": freq_comps,
        "rare_critical_red_flags": red_flags,
        "clinical_decision_nuances": {
            "universal_workhorse_modalities": [
                {
                    "modality": "Открытый релиз связки A1",
                    "applicable_spectrum": "Первичные формы стадий I–IV на любом луче кисти, включая I палец",
                    "practical_nuances": "Прямой визуальный контроль сосудисто-нервных пучков и ревизия состояния сухожилий сгибателей",
                    "surgeon_and_equipment_factors": "Не требует УЗИ-оборудования экспертного класса; воспроизводим при базовом опыте кистевого хирурга",
                    "patient_tradeoffs": "Транзиторная болезненность ладонного рубца в течение 2–8 недель в обмен на минимальный риск неполного релиза",
                    "evidence_pmids": ["88000001", "88000003"],
                },
                {
                    "modality": "УЗ-контролируемый чрескожный релиз",
                    "applicable_spectrum": "Первичные амбулаторные формы стадий I–III при чёткой сонографической визуализации",
                    "practical_nuances": "Минимальный кожный доступ ускоряет восстановление бытового захвата без ладонного рубца",
                    "surgeon_and_equipment_factors": "Критическая зависимость от наличия линейного датчика >=12 МГц и пройденной кривой обучения",
                    "patient_tradeoffs": "Возврат к работе за 7–14 дней при строгом соблюдении протокола визуализации пальцевых нервов",
                    "evidence_pmids": ["88000002", "88000004"],
                },
            ],
            "overlapping_indications_and_gray_zones": [
                {
                    "clinical_scenario": "Первичный стенозирующий лигаментит II–III стадии без фиксированной контрактуры ПМФС",
                    "competing_modalities": [
                        "Открытый релиз связки A1",
                        "УЗ-контролируемый чрескожный релиз",
                    ],
                    "why_no_single_winner": "Обе сквозные методики обеспечивают сопоставимую пятилетнюю ремиссию 92–94% в сопоставимых когортах",
                    "decisive_practical_factors": "Оснащённость операционной линейным УЗИ-датчиком, опыт хирурга, антикоагулянтный фон и приоритет пациента по срокам реабилитации",
                    "evidence_pmids": ["88000001", "88000002"],
                }
            ],
            "strict_niche_or_salvage_indications": [
                {
                    "modality": "Эндоскопическая декомпрессия и открытый ревизионный тенолиз",
                    "narrow_indication_or_salvage_role": "Рецидивные рубцовые адгезии после первичного вмешательства и фиксированная контрактура ПМФС",
                    "why_not_first_line_for_all": "Более высокая стоимость оснащения, длинная кривая обучения и редкий сосудисто-нервный риск не оправданы при первичных формах",
                    "evidence_pmids": ["88000005"],
                }
            ],
        },
    }
    kb_json_path = kb_dir / "kb_index.json"
    kb_json_path.write_text(json.dumps(kb_index, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4. Write clean Markdown reports & all 6 KB modules (each > 3500 bytes)
    diss_md = _build_synthetic_v2_dissertation_md()
    exec_md = _build_synthetic_v2_executive_summary_md()
    assert len(diss_md.encode("utf-8")) > 3500
    assert len(exec_md.encode("utf-8")) > 3500

    diss_path = rep_dir / "dissertation_report.md"
    exec_path = rep_dir / "executive_summary.md"
    prisma_path = rep_dir / "prisma_stats.md"
    audit_path = rep_dir / "verification_audit.md"

    diss_path.write_text(diss_md, encoding="utf-8")
    exec_path.write_text(exec_md, encoding="utf-8")
    prisma_path.write_text(
        "# PRISMA 2020 — Синтетический корпус v2.0\n\n"
        "- Включено статей: 36 (`PMID: 88000001..88000036`)\n"
        "- Кластер `complications_safety`: 36 записей, 5 строк `extracted_complications`\n",
        encoding="utf-8",
    )
    audit_path.write_text(
        f"# Сертификат автоматической верификации отчётов (`{nosology_id}`)\n\n"
        "- **Статус проверки:** `PASSED (Zero-Tolerance Gate)`\n"
        "- **Версия схемы:** `2.0`\n",
        encoding="utf-8",
    )

    kb_para = (
        "Аналитический справочный материал модульной базы знаний v2.0 по клиническим исходам, "
        "стратификации послеоперационных осложнений по шкале Clavien–Dindo, разграничению транзиторных "
        "явлений и красных флагов, а также практическим компромиссам между открытым и УЗ-контролируемым "
        "доступами [PMID: 88000001; PMID: 88000002; PMID: 88000003; PMCID: PMC8800001]. "
    )
    kb_md_paths: list[Path] = []
    for _mid, mtitle, mfile, _mcat in kb_module_specs:
        mod_path = kb_dir / mfile
        mod_text = f"# {mtitle}\n\n" + (kb_para * 13) + "\n"
        assert len(mod_text.encode("utf-8")) > 3500
        mod_path.write_text(mod_text, encoding="utf-8")
        kb_md_paths.append(mod_path)

    return {
        "nosology_id": nosology_id,
        "config": cfg_dict,
        "cfg_path": cfg_path,
        "db_path": db_path,
        "rep_dir": rep_dir,
        "kb_dir": kb_dir,
        "kb_json_path": kb_json_path,
        "kb_index": kb_index,
        "diss_path": diss_path,
        "exec_path": exec_path,
        "prisma_path": prisma_path,
        "audit_path": audit_path,
        "kb_md_paths": kb_md_paths,
        "freq_comps": freq_comps,
        "red_flags": red_flags,
    }


def _extract_docx_xml_root(docx_source: Path | bytes) -> tuple[ET.Element, bytes]:
    """Unzip a .docx file or bytes payload and return (ET root of word/document.xml, raw xml bytes)."""
    if isinstance(docx_source, Path):
        zf_ctx = zipfile.ZipFile(docx_source, "r")
    else:
        zf_ctx = zipfile.ZipFile(io.BytesIO(docx_source), "r")
    with zf_ctx as zf:
        raw_xml = zf.read("word/document.xml")
    return ET.fromstring(raw_xml), raw_xml


def _element_plain_text(el: ET.Element) -> str:
    """Concatenate all OpenXML <w:t> text nodes under an element."""
    return "".join(t.text or "" for t in el.findall(f".//{W}t"))


def _assert_openxml_table_invariants(root: ET.Element, *, min_tables: int = 0) -> list[ET.Element]:
    """Assert strict ECMA-376 <w:trPr> and <w:tcPr> invariants across every table in word/document.xml."""
    tables = root.findall(f".//{W}tbl")
    assert len(tables) >= min_tables, f"Expected >= {min_tables} tables, found {len(tables)}"
    for tbl in tables:
        trs = tbl.findall(f"{W}tr")
        assert len(trs) >= 1
        hdr_tr_pr = trs[0].find(f"{W}trPr")
        assert hdr_tr_pr is not None, "Header row missing <w:trPr>"
        hdr_tags = [child.tag.split("}")[-1] for child in hdr_tr_pr]
        assert hdr_tags == ["cantSplit", "tblHeader"], (
            f"Header <w:trPr> must be strictly ['cantSplit', 'tblHeader'], got {hdr_tags}"
        )
        for data_tr in trs[1:]:
            data_tr_pr = data_tr.find(f"{W}trPr")
            assert data_tr_pr is not None, "Data row missing <w:trPr>"
            data_tags = [child.tag.split("}")[-1] for child in data_tr_pr]
            assert data_tags == ["cantSplit"], (
                f"Data row <w:trPr> must be strictly ['cantSplit'], got {data_tags}"
            )
        for tr in trs:
            for tc in tr.findall(f"{W}tc"):
                tc_pr = tc.find(f"{W}tcPr")
                assert tc_pr is not None, "Cell missing <w:tcPr>"
                shds = tc_pr.findall(f"{W}shd")
                assert len(shds) == 1, f"Expected exactly 1 <w:shd> per <w:tcPr>, got {len(shds)}"
                tc_tags = [child.tag.split("}")[-1] for child in tc_pr]
                assert tc_tags == ["tcW", "shd", "vAlign"], (
                    f"<w:tcPr> child order must be ['tcW', 'shd', 'vAlign'], got {tc_tags}"
                )
    return tables


# ===========================================================================
# 1. End-to-End v2.0 pipeline & verify_reports (6-module, read-only)
# ===========================================================================


def test_v2_end_to_end_pipeline_and_verify_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify full v2.0 pipeline: harvester queries -> SQLite aggregation -> universal_schema(v2) -> verify_reports(v2, read-only)."""
    ws = _build_synthetic_v2_workspace(tmp_path)
    nos_id = ws["nosology_id"]
    cfg = ws["config"]

    # 1) harvester.build_complications_queries for surgical vs conservative profile
    q_surg = harvester.build_complications_queries(cfg)
    assert q_surg["profile"] == "surgical"
    assert q_surg["surgical_focus"] is True
    assert '"Postoperative Complications"[MeSH]' in q_surg["pubmed"]
    assert '"postoperative complications"' in q_surg["europepmc"]

    cfg_cons = copy.deepcopy(cfg)
    cfg_cons["nosology"]["surgical_focus"] = False
    cfg_cons["nosology"]["treatment_profile"] = "conservative"
    q_cons = harvester.build_complications_queries(cfg_cons)
    assert q_cons["profile"] == "conservative"
    assert q_cons["surgical_focus"] is False
    assert "Drug-Related Side Effects" in q_cons["pubmed"]
    assert '"Postoperative Complications"[MeSH]' not in q_cons["pubmed"]

    # 2) Verify SQLite aggregation output
    assert len(ws["freq_comps"]) == 3
    assert len(ws["red_flags"]) == 2
    assert any(fc["complication_name"] == SPECIAL_COMPLICATION_NAME for fc in ws["freq_comps"])
    assert all(0.0 <= rf["frequency_max_num"] < 1.0 for rf in ws["red_flags"])

    # 3) Verify isolated workspace discovery & universal_schema v2 validation
    monkeypatch.setenv("INFO_SEARCHER_ROOT", str(tmp_path))
    discovered = universal_schema.discover_nosologies()
    assert [d["id"] for d in discovered] == [nos_id]
    assert discovered[0]["surgical_focus"] is True
    assert universal_schema.verify_universal_schema(nos_id, schema_version="v2") == 0

    # 4) Verify verify_reports(v2, write_outputs=False) supports 6 KB modules & writes zero files (T-19-03)
    audit_mtime_before = ws["audit_path"].stat().st_mtime_ns
    res = verify_reports.verify_all_reports(
        nos_id,
        schema_version="v2",
        write_outputs=False,
        base_dir=tmp_path,
    )
    assert res["passed"] is True
    assert res["schema_version"] == "2.0"
    assert res["read_only"] is True
    assert res["kb_v2_errors"] == []
    assert res["bib_count"] == 36
    assert res["bold_lead_bullet_ratio"] <= 0.35
    # 2 top reports + 6 KB modules = 8 audited files including 06_complications_and_safety.md
    assert len(res["audit_rows"]) == 8
    assert any("06_complications_and_safety.md" in row["file"] for row in res["audit_rows"])

    # Read-only guarantee: no .docx generated and verification_audit.md untouched
    for docx_name in ("dissertation_report.docx", "executive_summary.docx", "full_clinical_dossier.docx"):
        assert not (ws["rep_dir"] / docx_name).exists()
    assert ws["audit_path"].stat().st_mtime_ns == audit_mtime_before

    # CSV UTF-8-SIG BOM & RFC 4180 column integrity check (T-19-04)
    df_comp = universal_schema.query_complications_df(ws["db_path"], include_casuistry=True)
    csv_bytes = universal_schema.dataframe_to_csv_bytes(df_comp)
    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    parsed_rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
    assert len(parsed_rows) == 5
    assert SPECIAL_COMPLICATION_NAME in {r["complication_name"] for r in parsed_rows}
    assert "2–8 недель" in {r["time_window"] for r in parsed_rows}


# ===========================================================================
# 2. OpenXML (.docx) DOM audit, v2.0 appendices, scoped shading & escaping
# ===========================================================================


def test_docx_exporter_v2_appendices_and_openxml_styling(tmp_path: Path) -> None:
    """Audit word/document.xml DOM, ECMA-376 ordering, scoped IIIb-V/Red Flags shading, escaping, and CLI/UI parity."""
    ws = _build_synthetic_v2_workspace(tmp_path)
    nos_id = ws["nosology_id"]

    paths = docx_exporter.export_nosology_docx_files(nos_id, base_dir=tmp_path)
    assert set(paths.keys()) == {"dissertation_docx", "executive_docx", "full_dossier_docx"}
    for p in paths.values():
        assert p.exists() and p.stat().st_size > 2048

    exec_root, exec_xml_bytes = _extract_docx_xml_root(paths["executive_docx"])
    full_root, full_xml_bytes = _extract_docx_xml_root(paths["full_dossier_docx"])
    diss_root, _ = _extract_docx_xml_root(paths["dissertation_docx"])

    # Strict ECMA-376 invariants across ALL tables in ALL 3 documents (D-07.1)
    exec_tables = _assert_openxml_table_invariants(exec_root, min_tables=6)
    full_tables = _assert_openxml_table_invariants(full_root, min_tables=6)
    _assert_openxml_table_invariants(diss_root, min_tables=0)

    # Pitfall 5 / T-19-02: Staging table ("Стадия IV") MUST NOT receive red/amber shading
    stage_tables = [t for t in exec_tables if "Стадия IV" in _element_plain_text(t)]
    assert len(stage_tables) >= 1, "Expected staging table containing 'Стадия IV' in executive_summary.docx"
    alert_fills = {"FEE2E2", "FECACA", "FFEDD5", "FED7AA"}
    for st_tbl in stage_tables:
        # Exclude Appendix B workhorse table which mentions 'стадий I–IV' rather than 'Стадия IV'
        st_fills = {shd.attrib.get(f"{W}fill") for shd in st_tbl.findall(f".//{W}shd")}
        assert st_fills.isdisjoint(alert_fills), (
            f"False-positive severity shading on staging table ('Стадия IV'): {st_fills & alert_fills}"
        )

    # Appendix A, Appendix B, Red Flags, special characters, and scoped IIIb / IV shading
    for doc_label, root, tables in (
        ("executive_summary.docx", exec_root, exec_tables),
        ("full_clinical_dossier.docx", full_root, full_tables),
    ):
        full_text = _element_plain_text(root)
        assert "Приложение А. Профиль частых осложнений лечения" in full_text, doc_label
        assert "Приложение Б. Клинические компромиссы и матрица выбора методики" in full_text, doc_label
        assert "Красные флаги: редкие критические осложнения" in full_text, doc_label
        assert "Сквозные методики" in full_text, doc_label
        assert "Перекрывающиеся показания" in full_text, doc_label
        assert "Узконишевые показания" in full_text, doc_label
        # T-19-02: Escaped special characters round-trip intact in XML text nodes
        assert SPECIAL_COMPLICATION_NAME in full_text, f"Special chars lost in {doc_label}"

        # Verify IIIb row shading (FFEDD5/FED7AA) and exact 10 columns despite '|' in complication name
        iiib_rows = [
            tr
            for tbl in tables
            for tr in tbl.findall(f"{W}tr")[1:]
            if SPECIAL_COMPLICATION_NAME in _element_plain_text(tr)
        ]
        assert len(iiib_rows) == 1, f"Expected 1 IIIb special-char row in {doc_label}, found {len(iiib_rows)}"
        assert len(iiib_rows[0].findall(f"{W}tc")) == 10, (
            f"Escaped pipe split table row unexpectedly in {doc_label}"
        )
        iiib_fills = {shd.attrib.get(f"{W}fill") for shd in iiib_rows[0].findall(f".//{W}shd")}
        assert "FFEDD5" in iiib_fills and "FED7AA" in iiib_fills, (
            f"Expected amber IIIb shading in {doc_label}, got {iiib_fills}"
        )

        # Verify IV / Red Flags rows receive red shading (FEE2E2/FECACA)
        rf_rows = [
            tr
            for tbl in tables
            for tr in tbl.findall(f"{W}tr")[1:]
            if "Стойкое повреждение лучевого пальцевого нерва" in _element_plain_text(tr)
        ]
        assert len(rf_rows) == 1, f"Expected Red Flag IV row in {doc_label}"
        rf_fills = {shd.attrib.get(f"{W}fill") for shd in rf_rows[0].findall(f".//{W}shd")}
        assert "FEE2E2" in rf_fills and "FECACA" in rf_fills, (
            f"Expected red IV/Red Flag shading in {doc_label}, got {rf_fills}"
        )

    # Explicit Grade V check via in-memory builder (D-07.2)
    kb_with_v = copy.deepcopy(ws["kb_index"])
    kb_with_v["rare_critical_red_flags"].append(
        {
            "modality": "Открытый релиз связки A1",
            "complication_name": "Фатальная анафилактическая реакция (модельный тест V)",
            "clavien_dindo_grade": "V",
            "reversibility": "permanent_deficit",
            "frequency_pct": "< 0.01%",
            "frequency_max_num": 0.01,
            "anatomical_substrate": "Системная реакция",
            "prevention_and_management": "Экстренный протокол СЛР",
            "evidence_pmids": ["88000001"],
        }
    )
    grade_v_root, _ = _extract_docx_xml_root(
        docx_exporter.build_executive_docx_bytes(ws["exec_path"].read_text(encoding="utf-8"), kb_with_v)
    )
    _assert_openxml_table_invariants(grade_v_root, min_tables=6)
    grade_v_rows = [
        tr
        for tbl in grade_v_root.findall(f".//{W}tbl")
        for tr in tbl.findall(f"{W}tr")[1:]
        if "Фатальная анафилактическая реакция" in _element_plain_text(tr)
    ]
    assert len(grade_v_rows) == 1
    grade_v_fills = {shd.attrib.get(f"{W}fill") for shd in grade_v_rows[0].findall(f".//{W}shd")}
    assert "FEE2E2" in grade_v_fills and "FECACA" in grade_v_fills

    # D-06: dissertation_report.docx MUST remain clean render without Appendix A/B duplication
    diss_text = _element_plain_text(diss_root)
    assert "Приложение А. Профиль частых осложнений" not in diss_text
    assert "Приложение Б. Клинические компромиссы" not in diss_text

    # Parity between in-memory builders (app.py buttons) and CLI export_nosology_docx_files()
    exec_md = ws["exec_path"].read_text(encoding="utf-8")
    diss_md = ws["diss_path"].read_text(encoding="utf-8")
    kb_mod_texts = [p.read_text(encoding="utf-8") for p in sorted(ws["kb_dir"].glob("*.md"))]

    inmem_exec_bytes = docx_exporter.build_executive_docx_bytes(exec_md, ws["kb_index"])
    inmem_full_bytes = docx_exporter.build_full_dossier_docx_bytes(
        exec_md, diss_md, kb_mod_texts, ws["kb_index"]
    )
    _, inmem_exec_xml = _extract_docx_xml_root(inmem_exec_bytes)
    _, inmem_full_xml = _extract_docx_xml_root(inmem_full_bytes)
    assert inmem_exec_xml == exec_xml_bytes
    assert inmem_full_xml == full_xml_bytes


# ===========================================================================
# 3. Security guards: path traversal & frozen v1.x overwrite protection
# ===========================================================================


def test_security_guards_path_traversal_and_frozen_v1_protection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify T-19-01 path traversal blocking (ValueError) and frozen v1.x repo-root PermissionError guards."""
    monkeypatch.delenv("INFO_SEARCHER_ROOT", raising=False)

    # 1) Path traversal and shell-injection slug rejection (ValueError)
    for bad_slug in ("../prom", "a/b", "prom;rm", "..\\trigger_finger", "prom/../../etc", ""):
        with pytest.raises(ValueError):
            docx_exporter.export_nosology_docx_files(bad_slug, base_dir=tmp_path)
        with pytest.raises(ValueError):
            universal_schema.save_new_nosology_config({"nosology": {"id": bad_slug}})

    # 2) Repo-root frozen v1.x overwrite protection (PermissionError)
    for frozen_id in ("prom", "metroplasty_pregnancy", "trigger_finger"):
        with pytest.raises(PermissionError):
            docx_exporter.export_nosology_docx_files(frozen_id)
        with pytest.raises(PermissionError):
            universal_schema.save_new_nosology_config({"nosology": {"id": frozen_id}})

    # 3) Exporting/saving a frozen slug inside an isolated tmp_path works freely without touching repo root
    ws_tmp_prom = _build_synthetic_v2_workspace(tmp_path, nosology_id="prom")
    exported = docx_exporter.export_nosology_docx_files("prom", base_dir=tmp_path)
    for docx_path in exported.values():
        assert docx_path.exists() and docx_path.is_relative_to(tmp_path)

    monkeypatch.setenv("INFO_SEARCHER_ROOT", str(tmp_path))
    saved_tmp_cfg = universal_schema.save_new_nosology_config(
        {
            "nosology": {
                "id": "prom",
                "name_ru": "Временная копия в tmp_path",
                "name_en": "Temp PROM",
            }
        }
    )
    assert saved_tmp_cfg.exists() and saved_tmp_cfg.is_relative_to(tmp_path)
    assert ws_tmp_prom["cfg_path"] == saved_tmp_cfg


# ===========================================================================
# 4. Isolated headless Streamlit AppTest across Tabs 1-4 (D-01..D-05, T-19-03/05)
# ===========================================================================


def _collect_block_text(block: Any) -> str:
    """Gather visible markdown, caption, info, warning, error, and code text from an AppTest block."""
    chunks: list[str] = []
    for attr in ("markdown", "caption", "info", "warning", "error", "success", "code"):
        items = getattr(block, attr, [])
        for item in items:
            val = getattr(item, "value", None)
            if val:
                chunks.append(str(val))
    return "\n".join(chunks)


def test_v2_isolated_apptest_tabs_and_configurator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise all 4 tabs, subtabs 2.5/2.6, Tab 3 casuistry toggle, Tab 4 live preview/save, and read-only audit."""
    ws = _build_synthetic_v2_workspace(tmp_path)
    nos_id = ws["nosology_id"]

    monkeypatch.setenv("INFO_SEARCHER_ROOT", str(tmp_path))
    monkeypatch.setenv("INFO_SEARCHER_APPTEST_ACTIVE", "1")
    st.cache_data.clear()

    try:
        at = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=60).run(timeout=60)
        assert len(at.exception) == 0, f"Initial v2.0 AppTest raised: {at.exception}"

        # 1) Sidebar KPI "Строк осложнений" (D-01)
        metric_map = {m.label: m.value for m in at.metric}
        assert "Строк осложнений" in metric_map
        assert metric_map["Строк осложнений"] == "5"

        # 2) Tab 1 dynamic Mode C (6 modules) + switching Mode B & Mode C (D-01)
        mode_opts = list(at.radio(key="tab1_report_mode").options)
        mode_b = next(o for o in mode_opts if o.startswith("Режим Б"))
        mode_c = next(o for o in mode_opts if o.startswith("Режим В"))
        assert "6" in mode_c, f"Expected 6 modules in Mode C label, got {mode_c!r}"

        at.radio(key="tab1_report_mode").set_value(mode_b).run(timeout=60)
        assert len(at.exception) == 0
        at.radio(key="tab1_report_mode").set_value(mode_c).run(timeout=60)
        assert len(at.exception) == 0

        # 3) Tab 2 subtabs 2.5 & 2.6 (D-01, D-02, D-03)
        t25 = next((t for t in at.tabs if "2.5" in t.label), None)
        t26 = next((t for t in at.tabs if "2.6" in t.label), None)
        assert t25 is not None and t26 is not None

        plotly_charts_25 = t25.get("plotly_chart")
        assert len(plotly_charts_25) >= 2, f"Expected >= 2 Plotly charts in subtab 2.5, got {len(plotly_charts_25)}"
        assert len(t25.dataframe) >= 1
        t25_text = _collect_block_text(t25)
        assert "Красные флаги" in t25_text
        assert "Стойкое повреждение лучевого пальцевого нерва" in t25_text

        # Toggle color mode to "Обратимость" (D-02)
        at.radio(key="t25_color_mode").set_value("Обратимость").run(timeout=60)
        assert len(at.exception) == 0

        # Check all 3 clinical_decision_nuances blocks in subtab 2.6 (D-03)
        t26 = next(t for t in at.tabs if "2.6" in t.label)
        t26_text = _collect_block_text(t26)
        assert "Сквозные методики" in t26_text
        assert "Перекрывающиеся показания" in t26_text
        assert "Узконишевые показания" in t26_text
        assert "Открытый релиз связки A1" in t26_text
        assert "Эндоскопическая декомпрессия и открытый ревизионный тенолиз" in t26_text

        # 4) Tab 3 option 5 (extracted_complications) + Tier 4 casuistry toggle (D-04)
        t3_opts = list(at.radio(key="tab3_table_choice").options)
        opt5 = next(o for o in t3_opts if o.startswith("5."))
        at.radio(key="tab3_table_choice").set_value(opt5).run(timeout=60)
        assert len(at.exception) == 0

        t3 = next(t for t in at.tabs if t.label.startswith("📚 3."))
        assert len(t3.dataframe) >= 1
        df_no_cas = t3.dataframe[0].value
        assert len(df_no_cas) == 4, f"Expected 4 non-casuistry rows, got {len(df_no_cas)}"
        assert "Эндоскопическая декомпрессия" not in set(df_no_cas["modality"].tolist())

        at.checkbox(key="t3_comp_casuistry").set_value(True).run(timeout=60)
        assert len(at.exception) == 0
        t3 = next(t for t in at.tabs if t.label.startswith("📚 3."))
        df_with_cas = t3.dataframe[0].value
        assert len(df_with_cas) == 5 > len(df_no_cas)
        assert "Эндоскопическая декомпрессия" in set(df_with_cas["modality"].tolist())

        # 5) Tab 4 reactive surgical_focus live preview & YAML save (D-05.1..D-05.3)
        t4 = next(t for t in at.tabs if t.label.startswith("🛡️ 4."))
        t4_codes_before = "\n".join(c.value for c in t4.code)
        assert "Postoperative Complications" in t4_codes_before

        cons_opt = next(
            o for o in at.radio(key="t4_profile_radio").options if "surgical_focus: false" in o
        )
        at.radio(key="t4_profile_radio").set_value(cons_opt).run(timeout=60)
        assert len(at.exception) == 0

        t4 = next(t for t in at.tabs if t.label.startswith("🛡️ 4."))
        t4_codes_after = "\n".join(c.value for c in t4.code)
        assert "Drug-Related Side Effects" in t4_codes_after
        assert "Postoperative Complications" not in t4_codes_after

        # Pitfall 3: set form widget value WITHOUT intermediate .run(), then submit form
        at.text_input(key="t4_new_id").set_value("demo_conservative_v2")
        at.form_submit_button[0].click().run(timeout=60)
        assert len(at.exception) == 0

        saved_yaml_path = tmp_path / "configs" / "demo_conservative_v2.yaml"
        assert saved_yaml_path.exists(), f"Expected saved YAML at {saved_yaml_path}"
        assert not (PROJECT_ROOT / "configs" / "demo_conservative_v2.yaml").exists()

        saved_cfg = yaml.safe_load(saved_yaml_path.read_text(encoding="utf-8"))
        assert saved_cfg["nosology"]["id"] == "demo_conservative_v2"
        assert saved_cfg["nosology"]["surgical_focus"] is False
        assert saved_cfg["nosology"]["treatment_profile"] == "conservative"
        assert "openalex_search" in saved_cfg["queries"]
        assert "clinical_trials_condition" in saved_cfg["queries"]
        assert "openalex" not in saved_cfg["queries"]
        assert "clinicaltrials" not in saved_cfg["queries"]

        # 6) T-19-03: Click btn_run_verify -> verifies --verify --read-only, shell=False, and 0 file mutations
        audit_mtime_before = ws["audit_path"].stat().st_mtime_ns
        audit_bytes_before = ws["audit_path"].read_bytes()
        recorded_calls: list[tuple[Any, dict[str, Any], int]] = []
        real_subprocess_run = subprocess.run

        def _spy_subprocess_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
            completed = real_subprocess_run(*args, **kwargs)
            recorded_calls.append((args[0] if args else kwargs.get("args"), dict(kwargs), completed.returncode))
            return completed

        monkeypatch.setattr(subprocess, "run", _spy_subprocess_run)
        at.button(key="btn_run_verify").click().run(timeout=60)
        assert len(at.exception) == 0

        verify_calls = [
            (cmd, kw, rc)
            for cmd, kw, rc in recorded_calls
            if isinstance(cmd, list) and any("verify_reports.py" in str(part) for part in cmd)
        ]
        assert len(verify_calls) == 1, f"Expected 1 verify_reports.py call, recorded {recorded_calls}"
        cmd_args, cmd_kwargs, cmd_rc = verify_calls[0]
        assert "--verify" in cmd_args
        assert "--read-only" in cmd_args
        assert "--nosology" in cmd_args and nos_id in cmd_args
        assert cmd_kwargs.get("shell", False) is False
        assert cmd_rc == 0, f"verify_reports.py --verify --read-only exited with {cmd_rc}"

        # Confirm zero file writes on disk from clicking btn_run_verify
        assert ws["audit_path"].stat().st_mtime_ns == audit_mtime_before
        assert ws["audit_path"].read_bytes() == audit_bytes_before
        for docx_name in ("dissertation_report.docx", "executive_summary.docx", "full_clinical_dossier.docx"):
            assert not (ws["rep_dir"] / docx_name).exists()
    finally:
        st.cache_data.clear()


# ===========================================================================
# 5. Frozen v1.x zero-mutation & backward-compatibility regression suite
# ===========================================================================


FROZEN_V1_IDS: tuple[str, ...] = ("prom", "metroplasty_pregnancy", "trigger_finger")


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file using streaming reads."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_frozen_v1_tree() -> tuple[dict[Path, tuple[str, int, int]], dict[str, set[Path]]]:
    """Capture recursive (sha256_hex, st_mtime_ns, st_size) snapshot of all 3 frozen v1.x corpora & configs.

    Tracks every file across data/{id}, reports/{id}, and configs/{id}.yaml (including literature.db and
    any pre-existing 0-byte .db-wal files), and separately tracks gitignored SQLite .db-wal/.db-shm sidecar
    sets so zero new sidecars and zero WAL writes (size == 0) are strictly enforced even on WAL-mode DBs.
    """
    snapshot: dict[Path, tuple[str, int, int]] = {}
    sidecars: dict[str, set[Path]] = {"wal": set(), "shm": set()}
    for nos_id in FROZEN_V1_IDS:
        data_dir = PROJECT_ROOT / "data" / nos_id
        rep_dir = PROJECT_ROOT / "reports" / nos_id
        cfg_file = PROJECT_ROOT / "configs" / f"{nos_id}.yaml"

        assert data_dir.exists(), f"Missing frozen data directory: {data_dir}"
        assert rep_dir.exists(), f"Missing frozen reports directory: {rep_dir}"
        assert cfg_file.exists(), f"Missing frozen config file: {cfg_file}"

        for wal_file in data_dir.rglob("*.db-wal"):
            assert wal_file.stat().st_size == 0, (
                f"Non-empty WAL sidecar indicates uncommitted DB write: {wal_file}"
            )
            sidecars["wal"].add(wal_file.resolve())
        for shm_file in data_dir.rglob("*.db-shm"):
            sidecars["shm"].add(shm_file.resolve())

        st_cfg = cfg_file.stat()
        snapshot[cfg_file.resolve()] = (_sha256_file(cfg_file), st_cfg.st_mtime_ns, st_cfg.st_size)

        for root_dir in (data_dir, rep_dir):
            for file_path in sorted(p for p in root_dir.rglob("*") if p.is_file()):
                # SQLite ?mode=ro updates mmap timestamp on pre-existing gitignored .db-shm lock files;
                # sidecar creation is strictly gated via sidecars["shm"], while .db and 0-byte .db-wal are hashed.
                if file_path.name.endswith(".db-shm"):
                    continue
                st_info = file_path.stat()
                snapshot[file_path.resolve()] = (
                    _sha256_file(file_path),
                    st_info.st_mtime_ns,
                    st_info.st_size,
                )
    return snapshot, sidecars


def test_v1_frozen_regression_and_zero_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify 100% v1.x backward compatibility and byte-level zero mutation on prom, metroplasty_pregnancy, trigger_finger."""
    monkeypatch.delenv("INFO_SEARCHER_ROOT", raising=False)
    monkeypatch.setenv("INFO_SEARCHER_APPTEST_ACTIVE", "1")
    st.cache_data.clear()

    before_files, before_sidecars = _snapshot_frozen_v1_tree()
    assert len(before_files) >= 9

    try:
        # 1) Data layer, schema verification, read-only report audit, in-memory DOCX, and write guards
        for nos_id in FROZEN_V1_IDS:
            bundle = universal_schema.load_nosology_bundle(nos_id)
            kb = bundle["kb_index"]

            # Even with in-memory default empty clinical_decision_nuances, v1.x MUST NOT be treated as v2.0
            assert docx_exporter.is_v2_kb_index(kb) is False, f"Frozen v1.x '{nos_id}' misclassified as v2.0"

            df_comp = universal_schema.query_complications_df(bundle["db_path"])
            assert df_comp.empty, f"Expected empty complications DataFrame for frozen v1.x '{nos_id}'"

            assert universal_schema.verify_universal_schema(nos_id, schema_version="auto") == 0

            res = verify_reports.verify_all_reports(nos_id, schema_version="auto", write_outputs=False)
            assert res["passed"] is True
            assert res["schema_version"] == "1.x"
            assert res["read_only"] is True

            # In-memory DOCX builders: valid OpenXML + <w:cantSplit/>/<w:tblHeader/>, strictly NO v2.0 appendices (D-06)
            exec_bytes = docx_exporter.build_executive_docx_bytes(bundle["executive_summary_md"], kb)
            kb_module_texts = [m["content"] for m in bundle["kb_modules"] if m.get("content")]
            full_bytes = docx_exporter.build_full_dossier_docx_bytes(
                bundle["executive_summary_md"],
                bundle["dissertation_md"],
                kb_module_texts,
                kb,
            )
            for doc_kind, payload_bytes in (("executive", exec_bytes), ("full_dossier", full_bytes)):
                assert payload_bytes.startswith(b"PK") and len(payload_bytes) > 2048
                root, _ = _extract_docx_xml_root(payload_bytes)
                _assert_openxml_table_invariants(root, min_tables=1)
                doc_text = _element_plain_text(root)
                assert "Приложение А. Профиль частых осложнений" not in doc_text, (
                    f"Unexpected v2.0 Appendix A in frozen v1.x {nos_id} ({doc_kind})"
                )
                assert "Приложение Б. Клинические компромиссы" not in doc_text, (
                    f"Unexpected v2.0 Appendix B in frozen v1.x {nos_id} ({doc_kind})"
                )

            # Repo-root overwrite protection (D-07.3, T-19-01)
            with pytest.raises(PermissionError):
                docx_exporter.export_nosology_docx_files(nos_id)
            with pytest.raises(PermissionError):
                universal_schema.save_new_nosology_config({"nosology": {"id": nos_id}})

        # 2) Full headless Streamlit AppTest across all 3 frozen v1.x nosologies on repo root
        at = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=60).run(timeout=60)
        assert len(at.exception) == 0, f"Initial repo-root AppTest raised: {at.exception}"

        for nos_id in FROZEN_V1_IDS:
            at.selectbox(key="sidebar_nosology_select").set_value(nos_id).run(timeout=60)
            assert len(at.exception) == 0, f"AppTest failed selecting frozen v1.x '{nos_id}': {at.exception}"

            # Sidebar must NOT display v2.0 "Строк осложнений" metric on v1.x
            metric_labels = {m.label for m in at.metric}
            assert "Строк осложнений" not in metric_labels, (
                f"Unexpected v2.0 'Строк осложнений' metric for frozen v1.x '{nos_id}'"
            )

            # Tab 1 Mode C must display 5 modules for frozen v1.x
            mode_opts = list(at.radio(key="tab1_report_mode").options)
            mode_c = next(o for o in mode_opts if o.startswith("Режим В"))
            assert "5" in mode_c, f"Expected 5 KB modules for frozen v1.x '{nos_id}', got {mode_c!r}"

            # Subtabs 2.5 and 2.6 must exist and render soft v1.x fallback info banners
            t25 = next((t for t in at.tabs if "2.5" in t.label), None)
            t26 = next((t for t in at.tabs if "2.6" in t.label), None)
            assert t25 is not None and t26 is not None, f"Missing 2.5/2.6 subtabs for '{nos_id}'"
            assert len(t25.info) >= 1, f"Missing v1.x fallback info banner in subtab 2.5 for '{nos_id}'"
            assert len(t26.info) >= 1, f"Missing v1.x fallback info banner in subtab 2.6 for '{nos_id}'"

            # Tab 3 option 5 (extracted_complications) renders calm read-only 0-row info message
            t3_opts = list(at.radio(key="tab3_table_choice").options)
            opt1 = next(o for o in t3_opts if o.startswith("1."))
            opt5 = next(o for o in t3_opts if o.startswith("5."))
            at.radio(key="tab3_table_choice").set_value(opt5).run(timeout=60)
            assert len(at.exception) == 0, f"Tab 3 option 5 failed for frozen v1.x '{nos_id}': {at.exception}"

            t3 = next(t for t in at.tabs if t.label.startswith("📚 3."))
            assert len(t3.info) >= 1, f"Missing read-only 0-row st.info in Tab 3 option 5 for '{nos_id}'"
            assert "extracted_complications" in _collect_block_text(t3)

            # Reset Tab 3 back to option 1 before switching to next nosology
            at.radio(key="tab3_table_choice").set_value(opt1).run(timeout=60)
            assert len(at.exception) == 0
    finally:
        st.cache_data.clear()

    # 3) Byte-level immutability gate: identical files, SHA-256, st_mtime_ns, st_size, and zero new -wal/-shm
    after_files, after_sidecars = _snapshot_frozen_v1_tree()
    assert after_files == before_files, (
        "Frozen v1.x files mutated (SHA-256 / st_mtime_ns / st_size mismatch)!"
    )
    assert after_sidecars == before_sidecars, (
        f"SQLite WAL/SHM sidecar set changed: before={before_sidecars}, after={after_sidecars}"
    )

    # 4) Git working-tree immutability gate across all 6 frozen v1.x directories + 3 frozen configs (IN-05)
    git_res = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "data/prom",
            "data/metroplasty_pregnancy",
            "data/trigger_finger",
            "reports/prom",
            "reports/metroplasty_pregnancy",
            "reports/trigger_finger",
            "configs/prom.yaml",
            "configs/metroplasty_pregnancy.yaml",
            "configs/trigger_finger.yaml",
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert git_res.stdout.strip() == "", f"Frozen v1.x git tree dirty:\n{git_res.stdout}"


# ===========================================================================
# 6. Phase 19 Code Review Regression Tests (CR-01..04, WR-01..07, IN-01..06)
# ===========================================================================


def _extract_docx_xml_and_rels(docx_source: Path | bytes) -> tuple[ET.Element, ET.Element]:
    """Return parsed (word/document.xml root, word/_rels/document.xml.rels root)."""
    if isinstance(docx_source, Path):
        zf_ctx = zipfile.ZipFile(docx_source, "r")
    else:
        zf_ctx = zipfile.ZipFile(io.BytesIO(docx_source), "r")
    with zf_ctx as zf:
        doc_root = ET.fromstring(zf.read("word/document.xml"))
        rels_root = ET.fromstring(zf.read("word/_rels/document.xml.rels"))
    return doc_root, rels_root


def _create_dir_link_or_junction(link_path: Path, target_path: Path) -> None:
    """Create a directory symlink or Windows NTFS junction (works without admin rights)."""
    try:
        os.symlink(target_path, link_path, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            raise
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link_path), str(target_path)],
            check=True,
            capture_output=True,
            text=True,
        )


def _remove_dir_link_safely(link_path: Path) -> None:
    """Remove a directory symlink/junction without touching the target directory."""
    if not link_path.exists() and not link_path.is_symlink():
        return
    try:
        os.rmdir(link_path)
    except OSError:
        link_path.unlink(missing_ok=True)


def test_docx_review_regressions_security_severity_and_escaping(tmp_path: Path) -> None:
    """Lock CR-03 (link injection), WR-01 (NaN/non-list), WR-02 (severity classifier), WR-03 (backslash-pipe), WR-07."""
    ws = _build_synthetic_v2_workspace(tmp_path)
    exec_md = ws["exec_path"].read_text(encoding="utf-8")

    # --- WR-07 & WR-02: Grade IV directly in frequent_complications + precision/recall ---
    kb_sev = copy.deepcopy(ws["kb_index"])
    kb_sev["frequent_complications"].extend(
        [
            {
                "modality": "Открытый релиз связки A1",
                "complication_name": "Тяжёлый ишемический некроз (частая IV)",
                "event_class": "true_complication",
                "clavien_dindo_grade": "IV",
                "reversibility": "requires_reoperation",
                "frequency_pct": "1.2%",
                "frequency_median_num": 1.2,
                "sample_size_total": 180,
                "time_window": "7 суток",
                "anatomical_substrate": "Сосудистая арка пальца",
                "prevention_and_management": "Экстренная реваскуляризация",
                "evidence_pmids": ["88000001"],
            },
            {
                "modality": "УЗ-контролируемый чрескожный релиз",
                "complication_name": "Целлюлит с в/в антибиотиками",
                "event_class": "true_complication",
                "clavien_dindo_grade": "II (IV antibiotics)",
                "reversibility": "requires_conservative_therapy",
                "frequency_pct": "2.1%",
                "frequency_median_num": 2.1,
                "sample_size_total": 200,
                "time_window": "10 суток",
                "anatomical_substrate": "Подкожная клетчатка",
                "prevention_and_management": "Внутривенный цефазолин",
                "evidence_pmids": ["88000002"],
            },
            {
                "modality": "Открытый релиз связки A1",
                "complication_name": "Ревизия с пунктуацией IIIb",
                "event_class": "true_complication",
                "clavien_dindo_grade": "IIIb.",
                "reversibility": "requires_reoperation",
                "frequency_pct": "1.5%",
                "frequency_median_num": 1.5,
                "sample_size_total": 160,
                "time_window": "30 суток",
                "anatomical_substrate": "Сухожильное влагалище",
                "prevention_and_management": "Тенолиз",
                "evidence_pmids": ["88000003"],
            },
            {
                "modality": "Открытый релиз связки A1",
                "complication_name": "Осложнение верхний регистр IIIB",
                "event_class": "true_complication",
                "clavien_dindo_grade": "IIIB",
                "reversibility": "requires_reoperation",
                "frequency_pct": "1.4%",
                "frequency_median_num": 1.4,
                "sample_size_total": 160,
                "time_window": "30 суток",
                "anatomical_substrate": "Капсула сустава",
                "prevention_and_management": "Ревизия",
                "evidence_pmids": ["88000003"],
            },
            {
                "modality": "Открытый релиз связки A1",
                "complication_name": "Осложнение с диапазоном IIIa–IV",
                "event_class": "true_complication",
                "clavien_dindo_grade": "Clavien–Dindo IIIa–IV",
                "reversibility": "requires_reoperation",
                "frequency_pct": "1.1%",
                "frequency_median_num": 1.1,
                "sample_size_total": 140,
                "time_window": "14 суток",
                "anatomical_substrate": "Сосудисто-нервный пучок",
                "prevention_and_management": "ОРИТ и ревизия",
                "evidence_pmids": ["88000004"],
            },
            {
                "modality": "Открытый релиз связки A1",
                "complication_name": "Критическая органная дисфункция с двоеточием",
                "event_class": "true_complication",
                "clavien_dindo_grade": "IV: ICU",
                "reversibility": "permanent_deficit",
                "frequency_pct": "1.0%",
                "frequency_median_num": 1.0,
                "sample_size_total": 140,
                "time_window": "48 ч",
                "anatomical_substrate": "Системная микроциркуляция",
                "prevention_and_management": "Интенсивная терапия",
                "evidence_pmids": ["88000004"],
            },
        ]
    )
    sev_root, _ = _extract_docx_xml_root(docx_exporter.build_executive_docx_bytes(exec_md, kb_sev))
    _assert_openxml_table_invariants(sev_root, min_tables=6)

    def _row_fills_by_needle(root_el: ET.Element, needle: str) -> set[str]:
        matched = [
            tr
            for tbl in root_el.findall(f".//{W}tbl")
            for tr in tbl.findall(f"{W}tr")[1:]
            if needle in _element_plain_text(tr)
        ]
        assert len(matched) == 1, f"Expected 1 row matching {needle!r}, got {len(matched)}"
        return {shd.attrib.get(f"{W}fill", "") for shd in matched[0].findall(f".//{W}shd")}

    alert_fills = {"FEE2E2", "FECACA", "FFEDD5", "FED7AA"}
    # Grade IV inside frequent_complications (NOT red flags table) MUST get red shading
    assert {"FEE2E2", "FECACA"}.issubset(_row_fills_by_needle(sev_root, "Тяжёлый ишемический некроз (частая IV)"))
    assert {"FEE2E2", "FECACA"}.issubset(_row_fills_by_needle(sev_root, "Осложнение с диапазоном IIIa–IV"))
    assert {"FEE2E2", "FECACA"}.issubset(_row_fills_by_needle(sev_root, "Критическая органная дисфункция с двоеточием"))
    # IIIb. and IIIB MUST get amber shading
    assert {"FFEDD5", "FED7AA"}.issubset(_row_fills_by_needle(sev_root, "Ревизия с пунктуацией IIIb"))
    assert {"FFEDD5", "FED7AA"}.issubset(_row_fills_by_needle(sev_root, "Осложнение верхний регистр IIIB"))
    # II (IV antibiotics) MUST NOT trigger red or amber shading!
    assert _row_fills_by_needle(sev_root, "Целлюлит с в/в антибиотиками").isdisjoint(alert_fills)

    # Broad chapter heading '## 4. Частые и критические осложнения лечения' MUST NOT paint Grade I/II rows red
    # Inline Russian 'Клавьен–Диндо IV', 'Clavien–Dindo класс IV', 'Clavien–Dindo IIIa–IV' MUST paint red
    md_inline = (
        "## 4. Частые и критические осложнения лечения\n\n"
        "| Событие | Описание |\n"
        "| :--- | :--- |\n"
        "| Лёгкий отёк | Осложнение Clavien–Dindo II (IV antibiotics) без ревизии |\n"
        "| Сепсис | Осложнение Клавьен–Диндо IV с переводом в ОРИТ |\n"
        "| Тромбоз | Осложнение Clavien–Dindo класс IV с экстренной ревизией |\n"
        "| Диапазон | Осложнение Clavien–Dindo IIIa–IV при повторной операции |\n"
        "| Свищ | Осложнение Clavien–Dindo IIIb. потребовавшее ревизии |\n"
    )
    inline_root, _ = _extract_docx_xml_root(docx_exporter.build_docx_bytes_from_markdown(md_inline))
    assert _row_fills_by_needle(inline_root, "Лёгкий отёк").isdisjoint(alert_fills)
    assert "FEE2E2" in _row_fills_by_needle(inline_root, "Сепсис")
    assert "FEE2E2" in _row_fills_by_needle(inline_root, "Тромбоз")
    assert "FEE2E2" in _row_fills_by_needle(inline_root, "Диапазон")
    assert "FFEDD5" in _row_fills_by_needle(inline_root, "Свищ")

    # --- CR-03: Markdown hyperlink injection neutralization (including nested bypass attempt) ---
    evil_link = "Pain [Click](https://evil.example/phish)"
    nested_evil_link = "Nested [[Click](https://evil.example/phish)](https://evil.example/phish)"
    kb_inj = copy.deepcopy(ws["kb_index"])
    kb_inj["frequent_complications"][0]["complication_name"] = evil_link
    kb_inj["frequent_complications"][0]["prevention_and_management"] = nested_evil_link
    kb_inj["clinical_decision_nuances"]["universal_workhorse_modalities"][0]["practical_nuances"] = evil_link

    inj_bytes = docx_exporter.build_executive_docx_bytes(exec_md, kb_inj)
    inj_doc, inj_rels = _extract_docx_xml_and_rels(inj_bytes)
    rel_targets = [el.attrib.get("Target", "") for el in inj_rels]
    assert not any("evil.example" in t for t in rel_targets), f"Injected external rel found: {rel_targets}"
    assert "https://pubmed.ncbi.nlm.nih.gov/88000001/" in rel_targets

    r_ns = docx_exporter.R_NS
    rel_by_id = {el.attrib.get("Id", ""): el.attrib.get("Target", "") for el in inj_rels}
    hyperlinks = inj_doc.findall(f".//{W}hyperlink")
    assert len(hyperlinks) >= 1
    for hl in hyperlinks:
        rid = hl.attrib.get(f"{{{r_ns}}}id", "")
        target = rel_by_id.get(rid, "")
        assert target.startswith("https://pubmed.ncbi.nlm.nih.gov/"), f"Unexpected hyperlink target: {target!r}"
        assert "Click" not in _element_plain_text(hl)

    plain_inj = _element_plain_text(inj_doc)
    assert evil_link in plain_inj, "Visible text lost or mangled with stray backslashes"
    assert nested_evil_link in plain_inj

    # --- WR-01: NaN / inf & non-list truthy kb_index resilience ---
    assert docx_exporter.is_v2_kb_index({"frequent_complications": "corrupt"}) is False
    assert docx_exporter.is_v2_kb_index({"frequent_complications": 123}) is False
    assert docx_exporter.is_v2_kb_index({"rare_critical_red_flags": {"bad": True}}) is False
    assert (
        docx_exporter.is_v2_kb_index(
            {"clinical_decision_nuances": {"universal_workhorse_modalities": "not-a-list"}}
        )
        is False
    )
    kb_nan = {
        "schema_version": "2.0",
        "frequent_complications": [
            {
                "modality": "Method A",
                "complication_name": "NaN numeric test",
                "event_class": "true_complication",
                "clavien_dindo_grade": "II",
                "reversibility": "requires_conservative_therapy",
                "frequency_pct": "",
                "frequency_median_num": float("nan"),
                "sample_size_total": float("nan"),
                "time_window": "7 days",
                "anatomical_substrate": None,
                "prevention_and_management": float("inf"),
                "evidence_pmids": ["88000001"],
            },
            {
                "modality": "Method B",
                "complication_name": "Inf numeric test",
                "event_class": "true_complication",
                "clavien_dindo_grade": "I",
                "reversibility": "transient_self_limiting",
                "frequency_pct": "3%",
                "frequency_median_num": float("inf"),
                "sample_size_total": float("-inf"),
                "time_window": "",
                "anatomical_substrate": "Skin",
                "prevention_and_management": "Rest",
                "evidence_pmids": ["88000001"],
            },
        ],
        "rare_critical_red_flags": 123,
        "clinical_decision_nuances": {
            "universal_workhorse_modalities": "corrupt",
            "overlapping_indications_and_gray_zones": [
                {
                    "clinical_scenario": "Overlap",
                    "competing_modalities": [None, "Method A", float("nan")],
                    "why_no_single_winner": "Equal",
                    "decisive_practical_factors": "Equipment",
                    "evidence_pmids": ["88000001"],
                }
            ],
            "strict_niche_or_salvage_indications": 999,
        },
    }
    nan_bytes = docx_exporter.build_executive_docx_bytes("# Exec\n\nBody text.", kb_nan)
    nan_root, _ = _extract_docx_xml_root(nan_bytes)
    nan_text = _element_plain_text(nan_root).lower()
    assert "nan%" not in nan_text
    assert "inf%" not in nan_text
    assert "none" not in nan_text

    # --- WR-03: _split_table_row() backslash-adjacent-to-pipe parsing ---
    assert docx_exporter._split_table_row(r"|foo\\|bar|") == ["foo\\", "bar"]
    assert docx_exporter._split_table_row(r"|A|B\\|") == ["A", "B\\"]
    assert docx_exporter._split_table_row(r"|A|B\|C|") == ["A", "B|C"]
    esc_a = docx_exporter._escape_md_cell("A\\")
    esc_b = docx_exporter._escape_md_cell("B\\|C")
    assert docx_exporter._split_table_row(f"|{esc_a}|{esc_b}|") == ["A\\", "B\\|C"]
    bs_md = f"| Col1 | Col2 |\n| :--- | :--- |\n| {esc_a} | {esc_b} |\n"
    bs_root, _ = _extract_docx_xml_root(docx_exporter.build_docx_bytes_from_markdown(bs_md))
    bs_data_row = bs_root.findall(f".//{W}tbl")[0].findall(f"{W}tr")[1]
    bs_cells = [_element_plain_text(tc) for tc in bs_data_row.findall(f"{W}tc")]
    assert bs_cells == ["A\\", "B\\|C"]


def test_security_and_data_layer_review_regressions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lock CR-02 (symlink/junction frozen guard), CR-04 (KB set equality), WR-04 (monkeypatch priority), IN-01/02/04/06."""
    # --- CR-02: Symlink/junction bypass & case-variant frozen v1.x protection ---
    link_base = tmp_path / "symlink_attack_docx"
    link_base.mkdir()
    reports_link = link_base / "reports"
    _create_dir_link_or_junction(reports_link, PROJECT_ROOT / "reports")
    try:
        with pytest.raises(PermissionError):
            docx_exporter.export_nosology_docx_files("prom", base_dir=link_base)
        with pytest.raises(PermissionError):
            docx_exporter.export_nosology_docx_files("PROM", base_dir=link_base)
        with pytest.raises(ValueError):
            docx_exporter.export_nosology_docx_files("non_frozen_escape", base_dir=link_base)
    finally:
        _remove_dir_link_safely(reports_link)

    cfg_link_base = tmp_path / "symlink_attack_cfg"
    cfg_link_base.mkdir()
    configs_link = cfg_link_base / "configs"
    _create_dir_link_or_junction(configs_link, PROJECT_ROOT / "configs")
    try:
        monkeypatch.setenv("INFO_SEARCHER_ROOT", str(cfg_link_base))
        with pytest.raises(PermissionError):
            universal_schema.save_new_nosology_config({"nosology": {"id": "prom"}})
        with pytest.raises(ValueError):
            universal_schema.save_new_nosology_config({"nosology": {"id": "non_frozen_escape"}})
    finally:
        monkeypatch.delenv("INFO_SEARCHER_ROOT", raising=False)
        _remove_dir_link_safely(configs_link)

    # --- CR-04: verify_all_reports() rejects orphaned/missing, duplicate, and path-traversal KB modules ---
    # (a) Orphaned .md paired with missing declared .md (equal count 6 == 6!)
    ws_orphan = _build_synthetic_v2_workspace(tmp_path / "cr04_orphan", nosology_id="cr04_orphan")
    (ws_orphan["kb_dir"] / "06_complications_and_safety.md").unlink()
    (ws_orphan["kb_dir"] / "99_orphan_unindexed.md").write_text(
        "# Orphan\n\n" + ("Контекст [PMID: 88000001]. " * 200),
        encoding="utf-8",
    )
    with pytest.raises(AssertionError):
        verify_reports.verify_all_reports(
            "cr04_orphan", schema_version="v2", write_outputs=False, base_dir=tmp_path / "cr04_orphan"
        )

    # (b) Duplicate module entry in kb_index.json
    ws_dup = _build_synthetic_v2_workspace(tmp_path / "cr04_dup", nosology_id="cr04_dup")
    kb_dup = json.loads(ws_dup["kb_json_path"].read_text(encoding="utf-8"))
    kb_dup["modules"][-1]["file"] = kb_dup["modules"][0]["file"]
    ws_dup["kb_json_path"].write_text(json.dumps(kb_dup, ensure_ascii=False, indent=2), encoding="utf-8")
    with pytest.raises(AssertionError, match="Duplicate KB module file"):
        verify_reports.verify_all_reports(
            "cr04_dup", schema_version="v2", write_outputs=False, base_dir=tmp_path / "cr04_dup"
        )

    # (c) Path traversal entry in kb_index.json["modules"]
    ws_trav = _build_synthetic_v2_workspace(tmp_path / "cr04_trav", nosology_id="cr04_trav")
    kb_trav = json.loads(ws_trav["kb_json_path"].read_text(encoding="utf-8"))
    kb_trav["modules"][-1]["file"] = "../../README.md"
    ws_trav["kb_json_path"].write_text(json.dumps(kb_trav, ensure_ascii=False, indent=2), encoding="utf-8")
    with pytest.raises(ValueError):
        verify_reports.verify_all_reports(
            "cr04_trav", schema_version="v2", write_outputs=False, base_dir=tmp_path / "cr04_trav"
        )

    # --- WR-04: Explicit monkeypatch on CONFIGS_DIR/DATA_DIR/REPORTS_DIR wins over INFO_SEARCHER_ROOT ---
    env_root = tmp_path / "wr04_env_root"
    patched_cfg = tmp_path / "wr04_patched_configs"
    patched_data = tmp_path / "wr04_patched_data"
    patched_rep = tmp_path / "wr04_patched_reports"
    monkeypatch.setenv("INFO_SEARCHER_ROOT", str(env_root))
    monkeypatch.setattr(universal_schema, "CONFIGS_DIR", patched_cfg)
    monkeypatch.setattr(universal_schema, "DATA_DIR", patched_data)
    monkeypatch.setattr(universal_schema, "REPORTS_DIR", patched_rep)
    assert universal_schema._get_configs_dir() == patched_cfg
    assert universal_schema._get_data_dir() == patched_data
    assert universal_schema._get_reports_dir() == patched_rep
    saved_wr04 = universal_schema.save_new_nosology_config({"nosology": {"id": "wr04_priority_test"}})
    assert saved_wr04.parent == patched_cfg.resolve()
    assert not (env_root / "configs" / "wr04_priority_test.yaml").exists()

    # --- IN-01: Legacy openalex / clinicaltrials stripped; whitespace-only dropped ---
    saved_ws_blank = universal_schema.save_new_nosology_config(
        {
            "nosology": {"id": "in01_blank"},
            "queries": {"pubmed": "q", "openalex": "   ", "clinicaltrials": "\t \n"},
        }
    )
    cfg_blank = yaml.safe_load(saved_ws_blank.read_text(encoding="utf-8"))
    assert "openalex" not in cfg_blank["queries"]
    assert "openalex_search" not in cfg_blank["queries"]
    assert "clinicaltrials" not in cfg_blank["queries"]
    assert "clinical_trials_condition" not in cfg_blank["queries"]

    saved_ws_strip = universal_schema.save_new_nosology_config(
        {
            "nosology": {"id": "in01_strip"},
            "queries": {"pubmed": "q", "openalex": "  Trigger Finger  ", "clinicaltrials": "  Hand  "},
        }
    )
    cfg_strip = yaml.safe_load(saved_ws_strip.read_text(encoding="utf-8"))
    assert cfg_strip["queries"]["openalex_search"] == "Trigger Finger"
    assert cfg_strip["queries"]["clinical_trials_condition"] == "Hand"

    # Undo monkeypatches before CLI / remaining checks
    monkeypatch.undo()

    # --- IN-02: docx_exporter CLI --nosology all honors INFO_SEARCHER_ROOT ---
    cli_root = tmp_path / "in02_cli_root"
    cli_ws = _build_synthetic_v2_workspace(cli_root, nosology_id="in02_cli_nos")
    cli_env = os.environ.copy()
    cli_env["INFO_SEARCHER_ROOT"] = str(cli_root)
    cli_res = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "src" / "docx_exporter.py"), "--nosology", "all"],
        env=cli_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    assert "in02_cli_nos" in cli_res.stdout
    assert (cli_ws["rep_dir"] / "executive_summary.docx").exists()

    # --- IN-04: query_complications_df() PMID regex validation & DOI prefix normalization ---
    in04_db = tmp_path / "in04_urls.db"
    conn = schema.init_db(in04_db)
    try:
        for row_vals in (
            ("88000001", "https://doi.org/10.1000/already", "ModA", "Comp1"),
            ("TBD", "doi: 10.1000/prefixed", "ModA", "Comp2"),
            ("0", "http://dx.doi.org/10.1000/dx", "ModA", "Comp3"),
        ):
            conn.execute(
                """
                INSERT INTO extracted_complications (
                    pmid, doi, evidence_tier, modality, complication_name,
                    event_class, clavien_dindo_grade, frequency_num, reversibility,
                    sample_size, is_rare_casuistry
                ) VALUES (?, ?, 2, ?, ?, 'true_complication', 'II', 5.0, 'requires_conservative_therapy', 50, 0)
                """,
                row_vals,
            )
        conn.commit()
    finally:
        conn.close()
    df_urls = universal_schema.query_complications_df(in04_db)
    url_by_comp = {
        r["complication_name"]: (r["pubmed_url"], r["doi_url"])
        for _, r in df_urls.iterrows()
    }
    assert url_by_comp["Comp1"] == ("https://pubmed.ncbi.nlm.nih.gov/88000001/", "https://doi.org/10.1000/already")
    assert url_by_comp["Comp2"] == ("", "https://doi.org/10.1000/prefixed")
    assert url_by_comp["Comp3"] == ("", "https://doi.org/10.1000/dx")

    # --- IN-06: CSV export neutralizes leading =/@/\t/\r while preserving clinical +/- ---
    df_csv = pd.DataFrame(
        {
            "val": [
                "=CMD|' /C calc'!A0",
                "@SUM(1+1)",
                "\t=1+1",
                "\r=2+2",
                "+12%",
                "-5°",
                "normal text",
            ]
        }
    )
    csv_raw = universal_schema.dataframe_to_csv_bytes(df_csv)
    assert csv_raw.startswith(b"\xef\xbb\xbf")
    csv_vals = [r["val"] for r in csv.DictReader(io.StringIO(csv_raw.decode("utf-8-sig")))]
    assert csv_vals == [
        "'=CMD|' /C calc'!A0",
        "'@SUM(1+1)",
        "'\t=1+1",
        "'\r=2+2",
        "+12%",
        "-5°",
        "normal text",
    ]


def _build_second_v2_workspace(base_dir: Path, nosology_id: str = "beta_knee_v2") -> dict[str, Any]:
    """Create a second v2.0 nosology with completely disjoint modalities/grades and JSON null edge cases."""
    ws = _build_synthetic_v2_workspace(base_dir, nosology_id=nosology_id)

    # Replace config name_ru so sidebar label is distinct
    cfg = yaml.safe_load(ws["cfg_path"].read_text(encoding="utf-8"))
    cfg["nosology"]["name_ru"] = "Синтетическое повреждение мениска коленного сустава (v2.0)"
    cfg["nosology"]["name_en"] = "Synthetic Meniscal Tear"
    cfg["nosology"]["icd10"] = "M23.2"
    ws["cfg_path"].write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")

    # Replace SQLite extracted_complications with 3 completely disjoint non-casuistry rows + 1 casuistry row
    conn = schema.init_db(ws["db_path"])
    try:
        conn.execute("DELETE FROM extracted_complications")
        art_ids = [r[0] for r in conn.execute("SELECT id FROM articles ORDER BY id ASC LIMIT 5").fetchall()]
        beta_rows = [
            {
                "article_id": art_ids[0],
                "pmid": "88000001",
                "doi": "10.1000/beta.1",
                "first_author_year": "KneeAuth1 2024",
                "evidence_tier": 2,
                "modality": "Артроскопический шов мениска",
                "complication_name": "Артрофиброз коленного сустава",
                "event_class": "true_complication",
                "timing_category": "late_postop",
                "clavien_dindo_grade": "IIIa",
                "frequency_pct": "4.8% (12/250)",
                "frequency_num": 4.8,
                "reversibility": "requires_reoperation",
                "time_window": "3–6 месяцев",
                "anatomical_substrate": "Капсула и передний интервал сустава",
                "prevention_and_management": "Ранняя мобилизация; редрессация под наркозом",
                "sample_size": 250,
                "is_rare_casuistry": 0,
            },
            {
                "article_id": art_ids[1],
                "pmid": "88000002",
                "doi": "10.1000/beta.2",
                "first_author_year": "KneeAuth2 2024",
                "evidence_tier": 2,
                "modality": "Парциальная менискэктомия",
                "complication_name": "Гемартроз послеоперационный",
                "event_class": "true_complication",
                "timing_category": "early_postop",
                "clavien_dindo_grade": "II",
                "frequency_pct": "6.1% (18/295)",
                "frequency_num": 6.1,
                "reversibility": "requires_conservative_therapy",
                "time_window": "7–14 суток",
                "anatomical_substrate": "Синовиальная оболочка",
                "prevention_and_management": "Холодовая компрессия, пункция при напряжённом выпоте",
                "sample_size": 295,
                "is_rare_casuistry": 0,
            },
            {
                "article_id": art_ids[2],
                "pmid": "88000003",
                "doi": "10.1000/beta.3",
                "first_author_year": "KneeAuth3 2025",
                "evidence_tier": 2,
                "modality": "Артроскопический шов мениска",
                "complication_name": "Септический артрит коленного сустава",
                "event_class": "true_complication",
                "timing_category": "early_postop",
                "clavien_dindo_grade": "IV",
                "frequency_pct": "1.2% (3/250)",
                "frequency_num": 1.2,
                "reversibility": "requires_reoperation",
                "time_window": "5–21 сутки",
                "anatomical_substrate": "Полость коленного сустава",
                "prevention_and_management": "Экстренный артроскопический лаваж и в/в антибиотики",
                "sample_size": 250,
                "is_rare_casuistry": 0,
            },
            {
                "article_id": art_ids[4],
                "pmid": "88000005",
                "doi": "10.1000/beta.5",
                "first_author_year": "KneeAuth5 2025",
                "evidence_tier": 4,
                "modality": "Трансплантация алломениска",
                "complication_name": "Травма подколенной артерии (казуистика Tier 4)",
                "event_class": "true_complication",
                "timing_category": "intraop",
                "clavien_dindo_grade": "IV",
                "frequency_pct": "1/1",
                "frequency_num": 100.0,
                "reversibility": "permanent_deficit",
                "time_window": "экстренно",
                "anatomical_substrate": "Подколенная артерия",
                "prevention_and_management": "Защитный ретрактор и сосудистая бригада",
                "sample_size": 1,
                "is_rare_casuistry": 1,
            },
        ]
        for row_payload in beta_rows:
            assert extractor_common.insert_extracted_complication(conn, row_payload) is not None
        conn.commit()
    finally:
        conn.close()

    # Update kb_index.json with disjoint modalities/grades + explicit JSON null values (WR-06)
    kb = json.loads(ws["kb_json_path"].read_text(encoding="utf-8"))
    kb["nosology_meta"]["title_ru"] = cfg["nosology"]["name_ru"]
    kb["nosology_meta"]["title_en"] = cfg["nosology"]["name_en"]
    kb["nosology_meta"]["icd10"] = "M23.2"
    kb["modalities"][0]["name"] = "Артроскопический шов мениска"
    kb["modalities"][1]["name"] = "Парциальная менискэктомия"
    kb["modalities"][2]["name"] = "Трансплантация алломениска"
    kb["frequent_complications"] = [
        {
            "modality": "Артроскопический шов мениска",
            "complication_name": "Артрофиброз коленного сустава",
            "event_class": "true_complication",
            "clavien_dindo_grade": "IIIa",
            "reversibility": "requires_reoperation",
            "frequency_pct": "4.8%",
            "frequency_median_num": 4.8,
            "sample_size_total": 250,
            "time_window": "3–6 месяцев",
            "anatomical_substrate": "Капсула сустава",
            "prevention_and_management": "Ранняя мобилизация",
            "evidence_pmids": ["88000001"],
        },
        {
            "modality": "Парциальная менискэктомия",
            "complication_name": "Событие с отсутствующей степенью и null-полями",
            "event_class": "true_complication",
            "clavien_dindo_grade": None,
            "reversibility": None,
            "frequency_pct": "6.1%",
            "frequency_median_num": 6.1,
            "sample_size_total": 295,
            "time_window": None,
            "anatomical_substrate": None,
            "prevention_and_management": None,
            "evidence_pmids": ["88000002"],
        },
    ]
    kb["rare_critical_red_flags"] = [
        {
            "modality": "Трансплантация алломениска",
            "complication_name": "Травма подколенной артерии",
            "clavien_dindo_grade": "IV",
            "reversibility": "permanent_deficit",
            "frequency_pct": "< 0.2%",
            "frequency_max_num": 0.2,
            "anatomical_substrate": None,
            "prevention_and_management": None,
            "evidence_pmids": ["88000005"],
        }
    ]
    kb["clinical_decision_nuances"]["universal_workhorse_modalities"][0]["modality"] = "Артроскопический шов мениска"
    kb["clinical_decision_nuances"]["universal_workhorse_modalities"][0]["practical_nuances"] = None
    kb["clinical_decision_nuances"]["overlapping_indications_and_gray_zones"][0]["competing_modalities"] = [
        None,
        "Артроскопический шов мениска",
        "Парциальная менискэктомия",
    ]
    ws["kb_json_path"].write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")
    return ws


def test_v2_apptest_multi_nosology_switch_overrides_and_resilience(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lock CR-01 (multi-nosology v2->v2 switch), WR-05 (subprocess errors), WR-06 (JSON null / missing CD), WR-07 (Tab 4 overrides & negative paths)."""
    _build_synthetic_v2_workspace(tmp_path, nosology_id="alpha_hand_v2")
    _build_second_v2_workspace(tmp_path, nosology_id="beta_knee_v2")

    monkeypatch.setenv("INFO_SEARCHER_ROOT", str(tmp_path))
    monkeypatch.setenv("INFO_SEARCHER_APPTEST_ACTIVE", "1")
    st.cache_data.clear()

    try:
        at = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=60).run(timeout=60)
        assert len(at.exception) == 0, f"Initial multi-v2 AppTest raised: {at.exception}"

        # Confirm starting on alpha_hand_v2
        assert at.selectbox(key="sidebar_nosology_select").value == "alpha_hand_v2"
        t25_alpha = next(t for t in at.tabs if "2.5" in t.label)
        assert len(t25_alpha.get("plotly_chart")) >= 2
        assert len(t25_alpha.dataframe) >= 1

        # Visit Tab 3 Option 5 on alpha_hand_v2 so its multiselect session_state keys are populated
        t3_opts_alpha = list(at.radio(key="tab3_table_choice").options)
        opt5_alpha = next(o for o in t3_opts_alpha if o.startswith("5."))
        at.radio(key="tab3_table_choice").set_value(opt5_alpha).run(timeout=60)
        assert len(at.exception) == 0
        t3_alpha = next(t for t in at.tabs if t.label.startswith("📚 3."))
        assert len(t3_alpha.dataframe[0].value) == 4

        # --- CR-01: Switch sidebar_nosology_select alpha_hand_v2 -> beta_knee_v2 ---
        at.selectbox(key="sidebar_nosology_select").set_value("beta_knee_v2").run(timeout=60)
        assert len(at.exception) == 0, f"Switching to beta_knee_v2 raised: {at.exception}"

        # Subtab 2.5 MUST immediately populate both charts & rows for beta_knee_v2 (0 stale filter lockout)
        t25_beta = next(t for t in at.tabs if "2.5" in t.label)
        assert len(t25_beta.get("plotly_chart")) >= 2, "CR-01 regression: Subtab 2.5 charts wiped out after switch!"
        assert len(t25_beta.dataframe) >= 1, "CR-01 regression: Subtab 2.5 table missing after switch!"
        df_25_beta = t25_beta.dataframe[0].value
        assert len(df_25_beta) == 2
        assert "Артроскопический шов мениска" in set(df_25_beta["Методика"].tolist())
        t25_beta_text = _collect_block_text(t25_beta)
        assert "Нет осложнений, соответствующих выбранным фильтрам" not in t25_beta_text

        # --- WR-06: Missing clavien_dindo_grade renders 'Не указан' (NOT 'I'), and JSON null never renders 'None' ---
        cd_vals_beta = set(df_25_beta["Clavien–Dindo"].tolist())
        assert "Не указан" in cd_vals_beta, f"Expected 'Не указан' for missing CD grade, got {cd_vals_beta}"
        assert "I" not in cd_vals_beta, f"Missing CD grade was fabricated as 'I': {cd_vals_beta}"
        t26_beta = next(t for t in at.tabs if "2.6" in t.label)
        t26_beta_text = _collect_block_text(t26_beta)
        assert "None" not in t25_beta_text, f"Literal 'None' leaked into Subtab 2.5: {t25_beta_text}"
        assert "None" not in t26_beta_text, f"Literal 'None' leaked into Subtab 2.6: {t26_beta_text}"

        # Subtab 2.4 comparator picks MUST refresh to beta_knee_v2 modalities
        picked_24 = list(at.multiselect(key="sub4_comparator_picks").value)
        assert "Артроскопический шов мениска" in picked_24

        # Tab 3 Option 5 on beta_knee_v2 MUST show all 3 non-casuistry rows immediately
        t3_opts_beta = list(at.radio(key="tab3_table_choice").options)
        opt5_beta = next(o for o in t3_opts_beta if o.startswith("5."))
        at.radio(key="tab3_table_choice").set_value(opt5_beta).run(timeout=60)
        assert len(at.exception) == 0
        t3_beta = next(t for t in at.tabs if t.label.startswith("📚 3."))
        assert len(t3_beta.dataframe) >= 1
        df_35_beta = t3_beta.dataframe[0].value
        assert len(df_35_beta) == 3, f"CR-01 regression: expected 3 beta rows in Tab 3.5, got {len(df_35_beta)}"
        assert "Артроскопический шов мениска" in set(df_35_beta["modality"].tolist())

        # --- WR-07: Tab 4 manual complications_queries override persists verbatim to YAML ---
        override_pm = '("Knee"[MeSH]) AND ("arthrofibrosis"[tiab])'
        override_epmc = '("knee") AND ("arthrofibrosis")'
        at.text_input(key="t4_new_id").set_value("knee_override_v2")
        at.text_area(key="t4_comp_override_pm").set_value(override_pm)
        at.text_area(key="t4_comp_override_epmc").set_value(override_epmc)
        at.form_submit_button[0].click().run(timeout=60)
        assert len(at.exception) == 0

        override_yaml = tmp_path / "configs" / "knee_override_v2.yaml"
        assert override_yaml.exists()
        saved_override = yaml.safe_load(override_yaml.read_text(encoding="utf-8"))
        assert saved_override["complications_queries"]["pubmed"] == override_pm
        assert saved_override["complications_queries"]["europepmc"] == override_epmc

        # --- WR-07 & IN-03: Tab 4 negative paths (invalid/empty ID + frozen PermissionError) show st.error cleanly ---
        for bad_id in ("../bad_id", ""):
            at.text_input(key="t4_new_id").set_value(bad_id)
            at.form_submit_button[0].click().run(timeout=60)
            assert len(at.exception) == 0, f"Unhandled exception for bad_id={bad_id!r}: {at.exception}"
            t4 = next(t for t in at.tabs if t.label.startswith("🛡️ 4."))
            assert len(t4.error) >= 1, f"Expected st.error for bad_id={bad_id!r}"

        real_save_cfg = universal_schema.save_new_nosology_config

        def _guard_frozen_in_apptest(payload: dict[str, Any], **kwargs: Any) -> Path:
            nos_id = str((payload.get("nosology") or {}).get("id") or "").strip().lower()
            if nos_id in universal_schema.FROZEN_V1_NOSOLOGIES:
                raise PermissionError(f"Замороженная конфигурация v1.x '{nos_id}' защищена от перезаписи.")
            return real_save_cfg(payload, **kwargs)

        monkeypatch.setattr(universal_schema, "save_new_nosology_config", _guard_frozen_in_apptest)
        at.text_input(key="t4_new_id").set_value("prom")
        at.form_submit_button[0].click().run(timeout=60)
        assert len(at.exception) == 0, f"Frozen ID PermissionError crashed AppTest: {at.exception}"
        t4 = next(t for t in at.tabs if t.label.startswith("🛡️ 4."))
        assert any("Защита замороженной нозологии v1.x" in e.value for e in t4.error)

        # --- WR-05: btn_run_verify passes errors='replace' and handles OSError gracefully ---
        seen_kwargs: list[dict[str, Any]] = []

        def _failing_subprocess_run(*args: Any, **kwargs: Any) -> Any:
            seen_kwargs.append(dict(kwargs))
            raise OSError("Simulated spawn failure on Windows")

        monkeypatch.setattr(subprocess, "run", _failing_subprocess_run)
        at.button(key="btn_run_verify").click().run(timeout=60)
        assert len(at.exception) == 0, f"btn_run_verify OSError crashed AppTest: {at.exception}"
        assert len(seen_kwargs) == 1 and seen_kwargs[0].get("errors") == "replace"
        t4 = next(t for t in at.tabs if t.label.startswith("🛡️ 4."))
        assert any("Не удалось выполнить аудит" in e.value for e in t4.error)
    finally:
        st.cache_data.clear()
