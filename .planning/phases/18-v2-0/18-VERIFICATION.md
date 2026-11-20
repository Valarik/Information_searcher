---
phase: 18-v2-0
verified: 2026-11-20T09:28:00Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
---

# Phase 18: Хуманизация v2.0 — нелинейная логика клинического выбора и структурный анти-ИИ линтер — Verification Report

**Phase Goal:** Убрать из будущих отчетов типичную ИИ-схематичность («этот метод — для 1, этот — для 2, этот — для 3») и перевести синтез на реальную клиническую логику сквозных конкурирующих методик и практических компромиссов с автоматическим контролем в `src/verify_reports.py`.
**Verified:** 2026-11-20T09:28:00Z
**Status:** passed
**Re-verification:** No — initial verification (post code-review fix commit `7da3c8d`)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | **[ROADMAP SC-1 / HUM2-01]** `.agent/skills/ru-medical-humanizer/SKILL.md` содержит раздел `v2.0` по архитектуре выводов и клинического выбора: запрет на «коробочную» ИИ-маршрутизацию, описание сквозных («рабочих») методик, перекрывающих весь спектр стадий, и практических нюансов реального выбора, плюс бюджет прозы (`bold_lead_bullet_ratio <= 0.35`) и удаление опечатки `主に`. | ✓ VERIFIED | `.agent/skills/ru-medical-humanizer/SKILL.md` L11–113: заголовок `v2.0`, опечатка `主に` заменена на `преимущественно` (L38), раздел `## 2` синхронизирован со всеми 11 фразами `BANNED_AI_V2_CONCLUSION_PHRASES` (`Missing v2 phrases in SKILL.md: []`), добавлен раздел `## 6. Хуманизация v2.0` (6.1 запрет «метод 1 подходит для 1…», 6.2 `universal_workhorse_modalities` с 6 факторами выбора, 6.3 `overlapping_indications_and_gray_zones` vs `strict_niche_or_salvage_indications`, 6.4 контрастный хирургический пример, 6.5 `bold_lead_bullet_ratio <= 0.35`). |
| 2 | **[ROADMAP SC-2 / HUM2-02]** `.agent/skills/nosology-research-pipeline/SKILL.md` и `src/universal_schema.py` фиксируют структуру `clinical_decision_nuances` (`universal_workhorse_modalities`, `overlapping_indications_and_gray_zones`, `strict_niche_or_salvage_indications`) и обязательный модуль/главу по осложнениям лечения для всех новых нозологий. | ✓ VERIFIED | `.agent/skills/nosology-research-pipeline/SKILL.md` L9–78 документирует `surgical_focus`, `treatment_profile`, `complications_queries`, `complications_safety`, `extracted_complications`, обязательный раздел/модуль осложнений (`frequent_complications`, `rare_critical_red_flags`), контракт `clinical_decision_nuances` и команды `--schema-version v2`. `src/universal_schema.py` L112–150, L665–713, L1178–1508 экспортирует `REQUIRED_CLINICAL_NUANCE_SECTIONS`, `REQUIRED_WORKHORSE_KEYS`, `REQUIRED_OVERLAP_KEYS`, `REQUIRED_NICHE_KEYS`, `validate_kb_clinical_nuances_v2()`, `validate_kb_v2()` и применяет их в `verify_universal_schema(..., schema_version="v2")`. |
| 3 | **[ROADMAP SC-3 / HUM2-03]** `src/verify_reports.py` включает структурный анти-ИИ линтер (`check_humanizer_v2_structure`): расширенный словарь штампов и клишированных выводов, контроль доли списков с жирным зачином (`bold_lead_bullet_ratio <= 0.35`), блокировку «коробочной» маршрутизации, проверку нелинейности заключительной главы и анализа осложнений для `v2.0`. | ✓ VERIFIED | `src/verify_reports.py` L87–609 и L777–1087 реализует `BANNED_AI_PHRASES` (19) + `BANNED_AI_V2_CONCLUSION_PHRASES` (11), `check_humanizer_v2_structure()`, `_BOLD_LEAD_BULLET_RE` (маркированные и нумерованные списки), `_extract_final_analytical_section()`, `_detect_pigeonhole_routing()` (проза, списки, глагол до стадии, «для 1..2..3», таблицы маршрутизации, исключения Clavien–Dindo/РКИ/опровержений), `_NUANCE_SIGNALS_RE`, `_has_section_complications_analysis()` и строгую интеграцию в `verify_all_reports()` вместе с `validate_kb_v2()` и проверкой `kb_index.json` `evidence_pmids` по SQLite. |
| 4 | **[Backward Compat / T-18-02, T-18-04]** Все замороженные нозологии `v1.x` (`prom`, `metroplasty_pregnancy`, `trigger_finger`) проходят read-only верификацию без единого изменения на диске, а строгий режим `--schema-version v2` корректно отклоняет legacy `v1.x` без записей на диск. | ✓ VERIFIED | Живые CLI-прогоны `src/verify_reports.py --verify --read-only` (exit 0 на всех 3 нозологиях), `src/universal_schema.py --verify` (exit 0 на всех 3), `app.py --self-test` (`[3/3] [PASS]`), строгий `--schema-version v2` отклоняет `prom` (exit 1 в обоих CLI), `git status --porcelain data/prom data/metroplasty_pregnancy data/trigger_finger reports/prom reports/metroplasty_pregnancy reports/trigger_finger` — полностью пусто. |
| 5 | **[Security / T-18-01, T-18-03, CR-02, CR-03]** Контуры безопасности защищены от обхода пути (`path traversal` / symlink escape), фиктивных `evidence_pmids` (`TBD`, `0`, `-1`, `[None]`) и галлюцинированных PMID в `kb_index.json`. | ✓ VERIFIED | `src/verify_reports.py:get_nosology_paths()` (L46–84) и `verify_all_reports()` (L824–826, L856–858) + `src/universal_schema.py:load_nosology_bundle()` (L671–691, L731–733) валидируют `nosology_id` и `.resolve().is_relative_to(...)` (включая `kb_index.json` и `modules[*].file`); `_has_valid_evidence_pmids()` (L1178–1196) требует `^[1-9]\d{0,8}$`; `verify_all_reports()` (L943–971) сверяет все 5 массивов `evidence_pmids` из `kb_index.json` против `valid_pmids` SQLite. |
| 6 | **[Tests & Review Closure]** Набор тестов `tests/test_phase18_humanizer.py` покрывает `HUM2-01..HUM2-03`, сквозной синтетический `v2.0` (read-only + writable `.docx`/`audit`), read-only `v1.x` и все 11 замечаний из `18-REVIEW.md` (`CR-01..03`, `WR-01..06`, `IN-01..02`). | ✓ VERIFIED | `pytest tests/ -v` выполнился полностью: **17 passed in 2.32s** (`11` тестов Фазы 17 + `6` тестов Фазы 18, включая `test_phase18_code_review_regressions`); все 11 пунктов `18-REVIEW.md` независимо подтверждены в коде (commit `7da3c8d`) и живыми пробами. |

**Score:** 6/6 must-haves verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `.agent/skills/ru-medical-humanizer/SKILL.md` | Раздел `## 6. Хуманизация v2.0`, расширенный словарь штампов, запрет «коробочной» маршрутизации, бюджет `bold_lead_bullet_ratio <= 0.35`, без `主に` | ✓ VERIFIED | 113 строк, не заглушка, все 11 фраз `BANNED_AI_V2_CONCLUSION_PHRASES` синхронизированы, `主に` удалена. |
| `.agent/skills/nosology-research-pipeline/SKILL.md` | Контракт пайплайна `v2.0` (`surgical_focus`, `complications_queries`, `complications_safety`, `extracted_complications`, `frequent_complications`, `rare_critical_red_flags`, `clinical_decision_nuances`) | ✓ VERIFIED | 78 строк, описаны все 5 фаз `v2.0`, анти-рецидивное правило и команды `--schema-version v2`. |
| `src/universal_schema.py` | `REQUIRED_CLINICAL_NUANCE_SECTIONS`, `validate_kb_clinical_nuances_v2()`, `validate_kb_v2()`, path-containment в `load_nosology_bundle()`, строгий `_PMID_STR_RE` | ✓ VERIFIED | 1566 строк, импортируется и используется в `src/verify_reports.py`, `app.py` и `tests/`. |
| `src/verify_reports.py` | `BANNED_AI_V2_CONCLUSION_PHRASES`, `check_humanizer_v2_structure()`, CRLF-safe `_FENCED_CODE_RE`, `verify_all_reports()` с `--schema-version`, `--read-only`, SQLite-проверкой `kb_index.json` PMIDs | ✓ VERIFIED | 1087 строк, автономный запуск через `uv run src/verify_reports.py` работает без дополнительных `--with` флагов. |
| `tests/test_phase18_humanizer.py` | Модульные, интеграционные, security, `v1.x` read-only и code-review регрессионные тесты Фазы 18 | ✓ VERIFIED | 855 строк, 6 комплексных тестовых функций, все 6 `PASSED`. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `src/universal_schema.py` | `.agent/skills/nosology-research-pipeline/SKILL.md` | Точные ключи `clinical_decision_nuances`: `universal_workhorse_modalities`, `overlapping_indications_and_gray_zones`, `strict_niche_or_salvage_indications` | ✓ WIRED | Полное совпадение имен секций и всех дочерних полей (`REQUIRED_WORKHORSE_KEYS`, `REQUIRED_OVERLAP_KEYS`, `REQUIRED_NICHE_KEYS`). |
| `src/verify_reports.py` | `.agent/skills/ru-medical-humanizer/SKILL.md` | Синхронизированный словарь `BANNED_AI_V2_CONCLUSION_PHRASES` и порог `bold_lead_bullet_ratio <= 0.35` | ✓ WIRED | 11/11 фраз из `BANNED_AI_V2_CONCLUSION_PHRASES` присутствуют в разделе `## 2` скилла; порог `0.35` идентичен. |
| `src/verify_reports.py` | `src/universal_schema.py` | Импорт `_connect_sqlite_readonly`, `validate_kb_v2` и вызов в `verify_all_reports()` (L40, L806, L939) | ✓ WIRED | Обе функции вызываются в основном потоке верификации; при `effective_version == "2.0"` несоответствия KB и отсутствующие в SQLite `evidence_pmids` блокируют прохождение. |
| `src/verify_reports.py` | `src/extractor_common.py` | Импорт и вызов `validate_nosology_id()` (L39, L48, L788) | ✓ WIRED | Исключает traversal на входе `get_nosology_paths()` и нормализует `nos_id` до передачи в `export_nosology_docx_files()`. |
| `tests/test_phase18_humanizer.py` | `src/verify_reports.py`, `src/universal_schema.py`, `SKILL.md` x2 | Прямые вызовы API + CLI subprocess + `git status` проверка замороженных `v1.x` | ✓ WIRED | Все 6 тестов выполняют реальные утверждения над живыми модулями и файлами. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `src/verify_reports.py` | `valid_pmids`, `kb_pmids`, `diss_lint`, `sum_lint` | Read-only SQLite `articles`/`clinical_trials` (`_connect_sqlite_readonly`), `kb_index.json`, 7 Markdown-файлов отчёта | Yes (живые БД `prom`: 2643 ст., `metroplasty_pregnancy`: 506 ст., `trigger_finger`: 1024 ст. + синтетическая SQLite БД `v2.0`) | ✓ FLOWING |
| `src/universal_schema.py` | `kb_data`, `v2_errors` | `reports/<id>/knowledge_base/kb_index.json` + read-only SQLite fallback | Yes (реальные JSON-индексы + валидация `v2.0` без подмены `clinical_decision_nuances` при `schema_version == "2.0"`) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Полный регрессионный набор `pytest` (Phase 17 + Phase 18) | `$env:PATH = "$HOME\.local\bin;" + $env:PATH; uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore pytest tests/ -v` | `17 passed in 2.32s` (exit 0) | ✓ PASS |
| Read-only верификация отчётов `v1.x` (`prom`, `metroplasty_pregnancy`, `trigger_finger`) | `uv run src/verify_reports.py --nosology <id> --verify --read-only` (x3) | Все 3 `PASSED` (`Schema=1.x`, `COMPAT_V1`, 97 / 78 / 98 refs, exit 0) | ✓ PASS |
| Строгое отклонение `v1.x` в режиме `--schema-version v2 --read-only` | `uv run src/verify_reports.py --nosology prom --verify --schema-version v2 --read-only` | `AssertionError: [Humanizer v2.0 Failure]` (`bold_lead_bullet_ratio=0.8065 > 0.35`, нет сигналов нелинейной логики), exit 1 | ✓ PASS |
| Верификация универсальной схемы `v1.x` (`prom`, `metroplasty_pregnancy`, `trigger_finger`) | `uv run src/universal_schema.py --verify --nosology <id>` (x3) | Все 3 `[PASS] [v1.x (compat)]` (DOCX, HTML, CSV, SQLite, exit 0) | ✓ PASS |
| Строгое отклонение `v1.x` в `universal_schema.py --schema-version v2` | `uv run src/universal_schema.py --verify --nosology prom --schema-version v2` | `[FAIL] Schema v2.0 validation failed for 'prom'` (5 ошибок контракта `v2.0`), exit 1 | ✓ PASS |
| Headless самотестирование веб-приложения `app.py` | `uv run app.py --self-test` | `[3/3] [PASS]` (0 exceptions, metrics=6, dataframes=6, tabs=8, exit 0) | ✓ PASS |
| Неприкосновенность замороженных папок `v1.x` | `git status --porcelain data/prom data/metroplasty_pregnancy data/trigger_finger reports/prom reports/metroplasty_pregnancy reports/trigger_finger` | Пустой вывод (0 изменённых/новых файлов, exit 0) | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| `HUM2-01` | `18-01`, `18-02` | Обновление `.agent/skills/ru-medical-humanizer/SKILL.md` до `v2.0`: запрет линейной маршрутизации, стандарт сквозных конкурирующих методик, баланс связной прозы и списков | ✓ SATISFIED | `SKILL.md` Section 2 & Section 6 (L25–29, L38, L66–113); `test_skills_v2_contracts` PASSED. |
| `HUM2-02` | `18-01`, `18-02` | Обновление `.agent/skills/nosology-research-pipeline/SKILL.md` и контракта `kb_index.json` (`v2.0`) блоком `clinical_decision_nuances` и обязательным разделом осложнений | ✓ SATISFIED | `nosology-research-pipeline/SKILL.md` L15–78; `src/universal_schema.py` `validate_kb_clinical_nuances_v2()` / `validate_kb_v2()` / `verify_universal_schema()`; `test_universal_schema_clinical_decision_nuances_v2` PASSED. |
| `HUM2-03` | `18-02` | Структурный анти-ИИ линтер `v2.0` в `src/verify_reports.py`: расширенный словарь штампов, `bold_lead_bullet_ratio`, блокировка «коробочных» выводов, проверка осложнений и перекрывающихся показаний | ✓ SATISFIED | `src/verify_reports.py` `check_humanizer_v2_structure()` & `verify_all_reports()`; `test_verify_reports_humanizer_v2_rejects_ai_antipatterns` & `test_verify_all_reports_v2_end_to_end_and_path_traversal` PASSED. |

*Orphaned requirements check:* `.planning/REQUIREMENTS.md` относит к Phase 18 ровно 3 требования (`HUM2-01`, `HUM2-02`, `HUM2-03`). Осиротевших требований нет (`0`). *(Примечание: таблица Traceability в `.planning/REQUIREMENTS.md` ещё содержит статус `Pending` для `HUM2-01..03` — оркестратор обновит чекбоксы после завершения верификации.)*

### Security & Threat Model Verification (`T-18-01`..`T-18-04`)

| Threat ID | Component | Mitigation Verified | Evidence |
| --- | --- | --- | --- |
| `T-18-01` | `src/universal_schema.py:validate_kb_clinical_nuances_v2` | ✓ VERIFIED | Проверяет типы `dict`/`list`/непустые `str`, `>= 2` различных (case-insensitive) `competing_modalities`, и строгое совпадение `evidence_pmids` с `^[1-9]\d{0,8}$` (отвергает `None`, `bool`, `"TBD"`, `0`, `-1`, смешанные массивы). |
| `T-18-02` | `src/universal_schema.py:load_nosology_bundle` | ✓ VERIFIED | Дефолт `_default_clinical_decision_nuances()` применяется только в памяти и только при `schema_version != "2.0"`; файлы `reports/*/knowledge_base/kb_index.json` не изменяются на диске. |
| `T-18-03` | `src/verify_reports.py:get_nosology_paths` + `src/universal_schema.py:load_nosology_bundle` | ✓ VERIFIED | `validate_nosology_id()` (`^[a-z0-9_]+$`) + `.resolve().is_relative_to(...)` для всех конфигов, БД, отчётов, `kb_index.json` и `modules[*].file`; живой тест `../../etc/passwd` и `../../secret.md` вызывает `ValueError`. |
| `T-18-04` | `src/verify_reports.py:verify_all_reports` | ✓ VERIFIED | SQLite открывается через `_connect_sqlite_readonly()` (`mode=ro`, `PRAGMA query_only = ON`); `--read-only` (`write_outputs=False`) не записывает `@PMID:`, `.docx` и `verification_audit.md`; `--compile-bibliography --read-only` отвергается CLI-парсером. |

### Code Review Findings Verification (`18-REVIEW.md` — 11/11 Resolved)

| ID | Severity | Finding Summary | Disk Status | Verification Evidence |
| --- | --- | --- | --- | --- |
| `CR-01` | BLOCKER | CRLF / 4-backtick fence truncation bypass in `_FENCED_CODE_RE` | ✓ FIXED | `src/verify_reports.py` L125 (`(`{3,}|~{3,})...\1`), L248–256 (`_normalize_newlines()`), L469–470, L886; подтверждено тестом CRLF + ```` ```` ```` и живой пробой `~~~` + CRLF. |
| `CR-02` | BLOCKER | `kb_index.json` `evidence_pmids` not checked against SQLite + `"TBD"`/`0`/`-1` accepted | ✓ FIXED | `src/universal_schema.py` L1178–1196 (`_PMID_STR_RE`); `src/verify_reports.py` L943–971 (сверка всех 5 секций KB против `valid_pmids`); тест с `"99999999"`, `"TBD"`, `0`, `-1` PASSED. |
| `CR-03` | BLOCKER | Path traversal in `load_nosology_bundle()` and untrusted `modules[*].file` | ✓ FIXED | `src/universal_schema.py` L673–690, L731–733; живые тесты `../../nonexistent_traversal_probe`, `../../etc/passwd` и `../../secret.md` выбрасывают `ValueError`. |
| `WR-01` | WARNING | False-positive pigeonhole on Clavien–Dindo I–III, 3-arm RCT, refutations, `первичная`/`вторичная` | ✓ FIXED | `src/verify_reports.py` L162–175, L226–230, L396–398; тест `WR-01` (`legit_prose`) даёт `pigeonhole_matches == []` и `passed == True`. |
| `WR-02` | WARNING | Missed Russian pigeonhole forms (verb-before-stage, `- **I стадия:**`, severity bullets, `для 1..2..3`, routing tables) | ✓ FIXED | `src/verify_reports.py` L187–243, L427–450; все 6 паттернов из `WR-02` пойманы в `test_phase18_code_review_regressions`. |
| `WR-03` | WARNING | Chapter 1 `Стратегия поиска` hijacking `_extract_final_analytical_section()` | ✓ FIXED | `src/verify_reports.py` L284–325 (фильтр второй половины, приоритет `primary` над `secondary`, добавление последней `## `-главы); тест `WR-03` PASSED. |
| `WR-04` | WARNING | Numbered bold-lead walls bypassing ratio; tables/code blocks merging bullet runs | ✓ FIXED | `src/verify_reports.py` L129 (`(?:[-*+]|\d+\.)`), L245/L276/L470 (`_BREAK_SENTINEL = "---"`), L494–497; тест `WR-04` (`bold_lead_bullets == 7`, `max_consecutive_bold_bullets == 4`) PASSED. |
| `WR-05` | WARNING | Over-broad substring false passes (`биодоступность`, `отсутствие альтернативы`, `неосложненным` + `профилактика`, диагноз `рубец`) | ✓ FIXED | `src/verify_reports.py` L142–159, L327–349 (отрицательные просмотры назад, co-occurrence в одном `## `-разделе / окне ±1500 симв.); тест `WR-05` и отдельная проба разнесённых глав PASSED. |
| `WR-06` | WARNING | `validate_kb_v2(None)` crash, non-dict `kb_index.json` crash, unnormalized `nosology_id` passed to `export_nosology_docx_files()` | ✓ FIXED | `src/universal_schema.py` L1201–1202, L1464–1465; `src/verify_reports.py` L788, L829, L983; тест `WR-06` (`" WRITE_V2_TEST "`, `validate_kb_v2(None)`) PASSED. |
| `IN-01` | INFO | Contract drift (`на сегодняшний день`, `является методом выбора для всех`, redundant workhorse `if/else`, fenced code strip in `verify_all_reports`) | ✓ FIXED | Все 11 фраз синхронизированы между `SKILL.md` и `src/verify_reports.py`; формулировка `SKILL.md` L78 согласована с `>= 1` в `universal_schema.py` L1359–1363; L886 очищает fenced code blocks. |
| `IN-02` | INFO | `load_nosology_bundle()` masking `v2.0` missing nuances, `kb_json_path` symlink guard, writable & CLI test coverage | ✓ FIXED | `src/universal_schema.py` L705; `src/verify_reports.py` L824–826; `tests/test_phase18_humanizer.py` L835–855 проверяют `write_outputs=True` (`.docx` + `verification_audit.md`) и CLI `--compile-bibliography --read-only`. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `src/verify_reports.py` | 380 | `clean = re.sub(r"[*_`]", "", final_section_no_tables)` удаляет ведущий маркер `* ` в списках со звёздочкой (`* **I стадия:** ...`) до запуска `_PIGEONHOLE_BULLET_*_RE` | ℹ️ Info | Не блокирует цель фазы: дефисные (`-`) и нумерованные (`1.`) списки, все 6 кейсов `WR-02`, все глагольные паттерны и подсчёт `bold_lead_bullet_ratio` для `* **...**` работают корректно; узкий edge case только для `* **I стадия:**` без глаголов маршрутизации при одновременном наличии сигналов нелинейности. |

*Debt-marker scan (`TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER`):* 0 незакрытых маркеров долга в исходном коде и скиллах (единственное вхождение `"TBD"` находится в тестовом входе `tests/test_phase18_humanizer.py:726`, проверяющем отклонение заглушек в `evidence_pmids`).

### Human Verification Required

None — все deliverables Фазы 18 (скиллы `.agent/skills/`, валидатор схемы `src/universal_schema.py`, структурный линтер `src/verify_reports.py` и автотесты `tests/test_phase18_humanizer.py`) являются детерминированными программными/текстовыми контрактами без новых UI-экранов (UI вынесен в Phase 19) и проверены автоматически.

### Gaps Summary

No gaps found. Все 3 критерия успеха ROADMAP, все 3 требования (`HUM2-01..HUM2-03`), все 4 угрозы (`T-18-01..T-18-04`) и все 11 замечаний код-ревью (`18-REVIEW.md`) подтверждены на реальном коде и живых прогонах при нулевых изменениях в замороженных корпусах `v1.x`.

---

_Verified: 2026-11-20T09:28:00Z_
_Verifier: the agent (gsd-verifier)_
