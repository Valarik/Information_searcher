# Roadmap: Information Searcher (Контрактура Дюпюитрена 2016–2026)

## Overview

Поэтапная реализация универсального агентского поисковика по нозологиям и создание полного аналитического отчета по контрактуре Дюпюитрена за 2016–2026 гг. в трех форматах (диссертационный обзор, краткое содержание, внутренняя база знаний).

## Phases

- [x] **Phase 1: Сбор корпуса и PRISMA-триаж** - Выгрузка литературы за 2016–2026 гг. из 4 API, дедупликация в SQLite, ранжирование по доказательности и выгрузка открытых полных текстов. (completed 2026-11-04)
- [x] **Phase 2: Роевая структурированная экстракция** - Параллельный разбор корпуса субагентами по 4 тематическим кластерам (этиология/генетика, молекулярный патогенез, консервативное/малоинвазивное лечение, хирургия и отдаленные результаты) с записью в таблицы БД. (completed 2026-11-04)
- [x] **Phase 3: Синтез отчетов в 3 форматах (Humanized)** - Сборка диссертационной работы, краткого аналитического резюме и модульной базы знаний по правилам `ru-medical-humanizer`. (completed 2026-11-04)
- [x] **Phase 4: Интерактивное приложение и верификация** - Разработка веб-витрины (Streamlit) для переключения 3 режимов отчета, фильтрации базы статей, сравнения исходов и подключения новых нозологий. (completed 2026-11-04)

## Phase Details

### Phase 1: Сбор корпуса и PRISMA-триаж

**Goal**: Собрать полный дедуплицированный корпус публикаций и клинических исследований по контрактуре Дюпюитрена за 2016–2026 гг. в локальную БД SQLite с разметкой уровней доказательности (`Tier 1–4`), тематических кластеров и выгрузкой доступных полнотекстовых XML.
**Depends on**: Nothing (first phase)
**Requirements**: [HARV-01, HARV-02, HARV-03, HARV-04]
**Success Criteria** (what must be TRUE):

  1. Скрипт `src/harvester.py` выгружает записи за 2016–2026 гг. из PubMed, Europe PMC, OpenAlex и ClinicalTrials.gov по конфигу `configs/dupuytren.yaml`.
  2. В `data/dupuytren/literature.db` создан дедуплицированный реестр статей и клинических исследований без дублей по PMID/DOI.
  3. Каждой статье присвоен уровень доказательности (`Tier 1–4`) и тематические кластеры; для открытых ключевых статей (`Tier 1–2`) скачаны полнотекстовые XML из Europe PMC.
  4. Сформирован проверяемый PRISMA-отчет `reports/dupuytren/prisma_stats.md` с точной статистикой по годам, типам работ и кластерам.

**Plans**: 2 plans

Plans:
**Wave 1**

- [x] 01-01: Разработка и запуск `src/harvester.py` (выгрузка из PubMed, Europe PMC, OpenAlex, ClinicalTrials.gov в сырой кэш и SQLite)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02: Разработка и запуск `src/triage.py` (дедупликация, классификация `Tier 1–4`, докачка full-text XML из Europe PMC, генерация `prisma_stats.md`)

### Phase 2: Роевая структурированная экстракция

**Goal**: Провести глубокую вычитку ранжированного корпуса параллельными субагентами и заполнить таблицы `extracted_mechanisms` и `extracted_clinical_evidence` конкретными цифрами, выборками, генами, сигнальными путями, осложнениями и частотами рецидивов.
**Depends on**: Phase 1
**Requirements**: [EXTR-01, EXTR-02, EXTR-03, EXTR-04]
**Success Criteria** (what must be TRUE):

  1. Заполнена таблица `extracted_mechanisms` по этиологии, эпидемиологии и генетике (GWAS, Wnt-путь, диабет, алкоголь, курение, вибрация/ручной труд, эпигенетика).
  2. Заполнена таблица `extracted_mechanisms` по клеточному и молекулярному патогенезу (миофибробласты, TGF-β1, механотрансдукция, иммунное микроокружение, матрикс).
  3. Заполнена таблица `extracted_clinical_evidence` по консервативным и малоинвазивным методам (игольная апоневротомия PNF, коллагеназа CCH, лучевая терапия, адалимумаб, физиотерапия/ортезирование).
  4. Заполнена таблица `extracted_clinical_evidence` по хирургическим методам и отдаленным результатам (селективная фасциэктомия, дермофасциэктомия, WALANT, липографтинг, рецидивы на горизонтах 1–10 лет раздельно по ПФС и ПМФС).

**Plans**: 4 plans

Plans:

- [x] 02-01: Экстракция кластера 1 — Этиология, эпидемиология и генетика
- [x] 02-02: Экстракция кластера 2 — Молекулярный и клеточный патогенез
- [x] 02-03: Экстракция кластера 3 — Консервативные и малоинвазивные методы лечения
- [x] 02-04: Экстракция кластера 4 — Хирургическое лечение, осложнения и отдаленные результаты (рецидивы)

### Phase 3: Синтез отчетов в 3 форматах (Humanized)

**Goal**: На основе таблиц базы данных сгенерировать три полных варианта отчета по контрактуре Дюпюитрена с проверкой каждой ссылки по локальной БД и вычиткой по правилам `ru-medical-humanizer`.
**Depends on**: Phase 2
**Requirements**: [SYNT-01, SYNT-02, SYNT-03]
**Success Criteria** (what must be TRUE):

  1. Сформирован фундаментальный отчет диссертационного уровня (`reports/dupuytren/dissertation_report.md`) со всеми 4 главами, сводными таблицами и библиографией.
  2. Сформировано краткое аналитическое содержание (`reports/dupuytren/executive_summary.md`).
  3. Сформирована модульная внутренняя база знаний (`reports/dupuytren/knowledge_base/`).
  4. Проведена автоматическая и редакторская проверка: отсутствие стоп-слов из `ru-medical-humanizer` и 100% валидность всех цитируемых PMID/DOI/NCT.

**Plans**: 3 plans

Plans:

- [x] 03-01: Написание глав 1–2 (Этиология, генетика, патогенез) и глав 3–4 (Подходы к лечению и отдаленные результаты) для режима `dissertation`
- [x] 03-02: Генерация режима `executive_summary` и карточек режима `knowledge_base`
- [x] 03-03: Верификация ссылок по БД и финальный прогон через фильтр `ru-medical-humanizer`

### Phase 4: Интерактивное приложение и верификация

**Goal**: Собрать веб-интерфейс (`app.py`) для чтения отчетов в трех режимах, интерактивного поиска и фильтрации по базе собранной литературы и запуска пайплайна по новым нозологиям.
**Depends on**: Phase 3
**Requirements**: [UI-01]
**Success Criteria** (what must be TRUE):

  1. Приложение `app.py` запускается локально и отображает переключатель 3 режимов отчета, интерактивную PRISMA-статистику, таблицу всех статей с фильтрами и сравнительную матрицу результатов лечения.

**Plans**: 1 plan

Plans:

- [x] 04-01: Разработка и проверка веб-интерфейса `app.py` и документации запуска

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Сбор корпуса и PRISMA-триаж | 2/2 | Complete    | 2026-11-04 |
| 2. Роевая структурированная экстракция | 4/4 | Complete    | 2026-11-04 |
| 3. Синтез отчетов в 3 форматах (Humanized) | 3/3 | Complete    | 2026-11-04 |
| 4. Интерактивное приложение и верификация | 1/1 | Complete    | 2026-11-04 |

---

## Milestone 2: Универсализация платформы и полный цикл по нозологии «Преждевременное излитие околоплодных вод» (`prom`, МКБ-10: `O42`)

- [x] **Phase 5: Полный декаплинг движка и сбор корпуса + PRISMA-триаж по ПИОВ/ПРПО (`configs/prom.yaml`)** — перенос нозологии Дюпюитрена в изолированный архив `archive/dupuytren/`, перевод `src/triage.py`, `src/verify_reports.py`, `src/universal_schema.py` и `app.py` на 100% конфигурационно-зависимую архитектуру, выгрузка литературы за 2016–2026 гг. по ПИОВ/ПРПО в `data/prom/literature.db` и генерация `reports/prom/prisma_stats.md`.
- [x] **Phase 6: Структурированная кластерная экстракция по ПИОВ/ПРПО (`src/extract_prom.py`)** — извлечение количественных патогенетических механизмов (`extracted_mechanisms`) и клинических доказательств (`extracted_clinical_evidence`) по 4 кластерам (этиология/микробиом, молекулярный патогенез/биомаркеры, выжидательная тактика/антибиотики/кортикостероиды/нейропротекция, индукция родов/серкляж/амниоинфузия/исходы) и генерация досье в `data/prom/extractions/`.
- [x] **Phase 7: Синтез отчётов по ПИОВ/ПРПО в 3 форматах (`reports/prom/`) и Zero-Tolerance верификация** — написание диссертационной монографии (`reports/prom/dissertation_report.md`), краткого клинического отчёта (`reports/prom/executive_summary.md`), 5 модулей базы знаний и универсального индекса `reports/prom/knowledge_base/kb_index.json` с прогоном `src/verify_reports.py --nosology prom --compile-bibliography --verify`.
- [x] **Phase 8: Проверка универсального веб-приложения `app.py` на нозологии `prom` и публикация на GitHub** — проверка всех 4 вкладок через `uv run app.py --self-test` и отправка обновлённого универсального приложения в GitHub (`Valarik/Information_searcher`).

---

## Milestone 3: Полный цикл исследования по теме «Клинические случаи метропластики и реконструкции матки во время беременности» (`metroplasty_pregnancy`, МКБ-10: `O34.2 / O71.0 / O71.1 / Q51`)

- [x] **Phase 9: Конфигурация `configs/metroplasty_pregnancy.yaml`, сбор корпуса и PRISMA-триаж (`data/metroplasty_pregnancy/`)** — выгрузка клинических случаев (`Case Reports`), серий наблюдений, когорт и обзоров по антенатальной и интранатальной метропластике во время беременности из `PubMed`, `Europe PMC`, `OpenAlex` и `ClinicalTrials.gov`, дедупликация в `data/metroplasty_pregnancy/literature.db`, загрузка полнотекстовых XML (включая `Tier 4 Case Reports`) и генерация `reports/metroplasty_pregnancy/prisma_stats.md`.
- [x] **Phase 10: Структурированная кластерная экстракция клинических случаев (`src/extract_metroplasty.py`)** — извлечение патоморфологических механизмов дегисценции/ниши/врастания (`extracted_mechanisms`) и клинических параметров операций (`extracted_clinical_evidence`: срок гестации на момент пластики, доступ, техника шва/патча, пролонгирование беременности в неделях, срок и исход родов) с записью 4 досье в `data/metroplasty_pregnancy/extractions/`.
- [x] **Phase 11: Синтез отчётов в 3 форматах (`reports/metroplasty_pregnancy/`) и Zero-Tolerance верификация** — написание диссертационной монографии (`reports/metroplasty_pregnancy/dissertation_report.md`), краткого клинического отчёта (`reports/metroplasty_pregnancy/executive_summary.md`), 5 модулей базы знаний и универсального индекса `reports/metroplasty_pregnancy/knowledge_base/kb_index.json` с прогоном `src/verify_reports.py --nosology metroplasty_pregnancy --compile-bibliography --verify`.
- [x] **Phase 12: Интеграция в универсальное веб-приложение `app.py`, самотестирование и публикация на GitHub** — проверка переключения нозологий (`metroplasty_pregnancy` и `prom`) и всех 4 вкладок через `uv run app.py --self-test` и отправка в `Valarik/Information_searcher`.

---

## Milestone 4: Полный цикл исследования по теме «Болезнь Нотта (стенозирующий лигаментит сгибателей пальцев кисти) с углубленным анализом боли и контрактуры ПМФС до и после операции» (`trigger_finger`, МКБ-10: `M65.3`)

- [x] **Phase 13: Конфигурация `configs/trigger_finger.yaml`, сбор корпуса и PRISMA-триаж (`data/trigger_finger/`)** — выгрузка публикаций из `PubMed`, `Europe PMC`, `OpenAlex` и `ClinicalTrials.gov` за 2010–2026 гг. по болезни Нотта (`trigger finger / stenosing tenosynovitis`), открытой и чрескожной лигаментотомии `A1`, консервативным методам, резекции ножки `FDS`, а также целевой поиск по **до- и послеоперационной боли и ограничению разгибания/движений в проксимальном межфаланговом суставе (ПМФС / PIP joint stiffness, extension deficit, flexion contracture) и феномену спонтанного разрешения через 3–6 месяцев**, дедупликация в `data/trigger_finger/literature.db`, загрузка полнотекстовых XML и генерация `reports/trigger_finger/prisma_stats.md`.
- [x] **Phase 14: Структурированная кластерная экстракция (`src/extract_trigger_finger.py`)** — извлечение патоморфологических и биомеханических механизмов (`extracted_mechanisms`, включая патогенез узла Нотта, трение в области хиазмы Кампера и связки `A2`, ретракцию ладонной пластинки ПМФС и 6-месячный цикл ремоделирования сухожилия после релиза `A1`) и клинических доказательств (`extracted_clinical_evidence`) с генерацией 4 досье в `data/trigger_finger/extractions/`.
- [x] **Phase 15: Синтез отчётов в 3 форматах (`reports/trigger_finger/`) и Zero-Tolerance верификация** — написание диссертационной монографии (`reports/trigger_finger/dissertation_report.md`), краткого клинического отчёта (`reports/trigger_finger/executive_summary.md`), 5 модулей базы знаний и универсального индекса `reports/trigger_finger/knowledge_base/kb_index.json` с отдельным детальным разбором до- и послеоперационной патологии ПМФС, прогоном `src/verify_reports.py --nosology trigger_finger --compile-bibliography --verify`.
- [x] **Phase 16: Интеграция в универсальное веб-приложение `app.py`, самотестирование и публикация на GitHub** — проверка всех нозологий в `app.py --self-test` и отправка в `Valarik/Information_searcher`.

---

## Milestone 5 (`v2.0`): Модернизация движка и скиллов — профиль хирургических осложнений и клиническая де-ИИзация выводов (Engine & Skills Only)

> **Scope constraint:** В рамках Milestone `v2.0` обновляются исключительно код движка (`src/`), универсальная схема данных, автотесты, веб-интерфейс `app.py` и агентские скиллы (`.agent/skills/`) для всех будущих нозологий с сохранением `100%` обратной совместимости с уже собранными папками `v1.x` (`prom`, `metroplasty_pregnancy`, `trigger_finger`).

- [x] **Phase 17: Сбор, PRISMA-триаж и реляционная схема частых осложнений лечения** — поддержка `surgical_focus` и `complications_queries` в `harvester.py`, тег `complications_safety` в `triage.py`, таблица SQLite `extracted_complications` и секция `frequent_complications` в `universal_schema.py`. (completed 2026-11-19)
- [x] **Phase 18: Хуманизация `v2.0` — нелинейная логика клинического выбора и структурный анти-ИИ линтер** — обновление скиллов `ru-medical-humanizer` и `nosology-research-pipeline`, модель сквозных методик и клинических компромиссов (`clinical_decision_nuances`), структурный линтер в `verify_reports.py`. (completed 2026-11-20)
- [x] **Phase 19: Визуализация осложнений и клинических нюансов в `app.py`, экспорт `.docx` и автотесты `v2.0`** — графики `Clavien–Dindo` и витрина перекрывающихся показаний в `app.py`, поддержка таблиц осложнений в `docx_exporter.py` и комплект автотестов `tests/test_v2_engine.py`. (completed 2026-11-22)

### Phase 17: Сбор, PRISMA-триаж и реляционная схема частых осложнений лечения

**Goal**: Научить сборщик, PRISMA-триаж, SQLite-ядро и универсальную схему `kb_index.json` прицельно собирать и структурированно хранить наиболее частые осложнения лечения (в первую очередь хирургических вмешательств) с сохранением 100% обратной совместимости с базами `v1.x`.
**Depends on**: Phase 16
**Requirements**: [COMP-01, COMP-02, COMP-03, COMP-04]
**Success Criteria** (what must be TRUE):

  1. `src/harvester.py` поддерживает флаг `surgical_focus` и блок `complications_queries` в YAML (а при их отсутствии у хирургической нозологии автоматически генерирует подзапрос по интра- и послеоперационным осложнениям для `PubMed` и `Europe PMC`).
  2. `src/triage.py` выделяет тематический тег `complications_safety`, отражает его в `prisma_stats.md` и включает работы по осложнениям в загрузку полнотекстовых XML.
  3. `src/schema.py` и `src/extractor_common.py` создают и обслуживают таблицу `extracted_complications` (`Clavien–Dindo`, частота `%`, обратимость, сроки, анатомическая причина, профилактика и лечение), корректно работая и со старыми базами `v1.x` без падений.
  4. `src/universal_schema.py` валидирует структуру `frequent_complications` в режиме `v2.0` и безопасно обрабатывает ее отсутствие в существующих нозологиях `v1.x`.

**Plans**: 3 plans

Plans:

**Wave 1**

- [x] 17-01: Реляционная схема `extracted_complications`, двойная ось тяжести `Clavien–Dindo` / `CTCAE`, анти-рецидивные парсеры в `extractor_common.py` и агрегация `frequent_complications` в `universal_schema.py` с защитой баз `v1.x`
- [x] 17-02: Гибридный API-сбор осложнений в `harvester.py` и двухконтурный PRISMA-триаж с приоритетной выгрузкой XML `complications_safety` в `triage.py`

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 17-03: Модульные, интеграционные и read-only `v1.x` регрессионные автотесты Фазы 17 (`tests/test_phase17_complications.py`)

### Phase 18: Хуманизация v2.0 — нелинейная логика клинического выбора и структурный анти-ИИ линтер

**Goal**: Убрать из будущих отчетов типичную ИИ-схематичность («этот метод — для 1, этот — для 2, этот — для 3») и перевести синтез на реальную клиническую логику сквозных конкурирующих методик и практических компромиссов с автоматическим контролем в `src/verify_reports.py`.
**Depends on**: Phase 17
**Requirements**: [HUM2-01, HUM2-02, HUM2-03]
**Success Criteria** (what must be TRUE):

  1. `.agent/skills/ru-medical-humanizer/SKILL.md` содержит раздел `v2.0` по архитектуре выводов и клинического выбора: как описывать универсальные («сквозные») методы, перекрывающие весь спектр стадий, и какие практические нюансы определяют выбор в реальной жизни.
  2. `.agent/skills/nosology-research-pipeline/SKILL.md` и `src/universal_schema.py` фиксируют структуру `clinical_decision_nuances` (`universal_workhorse_modalities`, `overlapping_indications_and_gray_zones`, `strict_niche_or_salvage_indications`) и обязательный модуль/главу по осложнениям лечения для всех новых нозологий.
  3. `src/verify_reports.py` включает структурный анти-ИИ линтер (`check_humanizer_v2_structure`): расширенный словарь штампов и клишированных выводов, контроль доли списков с жирным зачином (`- **Заголовок:** ...`) относительно аналитических абзацев и проверку нелинейности заключительной главы для нозологий `v2.0`.

**Plans**: 2 plans

Plans:

**Wave 1**

- [x] 18-01: Обновление скиллов `ru-medical-humanizer` и `nosology-research-pipeline` до `v2.0` и добавление контракта `clinical_decision_nuances` в `src/universal_schema.py`

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 18-02: Структурный анти-ИИ линтер `v2.0` в `src/verify_reports.py` и комплект автотестов `tests/test_phase18_humanizer.py`

### Phase 19: Визуализация осложнений и клинических нюансов в app.py, экспорт .docx и автотесты v2.0

**Goal**: Вывести матрицу и графики хирургических осложнений (`Clavien–Dindo`) и блок перекрывающихся показаний в `app.py` и `.docx`, подтвердив работу движка `v2.0` и обратную совместимость с `v1.x` автоматическими тестами.
**Depends on**: Phase 18
**Requirements**: [UI-02, EXPORT-02]
**Success Criteria** (what must be TRUE):

  1. Во вкладке 2 (`app.py`) отображаются интерактивные диаграммы частых осложнений (частота `%` и распределение по `Clavien–Dindo` в разрезе методик, фильтр обратимых/стойких осложнений) и панель клинических компромиссов (`clinical_decision_nuances`), а во вкладке 3 — таблица `extracted_complications` с поиском и экспортом в `.csv`.
  2. Конфигуратор новой нозологии во вкладке 4 (`app.py`) содержит переключатель хирургического профиля (`surgical_focus`) и автошаблон запросов по осложнениям.
  3. `src/docx_exporter.py` и комплект автотестов (`tests/test_v2_engine.py` + `uv run app.py --self-test`) проходят без единой ошибки как на эталонном наборе данных `v2.0`, так и на всех существующих нозологиях `v1.x`.

**Plans**: 3 plans

Plans:

**Wave 1**

- [x] 19-01: Бэкенд `v2.0` экспорта MS Word (`src/docx_exporter.py`), изоляция `INFO_SEARCHER_ROOT` и нормализация YAML (`src/universal_schema.py`), поддержка 6 модулей в `src/verify_reports.py`

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 19-02: Веб-интерфейс `app.py` `v2.0` — подвкладки `2.5` (`Clavien–Dindo`) и `2.6` (`clinical_decision_nuances`), таблица `extracted_complications` во вкладке 3, конфигуратор `surgical_focus` + `--read-only` аудит во вкладке 4 и расширенный `--self-test`

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 19-03: Комплект сквозных автотестов `tests/test_v2_engine.py` (синтетическая фикстура `v2.0`, OpenXML DOM, `AppTest` 1–4, охрана неизменности 3 замороженных `v1.x` нозологий) и финальный прогон `pytest` + `app.py --self-test`
