"""Offline unit, integration, security, and live read-only backward-compatibility tests for Phase 18.

Covers:
- HUM2-01: ru-medical-humanizer v2.0 skill rules, banned cliché catalog, non-linear conclusion model,
           bold_lead_bullet_ratio <= 0.35 budget, and zero legacy typo ('主に').
- HUM2-02: nosology-research-pipeline v2.0 skill contract + clinical_decision_nuances v2.0 validation
           (`validate_kb_clinical_nuances_v2`, `validate_kb_v2`) in `src/universal_schema.py`.
- HUM2-03: Structural anti-AI linter v2.0 (`check_humanizer_v2_structure`), expanded banned phrases,
           pigeonhole routing detection, complications & nuance gates, security hardening (`T-18-03`,
           `T-18-04`), and live read-only `v1.x` compatibility on `prom`, `metroplasty_pregnancy`,
           and `trigger_finger`.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.schema as schema
import src.universal_schema as universal_schema
import src.verify_reports as verify_reports


# ===========================================================================
# Helpers: valid v2.0 KB payload & genuine Russian analytical report text
# ===========================================================================


def _build_valid_v2_kb() -> dict[str, Any]:
    """Return a minimal schema-complete v2.0 kb_index.json payload."""
    modalities = [
        {
            "name": f"Методика {i}",
            "group": "Хирургические вмешательства" if i <= 4 else "Малоинвазивные / консервативные",
            "target_stage": "Стадии I–III",
            "primary_efficacy": "92–96%",
            "remission_5y_pct": "88%",
            "remission_5y_num": 88.0,
            "recurrence_1_2y": "4%",
            "recurrence_3y": "7%",
            "recurrence_5y_overall": "10%",
            "recurrence_5y_num": 10.0,
            "recurrence_10y": "14%",
            "recurrence_by_subtype": {"Благоприятный": "6%", "Тяжёлый": "15%"},
            "procediv_5y": "5%",
            "procediv_5y_num": 5.0,
            "reintervention_5y": "4%",
            "complications_profile": "Поверхностные раневые явления Clavien-Dindo I–II",
            "recovery_time": "2–4 недели",
            "pros": "Воспроизводимый визуальный контроль и стабильный отдалённый результат",
            "cons": "Болезненность рубца в ранние сроки реабилитации",
        }
        for i in range(1, 9)
    ]
    modules = [
        {"id": f"0{i}_module", "title": f"Модуль {i}", "file": f"0{i}_module.md", "category": "clinical"}
        for i in range(1, 6)
    ]
    return {
        "schema_version": "2.0",
        "nosology_id": "synthetic_hand_v2",
        "title_ru": "Тестовая хирургическая нозология кисти (M65.3)",
        "nosology_meta": {
            "nosology_id": "synthetic_hand_v2",
            "title_ru": "Тестовая хирургическая нозология кисти",
            "title_en": "Synthetic Hand Condition",
            "icd10": "M65.3",
            "icd11": "FB40.2",
            "specialty": "Хирургия кисти",
            "time_horizon": "2016–2026",
        },
        "modules": modules,
        "modalities": modalities,
        "frequent_complications": [
            {
                "modality": "Открытое рассечение кольцевидной связки A1",
                "complication_name": "Болезненность и уплотнение ладонного рубца",
                "event_class": "transient_postop_sequela",
                "clavien_dindo_grade": "I",
                "reversibility": "transient_self_limiting",
                "frequency_pct": "19% (14–25%)",
                "frequency_median_num": 19.0,
                "sample_size_total": 240,
                "time_window": "в течение 6–12 недель",
                "anatomical_substrate": "Кожно-подкожный ладонный рубец над проекцией связки A1",
                "prevention_and_management": "Щадящий разрез по кожным линиям, силиконовые пластины и ранний массаж рубца",
                "evidence_pmids": ["88000001", "88000002"],
            },
            {
                "modality": "Открытое рассечение кольцевидной связки A1",
                "complication_name": "Поверхностная инфекция области хирургического вмешательства",
                "event_class": "true_complication",
                "clavien_dindo_grade": "II",
                "reversibility": "requires_conservative_therapy",
                "frequency_pct": "3.4% (2.0–5.2%)",
                "frequency_median_num": 3.4,
                "sample_size_total": 310,
                "time_window": "первые 14 суток",
                "anatomical_substrate": "Края хирургической раны ладонной поверхности",
                "prevention_and_management": "Асептика, контроль гликемии у пациентов с диабетом, короткий курс пероральных антибиотиков",
                "evidence_pmids": ["88000003"],
            },
        ],
        "rare_critical_red_flags": [
            {
                "modality": "Чрескожный игольный релиз под УЗИ-контролем",
                "complication_name": "Ятрогенное повреждение лучевого пальцевого нерва",
                "clavien_dindo_grade": "IIIb",
                "reversibility": "requires_reoperation",
                "frequency_pct": "0.3% (единичные серии и наблюдения)",
                "frequency_max_num": 0.3,
                "anatomical_substrate": "Собственный ладонный пальцевой нерв, прилежащий к сухожильному влагалищу",
                "prevention_and_management": "Непрерывная динамическая сонографическая визуализация нервно-сосудистых пучков; при пересечении — микрохирургический шов",
                "evidence_pmids": ["88000004"],
            }
        ],
        "clinical_decision_nuances": {
            "universal_workhorse_modalities": [
                {
                    "modality": "Открытое рассечение кольцевидной связки A1",
                    "applicable_spectrum": "Первичные формы стадий I–IV без строгих анатомических ограничений",
                    "practical_nuances": "Прямая визуализация сосудисто-нервных пучков и возможность одномоментной оценки состояния сухожилий сгибателей",
                    "surgeon_and_equipment_factors": "Не требует высокочастотного УЗИ-датчика, воспроизводимо на базовом уровне подготовки кистевого хирурга",
                    "patient_tradeoffs": "Более длительная болезненность ладонного рубца в обмен на минимальный риск неполного рассечения связки",
                    "evidence_pmids": ["88000001", "88000005"],
                },
                {
                    "modality": "Чрескожный релиз под УЗИ-навигацией",
                    "applicable_spectrum": "Первичные формы стадий I–III у большинства амбулаторных пациентов",
                    "practical_nuances": "Минимальная травма кожи и быстрое восстановление бытового захвата в амбулаторных условиях",
                    "surgeon_and_equipment_factors": "Критическая зависимость от оснащения клиники линейным датчиком >=12 МГц и прохождения кривой обучения соноанатомии",
                    "patient_tradeoffs": "Возврат к ручной работе через 7–14 дней при условии принятия малого риска остаточных волокон или невропраксии",
                    "evidence_pmids": ["88000004", "88000006"],
                },
            ],
            "overlapping_indications_and_gray_zones": [
                {
                    "clinical_scenario": "Первичная симптоматическая форма II–III степени без фиксированной контрактуры ПМФС",
                    "competing_modalities": [
                        "Открытое рассечение кольцевидной связки A1",
                        "Чрескожный релиз под УЗИ-навигацией",
                    ],
                    "why_no_single_winner": "Обе сквозные методики обеспечивают сопоставимое купирование симптомов свыше 92% по данным РКИ и проспективных когорт",
                    "decisive_practical_factors": "Доступность УЗИ-навигации, опыт хирурга, антикоагулянтный фон, локальный рубцовый статус и приоритет пациента по срокам реабилитации",
                    "evidence_pmids": ["88000005", "88000006"],
                }
            ],
            "strict_niche_or_salvage_indications": [
                {
                    "modality": "Открытая ревизия с тенолизом и резекцией ножки FDS",
                    "narrow_indication_or_salvage_role": "Рецидив после первичной операции и фиксированная рубцовая контрактура ПМФС",
                    "why_not_first_line_for_all": "Повышенная хирургическая травматичность и риск адгезий сухожильного аппарата не оправданы при неосложнённых первичных формах",
                    "evidence_pmids": ["88000007"],
                }
            ],
        },
    }


def _build_good_v2_prose_report(*, include_bibliography: bool = True) -> str:
    """Return genuine Russian analytical prose compliant with Humanizer v2.0."""
    body = """# Клинико-хирургический синтез лечения стенозирующего процесса кисти

## Глава 1. Методология и структура доказательной базы

Систематический анализ современных рандомизированных контролируемых исследований и крупных проспективных когорт за 2016–2026 годы охватывает 36 верифицированных публикаций [1–6]. При сопоставлении исходов различных вмешательств авторы последовательно разграничивают истинный рецидив в зоне первичного вмешательства, продолженное поражение соседних лучей и послеоперационные осложнения, оцениваемые по шкале Clavien–Dindo [7–10]. Такой подход устраняет системную ошибку смешивания технического недосечения связки с истинными ятрогенными повреждениями мягких тканей и нервных стволов.

Сравнительная оценка методик показала, что в первичной амбулаторной практике выбор тактики опирается на анатомический профиль кисти, сопутствующий сахарный диабет, приём антикоагулянтов и функциональные требования к скорости восстановления хвата [11–16]. Плюсы и Минусы каждого подхода целесообразно оценивать не по изолированному проценту раннего купирования щелчка, а по совокупности раневой морбидности, сроков возврата к труду и частоты повторных обращений в пятилетнем горизонте [17–22].

## Глава 2. Профиль осложнений лечения и профилактика ятрогенных повреждений

Частые послеоперационные явления и истинные осложнения радикально различаются по клинической тяжести и обратимости [23–26]. При открытом рассечении кольцевидной связки ведущим транзиторным явлением остаётся болезненность и уплотнение ладонного рубца (медиана 19%, разброс 14–25%, Clavien–Dindo I), которые самостоятельно регрессируют в течение 6–12 недель на фоне раннего массажа и силиконовых пластин [27–29]. Поверхностные инфекции области хирургического вмешательства (Clavien–Dindo II) регистрируются у 2,0–5,2% оперированных, преимущественно у пациентов с декомпенсированным сахарным диабетом, и купируются коротким курсом пероральной антибактериальной терапии без ревизии раны [30, 31].

Редкие критические осложнения (Clavien–Dindo IIIb) вынесены в отдельный контур красных флагов с частотой ниже 1% [32, 33]. Наибольшую клиническую опасность при чрескожных техниках представляет ятрогенное повреждение собственного ладонного пальцевого нерва, особенно в области первого луча, где сосудисто-нервный пучок пересекает проекцию связки косо. Профилактика необратимого дефицита строится на обязательной непрерывной динамической сонографической визуализации нервно-сосудистых структур либо переходе на открытый доступ при сомнительной анатомии.

- **Ключевой маркер безопасности:** раздельная регистрация транзиторной болезненности рубца (Clavien–Dindo I) и истинных хирургических осложнений (Clavien–Dindo II–IIIb) исключает искусственное завышение риска открытых вмешательств [34].
- **Профилактика ятрогении:** отказ от «слепой» чрескожной методики при отсутствии высокочастотного датчика снижает частоту невропраксии и повреждений сухожилий сгибателей [35].

## Глава 3. Заключение и практическая тактика выбора метода

При первичных формах заболевания стадий I–III открытое рассечение связки и чрескожный релиз под ультразвуковой навигацией не делят пациентов по жёстким ступеням классификации — обе сквозные конкурирующие методики закрывают практически весь амбулаторный спектр и обеспечивают сопоставимую стойкую ремиссию свыше 92% [35, 36]. Реальные различия проходят по плоскости практических компромиссов, а не формального номера стадии.

Открытый доступ не зависит от сонографического оснащения клиники, обеспечивает прямой визуальный контроль сосудисто-нервных пучков и демонстрирует воспроизводимые результаты вне зависимости от длительности кривой обучения, однако требует готовности пациента принять болезненный рубец в первые недели после операции. УЗИ-ассистированная чрескожная техника сокращает реабилитацию до 1–2 недель и минимизирует кожную травму, но критически опирается на опыт хирурга, владение динамической соноанатомией и наличие высокочастотного датчика. При выборе между этими равноценными альтернативами решающую роль играют оснащение операционной, коморбидный фон и предпочтения пациента по скорости возврата к ручной нагрузке.

В отдельную узкую резервную нишу выносятся лишь ревизионные операции с открытым тенолизом и резекцией сухожильной ножки при рубцовом рецидиве или стойкой сгибательной контрактуре проксимального межфалангового сустава, где малоинвазивный релиз технически не устраняет вторичные адгезии [36].
"""
    if not include_bibliography:
        return body
    bib_lines = [
        f"{i}. Author{i} A. Synthetic clinical study #{i} on surgical safety and outcomes // Hand Surgery Review. — 2024. — PMID: {88000000 + i}."
        for i in range(1, 37)
    ]
    return body + "\n---\n\n## Список литературы\n\n" + "\n".join(bib_lines) + "\n"


# ===========================================================================
# 1. Skill v2.0 contract tests (HUM2-01, HUM2-02)
# ===========================================================================


def test_skills_v2_contracts() -> None:
    """Verify ru-medical-humanizer v2.0 and nosology-research-pipeline v2.0 skill contracts."""
    humanizer_path = PROJECT_ROOT / ".agent" / "skills" / "ru-medical-humanizer" / "SKILL.md"
    pipeline_path = PROJECT_ROOT / ".agent" / "skills" / "nosology-research-pipeline" / "SKILL.md"
    assert humanizer_path.exists()
    assert pipeline_path.exists()

    hum_text = humanizer_path.read_text(encoding="utf-8")
    hum_low = hum_text.lower()
    assert "主に" not in hum_text, "Legacy Japanese typo '主に' must be removed from ru-medical-humanizer/SKILL.md"
    assert "## 6. Хуманизация v2.0" in hum_text
    assert "bold_lead_bullet_ratio <= 0.35" in hum_text
    assert "метод 1 подходит для 1" in hum_low
    assert "universal_workhorse_modalities" in hum_text
    assert "overlapping_indications_and_gray_zones" in hum_text
    assert "strict_niche_or_salvage_indications" in hum_text

    # Confirm expanded v2.0 cliché dictionary appears in Section 2 of SKILL.md
    for phrase in (
        "подводя итог, можно заключить",
        "резюмируя вышеизложенное",
        "выбор метода зависит от индивидуальных особенностей",
        "индивидуальный подход к каждому пациенту",
        "не существует универсального метода",
        "заслуживает особого внимания",
        "в заключение следует отметить",
        "в контексте современной медицины",
    ):
        assert phrase in hum_low, f"Missing v2.0 banned cliché in ru-medical-humanizer/SKILL.md: {phrase!r}"

    pipe_text = pipeline_path.read_text(encoding="utf-8")
    for token in (
        "surgical_focus",
        "treatment_profile",
        "complications_queries",
        "complications_safety",
        "extracted_complications",
        "frequent_complications",
        "rare_critical_red_flags",
        "clinical_decision_nuances",
        "--schema-version v2",
    ):
        assert token in pipe_text, f"Missing v2.0 contract token in nosology-research-pipeline/SKILL.md: {token!r}"


# ===========================================================================
# 2. Universal Schema clinical_decision_nuances v2.0 validation (HUM2-02)
# ===========================================================================


def test_universal_schema_clinical_decision_nuances_v2() -> None:
    """Verify validate_kb_clinical_nuances_v2() and composite validate_kb_v2() enforce all v2.0 invariants."""
    valid_kb = _build_valid_v2_kb()
    assert universal_schema.validate_kb_clinical_nuances_v2(valid_kb) == []
    assert universal_schema.validate_kb_v2(valid_kb) == []

    # Empty strict_niche_or_salvage_indications list is allowed (>= 0 entries)
    kb_empty_niches = copy.deepcopy(valid_kb)
    kb_empty_niches["clinical_decision_nuances"]["strict_niche_or_salvage_indications"] = []
    assert universal_schema.validate_kb_clinical_nuances_v2(kb_empty_niches) == []

    # Missing clinical_decision_nuances rejected
    kb_missing = copy.deepcopy(valid_kb)
    kb_missing.pop("clinical_decision_nuances")
    errs_missing = universal_schema.validate_kb_clinical_nuances_v2(kb_missing)
    assert errs_missing and any("clinical_decision_nuances" in e for e in errs_missing)
    assert universal_schema.validate_kb_v2(kb_missing) == errs_missing

    # Empty universal_workhorse_modalities rejected
    kb_empty_wh = copy.deepcopy(valid_kb)
    kb_empty_wh["clinical_decision_nuances"]["universal_workhorse_modalities"] = []
    errs_wh = universal_schema.validate_kb_clinical_nuances_v2(kb_empty_wh)
    assert any("universal_workhorse_modalities" in e for e in errs_wh)

    # Overlapping zone with < 2 competing_modalities (single item and case-insensitive duplicates) rejected
    kb_one_comp = copy.deepcopy(valid_kb)
    kb_one_comp["clinical_decision_nuances"]["overlapping_indications_and_gray_zones"][0]["competing_modalities"] = [
        "Открытый релиз"
    ]
    errs_one = universal_schema.validate_kb_clinical_nuances_v2(kb_one_comp)
    assert any("competing_modalities" in e and ">= 2" in e for e in errs_one)

    kb_dup_comp = copy.deepcopy(valid_kb)
    kb_dup_comp["clinical_decision_nuances"]["overlapping_indications_and_gray_zones"][0]["competing_modalities"] = [
        "Открытый релиз",
        "  открытый релиз  ",
    ]
    errs_dup = universal_schema.validate_kb_clinical_nuances_v2(kb_dup_comp)
    assert any("competing_modalities" in e and ">= 2" in e for e in errs_dup)

    # Empty / whitespace string fields rejected across all three sections
    kb_empty_str = copy.deepcopy(valid_kb)
    kb_empty_str["clinical_decision_nuances"]["universal_workhorse_modalities"][0]["practical_nuances"] = "   "
    kb_empty_str["clinical_decision_nuances"]["overlapping_indications_and_gray_zones"][0]["why_no_single_winner"] = ""
    kb_empty_str["clinical_decision_nuances"]["strict_niche_or_salvage_indications"][0][
        "why_not_first_line_for_all"
    ] = "   "
    errs_str = universal_schema.validate_kb_clinical_nuances_v2(kb_empty_str)
    assert any("practical_nuances" in e for e in errs_str)
    assert any("why_no_single_winner" in e for e in errs_str)
    assert any("why_not_first_line_for_all" in e for e in errs_str)

    # Invalid evidence_pmids ([None], mixed valid+None, blank, bool) rejected (T-18-01)
    for bad_pmids in ([None], ["88000001", None], ["   "], [True], []):
        kb_bad_pmid = copy.deepcopy(valid_kb)
        kb_bad_pmid["clinical_decision_nuances"]["universal_workhorse_modalities"][0]["evidence_pmids"] = bad_pmids
        errs_pmid = universal_schema.validate_kb_clinical_nuances_v2(kb_bad_pmid)
        assert any("evidence_pmids" in e for e in errs_pmid), f"Failed to reject evidence_pmids={bad_pmids!r}"


# ===========================================================================
# 3. Structural Anti-AI Linter v2.0 unit tests (HUM2-03)
# ===========================================================================


def test_verify_reports_humanizer_v2_rejects_ai_antipatterns() -> None:
    """Verify check_humanizer_v2_structure() catches every v2.0 anti-pattern and passes genuine analytical prose."""
    good_text = _build_good_v2_prose_report(include_bibliography=True)

    # 1) Genuine analytical prose passes cleanly
    res_good = verify_reports.check_humanizer_v2_structure(
        good_text, mode="dissertation", schema_version="2.0"
    )
    assert res_good["passed"] is True, f"Unexpected errors on genuine prose: {res_good['errors']}"
    assert res_good["errors"] == []
    assert res_good["pigeonhole_matches"] == []
    assert res_good["has_overlapping_nuance_signals"] is True
    assert res_good["has_complications_analysis"] is True
    assert res_good["bold_lead_bullet_ratio"] <= 0.35
    assert res_good["prose_paragraphs"] >= 6

    # 2) Bullet-wall text (bold_lead_bullet_ratio > 0.35) fails in dissertation mode
    bullet_wall = """# Отчёт

## Осложнения
- **Инфекция раны:** встречается у 3% пациентов, классификация Clavien–Dindo II.
- **Гематома:** встречается у 2% пациентов, транзиторное течение, профилактика дренажом.
- **Отек кисти:** обратим в течение 4 недель.
- **Рубцовая боль:** встречается у 18% пациентов, транзиторная реакция.
- **Невропраксия:** редкое ятрогенное осложнение.
- **Контрактура:** требует ранней реабилитации.
- **Повторное вмешательство:** зависит от опыта хирурга.

## Заключение
Обе сквозные методики конкурируют и перекрывают спектр, а выбор определяется оснащением и предпочтениями пациента.
"""
    res_wall = verify_reports.check_humanizer_v2_structure(
        bullet_wall, mode="dissertation", schema_version="2.0"
    )
    assert res_wall["passed"] is False
    assert res_wall["bold_lead_bullet_ratio"] > 0.35
    assert res_wall["max_consecutive_bold_bullets"] == 7
    assert any("bold_lead_bullet_ratio" in e for e in res_wall["errors"])
    assert any("непрерывный блок" in w for w in res_wall["warnings"])

    # 3) Mechanical pigeonhole conclusions fail with pigeonhole_matches
    pigeonhole_variants = [
        (
            "## Заключение\n"
            "Для стадии I подходит метод А. Для стадии II подходит метод Б. Для стадии III подходит метод В.\n"
            "При этом опыт хирурга и оснащение стационара также учитываются при планировании вмешательства.\n"
        ),
        (
            "## Заключение\n"
            "- **Стадия I:** оптимальна консервативная терапия и локальные инъекции.\n"
            "- **Стадия II:** методом выбора выступает чрескожный релиз под УЗИ-контролем.\n"
            "- **Стадия III:** показана исключительно открытая операция.\n"
            "- **Стадия IV:** требуется расширенная реконструкция.\n"
        ),
        (
            "## Заключение\n"
            "Метод 1 подходит для 1 группы, метод 2 — для 2 группы, метод 3 — для 3 группы.\n"
        ),
        (
            "## Заключение\n"
            "Для стадии I — игольная апоневротомия, для стадии II — сегментарная фасциэктомия, "
            "для стадии III — дермофасциэктомия с кожной пластикой.\n"
        ),
    ]
    base_prefix = good_text.split("## Глава 3.")[0]
    for idx, bad_conclusion in enumerate(pigeonhole_variants):
        res_pig = verify_reports.check_humanizer_v2_structure(
            base_prefix + bad_conclusion, mode="dissertation", schema_version="2.0"
        )
        assert res_pig["passed"] is False, f"Pigeonhole variant #{idx} should fail"
        assert res_pig["pigeonhole_matches"], f"Pigeonhole variant #{idx} missed by pigeonhole detector"
        assert any("коробоч" in e.lower() for e in res_pig["errors"])

    # 4) Banned v2.0 AI conclusion clichés fail
    for cliche in (
        "Таким образом, каждый метод имеет свои преимущества и недостатки.",
        "Подводя итог, можно заключить, что выбор метода зависит от индивидуальных особенностей.",
    ):
        res_cliche = verify_reports.check_humanizer_v2_structure(
            good_text.replace("## Список литературы", f"\n{cliche}\n\n## Список литературы"),
            mode="dissertation",
            schema_version="2.0",
        )
        assert res_cliche["passed"] is False
        assert res_cliche["banned_phrases_found"]

    # 5) Report missing treatment complications analysis fails
    no_comp_text = (
        good_text.replace("осложнен", "исход")
        .replace("Осложнен", "Исход")
        .replace("Clavien", "Шкала")
    )
    res_nocomp = verify_reports.check_humanizer_v2_structure(
        no_comp_text, mode="dissertation", schema_version="2.0"
    )
    assert res_nocomp["passed"] is False
    assert res_nocomp["has_complications_analysis"] is False
    assert any("осложнений" in e for e in res_nocomp["errors"])

    # 6) Report missing overlapping/workhorse nuance signals in final chapter fails
    flat_conclusion = (
        base_prefix
        + "## Глава 3. Заключение\n\n"
        + "Проведённый анализ клинических исследований подтверждает высокую воспроизводимость хирургических вмешательств "
        + "на кисти в течение пятилетнего наблюдения при соблюдении стандартных протоколов асептики и реабилитации.\n"
    )
    res_nonuance = verify_reports.check_humanizer_v2_structure(
        flat_conclusion, mode="dissertation", schema_version="2.0"
    )
    assert res_nonuance["passed"] is False
    assert res_nonuance["has_overlapping_nuance_signals"] is False
    assert any("нелинейной клинической логики" in e for e in res_nonuance["errors"])

    # 7) Legacy v1.x compat mode converts v2 structural findings into non-blocking warnings
    res_v1_compat = verify_reports.check_humanizer_v2_structure(
        bullet_wall, mode="dissertation", schema_version="1.x"
    )
    assert res_v1_compat["passed"] is True
    assert res_v1_compat["errors"] == []
    assert res_v1_compat["warnings"]


# ===========================================================================
# 4. Synthetic end-to-end v2.0 report verification & T-18-03/T-18-04 security
# ===========================================================================


def _create_synthetic_v2_nosology(tmp_path: Path, nosology_id: str = "synthetic_hand_v2") -> dict[str, Path]:
    """Build a complete self-contained synthetic v2.0 nosology under tmp_path."""
    cfg_dir = tmp_path / "configs"
    data_dir = tmp_path / "data" / nosology_id
    rep_dir = tmp_path / "reports" / nosology_id
    kb_dir = rep_dir / "knowledge_base"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    kb_dir.mkdir(parents=True, exist_ok=True)

    cfg_path = cfg_dir / f"{nosology_id}.yaml"
    cfg_path.write_text(
        f"nosology_id: {nosology_id}\n"
        "name_ru: Тестовая хирургическая нозология кисти\n"
        "icd10: M65.3\n"
        "verification_rules:\n"
        "  required_terms:\n"
        "    - Плюсы\n"
        "    - Минусы\n",
        encoding="utf-8",
    )

    db_path = data_dir / "literature.db"
    conn = schema.init_db(db_path)
    try:
        for i in range(1, 37):
            pmid = str(88000000 + i)
            conn.execute(
                """
                INSERT INTO articles (
                    pmid, pmcid, doi, title, norm_title, abstract, authors, journal,
                    pub_year, prisma_status, evidence_tier
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pmid,
                    f"PMC8800{i:03d}",
                    f"10.1000/synth.{i}",
                    f"Synthetic clinical study {i} evaluating surgical complications and safety",
                    f"syntheticclinicalstudy{i}",
                    "Prospective comparative study referencing NCT05123456 with Clavien-Dindo safety outcomes.",
                    json.dumps([f"Author{i} A"]),
                    "Hand Surgery Review",
                    2024,
                    "included",
                    2,
                ),
            )
        conn.execute(
            """
            INSERT INTO clinical_trials (nct_id, brief_title, overall_status, phase, enrollment)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("NCT05123456", "Open vs US-Guided Release Comparative Trial", "COMPLETED", "PHASE3", 180),
        )
        conn.commit()
    finally:
        conn.close()

    diss_text = _build_good_v2_prose_report(include_bibliography=True)
    assert len(diss_text.encode("utf-8")) > 3500
    diss_path = rep_dir / "dissertation_report.md"
    diss_path.write_text(diss_text, encoding="utf-8")

    sum_text = (
        "# Краткое клиническое руководство (Executive Summary v2.0)\n\n"
        "## 1. Сравнительная сводка методик и профиль осложнений\n\n"
        "Плюсы и Минусы двух сквозных хирургических методик подтверждены в когортах [PMID: 88000001; PMID: 88000005] "
        "и рандомизированном протоколе NCT05123456. Профиль осложнений стратифицирован по Clavien–Dindo: "
        "транзиторная болезненность ладонного рубца (Clavien–Dindo I) регрессирует за 6–12 недель, а поверхностная "
        "инфекция раны (Clavien–Dindo II) контролируется пероральной антибиотикотерапией [PMID: 88000002; PMID: 88000003]. "
        "Ятрогенное повреждение пальцевого нерва относится к редким красным флагам (< 1%, Clavien–Dindo IIIb) и "
        "предотвращается постоянным сонографическим контролем либо открытой ревизией [PMID: 88000004].\n\n"
        "| Методика | Эффективность | Частые осложнения (Clavien–Dindo) | Красные флаги | Плюсы и Минусы |\n"
        "| :--- | :---: | :--- | :--- | :--- |\n"
        "| Открытый релиз | 94–97% | Болезненность рубца 19% (I), инфекция 3.4% (II) | Адгезия сухожилия < 0.5% | Плюсы: визуальный контроль; Минусы: рубец |\n"
        "| УЗИ-релиз | 92–96% | Транзиторная парестезия 5% (I) | Травма нерва 0.3% (IIIb) | Плюсы: быстрая реабилитация; Минусы: кривая обучения |\n\n"
        "## 2. Практическая тактика и клинические компромиссы\n\n"
        "Обе базовые операции конкурируют на одних и тех же первичных пациентах стадий I–III и демонстрируют "
        "равноценную отдалённую стойкость результата [PMID: 88000006]. Решение принимается не по формальной ступени, "
        "а с учётом оснащения клиники линейным УЗИ-датчиком, опыта хирурга, антикоагулянтной терапии и предпочтений "
        "пациента в отношении рубца и скорости возврата к работе. Ревизионный тенолиз и резекция сухожильной ножки "
        "остаются узкой резервной нишей для рецидивных и фиксированных контрактур [PMID: 88000007].\n\n"
        + (
            "Дополнительное клиническое наблюдение проспективных серий подтверждает стабильность отдалённых исходов "
            "при соблюдении протоколов ранней мобилизации, контроля гликемии и профилактики раневых осложнений "
            "[PMID: 88000008; PMID: 88000009]. "
            * 8
        )
    )
    assert len(sum_text.encode("utf-8")) > 3500
    sum_path = rep_dir / "executive_summary.md"
    sum_path.write_text(sum_text, encoding="utf-8")

    kb_body_base = (
        "Аналитический справочный модуль базы знаний v2.0 по клиническим исходам, профилю безопасности Clavien–Dindo, "
        "профилактике ятрогенных повреждений и практическим компромиссам конкурирующих методик "
        "[PMID: 88000001; PMID: 88000004; PMID: 88000005]. "
    )
    for i in range(1, 6):
        mod_path = kb_dir / f"0{i}_module.md"
        mod_text = f"# Модуль базы знаний {i}\n\n" + (kb_body_base * 14) + "\n"
        assert len(mod_text.encode("utf-8")) > 3500
        mod_path.write_text(mod_text, encoding="utf-8")

    kb_json_path = kb_dir / "kb_index.json"
    kb_json_path.write_text(json.dumps(_build_valid_v2_kb(), ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "cfg": cfg_path,
        "db": db_path,
        "diss": diss_path,
        "sum": sum_path,
        "kb_json": kb_json_path,
        "rep_dir": rep_dir,
    }


def test_verify_all_reports_v2_end_to_end_and_path_traversal(tmp_path: Path) -> None:
    """Verify full v2.0 synthetic pipeline (auto & v2), failure injections, read-only guarantee, and T-18-03 path blocking."""
    artifacts = _create_synthetic_v2_nosology(tmp_path)

    # 1) Passes cleanly in both 'auto' and explicit 'v2' read-only modes without creating .docx or audit files
    res_auto = verify_reports.verify_all_reports(
        "synthetic_hand_v2", schema_version="auto", write_outputs=False, base_dir=tmp_path
    )
    assert res_auto["passed"] is True
    assert res_auto["schema_version"] == "2.0"
    assert res_auto["read_only"] is True
    assert res_auto["bib_count"] == 36
    assert res_auto["bold_lead_bullet_ratio"] <= 0.35
    assert res_auto["kb_v2_errors"] == []
    assert not (artifacts["rep_dir"] / "verification_audit.md").exists()
    assert not (artifacts["rep_dir"] / "dissertation_report.docx").exists()

    res_v2 = verify_reports.verify_all_reports(
        "synthetic_hand_v2", schema_version="v2", write_outputs=False, base_dir=tmp_path
    )
    assert res_v2["passed"] is True
    assert res_v2["schema_version"] == "2.0"

    # 2) T-18-04: Read-only mode NEVER writes @PMID fixes to disk
    orig_sum = artifacts["sum"].read_text(encoding="utf-8")
    artifacts["sum"].write_text(orig_sum.replace("PMID: 88000001", "@PMID:88000001", 1), encoding="utf-8")
    res_ro_at = verify_reports.verify_all_reports(
        "synthetic_hand_v2", schema_version="v2", write_outputs=False, base_dir=tmp_path
    )
    assert res_ro_at["passed"] is True
    assert "@PMID:88000001" in artifacts["sum"].read_text(encoding="utf-8")
    artifacts["sum"].write_text(orig_sum, encoding="utf-8")

    # 3) Injecting pigeonhole conclusion into dissertation causes v2 failure
    orig_diss = artifacts["diss"].read_text(encoding="utf-8")
    pigeonhole_diss = orig_diss.replace(
        "## Глава 3. Заключение и практическая тактика выбора метода",
        "## Глава 3. Заключение и практическая тактика выбора метода\n\n"
        "Для стадии I подходит метод А. Для стадии II подходит метод Б. Для стадии III подходит метод В.\n",
    )
    artifacts["diss"].write_text(pigeonhole_diss, encoding="utf-8")
    with pytest.raises(AssertionError, match="Humanizer v2.0 Failure"):
        verify_reports.verify_all_reports(
            "synthetic_hand_v2", schema_version="v2", write_outputs=False, base_dir=tmp_path
        )
    artifacts["diss"].write_text(orig_diss, encoding="utf-8")

    # 4) Removing clinical_decision_nuances from kb_index.json causes v2 KB contract failure
    orig_kb = json.loads(artifacts["kb_json"].read_text(encoding="utf-8"))
    broken_kb = copy.deepcopy(orig_kb)
    broken_kb.pop("clinical_decision_nuances")
    artifacts["kb_json"].write_text(json.dumps(broken_kb, ensure_ascii=False, indent=2), encoding="utf-8")
    with pytest.raises(AssertionError, match="KB v2.0 Contract Failure"):
        verify_reports.verify_all_reports(
            "synthetic_hand_v2", schema_version="v2", write_outputs=False, base_dir=tmp_path
        )

    # 5) T-18-03: Path traversal nosology_id rejected with ValueError
    for malicious_id in ("../../escape", "../prom", "prom/../../evil", "bad-id", ""):
        with pytest.raises(ValueError):
            verify_reports.get_nosology_paths(malicious_id, base_dir=tmp_path)
        with pytest.raises(ValueError):
            verify_reports.verify_all_reports(malicious_id, write_outputs=False, base_dir=tmp_path)


# ===========================================================================
# 5. Live read-only v1.x backward-compatibility & immutability (T-18-04)
# ===========================================================================


def test_v1_reports_read_only_backward_compat() -> None:
    """Verify frozen v1.x corpora pass in auto/read-only mode, fail strict v2, and sustain zero disk mutations."""
    frozen_nosologies = ("prom", "metroplasty_pregnancy", "trigger_finger")

    for nos_id in frozen_nosologies:
        db_path = PROJECT_ROOT / "data" / nos_id / "literature.db"
        rep_dir = PROJECT_ROOT / "reports" / nos_id
        watched_files = [
            db_path,
            rep_dir / "dissertation_report.md",
            rep_dir / "executive_summary.md",
            rep_dir / "verification_audit.md",
            rep_dir / "knowledge_base" / "kb_index.json",
        ]
        stats_before = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in watched_files if p.exists()}
        wal_path = Path(f"{db_path}-wal")
        shm_path = Path(f"{db_path}-shm")
        wal_before = wal_path.exists()
        shm_before = shm_path.exists()

        # Auto read-only passes cleanly in v1.x compat mode
        res = verify_reports.verify_all_reports(nos_id, schema_version="auto", write_outputs=False)
        assert res["passed"] is True
        assert res["schema_version"] == "1.x"
        assert res["read_only"] is True
        assert res["bib_count"] >= 35

        # Explicit strict v2 cleanly rejects frozen v1.x reports without mutating disk
        with pytest.raises(AssertionError):
            verify_reports.verify_all_reports(nos_id, schema_version="v2", write_outputs=False)

        # Byte-level immutability across DB and report files
        for p, before_meta in stats_before.items():
            after_stat = p.stat()
            assert (after_stat.st_mtime_ns, after_stat.st_size) == before_meta, f"Frozen file mutated: {p}"
        assert wal_path.exists() == wal_before
        assert shm_path.exists() == shm_before

    # Explicitly scope git immutability assertion to the 6 frozen v1.x directories
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
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert git_res.stdout.strip() == "", f"Frozen v1.x directories modified:\n{git_res.stdout}"
