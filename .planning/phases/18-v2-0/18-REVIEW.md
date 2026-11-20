---
phase: 18-v2-0
reviewed: 2026-11-20T09:07:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - .agent/skills/ru-medical-humanizer/SKILL.md
  - .agent/skills/nosology-research-pipeline/SKILL.md
  - src/universal_schema.py
  - src/verify_reports.py
  - tests/test_phase18_humanizer.py
findings:
  critical: 3
  warning: 6
  info: 2
  total: 11
status: issues_found
---

# Phase 18: Code Review Report

**Reviewed:** 2026-11-20T09:07:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed all 5 Phase 18 (`18-v2-0`) deliverables against `HUM2-01`..`HUM2-03`, `18-01-PLAN.md`, `18-02-PLAN.md`, and the project's Zero-Tolerance & read-only `v1.x` invariants. While the skill upgrades, `clinical_decision_nuances` schema additions, and frozen `v1.x` read-only protections are well-structured and all 16 existing tests pass, adversarial probing surfaced **3 Critical (BLOCKER)** defects, **6 Warnings**, and **2 Info** items:

- **Linter bypass (`CR-01`):** `_FENCED_CODE_RE` fails to match closing fences on `\r\n` (CRLF) input or `>=4`-backtick fences and silently deletes the entire remainder of the report to `\Z`, allowing banned AI clichés, bullet walls, and pigeonhole conclusions to pass `check_humanizer_v2_structure()`.
- **Zero-Tolerance anti-hallucination gap (`CR-02`):** `verify_all_reports()` never cross-checks `kb_index.json` `evidence_pmids` (`frequent_complications`, `rare_critical_red_flags`, `clinical_decision_nuances`) against SQLite `valid_pmids`, and `_has_valid_evidence_pmids()` accepts placeholder strings (`"TBD"`, `0`, `-1`).
- **Path traversal (`CR-03`):** `src/universal_schema.py:load_nosology_bundle()` (reached directly via `--verify --nosology`) does not validate `nosology_id` or check `.resolve().is_relative_to(...)` on nosology or KB module file paths.
- **Structural linter accuracy (`WR-01`..`WR-05`):** The pigeonhole detector triggers false positives on legitimate Clavien–Dindo I–III summaries, 3-arm RCT reporting, and explicit refutations of stage-bucketing, while missing common Russian pigeonhole patterns (verb-before-stage, `I стадия` bullets, routing tables); `_extract_final_analytical_section()` can be hijacked by Chapter 1 (`Стратегия поиска`); numbered bold-lead walls bypass `bold_lead_bullet_ratio`; and substring matching in `_NUANCE_SIGNALS_RE` / `_COMPLICATIONS_*` permits trivial false passes.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: [BLOCKER] `_FENCED_CODE_RE` truncates the remainder of reports with CRLF (`\r\n`) line endings or `>=4`-backtick fences, enabling complete linter bypass

**File:** `src/verify_reports.py:123` (invoked at `src/verify_reports.py:330`)
**Issue:** `_FENCED_CODE_RE` is compiled as:
```python
_FENCED_CODE_RE = re.compile(r"(?ms)^[ \t]*(?:```|~~~).*?(?:^[ \t]*(?:```|~~~)[ \t]*$|\Z)")
```
In Python's `re` engine, `$` with `re.MULTILINE` matches only before `\n`, not `\r\n`, and `[ \t]*` does not consume `\r`. Because the closing fence alternates with `|\Z`, any Markdown string containing CRLF (`\r\n`) line endings (standard on Windows when decoded from bytes/HTTP/Streamlit) and a fenced code block (e.g., an ASCII clinical algorithm diagram) fails to match the closing ` ```\r\n` and **deletes everything from the opening fence to EOF**. Likewise, any valid CommonMark 4-backtick fence (```` ```` ````) opens on the first 3 backticks, cannot match the 3-backtick closing delimiter, and eats the rest of the document to `\Z`.

Reproduced live: a `v2.0` CRLF report containing a complications/nuance paragraph before a ` ```text ` block, followed by banned AI clichés (`подводя итог, можно заключить`), a 7-item bold-lead bullet wall, and a 3-stage pigeonhole conclusion after the block, returned `passed=True, errors=[]`.

**Fix:**
```python
_FENCED_CODE_RE = re.compile(
    r"(?ms)^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?(?:^[ \t]*\1[ \t]*$|\Z)"
)

def _normalize_newlines(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")
```
Call `_normalize_newlines(text)` at the start of `check_humanizer_v2_structure()` and `_strip_bibliography()`, and match the closing fence length/character via backreference `\1`.

---

### CR-02: [BLOCKER] `kb_index.json` `evidence_pmids` are never verified against SQLite `valid_pmids` in `v2.0` mode, and `_has_valid_evidence_pmids()` accepts non-PMID placeholders

**File:** `src/verify_reports.py:684-808` and `src/universal_schema.py:1305-1315`
**Issue:**
1. `verify_all_reports()` validates PMIDs only inside the 7 Markdown files (`report_files`), never inside `kb_index.json` (`frequent_complications[*].evidence_pmids`, `rare_critical_red_flags[*].evidence_pmids`, and all three sections of `clinical_decision_nuances`).
2. `_has_valid_evidence_pmids()` in `src/universal_schema.py:1305-1315` checks only `isinstance(p, (str, int)) and bool(str(p).strip())`. Reproduced live: `_has_valid_evidence_pmids(["TBD"])` and `_has_valid_evidence_pmids([0, -1])` both return `True`.
3. Consequently, completely hallucinated or placeholder PMIDs (`"99999999"`, `"TBD"`, `0`) in `kb_index.json` pass both `validate_kb_v2()` and `verify_all_reports(..., schema_version="v2")`, which then writes `Несуществующих / галлюцинированных PMID / PMCID / DOI / NCT ID: 0` into `verification_audit.md`.

**Fix:**
```python
# src/universal_schema.py
_PMID_STR_RE = re.compile(r"^[1-9]\d{0,8}$")

def _has_valid_evidence_pmids(pmids: Any) -> bool:
    if not isinstance(pmids, list) or len(pmids) == 0:
        return False
    return all(
        p is not None
        and not isinstance(p, bool)
        and isinstance(p, (str, int))
        and bool(_PMID_STR_RE.fullmatch(str(p).strip()))
        for p in pmids
    )
```
And in `src/verify_reports.py:verify_all_reports()` when `effective_version == "2.0"`:
```python
kb_pmids: set[str] = set()
for bucket in (kb_data.get("frequent_complications") or [], kb_data.get("rare_critical_red_flags") or []):
    if isinstance(bucket, list):
        for item in bucket:
            if isinstance(item, dict):
                kb_pmids.update(str(p).strip() for p in (item.get("evidence_pmids") or []) if p is not None and str(p).strip())
nuances_obj = kb_data.get("clinical_decision_nuances") or {}
if isinstance(nuances_obj, dict):
    for sec_key in ("universal_workhorse_modalities", "overlapping_indications_and_gray_zones", "strict_niche_or_salvage_indications"):
        for item in (nuances_obj.get(sec_key) or []):
            if isinstance(item, dict):
                kb_pmids.update(str(p).strip() for p in (item.get("evidence_pmids") or []) if p is not None and str(p).strip())
missing_kb_pmids = sorted(kb_pmids - valid_pmids)
assert not missing_kb_pmids, f"[{kb_json_path.name}] Missing evidence_pmids in {db_path}: {missing_kb_pmids}"
```

---

### CR-03: [BLOCKER] Path traversal vulnerability in `src/universal_schema.py:load_nosology_bundle()` (and untrusted `modules[*].file` joins)

**File:** `src/universal_schema.py:671-686, 711-715` (invoked by `verify_universal_schema()` at `1451-1457`)
**Issue:** While Phase 18 hardened `src/verify_reports.py:get_nosology_paths()` against `T-18-03`, `load_nosology_bundle(nosology_id)` (modified in Phase 18 and invoked directly by `src/universal_schema.py --verify --nosology <arg>`) constructs `CONFIGS_DIR / f"{nosology_id}.yaml"`, `DATA_DIR / nosology_id / "literature.db"`, and `REPORTS_DIR / nosology_id` without calling `validate_nosology_id(nosology_id)` or enforcing `.resolve().is_relative_to(...)`. Reproduced live: `load_nosology_bundle("../../nonexistent_traversal_probe")` runs without raising `ValueError`. In addition, line 713 reads `m_file = kb_dir / mod.get("file", "")` directly from untrusted `kb_index.json` without verifying `m_file.resolve().is_relative_to(kb_dir.resolve())`.

**Fix:**
```python
def load_nosology_bundle(nosology_id: str) -> dict[str, Any]:
    nosology_id = validate_nosology_id(nosology_id)
    configs_root = CONFIGS_DIR.resolve()
    data_root = DATA_DIR.resolve()
    reports_root = REPORTS_DIR.resolve()

    cfg_path = (configs_root / f"{nosology_id}.yaml").resolve()
    db_path = (data_root / nosology_id / "literature.db").resolve()
    rep_dir = (reports_root / nosology_id).resolve()
    kb_dir = (rep_dir / "knowledge_base").resolve()
    if (
        not cfg_path.is_relative_to(configs_root)
        or not db_path.is_relative_to(data_root)
        or not rep_dir.is_relative_to(reports_root)
        or not kb_dir.is_relative_to(reports_root)
    ):
        raise ValueError(f"Path traversal blocked for nosology_id={nosology_id!r}")
    ...
    for mod in kb_data.get("modules", []):
        m_file = (kb_dir / str(mod.get("file", ""))).resolve()
        if not m_file.is_relative_to(kb_dir):
            raise ValueError(f"KB module path escapes knowledge_base dir: {mod.get('file')!r}")
```

---

## Warnings

### WR-01: [WARNING] Pigeonhole detector produces severe false positives on legitimate clinical prose (Clavien–Dindo I–III summaries, 3-arm RCT reporting, and explicit refutations of stage-bucketing)

**File:** `src/verify_reports.py:151-183` (used at `275-310`)
**Issue:** `_PIGEONHOLE_STAGE_AFTER_RE` makes `(?:для|при)?` optional, `_STAGE_ROUTING_VERBS` includes generic clinical nouns (`операци\w*`, `терапи\w*`, `лечени\w*`, `вмешательств\w*`, `хирург\w*`), and `_STAGE_MARKERS` matches `перв\w*` (catching `первичная`!), `втор\w*` (catching `вторичная`!), and Roman numerals `I`/`II`/`III`. Reproduced live — all four valid `v2.0` conclusions falsely fail with `pigeonhole_matches`:
- Summarizing complications by Clavien–Dindo grade (`степени I ... после операции | степени II требуют консервативной терапии | степени III связаны с повторным вмешательством`).
- Explicitly refuting stage-bucketing (`При стадии I открытая и чрескожная операции конкурируют... при стадии II оба вида вмешательства равноценны... при стадии III выбор лечения определяется опытом хирурга`).
- Reporting a 3-arm RCT (`группы 1 ... терапию | группе 2 ... операция | группе 3 ... вмешательство`).
- Contrasting `первичной форме`, `вторичной форме`, and `тяжелой форме`.

**Fix:** Remove generic nouns (`операци\w*`, `терапи\w*`, `лечени\w*`, `вмешательств\w*`, `хирург\w*`, `релиз\w*`, `инъекц\w*`, `реконструкц\w*`) from `_STAGE_ROUTING_VERBS` and keep only prescriptive routing predicates (`подходит`, `показан\w*`, `рекоменд\w*`, `выбирают`, `оптимальн\w*`, `метод\w*\s+выбора`, `требуется`, `применяют`, `назначают`, `предпочтительн\w*`, `исключительно`); exclude `первичн`/`вторичн` (match `перв(?:ой|ая|ую|ом|ого)\b` and `втор(?:ой|ая|ую|ом|ого)\b`) and skip hits mentioning `clavien`/`ctcae` or explicit overlap negations (`конкурир`, `равноценн`, `обе`, `не делят`).

---

### WR-02: [WARNING] Pigeonhole detector misses common Russian clinical pigeonhole patterns (verb-before-stage, `I стадия` bullets, severity bullets, literal `HUM2-01` pattern, and Markdown routing tables)

**File:** `src/verify_reports.py:164-200, 266-318, 385-388`
**Issue:** Reproduced live — all six mechanical pigeonhole conclusions returned `pigeonhole_matches == []` (false negatives):
1. Verb-before-stage (`стадии I`): `"Консервативная терапия показана при стадии I. Чрескожный релиз оптимален при стадии II. Открытая операция выполняется при стадии III."`
2. Verb-before-stage (`I стадии`): `"Консервативная терапия показана при I стадии. Чрескожный релиз оптимален при II стадии. Открытая операция выполняется при III стадии."`
3. Bulleted stage-before-noun: `"- **I стадия:** консервативная терапия...\n- **II стадия:** чрескожный релиз...\n- **III стадия:** открытая операция."` (`_PIGEONHOLE_STAGE_BEFORE_RE` requires `для|при`, unlike `_PIGEONHOLE_STAGE_AFTER_RE`).
4. Bulleted severity buckets: `"- **Лёгкая степень:** ...\n- **Средняя степень:** ...\n- **Тяжёлая степень:** ..."`
5. Literal `HUM2-01` anti-pattern: `"Это лечение для 1, это для 2, это для 3."`
6. Pigeonhole routing placed in a Markdown table (`| Стадия I | Метод А | ...`), because `_strip_markdown_tables()` strips all table rows before `_detect_pigeonhole_routing()` runs.

**Fix:** Add a verb-before-stage pattern matching `routing_predicate + [^.\n;]{0,40} + (?:для|при)\s+(?:stage_noun stage_marker | stage_marker stage_noun)`, make `(?:для|при)?` optional at bullet/line start in `_PIGEONHOLE_STAGE_BEFORE_RE` (for `- **I стадия:**` / `- **Лёгкая степень:**`), add a short-slot pattern for `"для 1 ... для 2 ... для 3"`, and inspect conclusion table rows (excluding separator/header rows) for 1-to-1 stage-slot mappings.

---

### WR-03: [WARNING] `_extract_final_analytical_section()` can select Chapter 1 (`Стратегия поиска`) instead of the real conclusion, bypassing conclusion checks

**File:** `src/verify_reports.py:129-132, 229-250`
**Issue:** `_FINAL_SECTION_TITLE_RE` matches `стратег`, `алгоритм`, and `итог` anywhere in the document. If Chapter 1 is titled `## Глава 1. Стратегия поиска и PRISMA` and the final chapter lacks a keyword from `_FINAL_SECTION_TITLE_RE` (e.g., `## Глава 4. Сравнительный анализ хирургических методов`), `matching_indices[-1]` returns Chapter 1. Reproduced live: a report with `Стратегия поиска` in Chapter 1 and a blatant 3-stage pigeonhole routing in Chapter 2 passed with `passed=True, pigeonhole_matches=[]`. Even on the live `reports/metroplasty_pregnancy/executive_summary.md`, it selected `## 2. Алгоритм...` out of 4 sections and ignored sections 3 and 4.

**Fix:** Only treat a heading as the final analytical section if it falls in the second half of the document (`idx >= len(headings) // 2` or `match.start() >= len(body_text) * 0.45`), prioritize conclusion-specific keywords (`заключ|вывод|резюме|итог|рекомендац`) over earlier `стратег`/`алгоритм` headings, and when the matched heading is not the last `## ` section, also include the final `## ` section in pigeonhole scanning.

---

### WR-04: [WARNING] Numbered bold-lead walls (`1. **Заголовок:** ...`) bypass `bold_lead_bullet_ratio`, while tables/code blocks merge unrelated bullet runs into false `max_consecutive_bold_bullets` warnings

**File:** `src/verify_reports.py:126-127, 348-374`
**Issue:**
1. `_TOTAL_BULLET_RE` matches both `[-*+]` and `\d+\.`, whereas `_BOLD_LEAD_BULLET_RE` matches only `[-*+]`. Reproduced live: a 7-item numbered bold-lead list (`1. **Инфекция раны:** ...` .. `7. **Повторное вмешательство:** ...`) yields `total_bullets=7`, `bold_lead_bullets=0`, `bold_lead_bullet_ratio=0.0`, `max_consecutive_bold_bullets=0`, and `passed=True`.
2. `_strip_markdown_tables()` and `_FENCED_CODE_RE.sub("\n", ...)` replace tables and code blocks with blank lines, and the line loop (`if not stripped: _flush_paragraph(); continue`) does not reset `current_bold_run`. Reproduced live: two separate short bold-lead lists (4 items and 3 items) separated by a Markdown table merge into `max_consecutive_bold_bullets=7`, falsely triggering the `> 6` warning.

**Fix:** Update `_BOLD_LEAD_BULLET_RE` to `re.compile(r"^\s*(?:[-*+]|\d+\.)\s+\*\*[^*]{2,120}\*\*(?:\s*[:—–-])?")`, and replace stripped tables/code blocks with a structural break sentinel (e.g., `---`) instead of `""` so `current_bold_run` resets across tables and fenced code blocks while preserving loose-list behavior on single blank lines.

---

### WR-05: [WARNING] Over-broad substring matching in `_NUANCE_SIGNALS_RE` and `has_complications_analysis` enables trivial false passes

**File:** `src/verify_reports.py:134-147, 384-392`
**Issue:**
- `_NUANCE_SIGNALS_RE` matches substrings without boundaries or negation checks: `доступност` matches `"биодоступность"`, `альтернатив` matches `"отсутствие альтернативы"` (the opposite of competing methods), and `руб(?:ец|ц)` matches `"рубец на матке"` (the primary diagnosis in `metroplasty_pregnancy`, not a treatment trade-off).
- `has_complications_analysis` tests `осложнен` and `профилактик`/`обратим` independently anywhere in `body_no_code`. `"неосложненным течением"` (matches `осложнен`) + `"первичная профилактика"` (matches `профилактик`) anywhere in the document satisfies the complications gate with zero discussion of treatment complications.
- Reproduced live: a report with no treatment complications section and no overlapping-modality discussion (`"неосложненным течением"`, `"первичная профилактика"`, `"биодоступность"`, `"отсутствие альтернативы"`, `"рубцовом поражении"`) passed `v2.0` with `has_complications_analysis=True, has_overlapping_nuance_signals=True, errors=[]`.

**Fix:** Use negative lookbehinds/boundaries (`(?<![а-яё])осложн[её]н`, `(?<![а-яё])доступност`), exclude negated alternatives (`(?<!отсутстви\w\s)(?<!без\s)(?<!нет\s)(?<!не\sимеет\s)альтернатив`), replace bare `руб(?:ец|ц)` with trade-off phrases or require `>= 2` distinct nuance signal categories in `final_section_no_tables`, and require `осложн[её]н` and a complications structure term (`clavien|ctcae|ятроген|транзиторн|профилактик|обратим`) to co-occur within the same `## ` section (or within a ~1,500-char proximity window).

---

### WR-06: [WARNING] `validate_kb_v2()` crashes with `AttributeError` on non-dict input; `verify_all_reports()` crashes on non-dict `kb_index.json` and passes unnormalized `nosology_id` to `export_nosology_docx_files()`

**File:** `src/universal_schema.py:1158-1163, 1446-1448` and `src/verify_reports.py:650, 687-689, 813`
**Issue:**
1. `validate_kb_clinical_nuances_v2()` guards `if not isinstance(kb, dict):`, but `validate_kb_complications_v2()` does not; reproduced live, `validate_kb_v2(None)` raises `AttributeError: 'NoneType' object has no attribute 'get'`.
2. `verify_all_reports()` parses `kb_data = json.loads(...)` and immediately calls `kb_data.get("modules", [])` without checking `isinstance(kb_data, dict)`, crashing with `AttributeError` on malformed JSON arrays/nulls.
3. `verify_all_reports()` delegates normalization to `get_nosology_paths(nosology_id)` (which strips and lowercases `nos_id`) but passes the raw unnormalized `nosology_id` to `export_nosology_docx_files(nosology_id, root_dir)` on line 813 (causing `FileNotFoundError` for inputs like `" prom "` or `"PROM"` on case-sensitive filesystems) and calls `validate_nosology_id(nosology_id)` a second time on line 862.

**Fix:**
```python
# src/universal_schema.py
def validate_kb_complications_v2(kb: dict[str, Any]) -> list[str]:
    if not isinstance(kb, dict):
        return ["Knowledge base payload must be a dict"]
    ...

def validate_kb_v2(kb: dict[str, Any]) -> list[str]:
    if not isinstance(kb, dict):
        return ["Knowledge base payload must be a dict"]
    return validate_kb_complications_v2(kb) + validate_kb_clinical_nuances_v2(kb)
```
In `src/verify_reports.py:verify_all_reports()`: normalize `nos_id = validate_nosology_id(nosology_id)` once at the top, use `nos_id` consistently (including `export_nosology_docx_files(nos_id, root_dir)`), and add `assert isinstance(kb_data, dict), f"kb_index.json must be a JSON object: {kb_json_path}"`.

---

## Info

### IN-01: [INFO] Minor contract drift between `ru-medical-humanizer/SKILL.md`, `src/verify_reports.py`, and `src/universal_schema.py`

**File:** `.agent/skills/ru-medical-humanizer/SKILL.md:25, 29, 78`, `src/verify_reports.py:109-120, 743-749`, `src/universal_schema.py:1337-1348`
**Issue:**
- `SKILL.md` line 25 bans `«на сегодняшний день»` in `v2.0`, but `BANNED_AI_V2_CONCLUSION_PHRASES` in `src/verify_reports.py` omits it; conversely, `BANNED_AI_V2_CONCLUSION_PHRASES` enforces `"является методом выбора для всех"`, which is absent from `SKILL.md` Section 2.
- `SKILL.md` line 78 states `universal_workhorse_modalities` must list «две и более сквозные («рабочие») методики», while `validate_kb_clinical_nuances_v2()` enforces `>= 1` in both branches of `if isinstance(modalities, list) and len(modalities) >= 2:` (so the `if/else` alters only the error text).
- In `verify_all_reports()` line 744, banned-phrase scanning strips the bibliography (`_strip_bibliography`) in `v2.0` mode but does not strip fenced code blocks, whereas `check_humanizer_v2_structure()` strips both.

**Fix:** Synchronize the `v2.0` banned cliché catalog across `SKILL.md` and `src/verify_reports.py`, align the `universal_workhorse_modalities` minimum count wording between skill and validator (removing the redundant `if/else` if `>= 1` is canonical), and strip fenced code blocks consistently in `verify_all_reports()`.

---

### IN-02: [INFO] `load_nosology_bundle()` masks missing `clinical_decision_nuances` diagnostics for `v2.0`, `kb_json_path` lacks symlink containment check, and writable/CLI paths lack test coverage

**File:** `src/universal_schema.py:690-700`, `src/verify_reports.py:685`, `tests/test_phase18_humanizer.py:261-319, 571-634`
**Issue:**
- `load_nosology_bundle()` injects `_default_clinical_decision_nuances()` whenever `"clinical_decision_nuances" not in kb_data`, even for `schema_version == "2.0"`, converting a top-level missing-object diagnostic in `verify_universal_schema(..., schema_version="v2")` into child empty-list errors (still rejected, but less clear).
- `verify_all_reports()` line 685 reads `kb_json_path = kb_dir / "kb_index.json"` without the `.resolve().is_relative_to(reports_root)` symlink containment guard used on Markdown files at line 715.
- `tests/test_phase18_humanizer.py` only runs `verify_all_reports()` with `write_outputs=False` (leaving `verification_audit.md` v2 metric rendering, `export_nosology_docx_files()`, `--compile-bibliography --read-only` CLI error handling, and `verify_universal_schema(..., schema_version="v2")` untested).

**Fix:** Guard `kb_json_path.resolve().is_relative_to(reports_root)` in `verify_reports.py`; only auto-inject `_default_clinical_decision_nuances()` when `str(kb_data.get("schema_version", "")) != "2.0"`; and add isolated `tmp_path` tests covering `write_outputs=True`, CLI flag validation, `verify_universal_schema(..., schema_version="v2")`, and the regex/security regressions from `CR-01`..`WR-06`.

---

_Reviewed: 2026-11-20T09:07:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
