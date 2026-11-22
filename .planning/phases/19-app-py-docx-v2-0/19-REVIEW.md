---
phase: 19-app-py-docx-v2-0
reviewed: 2026-11-22T09:00:00Z
depth: deep
files_reviewed: 5
files_reviewed_list:
  - src/docx_exporter.py
  - src/universal_schema.py
  - src/verify_reports.py
  - app.py
  - tests/test_v2_engine.py
findings:
  critical: 4
  warning: 7
  info: 6
  total: 17
status: issues_found
---

# Phase 19: Code Review Report

**Reviewed:** 2026-11-22T09:00:00Z
**Depth:** deep
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Conducted a deep, adversarial cross-file code review of all Phase 19 changes (`git diff c10c724..HEAD` plus full reads and targeted read-only verification) across `src/docx_exporter.py`, `src/universal_schema.py`, `src/verify_reports.py`, `app.py`, and `tests/test_v2_engine.py` against locked decisions `D-01..D-08` and ASVS L1 threats `T-19-01..T-19-05`.

**What works well:**
- OpenXML `<w:trPr>` (`<w:cantSplit/><w:tblHeader/>`) and `<w:tcPr>` (`<w:tcW>`, single `<w:shd>`, `<w:vAlign>`) child ordering complies strictly with ECMA-376, and `dissertation_report.docx` stays clean while `executive_summary.docx` / `full_clinical_dossier.docx` share unified builders between CLI and `app.py`.
- Zero new `unsafe_allow_html=True` calls were added to `app.py`, `btn_run_verify` enforces `validate_nosology_id()`, `shell=False`, and `--verify --read-only`, and all 3 frozen `v1.x` corpora remain cleanly untouched in `git status`.

**Key defects found (4 Critical, 7 Warning, 6 Info):**
1. **`CR-01` (Reproduced live in AppTest):** Un-scoped static Streamlit `multiselect` keys (`t25_modalities`, `t25_grades`, `t3_comp_mod`, `t3_comp_cd`, `sub4_comparator_picks`, etc.) retain stale `st.session_state` values when switching between nosologies — completely blanking out Subtab `2.5` (0 charts, 0 rows, false "no matching complications" warning) and silently dropping rows/grades in Tab `3.5` when switching between two `v2.0` nosologies.
2. **`CR-02` (Security / `T-19-01`):** `export_nosology_docx_files()` checks `root == PROJECT_ROOT.resolve()` rather than the resolved target `rep_dir`, allowing a symlinked/junctioned `base_dir/reports` directory to bypass `FROZEN_V1_NOSOLOGIES` protection and overwrite frozen `v1.x` `.docx` files.
3. **`CR-03` (Security / `T-19-02`):** `_escape_md_cell()` does not neutralize Markdown link syntax `[label](https://...)`, so untrusted text in `kb_index.json` fields compiles into active `<w:hyperlink>` + external `<Relationship TargetMode="External"/>` entries in `.docx`, bypassing the PMID URL allowlist.
4. **`CR-04` (Correctness / Security):** `verify_all_reports()` checks only `len(kb_md_files) == len(kb_index_modules)` without verifying filenames, uniqueness, existence, or path containment of `kb_index.json["modules"][*]["file"]`, allowing missing/duplicated/path-traversal module entries paired with orphaned `.md` files to pass verification and break `app.py`.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Stale Streamlit `session_state` filter keys blank out Subtab 2.5 and silently drop complications in Tab 3.5 when switching nosologies

**File:** `app.py:165-172`, `app.py:543-579`, `app.py:1023-1029`, `app.py:1159-1166`, `app.py:1489-1538`
**Severity:** BLOCKER (Critical)
**Issue:**
All nosology-specific `st.multiselect` and filter widgets in Subtab `2.5` (`t25_modalities`, `t25_grades`, `t25_reversibility`, `t25_event_class`), Tab `3` Option 5 (`t3_comp_mod`, `t3_comp_cd`, `t3_comp_rev`, `t3_comp_class`, `t3_comp_casuistry`, `t3_comp_kw`), Subtab `2.3` (`sub3_group_filter`), and Subtab `2.4` (`sub4_comparator_picks`) use static keys that are never cleared or scoped when `sidebar_nosology_select` changes.

In Streamlit `1.67.0`, when `options` change on a rerun for an existing `key`, `st.multiselect` preserves `old_session_state ∩ new_options` instead of re-applying `default`. Reproduced directly against `app.py` via `AppTest` with two `v2.0` nosologies (`alpha_hand_v2` → `beta_knee_v2`):
- **Subtab `2.5`:** `t25_modalities` collapsed to `[]` and `t25_grades` silently dropped `IIIa`/`IV` (retaining only `['I']`), wiping out both Plotly charts and the table and rendering `⚠️ Нет осложнений, соответствующих выбранным фильтрам.` despite zero filter interaction.
- **Tab `3` Option 5:** `t3_comp_mod` intersected to only a single shared casuistry modality (`['Эндоскопическая декомпрессия']`) and `t3_comp_cd` silently dropped `'IIIa'`, causing the table to display **0 rows** out of 4 real non-casuistry complications.
- **Subtab `2.4`:** Switching between `prom`, `metroplasty_pregnancy`, and `trigger_finger` empties `sub4_comparator_picks` (`[]`), hiding all side-by-side comparison cards.

**Fix:**
Reset nosology-scoped widget state in `render_sidebar()` whenever `selected_id` changes (preserving all existing widget keys for `AppTest` compatibility):

```python
_NOSOLOGY_SCOPED_WIDGET_KEYS: tuple[str, ...] = (
    "tab1_diss_sec",
    "tab1_kb_mod_select",
    "sub3_group_filter",
    "sub4_comparator_picks",
    "sub4_sql_grp",
    "t25_modalities",
    "t25_grades",
    "t25_reversibility",
    "t25_event_class",
    "t3_art_tiers",
    "t3_art_xml",
    "t3_art_kw",
    "t3_clin_grp",
    "t3_clin_kw",
    "t3_mech_cat",
    "t3_mech_kw",
    "t3_tr_status",
    "t3_tr_kw",
    "t3_comp_casuistry",
    "t3_comp_mod",
    "t3_comp_cd",
    "t3_comp_rev",
    "t3_comp_class",
    "t3_comp_kw",
)

# Inside render_sidebar(), immediately after selected_id = st.selectbox(...):
prev_nos_id = st.session_state.get("_active_nosology_id")
if prev_nos_id is not None and prev_nos_id != selected_id:
    for wkey in _NOSOLOGY_SCOPED_WIDGET_KEYS:
        st.session_state.pop(wkey, None)
st.session_state["_active_nosology_id"] = selected_id
```

### CR-02: `FROZEN_V1_NOSOLOGIES` guard in `export_nosology_docx_files()` is bypassable via symlinked/junctioned `base_dir/reports`

**File:** `src/docx_exporter.py:988-999`
**Severity:** BLOCKER (Critical)
**Issue:**
`export_nosology_docx_files()` checks:
```python
root = (base_dir or PROJECT_ROOT).resolve()
reports_root = (root / "reports").resolve()
rep_dir = (reports_root / nos_id).resolve()
if not rep_dir.is_relative_to(reports_root):
    raise ValueError(...)

if root == PROJECT_ROOT.resolve() and nos_id in FROZEN_V1_NOSOLOGIES and not allow_frozen_overwrite:
    raise PermissionError(...)
```
Because the frozen check compares `root == PROJECT_ROOT.resolve()` rather than the actual resolved target directory `rep_dir` (and does not check `reports_root.is_relative_to(root)`), if a caller passes a `base_dir` whose `reports/` child is a symlink or Windows directory junction to `PROJECT_ROOT / "reports"`:
1. `root != PROJECT_ROOT.resolve()` evaluates to `False`, bypassing `PermissionError`;
2. `rep_dir` resolves to `PROJECT_ROOT / "reports" / "prom"`, which satisfies `rep_dir.is_relative_to(reports_root)`;
3. Frozen `v1.x` `.docx` files inside the repository root are silently overwritten, violating `T-19-01` and `D-07.3`.

(Contrast with `src/universal_schema.py:1224-1225`, which properly compares the resolved target file path against `(PROJECT_ROOT / "configs" / f"{nos_id}.yaml").resolve()`.)

**Fix:**
Check both `reports_root.is_relative_to(root)` and resolved target equality against `(PROJECT_ROOT / "reports" / nos_id).resolve()`:

```python
    nos_id = validate_nosology_id(nosology_slug)
    root = (base_dir if base_dir is not None else PROJECT_ROOT).resolve()
    reports_root = (root / "reports").resolve()
    if not reports_root.is_relative_to(root):
        raise ValueError(f"Reports root escapes base directory: {reports_root}")
    rep_dir = (reports_root / nos_id).resolve()
    if not rep_dir.is_relative_to(reports_root):
        raise ValueError(f"Reports directory escapes reports root: {rep_dir}")

    frozen_repo_rep_dir = (PROJECT_ROOT / "reports" / nos_id).resolve()
    if (
        nos_id in FROZEN_V1_NOSOLOGIES
        and (rep_dir == frozen_repo_rep_dir or rep_dir.is_relative_to(frozen_repo_rep_dir))
        and not allow_frozen_overwrite
    ):
        raise PermissionError(
            f"Замороженная нозология v1.x '{nos_id}' защищена от перезаписи в корневом репозитории ({rep_dir}). "
            "Для явной перезаписи укажите allow_frozen_overwrite=True или CLI-флаг --allow-frozen-overwrite."
        )
```

### CR-03: Markdown hyperlink injection via `_escape_md_cell()` injects arbitrary external `<w:hyperlink>` targets into `.docx`

**File:** `src/docx_exporter.py:235-241`, `src/docx_exporter.py:298-308`, `src/docx_exporter.py:362-369`
**Severity:** BLOCKER (Critical)
**Issue:**
`render_v2_kb_appendices_markdown()` passes arbitrary `kb_index.json` text fields (`modality`, `complication_name`, `anatomical_substrate`, `prevention_and_management`, `clinical_decision_nuances` strings) through `_escape_md_cell()` into a Markdown pipe table, which is then parsed by `_markdown_to_body_xml()` → `_render_inline_runs()`.

`_escape_md_cell()` only strips newlines and replaces `|` with `\|`; it does NOT neutralize Markdown link syntax `[label](https://...)` or inline markers (`**`, `*`, `` ` ``). Verified directly: injecting `Pain [Click](https://evil.example/phish)` into `complication_name` causes `build_executive_docx_bytes()` to emit an active `<w:hyperlink>` and an external `<Relationship Target="https://evil.example/phish" TargetMode="External"/>` in `word/_rels/document.xml.rels`, bypassing the strict PMID allowlist in `_format_pmid_links()` (`T-19-02`).

**Fix:**
Neutralize Markdown hyperlink syntax (and optionally unmatched inline markers) inside `_escape_md_cell()` so only explicitly constructed `_format_pmid_links()` cells can register external hyperlinks:

```python
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)")


def _escape_md_cell(value: Any) -> str:
    """Safely normalize an arbitrary value for inclusion inside a Markdown pipe table cell (T-19-02)."""
    if value is None:
        return "—"
    cleaned = " ".join(str(value).replace("\r\n", " ").replace("\r", " ").replace("\n", " ").split())
    if not cleaned:
        return "—"
    # Neutralize embedded Markdown links so untrusted KB text cannot inject external <w:hyperlink> rels
    cleaned = _MD_LINK_RE.sub(r"\1 (\2)", cleaned)
    return cleaned.replace("\\", r"\\").replace("|", r"\|")
```

### CR-04: `verify_all_reports()` validates only KB module count equality, allowing missing/duplicate/path-traversal `modules[].file` entries and orphaned `.md` files to pass

**File:** `src/verify_reports.py:841-860`
**Severity:** BLOCKER (Critical)
**Issue:**
Lines 841–855 check only:
```python
assert isinstance(kb_index_modules, list) and len(kb_index_modules) >= 5
...
assert len(kb_md_files) >= 5
assert len(kb_md_files) == len(kb_index_modules)
```
`verify_all_reports()` never inspects `mod.get("file")` inside `kb_index_modules`. As a result:
1. If `06_complications_and_safety.md` is missing or misspelled in `kb_index.json` while an orphaned `scratch.md` exists in `knowledge_base/` (or `kb_index.json` lists a module file twice), `len(kb_md_files) == len(kb_index_modules)` still holds and verification reports `PASSED`, while `load_nosology_bundle()` silently serves empty content `""` in `app.py` Tab 1 Mode C.
2. If `kb_index.json["modules"]` contains a path-traversal entry (e.g., `../../README.md`), `verify_all_reports()` certifies the corpus as `PASSED`, whereas `load_nosology_bundle()` (`src/universal_schema.py:766-768`) subsequently crashes `app.py` with `ValueError`.

**Fix:**
Validate every indexed module entry (`dict`, non-empty `file`, unique filename, containment within `kb_dir`, file exists on disk) and assert exact set equality against `kb_md_files`:

```python
    kb_index_modules = kb_data.get("modules", [])
    assert isinstance(kb_index_modules, list) and len(kb_index_modules) >= 5, (
        f"kb_index.json must index >= 5 modules, got "
        f"{len(kb_index_modules) if isinstance(kb_index_modules, list) else type(kb_index_modules).__name__}"
    )
    modalities_val = kb_data.get("modalities")
    assert isinstance(modalities_val, list) and len(modalities_val) >= 8, (
        "kb_index.json must include >= 8 treatment modalities"
    )

    kb_dir_resolved = kb_dir.resolve()
    indexed_md_paths: list[Path] = []
    seen_module_paths: set[Path] = set()
    for idx, mod in enumerate(kb_index_modules):
        assert isinstance(mod, dict), f"kb_index.json modules[{idx}] must be an object"
        raw_mod_file = str(mod.get("file") or "").strip()
        assert raw_mod_file, f"kb_index.json modules[{idx}] missing non-empty 'file'"
        mod_path = (kb_dir_resolved / raw_mod_file).resolve()
        if not mod_path.is_relative_to(kb_dir_resolved):
            raise ValueError(f"KB module path escapes knowledge_base dir: {raw_mod_file!r}")
        assert mod_path not in seen_module_paths, (
            f"Duplicate KB module file '{raw_mod_file}' in kb_index.json"
        )
        assert mod_path.exists() and mod_path.is_file(), (
            f"Indexed KB module file not found on disk: {mod_path}"
        )
        seen_module_paths.add(mod_path)
        indexed_md_paths.append(mod_path)

    kb_md_files = sorted(kb_dir.glob("*.md"))
    disk_md_set = {p.resolve() for p in kb_md_files}
    assert len(kb_md_files) >= 5, (
        f"Expected >= 5 KB Markdown files for '{nos_id}', found {len(kb_md_files)}"
    )
    assert seen_module_paths == disk_md_set, (
        f"KB module mismatch for '{nos_id}': "
        f"missing_on_disk={sorted(p.name for p in seen_module_paths - disk_md_set)}, "
        f"orphaned_on_disk={sorted(p.name for p in disk_md_set - seen_module_paths)}"
    )
```

## Warnings

### WR-01: Unhandled `NaN`/`inf` (`ValueError`/`OverflowError`) and non-list `kb_index` values (`TypeError`) crash `docx_exporter` and `app.py`

**File:** `src/docx_exporter.py:727-738`, `src/docx_exporter.py:764-776`, `src/docx_exporter.py:803-842`, `src/docx_exporter.py:870-873`, `app.py:449-450`, `app.py:718-726`
**Severity:** WARNING
**Issue:**
Verified directly with malformed inputs:
1. In `src/docx_exporter.py:837-842`, `isinstance(float("nan"), (int, float))` is `True`, so `int(n_val)` raises `ValueError: cannot convert float NaN to integer` (and `OverflowError` for `inf`). Likewise `frequency_median_num = float("nan")` renders literal `"nan%"` instead of falling back cleanly.
2. In `src/docx_exporter.py:764-776` and `app.py:449-450, 718-726`, `[x for x in (kb.get("frequent_complications") or []) if isinstance(x, dict)]` assumes any truthy value is iterable. Passing a non-list scalar (e.g., `123` or `True`) returns `True` from `is_v2_kb_index()` and then crashes with `TypeError: 'int' object is not iterable`.

**Fix:**
Add `import math` in `src/docx_exporter.py`, guard numeric formatting with `math.isfinite(float(...))`, and add a small helper `_dict_list(val: Any) -> list[dict[str, Any]]` (returning `[x for x in val if isinstance(x, dict)]` only when `isinstance(val, list)`) in both `src/docx_exporter.py` and `app.py` (and check `isinstance(..., list)` inside `is_v2_kb_index()`):

```python
def _dict_list(value: Any) -> List[Dict[str, Any]]:
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []

def _is_finite_number(value: Any) -> bool:
    return (
        value is not None
        and not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )
```

### WR-02: `Clavien–Dindo` / Red Flags severity classifier has false positives (`II (IV antibiotics)`, generic chapter headings) and misses valid grades (`IIIb.`, `IV:`, `IIIB`, Russian `Клавьен–Диндо`)

**File:** `src/docx_exporter.py:56-65`, `src/docx_exporter.py:388-411`, `src/docx_exporter.py:606-609`
**Severity:** WARNING
**Issue:**
Verified directly against `_classify_row_severity()` and `_RED_FLAG_HEADING_RE`:
1. **False positive on intravenous (`IV`) therapy in Clavien–Dindo column:** A Grade II row `"II (IV antibiotics)"` in a column matching `clavien|клавьен` matches `_CD_CRITICAL_CELL_RE` on `"IV"` and is falsely painted Critical Red (`FEE2E2`/`FECACA`).
2. **False positive on broad chapter headings:** `_RED_FLAG_HEADING_RE` matches bare `"критические осложнения"` — any general chapter heading such as `## 4. Частые и критические осложнения лечения` sets `is_red_flag_table=True` and paints *every* row (including mild Grade I/II rows) of a subsequent general complications table solid Critical Red.
3. **Missed valid severe/critical grades:**
   - `"IIIb."`, `"IV: ICU"` fail because `.` and `:` are absent from the right-boundary class `(?:$|[\s)/,;–—-])`.
   - Uppercase `"IIIB"`, `"IVA"`, `"IVB"` fail because `b`/`ab` are lowercase-only.
   - `_CD_INLINE_CONTEXT_RE` misses Russian `"Клавьен–Диндо IV"`, `"Clavien–Dindo класс IV"`, `"Clavien–Dindo (IV)"`, and ranges like `"Clavien–Dindo IIIa–IV"`.

**Fix:**
Tighten `_RED_FLAG_HEADING_RE`, exclude intravenous `IV` phrasing, and widen punctuation/case/Russian matching:

```python
_RED_FLAG_HEADING_RE = re.compile(
    r"красные\s+флаги|red\s+flags|редкие\s+критические\s+осложнения",
    re.IGNORECASE,
)
_IV_THERAPY_RE = re.compile(
    r"\bIV\s+(?:antibiotic\w*|infusion\w*|fluid\w*|therap\w*|steroid\w*|analges\w*|drug\w*|med\w*|abx)\b",
    re.IGNORECASE,
)
_CD_CRITICAL_CELL_RE = re.compile(r"(?:^|[\s(/–—-])(IV[aAbB]?|V)(?:$|[\s)/,;.:–—-])")
_CD_SEVERE_CELL_RE = re.compile(r"(?:^|[\s(/–—-])(III[bB])(?:$|[\s)/,;.:–—-])")
_CD_INLINE_CONTEXT_RE = re.compile(
    r"(?:Clavien[–—\-\s]*Dindo|Клавьен[–—\-\s]*Диндо)\s*"
    r"(?:(?:Grade|класс|степен[ьи])\s*)?\(?"
    r"(?:(?:I{1,3}[aAbB]?|IV[aAbB]?)\s*[–—-]\s*)?"
    r"(III[bB]|IV[aAbB]?|V)\b"
)
# Inside _classify_row_severity(), before applying _CD_CRITICAL_CELL_RE:
clean = _IV_THERAPY_RE.sub("", re.sub(r"[*_`]", "", padded_row[cd_col_idx])).strip()
```

### WR-03: `_split_table_row()` misparses backslashes preceding pipe delimiters (`|foo\\|bar|`, `|A|B\|`)

**File:** `src/docx_exporter.py:362-379`
**Severity:** WARNING
**Issue:**
`_split_table_row()` uses `not stripped.endswith(r"\|")` and `re.split(r"(?<!\\)\|", stripped)`, checking only a single preceding backslash. Verified directly:
- `|foo\\|bar|` (even backslash count before column separator `|`) splits into `['foo\\|bar']` (merges two columns).
- `|A|B\|` (cell ending with literal `\` before closing pipe) parses as `['A', 'B|']` (corrupts trailing backslash into `|`).
- `_escape_md_cell("A\\")` followed immediately by `|C|` without spaces (`|A\|C|`) merges into `['A|C']`.

**Fix:**
Escape `\` as `\\` in `_escape_md_cell()` (as shown in `CR-03`) and replace regex lookbehind splitting in `_split_table_row()` with a single-pass scanner that handles `\\` and `\|` unambiguously:

```python
def _split_table_row(line: str) -> List[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    cells: List[str] = []
    buf: List[str] = []
    i = 0
    n = len(s)
    ended_with_unescaped_pipe = False
    while i < n:
        ch = s[i]
        if ch == "\\" and i + 1 < n and s[i + 1] in ("|", "\\"):
            buf.append(s[i + 1])
            i += 2
            continue
        if ch == "|":
            cells.append("".join(buf).strip())
            buf = []
            if i == n - 1:
                ended_with_unescaped_pipe = True
            i += 1
            continue
        buf.append(ch)
        i += 1
    if not ended_with_unescaped_pipe:
        cells.append("".join(buf).strip())
    return cells
```

### WR-04: `INFO_SEARCHER_ROOT` unconditionally overrides explicit `monkeypatch.setattr(universal_schema, "CONFIGS_DIR" / "DATA_DIR" / "REPORTS_DIR", ...)`

**File:** `src/universal_schema.py:49-83`
**Severity:** WARNING
**Issue:**
`_get_configs_dir()`, `_get_data_dir()`, and `_get_reports_dir()` check `os.environ.get("INFO_SEARCHER_ROOT")` *before* checking the module globals `CONFIGS_DIR`, `DATA_DIR`, and `REPORTS_DIR`. If `INFO_SEARCHER_ROOT` happens to be set in a developer shell or CI environment, existing tests that isolate directories via `monkeypatch.setattr(universal_schema, "CONFIGS_DIR", tmp_path)` (`tests/test_phase17_complications.py:1281, 1625` and `tests/test_phase18_humanizer.py:751-753`) silently ignore the monkeypatch and read/write `$INFO_SEARCHER_ROOT` instead of `tmp_path`.

**Fix:**
Check whether the module-level constant was overridden before applying `INFO_SEARCHER_ROOT`:

```python
_DEFAULT_CONFIGS_DIR = PROJECT_ROOT / "configs"
_DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
_DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports"

CONFIGS_DIR = _DEFAULT_CONFIGS_DIR
DATA_DIR = _DEFAULT_DATA_DIR
REPORTS_DIR = _DEFAULT_REPORTS_DIR


def _get_configs_dir() -> Path:
    if CONFIGS_DIR != _DEFAULT_CONFIGS_DIR:
        return CONFIGS_DIR
    env_root = os.environ.get("INFO_SEARCHER_ROOT", "").strip()
    return (Path(env_root).resolve() / "configs") if env_root else CONFIGS_DIR


def _get_data_dir() -> Path:
    if DATA_DIR != _DEFAULT_DATA_DIR:
        return DATA_DIR
    env_root = os.environ.get("INFO_SEARCHER_ROOT", "").strip()
    return (Path(env_root).resolve() / "data") if env_root else DATA_DIR


def _get_reports_dir() -> Path:
    if REPORTS_DIR != _DEFAULT_REPORTS_DIR:
        return REPORTS_DIR
    env_root = os.environ.get("INFO_SEARCHER_ROOT", "").strip()
    return (Path(env_root).resolve() / "reports") if env_root else REPORTS_DIR
```

### WR-05: `btn_run_verify` subprocess lacks `errors="replace"` and `OSError` handling on Windows

**File:** `app.py:1645-1668`
**Severity:** WARNING
**Issue:**
`subprocess.run(..., text=True, encoding="utf-8", shell=False, timeout=60)` does not pass `errors="replace"` and catches only `subprocess.TimeoutExpired` and `ValueError`. On Windows, if the child process crashes before `sys.stdout.reconfigure(encoding="utf-8")` or emits locale-encoded (`cp1251`/`cp866`) bytes on `stderr`, `subprocess.run()` raises an unhandled `UnicodeDecodeError` (or `OSError` if the interpreter/script is unavailable), producing a raw Streamlit traceback.

**Fix:**
Add `errors="replace"` and catch `OSError` / `UnicodeError`:

```python
                res = subprocess.run(
                    [
                        sys.executable,
                        str(PROJECT_ROOT / "src" / "verify_reports.py"),
                        "--nosology",
                        safe_nos_id,
                        "--verify",
                        "--read-only",
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    shell=False,
                    timeout=60,
                )
...
            except (ValueError, OSError, UnicodeError) as exc:
                st.error(f"Не удалось выполнить аудит verify_reports.py: {exc}")
```

### WR-06: Explicit JSON `null` values render literal `"None"` in cards, and missing `clavien_dindo_grade` silently fabricates Grade `"I"` in Subtab 2.5

**File:** `app.py:435-443`, `app.py:479-504`, `app.py:740-781`
**Severity:** WARNING
**Issue:**
1. In `_render_red_flags_block` (`app.py:435-443`) and `_render_subtab_clinical_nuances` (`app.py:740-781`), expressions like `rf.get('anatomical_substrate', '—')` and `wh.get('practical_nuances', '—')` return `None` when the key is present in JSON with value `null`, displaying literal `"None"` in clinical cards (whereas `_format_text_or_list()` at `app.py:784` already handles `None`/blank strings safely).
2. In `_render_subtab_complications` (`app.py:482-500`), missing or `null` `clavien_dindo_grade` is silently filled with `"I"`, `reversibility` with `"transient_self_limiting"`, and `event_class` with `"true_complication"`. In a clinical risk UI, missing severity metadata must be rendered as `"—"` rather than silently misclassified as the mildest grade (`I`). Also `modality`/`complication_name` do not replace `""` with `"—"` (unlike `time_window`).

**Fix:**
Use `_format_text_or_list(item.get(...))` across `_render_red_flags_block` and `_render_subtab_clinical_nuances`, and replace missing/blank complication categorical values with `"—"` in `_render_subtab_complications`:

```python
def _clean_text_series(s: pd.Series, default: str = "—") -> pd.Series:
    return s.fillna(default).astype(str).str.strip().replace("", default)

df_fc["clavien_dindo_grade"] = _clean_text_series(df_fc["clavien_dindo_grade"])
df_fc["reversibility"] = _clean_text_series(df_fc["reversibility"])
df_fc["event_class"] = _clean_text_series(df_fc["event_class"])
```

### WR-07: `tests/test_v2_engine.py` misses `_CD_CRITICAL_CELL_RE` coverage, multi-nosology `v2.0` switching, and Tab 4 negative/override paths

**File:** `tests/test_v2_engine.py:999-1055`, `tests/test_v2_engine.py:1138-1281`
**Severity:** WARNING
**Issue:**
Three test reliability/coverage gaps directly allowed defects above to pass green:
1. **Unexercised `_CD_CRITICAL_CELL_RE` (`lines 1015-1055`):** Both Grade `IV` rows and the synthetic Grade `V` row are placed exclusively inside `rare_critical_red_flags`, where `is_red_flag_table=True` short-circuits `_classify_row_severity()` before `_CD_CRITICAL_CELL_RE` (or `_CD_INLINE_CONTEXT_RE`) ever executes.
2. **Single `v2.0` nosology in `AppTest` (`lines 1138-1281`):** Because only one `v2.0` workspace is created, switching between two `v2.0` nosologies is never tested — hiding `CR-01`.
3. **Untested Tab 4 overrides and error handling:** `t4_comp_override_pm` / `t4_comp_override_epmc` saving into `complications_queries` and negative form submissions (empty ID / frozen ID yielding `st.error` without traceback) are not asserted.

**Fix:**
1. Add a Grade `IV` / `V` row to `frequent_complications` (outside the Red Flags heading) in `test_docx_exporter_v2_appendices_and_openxml_styling` to verify `_CD_CRITICAL_CELL_RE` directly.
2. Create a second `v2.0` nosology with distinct modalities/grades in `test_v2_isolated_apptest_tabs_and_configurator`, switch `sidebar_nosology_select` between them, and assert Subtab `2.5` retains 2 Plotly charts + dataframe rows and Tab `3.5` shows all non-casuistry rows of the second nosology.
3. Submit Tab 4 with non-empty `t4_comp_override_pm`/`t4_comp_override_epmc` (verifying `complications_queries` in YAML) and with empty/invalid ID (verifying `len(at.exception) == 0` and `len(t4.error) >= 1`).

## Info

### IN-01: `save_new_nosology_config()` migrates whitespace-only legacy `openalex` / `clinicaltrials` strings

**File:** `src/universal_schema.py:1197-1204`
**Issue:** `legacy_openalex not in (None, "")` evaluates `True` for whitespace-only `"   "`, copying blank whitespace into `openalex_search` / `clinical_trials_condition`.
**Fix:** Check `str(legacy_openalex or "").strip()` (and store the stripped string) before assigning `openalex_search` / `clinical_trials_condition`.

### IN-02: `docx_exporter.py` CLI `--nosology all` frozen check is case-sensitive and ignores `INFO_SEARCHER_ROOT`

**File:** `src/docx_exporter.py:989`, `src/docx_exporter.py:1052-1066`
**Issue:** On Windows case-insensitive filesystems, a config named `PROM.yaml` fails `slug in FROZEN_V1_NOSOLOGIES` in the CLI `--nosology all` skip check (line 1061) and aborts the batch loop with `PermissionError`. Additionally, CLI `root_dir` hardcodes `PROJECT_ROOT` instead of honoring `INFO_SEARCHER_ROOT` like `universal_schema.py` and `verify_reports.py`.
**Fix:** Use `slug.lower() in FROZEN_V1_NOSOLOGIES` at line 1061 and resolve `root_dir` via `os.environ.get("INFO_SEARCHER_ROOT")` when set.

### IN-03: Redundant exception handler in Tab 4 form submission

**File:** `app.py:1807-1810`
**Issue:** `except (ValueError, PermissionError) as exc:` and `except Exception as exc:` execute the exact same body (`st.error(f"Ошибка сохранения: {exc}")`).
**Fix:** Consolidate into a single handler or differentiate user validation errors from unexpected I/O failures.

### IN-04: `query_complications_df()` builds `pubmed_url` and `doi_url` without PMID regex or DOI prefix normalization

**File:** `src/universal_schema.py:1160-1165`
**Issue:** Unlike `_format_pmid_links_md()` (`app.py:97`), `query_complications_df()` interpolates raw `pmid` without validating `^[1-9]\d{0,8}$` and prepends `https://doi.org/` even if `doi` already begins with `https://doi.org/`, which can produce malformed URLs in Tab 3 Option 5 `LinkColumn`.
**Fix:** Validate `pmid` with `_PMID_STR_RE.fullmatch(pid)` and strip any leading `https?://doi.org/` / `doi:` prefix before constructing `doi_url`.

### IN-05: Frozen `v1.x` `git status` check in `tests/test_v2_engine.py` omits the 3 frozen YAML configs

**File:** `tests/test_v2_engine.py:1453-1470`
**Issue:** `_snapshot_frozen_v1_tree()` hashes `configs/{prom,metroplasty_pregnancy,trigger_finger}.yaml`, but the final `git status --porcelain` check passes only the 6 `data/` and `reports/` directories.
**Fix:** Include `"configs/prom.yaml"`, `"configs/metroplasty_pregnancy.yaml"`, and `"configs/trigger_finger.yaml"` in the `git status --porcelain` argument list for full symmetry.

### IN-06: CSV export (`dataframe_to_csv_bytes`) does not neutralize leading `=`, `@`, `\t`, `\r` formula prefixes

**File:** `src/universal_schema.py:953-955`, `app.py:705`, `app.py:1625`
**Issue:** Threat `T-19-04` explicitly accepts leading `+`/`-` for clinical deltas/angles on local trusted SQLite/KB data, so this is non-blocking; however, leading `=`, `@`, `\t`, `\r` are never legitimate clinical prefixes and could trigger Excel formula evaluation if exported `.csv` files are shared externally.
**Fix:** Optionally prefix string cells starting with `("=", "@", "\t", "\r")` with a leading `'` inside `dataframe_to_csv_bytes()` while leaving `+`/`-` untouched.

---

_Reviewed: 2026-11-22T09:00:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
