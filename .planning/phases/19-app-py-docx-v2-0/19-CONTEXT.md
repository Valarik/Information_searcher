# Phase 19: Визуализация осложнений и клинических нюансов в app.py, экспорт .docx и автотесты v2.0 - Context

**Gathered:** 2026-11-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Вывод профиля частых хирургических/терапевтических осложнений (`Clavien–Dindo`, частота `%`, обратимость, «красные флаги») и матрицы нелинейного клинического выбора (`clinical_decision_nuances`) в веб-приложении `app.py` (вкладки 2, 3, 4) и экспортере MS Word `src/docx_exporter.py`, а также сквозная верификация всего движка `v2.0` комплектом автотестов (`tests/test_v2_engine.py` + расширенный `uv run app.py --self-test`). Все 3 замороженные нозологии `v1.x` (`prom`, `metroplasty_pregnancy`, `trigger_finger`) остаются полностью неизменными на диске и обязаны открываться и экспортироваться со `100%` обратной совместимостью.

</domain>

<decisions>
## Implementation Decisions

### Вкладка 2 (`app.py`): подвкладки `2.5 Осложнения (Clavien–Dindo)` и `2.6 Клинические компромиссы и серые зоны`
- **D-01:** Во вкладке 2 (`render_tab_clinical_matrix`) добавляются **две отдельные подвкладки** к существующим `2.1–2.4`:
  - `2.5 «⚠️ Осложнения (Clavien–Dindo)»`
  - `2.6 «🧭 Клинические компромиссы и серые зоны»`
  Существующие подвкладки `2.1–2.4` не перегружаются. Дополнительно: подпись Режима В во вкладке 1 показывает динамическое число модулей `len(kb_modules)` (в `v2.0` их 6, включая `06_complications_and_safety.md`), а в сайдбаре выводится метрика `Строк осложнений` при `extracted_complications_rows > 0` или `schema_version == "2.0"`.
- **D-02:** Подвкладка `2.5` для нозологий `v2.0` включает:
  1. Интерактивные фильтры: методики (`multiselect`), тяжесть `clavien_dindo_grade` (`I`, `II`, `IIIa`, `IIIb`, `IV`, `V`), обратимость (`reversibility`) и класс события (`event_class`: `true_complication` vs `transient_postop_sequela`).
  2. Два интерактивных графика Plotly: (а) горизонтальный bar chart медианных частот (`frequency_median_num`, `%`) с цветовой кодировкой по `Clavien–Dindo` (и переключением цвета на `reversibility`) и подробным hover (`frequency_pct`, `time_window`, `sample_size_total`, `evidence_pmids`); (б) stacked bar chart распределения осложнений по классам `Clavien–Dindo` (`I–V`) в разрезе лечебных методик.
  3. Отфильтрованную таблицу `frequent_complications` (методика, осложнение, класс события, `Clavien–Dindo`, частота `%`, обратимость, окно разрешения `time_window`, анатомический субстрат, профилактика и лечение, выборка `N`, `PMID`) с кнопкой экспорта `.csv`.
  4. Отдельный визуально выделенный блок **«Красные флаги: редкие критические осложнения (<1%)»** (`rare_critical_red_flags`).
  5. **Fallback для замороженных нозологий `v1.x`:** при отсутствии/пустоте `frequent_complications` выводится мягкий информационный баннер `v1.x` и сводная таблица текстовых полей `complications_profile` из `modalities` (без ошибок и без записи на диск).
- **D-03:** Подвкладка `2.6` для нозологий `v2.0` визуализирует `clinical_decision_nuances` тремя блоками:
  1. **Сквозные методики («рабочие лошадки»)** (`universal_workhorse_modalities`): покрываемый спектр стадий (`applicable_spectrum`), практические нюансы (`practical_nuances`), факторы опыта хирурга и оснащения (`surgeon_and_equipment_factors`), компромиссы для пациента (`patient_tradeoffs`), `evidence_pmids`.
  2. **Перекрывающиеся показания и «серые зоны»** (`overlapping_indications_and_gray_zones`): клинический сценарий (`clinical_scenario`), конкурирующие методики (`competing_modalities`), почему нет одного «победителя» (`why_no_single_winner`), решающие практические факторы (`decisive_practical_factors`), `evidence_pmids`.
  3. **Узконишевые показания и методики спасения** (`strict_niche_or_salvage_indications`, отображается при наличии записей): роль (`narrow_indication_or_salvage_role`), почему не первая линия (`why_not_first_line_for_all`), `evidence_pmids`.
  4. **Fallback для `v1.x`:** информационный баннер `v1.x` со ссылкой на подвкладку `2.4` («Бок-о-бок сравнение методик»).

### Вкладки 3 и 4 (`app.py`): навигатор `extracted_complications`, форма `surgical_focus` и read-only аудит
- **D-04:** Вкладка 3 (`render_tab_prisma_explorer`) получает **5-ю опцию** радио-переключателя: `5. Извлечённые осложнения лечения (extracted_complications)` через кэшированную функцию `universal_schema.query_complications_df(db_path, include_casuistry=...)`. Внутри:
  - фильтры по методике (`modality`), `clavien_dindo_grade`, обратимости (`reversibility`), классу события (`event_class`);
  - чекбокс «Показать редкую казуистику (`Tier 4 / N<20`)»;
  - текстовый поиск по названию осложнения, анатомическому субстрату и профилактике/лечению;
  - кликабельные столбцы `PubMed` / `DOI` (`LinkColumn`) и кнопка скачивания `.csv` (`utf-8-sig`).
  На базах `v1.x` без таблицы `extracted_complications` отображается спокойное информационное сообщение (0 записей) в строго read-only режиме.
- **D-05:** Вкладка 4 (`render_tab_configurator_and_audit`):
  1. В форме создания новой нозологии (`new_nosology_form`) добавляется переключатель клинического профиля: **«Хирургическая / смешанная (`surgical_focus: true`)»** vs **«Чисто консервативная (`surgical_focus: false`, `treatment_profile: conservative`)»**.
  2. На основе введённых терминов и выбранного профиля показывается **живой предпросмотр автогенерируемого запроса осложнений** (через `harvester.build_complications_queries()`), плюс два необязательных текстовых поля для ручного переопределения `complications_queries.pubmed` и `complications_queries.europepmc`.
  3. Выравниваются ключи сохраняемого YAML в `save_new_nosology_config()`: `queries.openalex_search` и `queries.clinical_trials_condition` (в соответствии с `src/harvester.py` вместо старых `openalex` / `clinicaltrials`).
  4. Кнопка перезапуска аудита (`verify_reports.py`) запускает проверку строго с флагом **`--read-only`** (`--nosology <id> --verify --read-only`), предотвращая случайную перезапись `verification_audit.md` у замороженных нозологий `v1.x`.

### Экспорт MS Word (`src/docx_exporter.py`)
- **D-06:** В `src/docx_exporter.py` добавляется единый публичный генератор структурированных Markdown-приложений `render_v2_kb_appendices_markdown(kb_index)` (и вспомогательные функции сборки секций `build_executive_docx_bytes(exec_md, kb_index)` / `build_full_dossier_docx_bytes(exec_md, diss_md, kb_modules_md, kb_index)`), который для нозологий `v2.0` (при `schema_version == "2.0"` или непустых `frequent_complications` / `clinical_decision_nuances`) формирует:
  - структурированную таблицу частых осложнений (`Clavien–Dindo`, медиана и диапазон `%`, класс события, обратимость и сроки, анатомический субстрат, профилактика и лечение, `PMID`) + отдельный подблок `rare_critical_red_flags`;
  - структурированную матрицу `clinical_decision_nuances` (сквозные методики, перекрывающиеся показания и «серые зоны», узконишевые/спасательные методики с `PMID`).
  Эти приложения автоматически добавляются в конец **`full_clinical_dossier.docx`** и **`executive_summary.docx`** — единым кодом как в CLI (`export_nosology_docx_files()`), так и в кнопках скачивания `app.py`. Файл **`dissertation_report.docx`** остаётся чистым рендером `dissertation_report.md` без дублирования глав. Для нозологий `v1.x` вывод всех трёх `.docx` остаётся `100%` идентичным `v1.x`.
- **D-07:** Улучшение OpenXML-вёрстки таблиц в `src/docx_exporter.py` и защита `v1.x`:
  1. Строке заголовка каждой таблицы добавляется `<w:tblHeader/>` (автоповтор шапки при переносе на новую страницу), каждой строке — `<w:cantSplit/>` (запрет разрыва строки пополам).
  2. Для ячеек/строк с критической тяжестью `Clavien–Dindo IIIb / IV / V` и подблока «Красных флагов» применяется мягкая академическая заливка (`<w:shd w:fill="..."/>` — пастельно-красный/янтарный фон с контрастным тёмным текстом).
  3. В `export_nosology_docx_files()` (при записи в корневой `reports/<id>` проекта) добавляется защита замороженных нозологий `v1.x` (`prom`, `metroplasty_pregnancy`, `trigger_finger`): перезапись блокируется без явного `allow_frozen_overwrite=True` / CLI-флага `--allow-frozen-overwrite` (in-memory генерация в `app.py` и экспорт во временный `base_dir` в тестах работают без ограничений).

### Автотесты `v2.0` и самотестирование (`tests/test_v2_engine.py` + `app.py --self-test`)
- **D-08:** Финальный тестовый контур Фазы 19 включает:
  1. **`tests/test_v2_engine.py` (E2E `v2.0`):** временная синтетическая нозология `v2.0` (`tmp_path`), проходящая полный цикл: конфиг с `surgical_focus: true` -> `harvester.build_complications_queries()` -> SQLite (`articles`, `extracted_complications`, `extracted_clinical_evidence`, `extracted_mechanisms`, `clinical_trials`) -> `aggregate_complications_from_sqlite()` -> `kb_index.json v2.0` + `dissertation_report.md` + `executive_summary.md` + 6 модулей БЗ -> `verify_reports` (`--schema-version v2 --read-only`) -> `docx_exporter` с разбором `word/document.xml` (проверка `<w:tblHeader/>`, `<w:cantSplit/>`, подсветки `IIIb–V`, наличия таблиц осложнений и `clinical_decision_nuances`) -> `Streamlit AppTest` с рендерингом вкладок 1–4, включая подвкладки `2.5` и `2.6`, таблицу `extracted_complications` во вкладке 3 и форму `surgical_focus` во вкладке 4.
  2. **`tests/test_v2_engine.py` (Регрессия и неизменность `v1.x`):** прогон всех 3 замороженных нозологий (`prom`, `metroplasty_pregnancy`, `trigger_finger`) через `load_nosology_bundle`, `query_complications_df`, `verify_universal_schema`, in-memory `docx_exporter`, защиту `export_nosology_docx_files` от перезаписи `v1.x` и `Streamlit AppTest` с проверкой контрольного снимка файлов (sha256/mtime) до и после тестов.
  3. **Расширенный `uv run app.py --self-test`:** проверяет рендеринг новых подвкладок `2.5` и `2.6`, 5-ю таблицу `extracted_complications` во вкладке 3 и `0` исключений `AppTest` на всех обнаруженных нозологиях.

### the agent's Discretion
- Точная цветовая палитра Plotly для классов `Clavien–Dindo` (`I` -> зелёный/бирюзовый, `II` -> синий, `IIIa` -> янтарный, `IIIb` -> оранжевый, `IV` -> красный, `V` -> тёмно-бордовый) и пастельных заливок OpenXML `<w:shd>` в `src/docx_exporter.py`.
- Точные русские подписи (display labels) для enum-значений `reversibility` (`transient_self_limiting`, `requires_conservative_therapy`, `requires_reoperation`, `permanent_deficit`) и `event_class` (`true_complication`, `transient_postop_sequela`) в фильтрах, таблицах `app.py` и `.docx`.
- Чистка устаревшего параметра Streamlit `use_container_width=True` -> `width="stretch"` (если поддерживается текущей версией Streamlit в `uv`-окружении без ломки `AppTest`) для устранения предупреждений в консоли.
- Имена вспомогательных функций внутри `app.py` и `src/docx_exporter.py` при условии сохранения обратной совместимости публичных сигнатур `build_docx_bytes_from_markdown`, `build_docx_bytes_from_markdown_sections`, `export_nosology_docx_files`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Планирование и требования Milestone v2.0
- `.planning/PROJECT.md` — Глобальные ограничения проекта и граница `Engine & Skills Only`.
- `.planning/REQUIREMENTS.md` — Требования `UI-02`, `EXPORT-02` и матрица трассируемости Phase 19.
- `.planning/ROADMAP.md` — Цель и 3 критерия приемки (`Success Criteria`) для Phase 19.
- `.planning/phases/17-prisma/17-CONTEXT.md` — Зафиксированные решения `D-01..D-09` Фазы 17 (контракт `extracted_complications`, `frequent_complications`, `rare_critical_red_flags`, `surgical_focus`).
- `.planning/phases/18-v2-0/18-VERIFICATION.md` — Подтверждённый контракт `clinical_decision_nuances` и `verify_reports.py --schema-version v2 --read-only`.

### Объекты модификации и интеграции Phase 19
- `app.py` — Основное Streamlit-приложение (сайдбар, вкладки 1–4, `run_self_test()`).
- `src/docx_exporter.py` — Чистый OpenXML-генератор `.docx` (парсер Markdown-таблиц, `build_docx_bytes_from_markdown_sections`, `export_nosology_docx_files`).
- `src/universal_schema.py` — Источник `query_complications_df()`, `aggregate_complications_from_sqlite()`, `validate_kb_v2()`, `save_new_nosology_config()`, `get_sqlite_corpus_stats()`.
- `src/harvester.py` — Источник `build_complications_queries()` и `resolve_treatment_profile()` для предпросмотра запросов в форме вкладки 4.
- `src/verify_reports.py` — Поддержка `--read-only` и `--schema-version {auto,v1,v2}` для кнопки аудита во вкладке 4 и E2E-теста.
- `tests/test_phase17_complications.py` и `tests/test_phase18_humanizer.py` — Существующие паттерны фикстур `v2.0` и read-only регрессий `v1.x`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `query_complications_df(db_path, include_casuistry=True)` в `src/universal_schema.py`: уже возвращает готовый `pd.DataFrame` с `pubmed_url` / `doi_url` и безопасным read-only возвратом пустого `DataFrame` для баз `v1.x` без таблицы `extracted_complications`.
- `build_complications_queries(config)` и `resolve_treatment_profile(config)` в `src/harvester.py`: уже реализованы и протестированы в Фазе 17 — могут вызываться напрямую во вкладке 4 для живого предпросмотра запросов осложнений.
- `save_new_nosology_config(payload)` в `src/universal_schema.py`: уже нормализует `surgical_focus`, `treatment_profile`, `complications_queries` и валидирует `nosology_id` против path traversal.
- `get_sqlite_corpus_stats(db_path)` в `src/universal_schema.py`: уже возвращает `extracted_complications_rows` (с `sqlite_master` защитой для `v1.x`).
- `_build_table_xml()` в `src/docx_exporter.py`: централизованная функция генерации OpenXML-таблиц — добавление `<w:tblHeader/>`, `<w:cantSplit/>` и условного `<w:shd>` делается в одном месте и автоматически валидируется через `ET.fromstring()` перед упаковкой в `.docx`.

### Established Patterns
- Все кэшируемые запросы в `app.py` обёрнуты в `@st.cache_data(show_spinner=False)` с передачей `str(db_path)` (а не `Path`) для стабильного кэширования Streamlit.
- `app.py --self-test` запускает `streamlit.testing.v1.AppTest.from_file("app.py", default_timeout=45)` и проверяет `assert not at.exception` после переключения режимов и виджетов.
- Тесты в `tests/` используют `tmp_path`, не требуют сетевого доступа и запускаются через `uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore pytest tests/ -v`.

### Integration Points
- `app.py` (Tab 4 form) -> `src/harvester.py:build_complications_queries()` (предпросмотр) -> `src/universal_schema.py:save_new_nosology_config()` (запись `configs/<id>.yaml`).
- `app.py` (Tab 1 / Sidebar download buttons) & CLI `src/docx_exporter.py` -> единые функции сборки `executive_summary.docx` и `full_clinical_dossier.docx` с приложениями `v2.0` из `kb_index.json`.
- `app.py` (Tab 4 audit button) -> `subprocess.run([sys.executable, "src/verify_reports.py", "--nosology", nos_id, "--verify", "--read-only"])`.

</code_context>

<specifics>
## Specific Ideas

- В подвкладке `2.5` важно наглядно отличать ожидаемые временные послеоперационные явления (`transient_postop_sequela`, например преходящая тугоподвижность или рубцовая болезненность с указанием `time_window`) от истинных осложнений (`true_complication`) и редких катастроф (`rare_critical_red_flags` < 1%), чтобы хирург видел реальный профиль риска, а не смесь рецидивов и казуистики.
- В подвкладке `2.6` акцент на реальную клиническую практику: несколько конкурирующих методик могут быть применимы к одному и тому же спектру стадий (`universal_workhorse_modalities`), а решающими оказываются оснащение, кривая обучения, профиль осложнений и приоритеты пациента (`overlapping_indications_and_gray_zones`).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 19-app-py-docx-v2-0*
*Context gathered: 2026-11-22*
