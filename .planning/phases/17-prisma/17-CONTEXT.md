# Phase 17: Сбор, PRISMA-триаж и реляционная схема частых осложнений лечения - Context

**Gathered:** 2026-11-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Модернизация ядра сбора, PRISMA-скрининга, SQLite-экстракции и универсальной JSON-схемы (`src/harvester.py`, `src/triage.py`, `src/schema.py`, `src/extractor_common.py`, `src/universal_schema.py`) для прицельной выгрузки, стратификации и хранения профиля наиболее частых осложнений лечения (в первую очередь хирургических и инвазивных вмешательств) для всех будущих нозологий `v2.0`. Существующие собранные нозологии `v1.x` (`prom`, `metroplasty_pregnancy`, `trigger_finger`) не пересобираются и обязаны продолжать открываться со 100% обратной совместимостью. Визуализация осложнений в `app.py` и рендеринг новых секций в `.docx` относятся к Phase 19, а структурный анти-ИИ линтер и правила нелинейных выводов — к Phase 18.

</domain>

<decisions>
## Implementation Decisions

### Генерация API-запросов и сбор корпуса по осложнениям (`harvester.py` & `configs/<id>.yaml`)
- **D-01:** Отдельный поисковый проход по осложнениям лечения в `src/harvester.py` включен **по умолчанию** для хирургических и смешанных (консервативно-хирургических) нозологий (`surgical_focus: true` по умолчанию / `treatment_profile: surgical | mixed`). Если в конфиге явно указан чисто терапевтический профиль (`surgical_focus: false` / `treatment_profile: conservative`), сборщик автоматически переключается на поисковый блок нежелательных лекарственных/консервативных явлений (`adverse effects / drug-related side effects`).
- **D-02:** Используется **гибридная сборка запросов**: если в `configs/<id>.yaml` задан блок `complications_queries` (`pubmed`, `europepmc`), `harvester.py` выполняет запросы из него (для захвата специфических осложнений конкретной операции); если блок отсутствует, `harvester.py` автоматически строит запрос из `core_terms` / `mesh_terms` нозологии в пересечении со стандартным хирургическим блоком осложнений (`"Postoperative Complications"[MeSH] OR "Intraoperative Complications"[MeSH] OR "iatrogenic"[tiab] OR "complication rate"[tiab] OR "adverse effects"[Subheading]` и аналогичным фильтром для `Europe PMC` в границах `date_range`).
- **D-03:** Выгрузка прицельного прохода кэшируется в отдельные файлы `data/<id>/raw/pubmed_complications.json` и `data/<id>/raw/europepmc_complications.json`, после чего дедуплицируется в общую таблицу `articles` (по `PMID -> DOI -> norm_title`) с добавлением маркеров провенанса `PubMed:Complications` и `EuropePMC:Complications` в JSON-массив `articles.sources`.

### PRISMA-триаж частых осложнений против казуистики (`triage.py`)
- **D-04:** Вводится **двухконтурный учет** частоты и казуистики: количественные показатели «наиболее частых» осложнений (`%`) извлекаются строго из выборок `N >= 20` (мета-анализы, РКИ, регистры и когорты `evidence_tier IN (1, 2, 3)`), тогда как единичные клинические наблюдения (`Tier 4 Case Reports`, `N < 20`) маркируются отдельно как редкая хирургическая казуистика (`rare_catastrophic_case`, ориентир `< 0.5%`), чтобы не искажать частотный профиль рутинных вмешательств.
- **D-05:** Кластерный тег `complications_safety` в `articles.clusters` (с отдельным отображением в `reports/<id>/prisma_stats.md`) присваивается комбинированно: (а) всем включенным статьям с провенансом `PubMed:Complications` / `EuropePMC:Complications`, (б) статьям, совпавшим со встроенным универсальным хирургическим/терапевтическим словарем осложнений в `src/triage.py`, и (в) статьям, совпавшим со специфическими терминами осложнений из `configs/<id>.yaml` (`triage_rules.complication_terms` и `triage_rules.rare_complication_terms`).
- **D-06:** При скачивании открытых полнотекстовых XML из `Europe PMC` статьи `Tier 1–3` с кластерным тегом `complications_safety` получают повышенный приоритет очереди выгрузки, поскольку таблицы мелких и частых послеоперационных осложнений в `%` обычно находятся в разделе `Results` полного текста, а не в абстракте.

### Реляционная схема `extracted_complications` и агрегация `frequent_complications` (`schema.py`, `extractor_common.py`, `universal_schema.py`)
- **D-07:** В таблице SQLite `extracted_complications` тяжесть кодируется по **двойной оси**: (1) универсальный хирургический стандарт `clavien_dindo_grade` (`I`, `II`, `IIIa`, `IIIb`, `IV`, `V`; для чисто консервативных модальностей — с маппингом `CTCAE Grade 1–5`) и (2) клиническая обратимость `reversibility` (`transient_self_limiting` — транзиторное самокупирующееся, `requires_conservative_therapy` — требует консервативного лечения/реабилитации, `requires_reoperation` — требует повторной операции/ревизии, `permanent_deficit` — стойкий функциональный или анатомический дефицит).
- **D-08:** Поле `event_class` разделяет записи на `true_complication` (инфекция, гематома, несостоятельность шва, КРБС, ятрогенная травма нерва/сосуда/связки/органа) и `transient_postop_sequela` (ожидаемые временные состояния послеоперационного ремоделирования — рубцовая болезненность, отек, преходящая тугоподвижность с фиксацией типичного срока разрешения в `time_window`). Рецидивы болезни и технически неполный релиз в `extracted_complications` не дублируются и остаются строго в контуре рецидивов/реинтервенций (`extracted_clinical_evidence` и поля `recurrence_*` в `modalities`).
- **D-09:** В `src/universal_schema.py` контракт `kb_index.json` (`schema_version: "2.0"`) включает основной массив `frequent_complications` (события с частотой `>= 1.0%` из когорт `Tier 1–3` при `N >= 20`, отсортированные по убыванию медианы частоты `frequency_median_num` в разрезе каждой лечебной модальности) и отдельный подблок `rare_critical_red_flags` (`< 1.0%`, тяжелые ятрогенные повреждения нервов, магистральных сосудов, сухожилий или полых органов). Для всех ранее собранных баз и отчетов `v1.x` гарантируется безошибочный fallback-режим (проверка существования таблицы `extracted_complications` через `sqlite_master` и мягкая обратная совместимость при отсутствии ключей `v2.0`).

### the agent's Discretion
- Точные имена вспомогательных хелперов и регулярных выражений в `src/extractor_common.py` для парсинга процентов частоты осложнений (`n/N (%)`), классов `Clavien–Dindo` и окон разрешения (`time_window`) из JATS XML и абстрактов.
- Точный лимит `retmax` / `pageSize` для дополнительного прохода осложнений в `src/harvester.py` (в разумных пределах API-квот, сопоставимо с основным проходом).
- Правила дедупликации и расчета медианы/диапазона (`min–max %`) при динамической сборке `frequent_complications` из SQLite в `build_dynamic_fallback_kb()` внутри `src/universal_schema.py`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Планирование и требования Milestone v2.0
- `.planning/PROJECT.md` — Глобальные ограничения проекта и граница `Engine & Skills Only` (запрет пересборки готовых нозологий `v1.x`).
- `.planning/REQUIREMENTS.md` — Требования `COMP-01`, `COMP-02`, `COMP-03`, `COMP-04` и матрица трассируемости Phase 17.
- `.planning/ROADMAP.md` — Цель и 4 критерия приемки (`Success Criteria`) для Phase 17.

### Кодовая база ядра пайплайна (объекты модификации Phase 17)
- `src/harvester.py` — Текущая логика опроса `PubMed`, `Europe PMC`, `OpenAlex`, `ClinicalTrials.gov` и дедупликации в `articles` (с мержем JSON-поля `sources`).
- `src/triage.py` — PRISMA-скрининг, классификация `Tier 1–4`, присвоение кластерных тегов, очередь загрузки Europe PMC Full-Text XML и генерация `prisma_stats.md`.
- `src/schema.py` — Инициализация таблиц SQLite (`articles`, `clinical_trials`, `extracted_clinical_evidence`, `extracted_mechanisms`), куда добавляется `extracted_complications`.
- `src/extractor_common.py` — Общие утилиты подключения к SQLite, парсинга JATS XML (`parse_jats_xml`), извлечения размера выборки (`extract_sample_size`) и статистических метрик.
- `src/universal_schema.py` — Валидатор `kb_index.json`, чтение метрик корпуса `get_sqlite_corpus_stats()` и динамический fallback-билдер `build_dynamic_fallback_kb()`.

### Примеры конфигураций и эталонных данных `v1.x` (для контроля обратной совместимости)
- `configs/trigger_finger.yaml` — Пример хирургической конфигурации `v1.x` с блоком `triage_rules.rare_complication_terms`.
- `configs/prom.yaml` — Пример акушерской консервативно-инвазивной конфигурации `v1.x`.
- `configs/metroplasty_pregnancy.yaml` — Пример хирургической конфигурации `v1.x` с приоритетом клинических случаев (`prioritize_case_reports: true`).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `upsert_article()` в `src/harvester.py`: уже умеет дедуплицировать статьи по каскаду `PMID -> DOI -> norm_title` и объединять массив `sources` без потери ранее найденных метаданных — идеально переиспользуется для прохода `PubMed:Complications` и `EuropePMC:Complications`.
- `download_fulltext_xmls()` в `src/triage.py`: уже скачивает полнотекстовые JATS XML через `ThreadPoolExecutor(max_workers=8)` для `evidence_tier IN (1, 2, 3)`; достаточно расширить `ORDER BY` приоритетом наличия `complications_safety` в `clusters` и `sources`.
- `parse_jats_xml()` и `extract_sample_size()` в `src/extractor_common.py`: готовы для извлечения текста секций/таблиц JATS XML и проверки порога `N >= 20` при разделении когортных частых осложнений и казуистики.

### Established Patterns
- Все скрипты в `src/` содержат inline-метаданные PEP 723 (`# /// script`) для запуска через `uv run` без глобального `pyproject.toml`.
- `get_sqlite_corpus_stats()` в `src/universal_schema.py` вызывается при рендеринге любой нозологии в `app.py` (включая старые базы `data/prom/literature.db`, `data/metroplasty_pregnancy/literature.db`, `data/trigger_finger/literature.db`), поэтому запросы к новой таблице `extracted_complications` обязаны проверять ее наличие через `sqlite_master` (либо возвращать `0`), не модифицируя файлы `v1.x` при чтении.

### Integration Points
- `configs/<id>.yaml` -> `src/harvester.py` (чтение `surgical_focus` / `treatment_profile` и `complications_queries`).
- `articles.sources` -> `src/triage.py` (распознавание прицельного прохода осложнений, проставление `complications_safety` и запись строки в раздел тематических кластеров `prisma_stats.md`).
- `src/schema.py` & `src/extractor_common.py` -> таблица `extracted_complications` -> агрегация в `kb_index.json` (`frequent_complications` и `rare_critical_red_flags`) в `src/universal_schema.py`, которую затем будут читать `verify_reports.py` (Phase 18) и `app.py` / `docx_exporter.py` (Phase 19).

</code_context>

<specifics>
## Specific Ideas

- Акцент пользователя на реальной хирургической практике: частые послеоперационные явления (такие как рубцовая болезненность, локальный отек или транзиторная тугоподвижность сустава до 3–6 месяцев после лигаментотомии) не должны ни теряться, ни смешиваться с истинными ятрогенными катастрофами или рецидивами основного заболевания — отсюда разделение `event_class` (`true_complication` vs `transient_postop_sequela`) и двойная шкала `Clavien–Dindo` + `reversibility`.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 17-prisma*
*Context gathered: 2026-11-17*
