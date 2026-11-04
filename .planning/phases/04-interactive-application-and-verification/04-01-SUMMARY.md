---
phase: 04-interactive-application-and-verification
plan: 01
subsystem: ui-application-and-universal-schema
tags: [streamlit, plotly, sqlite, universal-schema, export-html-csv, verification]
requires:
  - 03-multi-mode-synthesis
provides:
  - src/universal_schema.py
  - reports/dupuytren/knowledge_base/kb_index.json
  - app.py
  - README.md
affects:
  - UI-01
tech-stack:
  added: [streamlit, plotly, markdown, pandas, pyyaml]
  patterns: [Universal Nosology-Agnostic Schema, 4-Tab Streamlit Dashboard, Print-Ready HTML & UTF-8-SIG CSV Export, Streamlit AppTest Headless Verification]
key-files:
  created:
    - src/universal_schema.py
    - app.py
    - README.md
  modified:
    - reports/dupuytren/knowledge_base/kb_index.json
key-decisions:
  - "D-01: Унифицированная нозологически-независимая схема клинических данных (стадии, подтипы/локализации, факторы риска/протекции, фазы патогенеза, естественное течение и сравнение методик по первичной эффективности, 5-летней ремиссии, истинному рецидиву 1–10 лет и процедиву)"
  - "D-02: Четыре универсальные вкладки в app.py (1: 3 режима отчётов, 2: Клиническая матрица и компаратор методик, 3: SQLite PRISMA-навигатор по 1775 статьям / 1213 клин. записям / 1062 механизмам / 80 РКИ, 4: Аудит верификации и YAML-конфигуратор новых нозологий)"
  - "D-03: Экспорт любого отчёта в .md и печатный .html (под PDF/Word) и выгрузка любых отфильтрованных таблиц в .csv (UTF-8 with BOM для Excel)"
requirements-completed:
  - UI-01
duration: 15m
completed: 2026-11-04
---

# Phase 04 Plan 01 Summary: Universal Multi-Nosology Web Application (`app.py`) & Verification

## What Was Built

1. **Универсальная нозологически-независимая схема (`reports/dupuytren/knowledge_base/kb_index.json` и `src/universal_schema.py`, `D-01`):**
   - Расширен индекс базы знаний `kb_index.json` до полной универсальной схемы:
     - `nosology_meta` (МКБ-10 `M72.0`, МКБ-11 `FB51.0`, горизонт 2016–2026, живая статистика PRISMA-корпуса);
     - `staging_and_classification` (5 стадий `Tubiana N, I–IV` с сопоставлением популяционной доли и доли в потоке хирургии кисти, а также темпом естественного прогрессирования);
     - `anatomical_or_subtype_distribution` (5 лучей кисти `IV > V > III > I > II` + 2 суставных уровня `ПФС vs ПМФС`);
     - `etiology_and_risk_factors` (7 ключевых факторов риска `↑` и протективных модификаторов `↓`, включая парадокс ИМТ и шкалу диатеза `Abe`);
     - `pathogenesis_phases` (3 фазы патогенеза с клеточными событиями, клиническими коррелятами и терапевтическими окнами);
     - `natural_history_and_dynamics` и `modalities` (13 методик лечения со стандартизованными метриками: первичная эффективность, 5-летняя ремиссия, истинный рецидив на 1–2, 3, 5 и 10 годах, рецидив по подтипам, **процедив / распространение болезни**, повторные вмешательства, осложнения, реабилитация, **плюсы** и **минусы**).
   - Модуль `src/universal_schema.py` автоматически сканирует `configs/*.yaml`, подгружает пакет нозологии (включая динамический фоллбэк из SQLite для новых нозологий) и формирует печатный HTML (`render_printable_html`) и CSV с BOM (`dataframe_to_csv_bytes`).

2. **Интерактивное веб-приложение `app.py` на Streamlit (`UI-01`, `D-02`, `D-03`):**
   - **Боковая панель:** выбор нозологии из `configs/*.yaml`, сводные метрики доказательной базы и быстрые кнопки скачивания отчётов в `.md` и `.html`.
   - **Вкладка 1 (Аналитические отчёты — 3 режима):** чтение и навигация по главам Диссертационной монографии, Краткого клинического отчёта и 5 модулей Базы знаний с поиском терминов и экспортом в `.md` / `.html`.
   - **Вкладка 2 (Унифицированная клиническая аналитика):** 4 подвкладки с интерактивными графиками Plotly (структура стадий, ранжирование локализаций, 5-летняя ремиссия против истинного рецидива и процедива, кривые накопления рецидивов 1–10 лет, бок-о-бок компаратор 2–4 методик и привязка к первичным записям `extracted_clinical_evidence`).
   - **Вкладка 3 (База литературы и PRISMA-навигатор):** поиск и фильтрация по 1 775 включённым статьям, 1 213 клиническим записям, 1 062 механизмам и 80 протоколам `ClinicalTrials.gov` с прямыми ссылками `PubMed / DOI / NCT` и выгрузкой в `.csv`.
   - **Вкладка 4 (Аудит верификации и Конфигуратор нозологий):** отображение сертификата `verification_audit.md`, кнопка повторного запуска `verify_reports.py` и интерактивный конструктор новых `configs/<id>.yaml`.

## Verification Results

- `uv run src/universal_schema.py --verify` — **PASS** (`5` стадий, `7` локализаций/подтипов, `7` этиологических факторов, `3` фазы патогенеза, `13` методик лечения; загружено `1775` статей, `1213` клинических строк, `1062` механизма, `80` РКИ).
- `uv run app.py --self-test` — **PASS** (`Streamlit AppTest` отрендерил все 4 вкладки, 8 субтабов, 6 метрик и 6 таблиц и переключил все 3 режима отчётов с `0` исключений).
