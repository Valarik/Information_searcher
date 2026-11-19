---
phase: 17-prisma
reviewed: 2026-11-19T17:06:06Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - src/schema.py
  - src/extractor_common.py
  - src/universal_schema.py
  - src/harvester.py
  - src/triage.py
  - tests/test_phase17_complications.py
findings:
  critical: 5
  warning: 9
  info: 5
  total: 19
status: issues_found
---

# Phase 17: Code Review Report

**Reviewed:** 2026-11-19T17:06:06Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Adversarial review of Phase 17 (`17-prisma`, commits `a302217..HEAD`) covering `src/schema.py`, `src/extractor_common.py`, `src/universal_schema.py`, `src/harvester.py`, `src/triage.py`, and `tests/test_phase17_complications.py` against `COMP-01..COMP-04`, `D-01..D-09`, and threat controls `T-17-01..T-17-05`.

`src/schema.py` is clean and idempotent, parameterized SQL (`?`) is used consistently across new CRUD queries, `PMCID_RE` path-traversal protection in `src/triage.py` is intact, and all 10 tests in `tests/test_phase17_complications.py` currently pass. However, adversarial testing and cross-file inspection uncovered **5 Critical (BLOCKER)** defects and **9 Warnings (WARNING)** that must be addressed before shipping:

1. **Path traversal via unvalidated YAML `nosology_id`** in `src/harvester.py` and `src/triage.py` (violating Trust Boundary `T-17-03`).
2. **Read-only SQLite bypass** in `src/universal_schema.py:_connect_sqlite_readonly()` due to missing URI percent-encoding and a silent fallback to unrestricted read-write `sqlite3.connect()` (violating `T-17-02` / `D-09`).
3. **Silent batch drop and permanent cache poisoning** in `src/harvester.py:harvest_pubmed_complications()` when `pubmed_api.py` returns `{"error": ...}` dicts on transient HTTP/XML failures.
4. **Severe clinical severity misclassification** in `src/extractor_common.py:extract_clavien_dindo_grade()` and `normalize_clavien_dindo()`, which parse CTCAE version numbers (`CTCAE 4.0`, `NCI-CTCAE 5.0`) as `Grade IV` (life-threatening) / `Grade V` (patient death).
5. **Multiple contract bypasses and a `NaN` crash** in `src/universal_schema.py:validate_kb_complications_v2()`, which passes `NaN` rates, `> 100%` medians, empty `modality`, and `[None]` PMIDs.

Additional warnings affect Tier 2->Tier 4 false demotion in `src/triage.py`, AMA/JAMA-style `95% CI` leaks in `extract_complication_frequency()`, `article_id`-linked row loss in `aggregate_complications_from_sqlite()`, dropped `pubmed_max_results`/`europepmc_max_results` in `save_new_nosology_config()`, false rejection of partial nerve/tendon injuries in `is_excluded_recurrence_event()`, JATS `"Patient Safety"` misrouting, and a flaky `git status` scope in the regression test.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Unvalidated YAML `nosology_id` enables path traversal in `harvester.py`, `triage.py`, and `universal_schema.py`

**Severity:** Critical (BLOCKER)
**File:** `src/harvester.py:927-934`, `src/triage.py:908-925` (also `src/universal_schema.py:146-148`)
**Issue:** While `save_new_nosology_config()` enforces `re.fullmatch(r"[a-z0-9_]+", nos_id)` and `.resolve()` parent containment (`T-17-05`), `harvester.py:main()` and `triage.py:main()` read `nosology_id` directly from external/user-authored YAML configs (`cfg.get("nosology_id") or (cfg.get("nosology") or {}).get("id") or cfg_path.stem`) and construct `Path("data") / nosology_id` and `Path("reports") / nosology_id / "prisma_stats.md"` with zero validation. A crafted YAML specifying `nosology_id: "../../outside"` causes `raw_dir.mkdir(parents=True, exist_ok=True)`, `init_db(db_path)`, cache writes (`pubmed_complications.json`, `europepmc_complications.json`), XML downloads, and `report_path.write_text(...)` to write outside `data/` and `reports/`, violating Trust Boundary `T-17-03`. Similarly, `discover_nosologies()` (`src/universal_schema.py:146-148`) joins unvalidated `nos_id` into `DATA_DIR / nos_id` and `REPORTS_DIR / nos_id`.
**Fix:**
```python
NOSOLOGY_ID_RE = re.compile(r"^[a-z0-9_]+$")

def _validate_nosology_id(raw_id: Any) -> str:
    nos_id = str(raw_id or "").strip().lower()
    if not NOSOLOGY_ID_RE.fullmatch(nos_id):
        raise ValueError(f"Invalid nosology_id {raw_id!r}: must match ^[a-z0-9_]+$")
    return nos_id

# In harvester.py:main() and triage.py:main():
nosology_id = _validate_nosology_id(
    cfg.get("nosology_id") or (cfg.get("nosology") or {}).get("id") or cfg_path.stem
)
base_data = Path("data").resolve()
data_dir = (base_data / nosology_id).resolve()
if not data_dir.is_relative_to(base_data):
    raise ValueError(f"Path traversal blocked for nosology_id={nosology_id!r}")
```

### CR-02: `_connect_sqlite_readonly()` lacks URI percent-encoding and silently falls back to read-write mode, bypassing `T-17-02`

**Severity:** Critical (BLOCKER)
**File:** `src/universal_schema.py:124-132`
**Issue:** `_connect_sqlite_readonly()` builds `f"file:{resolved.as_posix()}?mode=ro"` without URI-encoding reserved characters (`#`, `?`, `%`). When `sqlite3.connect(..., uri=True)` raises `sqlite3.OperationalError` — for example, when any parent directory contains `#`, `?`, or `%`, or when opening a WAL-mode database where `-shm` cannot be created in read-only mode — lines 129–130 silently fall back to `sqlite3.connect(str(db_path))` in unrestricted **read-write** mode without `PRAGMA query_only = ON`. Verified empirically: opening a DB under a `proj#1_` directory returned a writable connection where `CREATE TABLE` succeeded. On frozen `v1.x` databases (`prom`, `metroplasty_pregnancy`, `trigger_finger`), a silent RW fallback can trigger WAL recovery/sidecar creation and mutate `literature.db`, defeating `T-17-02` and `D-09`.
**Fix:**
```python
from urllib.parse import quote

def _connect_sqlite_readonly(db_path: Path) -> sqlite3.Connection:
    """Open an existing SQLite DB strictly read-only without mutating disk files (T-17-02, D-09)."""
    resolved = db_path.resolve()
    encoded_path = quote(resolved.as_posix(), safe="/:")
    try:
        conn = sqlite3.connect(f"file:{encoded_path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        # Read-only fallback for read-only media / uncheckpointed WAL without ever opening RW
        conn = sqlite3.connect(f"file:{encoded_path}?mode=ro&immutable=1", uri=True)
    conn.execute("PRAGMA query_only = ON;")
    conn.row_factory = sqlite3.Row
    return conn
```

### CR-03: `harvest_pubmed_complications()` ignores `pubmed_api.py` error dicts, silently dropping 180-article batches and poisoning `pubmed_complications.json`

**Severity:** Critical (BLOCKER)
**File:** `src/harvester.py:750-824`
**Issue:** Verified against `pubmed_api.py` (lines 209–215 and 584–599): both `fetch_article_abstracts()` and `fetch_database_summary()` return `{"error": "...", "endpoint": "..."}` (a `dict`, not a `list`) instead of raising exceptions on HTTP 429/5xx, network errors, or malformed XML/JSON. Unlike line 741 (`search_pubmed`), `harvest_pubmed_complications()` never checks `abs_list` or `sum_list` for `"error"` — it merely gates on `if isinstance(sum_list, list):` (line 760) and `if isinstance(abs_list, list):` (line 765). On a transient NCBI error:
- If `fetch_article_abstracts` returns an error dict, all 180 records in the batch are silently lost.
- If `fetch_database_summary` returns an error dict, all `pub_types`, `pmcid`, and `lang` fields for the batch are silently stripped (breaking Tier 1/4 triage and Full-Text XML fetching).
- Line 814 then writes the truncated/empty `records` list into `pubmed_complications.json` as a permanent cache, and line 824 still reports `len(pmids)`. Every subsequent run loads the poisoned cache and never retries.
**Fix:**
```python
            abs_list = pubmed_mod.fetch_article_abstracts(batch)
            if isinstance(abs_list, dict) and "error" in abs_list:
                raise RuntimeError(f"PubMed complications efetch error (batch {b_idx + 1}): {abs_list}")
            if not isinstance(abs_list, list):
                raise RuntimeError(f"Unexpected PubMed efetch payload type: {type(abs_list).__name__}")

            sum_list = pubmed_mod.fetch_database_summary("pubmed", batch)
            if isinstance(sum_list, dict) and "error" in sum_list:
                raise RuntimeError(f"PubMed complications esummary error (batch {b_idx + 1}): {sum_list}")
            if not isinstance(sum_list, list):
                raise RuntimeError(f"Unexpected PubMed esummary payload type: {type(sum_list).__name__}")
```
Write `cache_file` atomically via a temporary file + `Path.replace()` only after all batches succeed, and similarly verify `not (isinstance(res_data, dict) and "error" in res_data)` in `harvest_europepmc_complications()` (lines 845–858).

### CR-04: `extract_clavien_dindo_grade()` and `normalize_clavien_dindo()` misclassify CTCAE version numbers (`CTCAE 4.0`, `CTCAE 5.0`, `CTCAE 3.0`) as severe/fatal complications (`IV`, `V`, `IIIa`)

**Severity:** Critical (BLOCKER)
**File:** `src/extractor_common.py:424-435`, `src/extractor_common.py:562-575`
**Issue:** Both regexes use `r"\b(?:nci[\s\-–—]*)?ctcae(?:\s+v?\d+(?:\.\d+)?)?\s*(?:grade|g)?\s*[:\-–—]?\s*([1-5])\b"` where both the version group AND `(?:grade|g)` are optional, and the `.` in `4.0` / `5.0` satisfies `\b`. Verified empirically:
- `extract_clavien_dindo_grade("Toxicities were assessed using NCI-CTCAE 5.0.")` -> `('V', 'Grade 5')` (patient death!).
- `extract_clavien_dindo_grade("Adverse events were graded according to CTCAE 4.0 criteria.")` -> `('IV', 'Grade 4')` (life-threatening!).
- `extract_clavien_dindo_grade("Adverse events graded by CTCAE 3.0.")` -> `('IIIa', 'Grade 3')`.
- `normalize_clavien_dindo("CTCAE 5.0")` -> `('V', 'Grade 5')`.

Because standard medical abstracts routinely cite the methodology version (`CTCAE 4.0`, `CTCAE 5.0`) in Methods without stating a grade in that clause, this silently fabricates fatal Grade V / life-threatening Grade IV complication rows.
**Fix:**
```python
# Require an explicit grade keyword (grade/gr/g) when extracting from free text,
# and forbid matching version decimals such as 4.0 / 5.0 via negative lookahead (?!\.\d):
_CTCAE_FREE_TEXT_RE = re.compile(
    r"\b(?:nci[\s\-–—]*)?ctcae(?:\s+v?\d+(?:\.\d+)?)?\s*"
    r"(?:grade|gr\.?|g)\s*[:\-–—]?\s*([1-5])(?!\.\d)\b",
    flags=re.IGNORECASE,
)
# In normalize_clavien_dindo() inline CTCAE branch, also reject version-only strings:
m_inline_ctcae = re.fullmatch(
    r"(?:nci[\s\-–—]*)?ctcae(?:\s+v?\d+(?:\.\d+)?)?\s*"
    r"(?:(?:grade|gr\.?|g)\s*[:\-–—]?|[:\-–—])\s*([1-5])(?!\.\d)",
    grade_str,
    flags=re.IGNORECASE,
)
```

### CR-05: `validate_kb_complications_v2()` passes `NaN`, `> 100%` medians, empty `modality`, and `[None]` PMIDs, and crashes on `NaN` `sample_size_total`

**Severity:** Critical (BLOCKER)
**File:** `src/universal_schema.py:1060-1155`
**Issue:** Verified empirically: passing a malformed KB containing `modality: ""`, `frequency_median_num: float("nan")`, `frequency_median_num: 250.0`, `frequency_max_num: float("nan")`, and `evidence_pmids: [None]` returns `[]` (zero validation errors):
1. Lines 1113 and 1153 check `any(str(p).strip() for p in pmids)` without `p is not None` — `str(None).strip()` is `"None"` (truthy), so `[None]` passes.
2. Lines 1093, 1099, and 1147 do not guard with `math.isfinite(...)`, so `float("nan")` makes `< 1.0`, `>= 1.0`, `< 0.0`, and `med_val > last_median_by_modality[mod]` all evaluate `False`.
3. `frequency_median_num` has no `<= 100.0` upper bound (accepts `250.0` or `inf`).
4. Empty `modality` is never flagged in either `frequent_complications` or `rare_critical_red_flags`, and on line 1098 `if mod:` silently skips the descending-sort check.
5. On line 1107, `int(n_raw)` raises an unhandled `ValueError` / `OverflowError` if `sample_size_total` is `float("nan")` or `float("inf")` instead of appending an error.
**Fix:**
```python
import math

# Inside frequent_complications loop:
mod = str(entry.get("modality") or "").strip()
if not mod:
    errors.append(f"frequent_complications[{idx}] has empty modality")

med_raw = entry.get("frequency_median_num")
if isinstance(med_raw, bool) or not isinstance(med_raw, (int, float)) or not math.isfinite(float(med_raw)):
    errors.append(f"frequent_complications[{idx}] frequency_median_num must be a finite number")
else:
    med_val = float(med_raw)
    if med_val < 1.0 or med_val > 100.0:
        errors.append(
            f"frequent_complications[{idx}] frequency_median_num must be in [1.0, 100.0], got {med_val}"
        )
    elif mod:
        mod_key = mod.lower()
        if mod_key in last_median_by_modality and med_val > last_median_by_modality[mod_key]:
            errors.append(
                f"frequent_complications[{idx}] for modality '{mod}' is not sorted descending "
                f"by frequency_median_num ({med_val} > {last_median_by_modality[mod_key]})"
            )
        last_median_by_modality[mod_key] = med_val

n_raw = entry.get("sample_size_total")
if (
    isinstance(n_raw, bool)
    or not isinstance(n_raw, (int, float))
    or not math.isfinite(float(n_raw))
    or int(n_raw) < 20
):
    errors.append(f"frequent_complications[{idx}] sample_size_total must be finite and >= 20, got {n_raw!r}")

pmids = entry.get("evidence_pmids")
if not isinstance(pmids, list) or not any(p is not None and str(p).strip() for p in pmids):
    errors.append(f"frequent_complications[{idx}] evidence_pmids must be a non-empty list")
```
Apply the same `math.isfinite`, non-empty `modality`, and `p is not None` checks in the `rare_critical_red_flags` loop (lines 1120–1155).

---

## Warnings

### WR-01: `classify_evidence_tier()` falsely demotes Tier 2 multicenter/prospective cohorts to Tier 4 `rare_catastrophic_case` on arm counts (`"2 procedures"`) or event numerators (`"1 patient"`)

**Severity:** Warning (WARNING)
**File:** `src/triage.py:195-200`, `src/triage.py:452-496`
**Issue:** `CLINICAL_SAMPLE_SIZE_PATTERNS[3]` (line 199) matches `procedures?|operations?|releases?|interventions?`, and the `1 <= eff_n < 20` demotion check (lines 453–456) executes *before* `tier2_pt_markers` (`"multicenter study"`, `"comparative study"`, `"clinical trial, phase ii/iii/iv"`) and `tier2_text_markers` (`"prospective cohort"`, `"national registry"`, `"population-based"`). Verified empirically:
- A `['Multicenter Study', 'Comparative Study']` comparing `"2 procedures"` across 4 hospitals at 5-year follow-up is demoted to `(4, ['Multicenter Study', 'Comparative Study', 'rare_catastrophic_case'])`.
- A prospective cohort (`['Observational Study']`) whose abstract omits total cohort N in digits but reports `"Two patients developed superficial wound infection and 1 patient had transient paresthesia"` is demoted to `(4, ['Observational Study', 'rare_catastrophic_case'])`.

This removes genuine Tier 2 cohorts from the Tier 1–3 XML download priority queue (`D-06`) and from `frequent_complications` aggregation (`D-04`).
**Fix:** Remove comparative arm nouns (`procedures?`, `operations?`, `releases?`, `interventions?`) from `CLINICAL_SAMPLE_SIZE_PATTERNS` unless preceded by total-sample framing (`total of N`, `series of N`, `N consecutive`), and guard small-N demotion so PubMed-indexed `Multicenter Study`, `Clinical Trial, Phase II/III/IV`, `national registry`, and `population-based` studies are not demoted by an incidental event-numerator match (`"1 patient"`).

### WR-02: `extract_complication_frequency()` leaks comma-delimited / `%`-bound `95% CI` clauses and aborts on first invalid match

**Severity:** Warning (WARNING)
**File:** `src/extractor_common.py:475-536`
**Issue:** The unparenthesized CI-stripping regex on lines 504–510 only accepts `[:=]?` after `CI` and omits `%?` after the first bound, and does not strip bracketed `[95% CI ...]` clauses. Verified empirically:
- `"Rate was 12.5%, 95% CI, 8.1–17.2%"` returns `("8.1–17.2%", 12.65, None)` — branch `(c)` matches the unstripped AMA/JAMA-style CI and overrides the actual `12.5%` complication rate.
- `"Wound infection 95% CI, 10.2–28.1%"` returns `("10.2–28.1%", 19.15, None)` instead of `(None, None, None)`.
- `"95% CI 10.2% to 28.1%"` returns `("10.2%", 10.2, None)`.

Additionally, branches `(a)`, `(b)`, and `(c)` use `re.search` instead of `re.finditer`, so an invalid first hit (e.g., `num > denom` or `lo > hi`) prevents checking subsequent valid matches in the same text.
**Fix:**
```python
    cleaned = re.sub(
        r"[\(\[]\s*(?:90|95|99)\s*%\s*(?:CI|ДИ|confidence\s+interval)[^\)\]]*[\)\]]",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:90|95|99)\s*%\s*(?:CI|ДИ|confidence\s+interval)\s*[,;:=]?\s*"
        r"\d+(?:[.,]\d+)?\s*%?\s*(?:–|-|—|to|,)\s*\d+(?:[.,]\d+)?\s*%?",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
```
Use `for m in re.finditer(...):` in branches `(a)`, `(b)`, and `(c)` so invalid early matches do not shadow later valid rates.

### WR-03: `aggregate_complications_from_sqlite()` silently drops `article_id`-linked rows lacking redundant `c.evidence_tier`/`c.pmid`, drops qualitative Tier 1–3 rows, and writes median into `frequency_max_num`

**Severity:** Warning (WARNING)
**File:** `src/universal_schema.py:248-277`, `src/universal_schema.py:322-358`, `src/universal_schema.py:407`, `src/universal_schema.py:445-450`
**Issue:**
1. When joining `articles a`, the `SELECT` pulls raw `c.evidence_tier` and `c.pmid` instead of `COALESCE(c.evidence_tier, a.evidence_tier)` and `COALESCE(c.pmid, a.pmid)`. Verified empirically: a valid complication row linked via `article_id` to an included Tier 2 article (`pmid='88888888'`) with `c.evidence_tier = None` is silently dropped (`([], [])`), and `c.pmid = None` produces `evidence_pmids = []` (which fails `validate_kb_complications_v2()`).
2. Rows with `evidence_tier in (1, 2, 3)`, `sample_size >= 20`, `is_rare_casuistry == 0`, and `frequency_num IS NULL` match neither the `if` (line 348) nor the `elif` (line 356) and are silently discarded.
3. Line 407 sets `"frequency_max_num": f_max if f_max < 1.0 else med`. Verified empirically for cohorts `[0.2, 0.4, 1.5]`: it emits `frequency_pct: '0.4% (0.2–1.5%)'` alongside `frequency_max_num: 0.4`, contradicting its own field name and range string.
4. Grouping folds case via `mod.lower()` (line 291), while `frequent_complications.sort()` (line 446) uses case-sensitive `item["modality"]`, splitting `"Open release"` and `"open release"` across separate modalities.
**Fix:** Use `COALESCE(c.evidence_tier, a.evidence_tier) AS evidence_tier`, `COALESCE(c.pmid, a.pmid) AS pmid`, and `COALESCE(c.doi, a.doi) AS doi` in the joined `SELECT`; decide red-flag eligibility cleanly when `f_max >= 1.0` (e.g., report true `f_max` or classify cohorts with `med < 1.0` using a separate `frequency_median_num` / cap consistency rule documented across aggregator & validator); route qualitative severe Tier 1–3 rows instead of dropping them; and sort by `item["modality"].lower()`.

### WR-04: `save_new_nosology_config()` drops `pubmed_max_results` / `europepmc_max_results`, retains empty `complications_queries`, mutates caller input, and crashes on `{"nosology": None}`

**Severity:** Warning (WARNING)
**File:** `src/universal_schema.py:1005-1035`
**Issue:** Verified empirically:
1. Line 1031 allowlists only `("pubmed", "europepmc", "max_results")`, silently discarding `pubmed_max_results` and `europepmc_max_results` even though `src/harvester.py:136-137` explicitly consumes those keys.
2. When `complications_queries` contains only empty strings (`{"pubmed": "", "europepmc": ""}`), `cleaned_queries` is empty so `if cleaned_queries:` is `False` — leaving the uncleaned empty dict intact in the saved YAML instead of removing it.
3. Line 1007 `config_payload.setdefault("nosology", {})` returns `None` when `"nosology": None` is present, crashing on line 1008 with `AttributeError`.
4. `config_payload` is mutated in place.
**Fix:**
```python
    payload = copy.deepcopy(config_payload)
    nos_meta = payload.get("nosology")
    if not isinstance(nos_meta, dict):
        nos_meta = {}
        payload["nosology"] = nos_meta
    ...
    comp_queries = payload.get("complications_queries")
    if isinstance(comp_queries, dict):
        cleaned_queries = {
            k: v
            for k, v in comp_queries.items()
            if k in ("pubmed", "europepmc", "max_results", "pubmed_max_results", "europepmc_max_results")
            and v not in (None, "")
        }
        if cleaned_queries:
            payload["complications_queries"] = cleaned_queries
        else:
            payload.pop("complications_queries", None)
```

### WR-05: `insert_extracted_complication()` treats string `"0"`/`"false"` as truthy casuistry, lacks numeric bounds checks, and `normalize_clavien_dindo()` crashes on non-string `grade` / rejects `CTCAE-3`

**Severity:** Warning (WARNING)
**File:** `src/extractor_common.py:409-468`, `src/extractor_common.py:664-689`
**Issue:**
1. Line 676 uses `bool(record.get("is_rare_casuistry"))`. Verified empirically: passing `"0"` or `"false"` (common from CSV/form deserialization) evaluates `True` and stores `is_rare_casuistry = 1`, excluding a valid Tier 2 cohort from `frequent_complications`.
2. `frequency_num` has no finite `[0.0, 100.0]` check and `sample_size` has no `> 0` check, allowing negative rates, `> 100%`, `NaN`, or `sample_size <= 0` into SQLite.
3. Line 422 `(grade or "").strip()` raises `AttributeError` if `grade` is an `int` (e.g., `2`), whereas `ctcae_grade` coerces via `str(...)`.
4. Line 412 (`ctcae_grade` regex) omits `[:\-–—]?`, rejecting `"CTCAE-3"` and `"Grade: 3"` while line 426 (`grade`) accepts `"CTCAE-3"`.
**Fix:** Parse boolean flags via a helper treating `{"0", "false", "no", "off", ""}` as `False`; validate `0.0 <= frequency_num <= 100.0` with `math.isfinite()` and `sample_size > 0` (raising `ValueError`); normalize `grade_str = str(grade).strip() if grade is not None else ""`; and allow `[:\-–—]?` in `m_ctcae`.

### WR-06: `is_excluded_recurrence_event()` falsely rejects partial iatrogenic nerve/tendon injuries

**Severity:** Warning (WARNING)
**File:** `src/extractor_common.py:369-378`
**Issue:** Pattern `r"\bincomplete\s+(?:release|division|transection)\b"` (line 373) matches any string starting with `"incomplete transection"` or `"incomplete division"`. Verified empirically: `"Incomplete transection of radial digital nerve"` and `"Incomplete division of flexor tendon"` both return `True`, causing `insert_extracted_complication()` to reject them, `aggregate_complications_from_sqlite()` to drop them, and `validate_kb_complications_v2()` to flag them as errors — contradicting `D-08` (which classifies iatrogenic nerve/tendon injuries as `true_complication` / `rare_critical_red_flags` and excludes only technical incomplete release of the target structure).
**Fix:** Add a negative lookahead excluding anatomical injury targets:
```python
r"\bincomplete\s+(?:release|(?:division|transection)(?!\s+of\s+(?:the\s+)?(?:[\w-]+\s+){0,3}(?:nerve|artery|vessel|tendon|organ|bowel|bladder|ureter)))\b"
```

### WR-07: `parse_jats_xml()` routes `"Patient Safety"` / `"Patient Complications"` sections into `methods_text` instead of `results_text`

**Severity:** Warning (WARNING)
**File:** `src/extractor_common.py:106-127`
**Issue:** Line 106 checks `"patient"` for `methods_parts` *before* line 108 checks `"safety"`, `"complication"`, `"adverse"`, `"outcome"`, or `"morbidity"` for `results_parts`. Verified empirically: a JATS section titled `"Patient Safety and Postoperative Complications"` yields `methods_text len: 351, results_text len: 0`, hiding complication percentages from downstream readers inspecting `results_text`.
**Fix:** Check the results/safety/complications keywords (line 108) before the generic `"patient"` methods clause, or exclude safety/outcome titles from the `methods_parts` branch.

### WR-08: Top-level `surgical_focus: true` cannot override nested `nosology.surgical_focus: false`, and `discover_nosologies()` can emit contradictory metadata

**Severity:** Warning (WARNING)
**File:** `src/harvester.py:72-83`, `src/universal_schema.py:150-162`, `src/universal_schema.py:1013-1025`
**Issue:** Both `resolve_treatment_profile()` and `discover_nosologies()` test `if "surgical_focus" in cfg and cfg["surgical_focus"] is False:` and then independently test `if "surgical_focus" in meta and meta["surgical_focus"] is False:`. Consequently, an explicit top-level `surgical_focus: true` is ignored when `nosology.surgical_focus: false` exists. Furthermore, if a YAML sets `treatment_profile: mixed` and `surgical_focus: false`, `discover_nosologies()` returns `{"treatment_profile": "mixed", "surgical_focus": False}`, diverging from `resolve_treatment_profile()` (`"conservative"`).
**Fix:** Resolve `surgical_focus` with proper precedence (`cfg["surgical_focus"]` if `"surgical_focus" in cfg` else `meta.get("surgical_focus")`) in a single shared helper imported by both `harvester.py` and `universal_schema.py`.

### WR-09: `test_v1_backward_compat_prom_metroplasty_trigger_finger_readonly()` checks all of `data/` and `reports/` via `git status`, making the test flaky during active `v2.0` work

**Severity:** Warning (WARNING)
**File:** `tests/test_phase17_complications.py:1380-1388`
**Issue:** `git status --porcelain data/ reports/` asserts that no file anywhere in `data/` or `reports/` is modified or untracked. While valid in a clean repo right after Phase 17, any uncommitted work on a future `v2.0` nosology under `data/<new_id>/` or `reports/<new_id>/` will cause this frozen-`v1.x` regression test to fail spuriously even though `prom`, `metroplasty_pregnancy`, and `trigger_finger` are untouched.
**Fix:** Restrict the `git status` arguments explicitly to the three frozen `v1.x` directories:
```python
    git_res = subprocess.run(
        [
            "git", "status", "--porcelain",
            "data/prom", "data/metroplasty_pregnancy", "data/trigger_finger",
            "reports/prom", "reports/metroplasty_pregnancy", "reports/trigger_finger",
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
```

---

## Info

### IN-01: `classify_evidence_tier()` omits `_append_tier4_comp_markers()` on missing-abstract Tier 4 articles

**Severity:** Info
**File:** `src/triage.py:448-450`
**Issue:** Unlike the other three Tier 4 return branches (lines 394, 410, 455), the missing/short-abstract branch returns `4, updated_types` without calling `_append_tier4_comp_markers()`, so title-only catastrophic case notes omit `rare_catastrophic_case`.
**Fix:** Call `_append_tier4_comp_markers()` before `return 4, updated_types` on line 450.

### IN-02: `build_complications_queries()` does not normalize `/` date separators for Europe PMC and overrides explicit `0` limits

**Severity:** Info
**File:** `src/harvester.py:98-99`, `src/harvester.py:125`, `src/harvester.py:134-137`
**Issue:** `start_date`/`end_date` replace `-` with `/` for PubMed (lines 117–118), but do not replace `/` with `-` for Europe PMC `FIRST_PDATE` (line 125). In addition, `explicit.get("pubmed_max_results") or ... or 800` overrides an explicit `0` with `800`, and `(explicit.get("pubmed") or "").strip()` assumes a string value.
**Fix:** Use `start_date.replace("/", "-")` / `end_date.replace("/", "-")` in `epmc_date_clause`, coerce explicit query values with `str(...)`, and use `is not None` checks for max-result overrides.

### IN-03: `generate_prisma_report()` section 3 heading hardcodes `"по 5 тематическим кластерам"`

**Severity:** Info
**File:** `src/triage.py:857`
**Issue:** When `complications_safety` is appended as a 6th cluster (lines 781–796), the rendered table has 6 rows while the heading still states `"## 3. Распределение по 5 тематическим кластерам"`.
**Fix:** Render `f"## 3. Распределение по тематическим кластерам ({len(cluster_stats)})"`.

### IN-04: `query_complications_df()` omits the `table_exists(conn, "articles")` guard used in `aggregate_complications_from_sqlite()`

**Severity:** Info
**File:** `src/universal_schema.py:958-992`
**Issue:** Unlike `aggregate_complications_from_sqlite()` (line 248), `query_complications_df()` unconditionally `LEFT JOIN`s `articles`, which fails with `OperationalError` on standalone DBs containing only `extracted_complications`.
**Fix:** Guard the join with `if table_exists(conn, "articles"):` as done in `aggregate_complications_from_sqlite()`.

### IN-05: `BASIC_SCIENCE_MARKERS` matches `"rat "` (singular with trailing space) and misses plural `"rats"`

**Severity:** Info
**File:** `src/triage.py:187`
**Issue:** `"rat "` fails to match `"in 12 Wistar rats"` (followed by `s` rather than space), potentially causing small rodent studies without `"animal model"` to be misclassified as clinical `N < 20` Tier 4 casuistry.
**Fix:** Check `re.search(r"\brats?\b", low)` in `_is_basic_science_study()`.

---

_Reviewed: 2026-11-19T17:06:06Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
