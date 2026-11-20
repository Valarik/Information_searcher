---
name: nosology-research-pipeline
description: >-
  Универсальный многофазный пайплайн сбора, PRISMA-скрининга, структурированной
  экстракции и аналитического синтеза медицинской литературы по любой нозологии
  с использованием API PubMed, Europe PMC, OpenAlex и ClinicalTrials.gov.
---

# Пайплайн глубокого исследования нозологии (Nosology Research Pipeline v2.0)

Стандарт работы агентов при создании систематических аналитических отчетов по медицинским нозологиям за заданный горизонт лет с профилем осложнений лечения и нелинейной клинической логикой выводов (`schema_version: "2.0"`).

## Архитектура пайплайна (5 фаз)

### Фаза 0: Конфигурация нозологии (`configs/<nosology>.yaml`)
Перед запуском поиска формируется конфигурационный файл нозологии:
- `nosology_id`, название (RU / EN), коды МКБ-10 / МКБ-11, MeSH-дескрипторы.
- Временной диапазон (например, `2016-01-01` — `2026-12-31`).
- Профиль лечения и фокус осложнений (`v2.0`):
  - **`surgical_focus`** (по умолчанию `true`): включает прицельный сбор интра- и послеоперационных осложнений (`Postoperative Complications` / `Intraoperative Complications` / `Clavien–Dindo`); при `surgical_focus: false` активируется консервативный профиль лекарственной/системной безопасности (`Drug-Related Side Effects and Adverse Reactions` / `CTCAE`).
  - **`treatment_profile`**: явный режим профиля лечения — `surgical | mixed | conservative` (`surgical` и `mixed` используют хирургический контур осложнений).
  - **`complications_queries`**: опциональный блок ручного переопределения целевых запросов по осложнениям (`pubmed`, `europepmc`, опционально `max_results`, `pubmed_max_results`, `europepmc_max_results`). Если блок не задан, `src/harvester.py` автоматически строит гибридные запросы по `mesh_terms`, `triage_rules.core_terms` и `date_range`.
  - **`triage_rules.complication_terms`** и **`triage_rules.rare_complication_terms`**: специфические для нозологии термины частых и редких критических осложнений для PRISMA-разметки.
- Основные поисковые запросы для каждой базы:
  - **PubMed:** MeSH + Title/Abstract синонимы.
  - **Europe PMC:** запрос для выгрузки метаданных и открытых полных текстов (`HAS_FT:y` / `OPEN_ACCESS:y`).
  - **OpenAlex:** разрешение концепта/топика через ID и фильтрация по цитируемости и годам.
  - **ClinicalTrials.gov:** поиск клинических исследований по условию (`condition`).
- Тематические кластеры и схема полей для экстракции.

### Фаза 1: Сбор и PRISMA-картирование (`src/harvester.py` и `src/triage.py`)
1. Выгрузка всех найденных публикаций из 4 основных источников через штатные API-обертки плюс **отдельный целевой проход по осложнениям лечения** (`v2.0`):
   - Сырой кэш осложнений сохраняется отдельно в `data/<nosology>/raw/pubmed_complications.json` и `data/<nosology>/raw/europepmc_complications.json`.
   - При слиянии в SQLite через `upsert_article()` сохраняется точный провенанс источников: `PubMed:Complications` и `EuropePMC:Complications` (объединяется с основным списком `sources` без дублирования строк).
2. Загрузка и триаж в единой базе `data/<nosology>/literature.db` (SQLite):
   - Дедупликация по нормализованному `DOI`, `PMID`, `PMCID` и совпадению нормализованного заголовка + года.
   - Автоматическая классификация по уровню доказательности и **двухконтурное разделение когорт и казуистики**:
     - `Tier 1`: Систематические обзоры, метаанализы, рандомизированные контролируемые исследования (РКИ / RCT), клинические рекомендации.
     - `Tier 2`: Проспективные когортные исследования, сравнительные исследования, GWAS / scRNA-seq / мультиомиксные фундаментальные работы.
     - `Tier 3`: Ретроспективные серии (`N >= 20`), исследования случай-контроль, экспериментальные работы *in vitro* / *ex vivo*, нарративные обзоры.
     - `Tier 4`: Одиночные клинические случаи (`Case Reports`), малые клинические серии (`N < 20`), письма, комментарии, статьи без абстракта. Клинические случаи и серии `N < 20` с тяжелыми осложнениями маркируются как `rare_catastrophic_case` и строго отделяются от когортного контура `Tier 1–3` (`N >= 20`), чтобы единичные наблюдения (`1/1 = 100%`) не искажали популяционные частоты.
   - Автоматическая тематическая разметка: к кластерам из YAML добавляется сквозной тег **`complications_safety`** по трем независимым триггерам (провенанс `:Complications`, универсальный словарь безопасности/осложнений, а также `triage_rules.complication_terms` / `rare_complication_terms`), с отдельной строкой статистики в `reports/<nosology>/prisma_stats.md`.
   - Приоритетная докачка полнотекстовых XML из Europe PMC: публикации `Tier 1–3` с тегом `complications_safety` получают повышенный приоритет в очереди загрузки XML для извлечения полных таблиц нежелательных явлений.

### Фаза 2: Роевая структурированная экстракция (`Extractor Swarm`)
Вместо неструктурированного RAG-поиска корпус делится на тематические домены. Специализированные экстракторы читают полнотекстовые XML и абстракты работ `Tier 1–3` (а для редких критических осложнений — и верифицированные `Tier 4`) и заполняют три реляционные таблицы в `data/<nosology>/literature.db`:
- **`extracted_mechanisms`**: `article_id`, `pmid`, `doi`, `first_author_year`, `category`, `targets_genes_pathways`, `study_model`, `sample_size`, `quantitative_findings`, `mechanism_summary`, `therapeutic_implication`.
- **`extracted_clinical_evidence`**: `article_id`, `pmid`, `doi`, `first_author_year`, `study_design`, `evidence_tier`, `n_patients`, `n_rays_or_joints`, `baseline_severity`, `intervention_group`, `comparator_group`, `followup_months`, `mcp_outcome`, `pip_outcome`, `recurrence_definition`, `recurrence_rate_overall`, `recurrence_rate_mcp`, `recurrence_rate_pip`, `complications_summary`, `complications_rate`, `prom_scores`, `key_conclusion`.
- **`extracted_complications`** (`v2.0`): `article_id`, `pmid`, `doi`, `first_author_year`, `evidence_tier`, `modality`, `complication_name`, `event_class` (`true_complication` | `transient_postop_sequela`), `timing_category`, `clavien_dindo_grade` (`I`, `II`, `IIIa`, `IIIb`, `IV`, `V`), `ctcae_grade`, `frequency_pct`, `frequency_num`, `reversibility` (`transient_self_limiting` | `requires_conservative_therapy` | `requires_reoperation` | `permanent_deficit`), `time_window`, `anatomical_substrate`, `prevention_and_management`, `sample_size`, `is_rare_casuistry`.
  - **Анти-рецидивное правило:** в `extracted_complications` запрещено дублировать истинный рецидив заболевания (`true recurrence` / `disease recurrence` / `истинный рецидив`) и неполную первичную коррекцию (`incomplete release` / `неполный релиз`) — они учитываются исключительно в таблице эффективности `extracted_clinical_evidence`.
  - Для транзиторных послеоперационных явлений (`transient_postop_sequela`) обязательно фиксируется окно разрешения `time_window`; для `Tier 4` / `N < 20` выставляется `is_rare_casuistry = 1` и обнуляется `frequency_num`.

### Фаза 3: Многорежимный синтез отчета (`Synthesizer v2.0`), контракт `kb_index.json` и экспорт `.docx`
На основе таблиц из Фазы 2 генерируются тексты в трех режимах (строго по правилам скилла `ru-medical-humanizer v2.0`), которые компилируются в `.md` и MS Word (`.docx`) через `src/docx_exporter.py` и `src/verify_reports.py`:
1. `reports/<nosology>/dissertation_report.md` и **`reports/<nosology>/dissertation_report.docx`** — полный текст диссертационного / монографического уровня с нумерованной библиографией, **обязательной главой/разделом разбора осложнений лечения** (частые когортные осложнения `>= 1%` с градацией `Clavien–Dindo` / `CTCAE` отдельно от редких критических «красных флагов» `< 1%`) и нелинейным клиническим заключением в связной прозе (`bold_lead_bullet_ratio <= 0.35`).
2. `reports/<nosology>/executive_summary.md` и **`reports/<nosology>/executive_summary.docx`** — концентрированное клиническое руководство с матрицей осложнений и практическими компромиссами выбора сквозных методик.
3. `reports/<nosology>/knowledge_base/` и **`reports/<nosology>/full_clinical_dossier.docx`** — модульная база знаний (включая обязательный модуль профиля осложнений лечения), сводное клиническое досье `.docx` и структурированный индекс **`kb_index.json`** формата **`schema_version: "2.0"`**.

**Обязательный контракт `kb_index.json` (`schema_version: "2.0"`):**
- **`frequent_complications`**: непустой массив частых осложнений из когорт `Tier 1–3` (`N >= 20`, медианная частота `frequency_median_num >= 1.0%`), отсортированный по убыванию частоты внутри каждой методики, с полями `modality`, `complication_name`, `event_class`, `clavien_dindo_grade`, `reversibility`, `frequency_pct`, `frequency_median_num`, `sample_size_total`, `time_window`, `anatomical_substrate`, `prevention_and_management`, `evidence_pmids`.
- **`rare_critical_red_flags`**: массив редких критических осложнений (`frequency_max_num < 1.0%`, тяжесть `IIIa–V` или `requires_reoperation` / `permanent_deficit`) с `evidence_pmids`.
- **`clinical_decision_nuances`**: структурированный блок нелинейной клинической логики выбора (без «коробочной» маршрутизации «метод 1 для 1, метод 2 для 2, метод 3 для 3» по стандарту `ru-medical-humanizer v2.0`):
  - `universal_workhorse_modalities` — сквозные конкурирующие методики (`modality`, `applicable_spectrum`, `practical_nuances`, `surgeon_and_equipment_factors`, `patient_tradeoffs`, `evidence_pmids`);
  - `overlapping_indications_and_gray_zones` — сценарии прямого перекрытия показаний (`clinical_scenario`, `competing_modalities` `>= 2` различных методик, `why_no_single_winner`, `decisive_practical_factors`, `evidence_pmids`);
  - `strict_niche_or_salvage_indications` — действительно узкие или резервные (`salvage`) показания (`modality`, `narrow_indication_or_salvage_role`, `why_not_first_line_for_all`, `evidence_pmids`).

Каждый численный тезис в отчете обязан иметь ссылку вида `[Автор, Год; PMID: XXXXXXXX]` или `[NCTXXXXXXXX]`, проверяемую по локальной БД. Обязательная финальная верификация для всех новых нозологий `v2.0`:
- `uv run src/verify_reports.py --nosology <id> --compile-bibliography --verify --schema-version v2`
- `uv run src/universal_schema.py --verify --nosology <id> --schema-version v2`

Архивные нозологии `v1.x` (`prom`, `metroplasty_pregnancy`, `trigger_finger`) остаются полностью работоспособными в read-only режиме обратной совместимости (`--schema-version auto` / `v1`).

### Фаза 4: Интерактивный навигатор (`app.py`)
Веб-интерфейс (Streamlit), подключающийся к `data/<nosology>/literature.db` и папке `reports/<nosology>/`:
- Переключатель нозологий (`v1.x` и `v2.0`) и трех режимов чтения отчета.
- PRISMA-статистика, библиометрические графики и интерактивная таблица `extracted_complications` с выгрузкой в `.csv`.
- Интерактивный фильтр по всем статьям корпуса и извлеченным клиническим/молекулярным таблицам.
- Сравнительный калькулятор исходов, профиль осложнений (`Clavien–Dindo`) и панель клинических компромиссов (`clinical_decision_nuances`).
