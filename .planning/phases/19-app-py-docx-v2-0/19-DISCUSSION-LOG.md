# Phase 19: Визуализация осложнений и клинических нюансов в app.py, экспорт .docx и автотесты v2.0 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-22
**Phase:** 19-app-py-docx-v2-0
**Areas discussed:** Компоновка вкладки 2 (`app.py`), Вкладки 3 и 4 (`app.py`), Экспорт MS Word (`src/docx_exporter.py`), Объём автотестов `v2.0` (`tests/test_v2_engine.py` + `app.py --self-test`)

---

## Area 1: Вкладка 2 (`app.py`) — графики осложнений (`Clavien–Dindo`) и панель `clinical_decision_nuances`

### Q1.1: Как скомпоновать блоки осложнений и `clinical_decision_nuances` во вкладке 2?

| Option | Description | Selected |
|--------|-------------|----------|
| Две отдельные подвкладки 2.5 и 2.6 (Recommended) | `2.5 «Осложнения (Clavien–Dindo)»` и `2.6 «Клинические компромиссы и серые зоны»` отдельно от `2.1–2.4` | ✓ |
| Одна объединённая подвкладка 2.5 | Один длинный экран `2.5 «Осложнения и клинические компромиссы»` | |
| Встроить в существующие 2.3 и 2.4 | Без добавления подвкладок: осложнения в 2.3, компромиссы в 2.4 | |

**User's choice:** Две отдельные подвкладки: `2.5 «Осложнения (Clavien–Dindo)»` и `2.6 «Клинические компромиссы и серые зоны»`.

### Q1.2: Набор визуализаций осложнений и поведение для замороженных нозологий `v1.x`?

| Option | Description | Selected |
|--------|-------------|----------|
| Полный набор графиков + мягкий fallback `v1.x` с таблицей `complications_profile` (Recommended) | Горизонтальный бар частот (`%`) по `Clavien–Dindo` + stacked bar тяжести по методикам + фильтры обратимости и `event_class` + блок «Красные флаги (`<1%`)»; на `v1.x` — мягкий баннер `v1.x` + сводка текстовых `complications_profile` из `modalities` | ✓ |
| Полный набор графиков + нейтральная заглушка `v1.x` | Без дублирования `modalities` на `v1.x` | |
| Минимальный вариант (1 график) + скрытие вкладок на `v1.x` | Только 1 график частот (`%`) и скрытие подвкладок `v2.0` для старых нозологий | |

**User's choice:** Полный набор графиков, фильтры обратимости/`event_class`, блок «Красные флаги (`<1%`)» и мягкий баннер `v1.x` со сводкой текстовых `complications_profile` из `modalities`.

---

## Area 2: Вкладки 3 и 4 (`app.py`) — `extracted_complications`, форма `surgical_focus` и кнопка аудита

### Q2.1: Функциональность 5-й таблицы `extracted_complications` во вкладке 3?

| Option | Description | Selected |
|--------|-------------|----------|
| 5-я опция с полными фильтрами и экспортом `.csv` (Recommended) | Фильтры по методике, `Clavien–Dindo`, обратимости, `event_class`, чекбокс «Редкая казуистика (`Tier 4 / N<20`)», кликабельные PubMed/DOI, поиск и экспорт `.csv` | ✓ |
| 5-я опция только с поиском и `.csv` | Без отдельных фильтров по клиническим шкалам | |

**User's choice:** 5-я опция с полными фильтрами, чекбоксом редкой казуистики, кликабельными ссылками и выгрузкой `.csv`.

### Q2.2: Профиль осложнений в форме новой нозологии (вкладка 4) и режим кнопки перепроверки?

| Option | Description | Selected |
|--------|-------------|----------|
| Переключатель профиля + живой предпросмотр + `--read-only` аудит (Recommended) | Переключатель `surgical_focus` / `treatment_profile`, живой предпросмотр через `harvester.build_complications_queries()`, опциональное ручное переопределение `complications_queries`, выравнивание ключей `openalex_search` / `clinical_trials_condition`, запуск `verify_reports.py` с `--read-only` | ✓ |
| Простой чекбокс + пустые поля без предпросмотра | Без автопредпросмотра и без `--read-only` на кнопке аудита | |

**User's choice:** Переключатель профиля, живой предпросмотр запросов осложнений, выравнивание ключей YAML и перевод кнопки аудита в режим `--read-only`.

---

## Area 3: Экспорт MS Word (`src/docx_exporter.py`)

### Q3.1: Куда включать автогенерируемые таблицы осложнений и `clinical_decision_nuances` из `kb_index.json`?

| Option | Description | Selected |
|--------|-------------|----------|
| Единый генератор приложений в `full_clinical_dossier.docx` и `executive_summary.docx` (Recommended) | `render_v2_kb_appendices_markdown()` добавляется в конец `full_clinical_dossier.docx` и `executive_summary.docx` (одинаково в CLI и `app.py`); `dissertation_report.docx` остаётся без дублирования; `v1.x` без изменений | ✓ |
| Только в `full_clinical_dossier.docx` | `executive_summary.docx` и `dissertation_report.docx` строго из их `.md` | |
| Отдельный 4-й файл `complications_and_nuances_appendix.docx` | Не менять состав существующих 3 файлов | |

**User's choice:** Единый генератор приложений в конец `full_clinical_dossier.docx` и `executive_summary.docx` (в CLI и `app.py`), без дублирования в `dissertation_report.docx` и без изменений вывода `v1.x`.

### Q3.2: Вёрстка широких таблиц осложнений в OpenXML и защита замороженных папок `v1.x`?

| Option | Description | Selected |
|--------|-------------|----------|
| `<w:tblHeader/>` + `<w:cantSplit/>` + мягкая подсветка `IIIb–V` / «Красных флагов» + защита `v1.x` в CLI (Recommended) | Повтор шапки на разрывах страниц, запрет разрыва строк, пастельная заливка критических строк и защита замороженных `v1.x` в CLI | ✓ |
| Только `<w:tblHeader/>` и `<w:cantSplit/>` | Без цветовой подсветки ячеек и защиты CLI | |
| Оставить текущую OpenXML-разметку таблиц | Без изменений в `_build_table_xml` | |

**User's choice:** `<w:tblHeader/>`, `<w:cantSplit/>`, мягкая цветовая подсветка `Clavien–Dindo IIIb–V` / «Красных флагов» и защита замороженных `v1.x` в CLI.

---

## Area 4: Автотесты `v2.0` (`tests/test_v2_engine.py` + `app.py --self-test`)

### Q4.1: Объём покрытия автотестами Фазы 19?

| Option | Description | Selected |
|--------|-------------|----------|
| Полный E2E `v2.0` + регрессия неизменности 3 замороженных `v1.x` + расширенный `app.py --self-test` (Recommended) | Временная синтетическая фикстура `v2.0` через весь цикл (`SQLite -> агрегация -> kb_index -> verify_reports v2 -> docx_exporter OpenXML -> Streamlit AppTest 1–4`) + регрессия и sha256/mtime-проверка 3 `v1.x` нозологий + расширение `app.py --self-test` на `2.5`/`2.6` и `extracted_complications` | ✓ |
| Только модульные тесты + текущий `--self-test` | Без сквозного E2E-контура | |

**User's choice:** Полный сквозной E2E-тест `v2.0`, регрессия неизменности всех 3 замороженных `v1.x` нозологий и расширение `app.py --self-test`.
