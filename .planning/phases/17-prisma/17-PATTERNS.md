# Phase 17: Сбор, PRISMA-триаж и реляционная схема частых осложнений лечения - Pattern Map

**Mapped:** 2026-11-19
**Files analyzed:** 6 (5 modified core modules, 1 new test suite)
**Analogs found:** 6 / 6 (5 exact, 1 role-match)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/schema.py` | model | CRUD | `src/schema.py` (`extracted_clinical_evidence` & `articles` DDL, lines 18-109) | exact |
| `src/extractor_common.py` | utility | transform | `src/extractor_common.py` (lines 20-183) + `src/extract_trigger_finger.py` (lines 223-261) | exact |
| `src/universal_schema.py` | service | CRUD | `src/universal_schema.py` (lines 67-290, 541-579, 640-726) | exact |
| `src/harvester.py` | service | batch | `src/harvester.py` (lines 110-413, 617-668) + `configs/trigger_finger.yaml` (lines 1-37) | exact |
| `src/triage.py` | service | batch | `src/triage.py` (lines 107-126, 145-441, 444-722) | exact |
| `tests/test_phase17_complications.py` | test | batch | `src/verify_reports.py` (lines 220-318) + `src/universal_schema.py` (lines 652-715) + `app.py` (lines 1045-1085) | role-match |

---

## Pattern Assignments

### `src/schema.py` (model, CRUD) — MODIFIED

**Analog:** `src/schema.py` (in-place extension of `init_db()` multi-statement `cur.executescript(...)`)

**Imports & connection setup pattern** (`src/schema.py`, lines 1-16):
```python
import sqlite3
from pathlib import Path


def init_db(db_path: str | Path) -> sqlite3.Connection:
    """Initialize the SQLite database for a nosology corpus and structured extraction."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;
```

**Core relational table + index DDL pattern** (`src/schema.py`, lines 45-50, 68-92):
```python
        CREATE INDEX IF NOT EXISTS idx_articles_doi ON articles(doi);
        CREATE INDEX IF NOT EXISTS idx_articles_norm_title ON articles(norm_title);
        CREATE INDEX IF NOT EXISTS idx_articles_pmcid ON articles(pmcid);
        CREATE INDEX IF NOT EXISTS idx_articles_year ON articles(pub_year);
        CREATE INDEX IF NOT EXISTS idx_articles_tier ON articles(evidence_tier);
        CREATE INDEX IF NOT EXISTS idx_articles_prisma ON articles(prisma_status);
...
        CREATE TABLE IF NOT EXISTS extracted_clinical_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER REFERENCES articles(id),
            pmid TEXT,
            doi TEXT,
            first_author_year TEXT,
            study_design TEXT,
            evidence_tier INTEGER,
            n_patients INTEGER,
            n_rays_or_joints INTEGER,
            baseline_severity TEXT,
            intervention_group TEXT,
            comparator_group TEXT,
            followup_months REAL,
            mcp_outcome TEXT,
            pip_outcome TEXT,
            recurrence_definition TEXT,
            recurrence_rate_overall TEXT,
            recurrence_rate_mcp TEXT,
            recurrence_rate_pip TEXT,
            complications_summary TEXT,
            complications_rate TEXT,
            prom_scores TEXT,
            key_conclusion TEXT
        );
```

**Commit & return pattern** (`src/schema.py`, lines 108-111):
```python
        """
    )
    conn.commit()
    return conn
```

**Phase 17 Modification Anchor (`COMP-03`, `D-07`, `D-08`):**
- Append `CREATE TABLE IF NOT EXISTS extracted_complications (...)` and `CREATE INDEX IF NOT EXISTS idx_ext_comp_article / idx_ext_comp_modality / idx_ext_comp_grade / idx_ext_comp_class` directly after `extracted_mechanisms` (before line 108 `"""`) inside `init_db()`.
- Keep `article_id INTEGER REFERENCES articles(id)`, `pmid TEXT`, `doi TEXT`, `first_author_year TEXT`, `evidence_tier INTEGER` identical to `extracted_clinical_evidence` (lines 70-75) for uniform `LEFT JOIN articles a ON c.article_id = a.id`.

---

### `src/extractor_common.py` (utility, transform) — MODIFIED

**Analogs:**
- `src/extractor_common.py` (JATS XML & regex extractors, lines 10-27, 66-183)
- `src/extract_trigger_finger.py` (parameterized SQLite insertion into `extracted_*` tables, lines 20-27, 223-261)

**Imports & SQLite WAL helper pattern** (`src/extractor_common.py`, lines 10-27):
```python
from __future__ import annotations

import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def get_db_connection(db_path: str | Path = "data/dupuytren/literature.db") -> sqlite3.Connection:
    """Open SQLite connection with WAL mode and 30-second busy timeout for safe concurrent access."""
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn
```

**Core JATS XML section & table extraction pattern** (`src/extractor_common.py`, lines 100-134):
```python
    for sec in root.findall(".//body//sec"):
        title_elem = sec.find("title")
        sec_title = _iter_text(title_elem).lower()
        sec_text = _iter_text(sec)
        if not sec_text:
            continue
        if any(k in sec_title for k in ("method", "material", "patient", "study design", "cohort", "population")):
            methods_parts.append(sec_text[:4000])
        elif any(k in sec_title for k in ("result", "finding", "outcome", "complication", "recurrence", "efficacy")):
            results_parts.append(sec_text[:5000])
        elif any(k in sec_title for k in ("discussion", "conclusion")):
            discussion_parts.append(sec_text[:3000])
...
    # Tables
    tables_out: list[str] = []
    for tw in root.findall(".//table-wrap"):
        label = _iter_text(tw.find("label"))
        caption = _iter_text(tw.find("caption"))
        rows_str: list[str] = []
        for tr in tw.findall(".//tr")[:25]:
            cells = [_iter_text(c) for c in list(tr) if c.tag in ("th", "td")]
            if cells:
                rows_str.append(" | ".join(cells))
        t_summary = f"{label}: {caption}\n" + "\n".join(rows_str[:15])
        if t_summary.strip():
            tables_out.append(t_summary[:2500])
```

**Core regex numeric extraction & guard pattern** (`src/extractor_common.py`, lines 137-162):
```python
def extract_sample_size(text: str) -> tuple[int | None, int | None, str]:
    """Extract (n_patients, n_rays_or_joints, sample_description) from abstract/results text."""
    if not text:
        return None, None, "Not specified"

    n_patients: int | None = None
    n_joints: int | None = None
    matches_desc: list[str] = []

    # Patterns for patients / cases / controls / samples
    pat_regexes = [
        r"\b(\d[\d,]{0,6})\s+(?:patients|subjects|participants|individuals|cases|men and women|adults)\b",
        r"\b(?:n|N)\s*=\s*(\d[\d,]{0,6})\s*(?:patients|cases|subjects|samples)?\b",
        r"\bcohort of\s+(\d[\d,]{0,6})\b",
        r"\b(\d[\d,]{0,6})\s+Dupuytren(?:'s)?\s+(?:patients|cases|samples|nodules|tissues)\b",
    ]
    for rgx in pat_regexes:
        for m in re.finditer(rgx, text, flags=re.IGNORECASE):
            val_str = m.group(1).replace(",", "")
            if val_str.isdigit():
                val = int(val_str)
                if 1 <= val <= 1000000 and (val < 1990 or val > 2030):
                    if n_patients is None or val > n_patients:
                        n_patients = val
                    matches_desc.append(m.group(0).strip())
```

**Parameterized SQLite row insertion pattern** (`src/extract_trigger_finger.py`, lines 223-233):
```python
        cur.execute(
            """
            INSERT INTO extracted_clinical_evidence (
                article_id, pmid, doi, first_author_year, study_design,
                evidence_tier, n_patients, n_rays_or_joints, baseline_severity,
                intervention_group, comparator_group, followup_months,
                mcp_outcome, pip_outcome, recurrence_definition,
                recurrence_rate_overall, recurrence_rate_mcp, recurrence_rate_pip,
                complications_summary, complications_rate, prom_scores, key_conclusion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
```

**Phase 17 Modification Anchors (`COMP-03`, `D-04`, `D-07`, `D-08`):**
- Extend line 108 in `parse_jats_xml()` to include safety section headers (`"adverse"`, `"safety"`, `"morbidity"`, `"side effect"`, `"sequela"`, `"harms"`).
- Add `table_exists(conn, table_name)` querying `sqlite_master` with parameterized `?`.
- Add enum constants (`VALID_CLAVIEN_DINDO`, `VALID_REVERSIBILITY`, `VALID_EVENT_CLASS`, `CTCAE_TO_CLAVIEN_MAP`), `normalize_clavien_dindo()`, `is_excluded_recurrence_event()` (`D-08` guard rejecting relapse / incomplete release), `extract_complication_frequency()` (with `(?!\s*(?:CI|ДИ|confidence))` lookahead), `extract_clavien_dindo_grade()`, `extract_resolution_time_window()`, and parameterized CRUD helpers `insert_extracted_complication()` + `fetch_extracted_complications()`.

---

### `src/universal_schema.py` (service, CRUD) — MODIFIED

**Analog:** `src/universal_schema.py` (`get_sqlite_corpus_stats`, `build_dynamic_fallback_kb`, `query_clinical_evidence_df`, `save_new_nosology_config`, `verify_universal_schema`)

**PEP 723 header & module path constants pattern** (`src/universal_schema.py`, lines 1-32):
```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pandas>=2.2.0",
#   "pyyaml>=6.0.1",
#   "markdown>=3.6",
# ]
# ///
...
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = PROJECT_ROOT / "configs"
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
```
*(Note: Add `if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))` right after line 28, matching `src/harvester.py:37` and `src/verify_reports.py:320-322`, so `from src.docx_exporter import ...` works in direct CLI execution).*

**Read-only SQLite stats pattern** (`src/universal_schema.py`, lines 98-145):
```python
def get_sqlite_corpus_stats(db_path: Path) -> dict[str, int]:
    """Read live row counts from `data/<nosology>/literature.db`."""
    stats = {
        "unique_articles": 0,
        "included_articles": 0,
        "excluded_articles": 0,
        "fulltext_xml_count": 0,
        "clinical_trials_nct": 0,
        "extracted_mechanisms_rows": 0,
        "extracted_clinical_rows": 0,
        "tier_1": 0,
        "tier_2": 0,
        "tier_3": 0,
        "tier_4": 0,
    }
    if not db_path.exists():
        return stats
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        stats["unique_articles"] = cur.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
...
    finally:
        conn.close()
    return stats
```

**SQLite -> DataFrame joined query pattern** (`src/universal_schema.py`, lines 541-579):
```python
def query_clinical_evidence_df(db_path: Path) -> pd.DataFrame:
    """Load `extracted_clinical_evidence` joined with article metadata."""
    if not db_path.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(db_path))
    try:
        df = pd.read_sql_query(
            """
            SELECT
                c.id,
                c.pmid,
                c.first_author_year,
                a.pub_year,
                c.evidence_tier,
                ...
            FROM extracted_clinical_evidence c
            LEFT JOIN articles a ON c.article_id = a.id
            ORDER BY c.evidence_tier ASC, a.pub_year DESC
            """,
            conn,
        )
    finally:
        conn.close()
    return df
```

**YAML config serializer pattern** (`src/universal_schema.py`, lines 640-649):
```python
def save_new_nosology_config(config_payload: dict[str, Any]) -> Path:
    """Save a new nosology configuration to `configs/<id>.yaml`."""
    nos_id = config_payload.get("nosology", {}).get("id", "").strip().lower()
    if not nos_id or not nos_id.replace("_", "").isalnum():
        raise ValueError("Идентификатор нозологии должен содержать только латинские буквы, цифры и '_'")
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CONFIGS_DIR / f"{nos_id}.yaml"
    yaml_str = yaml.safe_dump(config_payload, allow_unicode=True, sort_keys=False)
    out_path.write_text(yaml_str, encoding="utf-8")
    return out_path
```

**Schema validator & CLI entry pattern** (`src/universal_schema.py`, lines 652-680, 718-729):
```python
def verify_universal_schema(nosology_id: str | None = None) -> int:
    """Validate that `kb_index.json` and `universal_schema.py` satisfy D-01 and D-03."""
    if not nosology_id:
        discovered = discover_nosologies()
        nosology_id = discovered[0]["id"] if discovered else "prom"
    bundle = load_nosology_bundle(nosology_id)
    kb = bundle["kb_index"]

    missing_top = [k for k in REQUIRED_UNIVERSAL_KEYS if k not in kb]
    if missing_top:
        print(f"[FAIL] Missing top-level universal keys: {missing_top}")
        return 1
...
def main() -> int:
    parser = argparse.ArgumentParser(description="Universal Nosology Schema Adapter")
    parser.add_argument("--verify", action="store_true", help="Verify universal schema & exports")
    parser.add_argument("--nosology", default=None, help="Nosology ID")
    args = parser.parse_args()
    if args.verify:
        return verify_universal_schema(args.nosology)
    return 0
```

**Phase 17 Modification Anchors (`COMP-01`, `COMP-04`, `D-09`):**
- In `get_sqlite_corpus_stats()` (lines 100-144) and new `query_complications_df(db_path)`: check `sqlite_master` for `extracted_complications` before running `SELECT` so `v1.x` DBs (`prom`, `metroplasty_pregnancy`, `trigger_finger`) return `0` / empty `DataFrame` without calling `init_db()` or mutating disk files.
- Add `aggregate_complications_from_sqlite(db_path)` using `statistics.median()` to populate `"schema_version": "2.0"`, `"frequent_complications"` (`>= 1.0%`, `Tier 1–3`, `sample_size >= 20`, sorted descending by `frequency_median_num` within each modality), and `"rare_critical_red_flags"` (`< 1.0%`) inside `build_dynamic_fallback_kb()` (lines 147-290).
- Normalize `surgical_focus` (default `True`) and optional `complications_queries` in `discover_nosologies()` / `save_new_nosology_config()`.
- Add `validate_kb_complications_v2(kb)` and `--schema-version` (`choices=["auto", "v1", "v2"]`, default `"auto"`) to `verify_universal_schema()` and `main()`.

---

### `src/harvester.py` (service, batch) — MODIFIED

**Analogs:**
- `src/harvester.py` (`upsert_article`, `harvest_pubmed`, `harvest_europepmc`, `main`)
- `configs/trigger_finger.yaml` (dual-level YAML metadata + query block conventions, lines 1-37)

**PEP 723 header, TLS injection & skill loader pattern** (`src/harvester.py`, lines 1-10, 32-54):
```python
# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = [
#   "pyyaml",
#   "polite-http",
#   "python-dotenv",
#   "pip-system-certs",
#   "truststore",
# ]
# ///
...
import truststore
truststore.inject_into_ssl()

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.schema import init_db

SKILLS_ROOT = Path.home() / ".gemini" / "config" / "plugins" / "science" / "skills"
PUBMED_SCRIPT = SKILLS_ROOT / "pubmed_database" / "scripts" / "pubmed_api.py"
EPMC_SCRIPT = SKILLS_ROOT / "literature_search_europepmc" / "scripts" / "europepmc_api.py"
...
def load_skill_module(name: str, script_path: Path):
    spec = importlib.util.spec_from_file_location(name, str(script_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {script_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
```

**Deduplication & `sources` provenance merge pattern** (`src/harvester.py`, lines 124-138, 209-214):
```python
    existing = None
    if pmid:
        existing = cur.execute("SELECT * FROM articles WHERE pmid = ?", (pmid,)).fetchone()
    if not existing and doi:
        existing = cur.execute("SELECT * FROM articles WHERE doi = ?", (doi,)).fetchone()
    if not existing and norm_t and len(norm_t) >= 20:
        existing = cur.execute("SELECT * FROM articles WHERE norm_title = ?", (norm_t,)).fetchone()
...
    new_sources = rec.get("sources") or []
...
        try:
            old_sources = json.loads(existing["sources"] or "[]")
        except Exception:
            old_sources = []
        merged_sources = list(dict.fromkeys(old_sources + list(new_sources)))
```

**PubMed batched fetch & local JSON cache pattern** (`src/harvester.py`, lines 245-329):
```python
def harvest_pubmed(query: str, raw_dir: Path, conn: sqlite3.Connection) -> int:
    print("[1/4] Harvesting PubMed via pubmed_api.py...", flush=True)
    pubmed_mod = load_skill_module("pubmed_api", PUBMED_SCRIPT)

    pmids_file = raw_dir / "pubmed_pmids.json"
    if not pmids_file.exists():
        pmids_res = pubmed_mod.search_pubmed(query, max_results=2000, sort_by="pub_date")
        if isinstance(pmids_res, dict) and "error" in pmids_res:
            raise RuntimeError(f"PubMed search error: {pmids_res}")
        pmids_file.write_text(json.dumps(pmids_res, indent=2), encoding="utf-8")

    pmids: list[str] = json.loads(pmids_file.read_text(encoding="utf-8"))
...
    batch_size = 180
    total_batches = (len(pmids) + batch_size - 1) // batch_size

    for b_idx in range(total_batches):
        batch = pmids[b_idx * batch_size : (b_idx + 1) * batch_size]
        ...
                upsert_article(
                    conn,
                    {
                        "pmid": pmid,
                        "pmcid": pmcid,
                        "doi": doi,
                        ...
                        "sources": ["PubMed"],
                    },
                )
        conn.commit()
```

**Europe PMC core search & record normalization pattern** (`src/harvester.py`, lines 333-404):
```python
def harvest_europepmc(query: str, raw_dir: Path, conn: sqlite3.Connection) -> int:
    print("[2/4] Harvesting Europe PMC (Open Access + Preprints) via europepmc_api.py...", flush=True)
    epmc_mod = load_skill_module("europepmc_api", EPMC_SCRIPT)
...
            res_data = epmc_mod.search(
                query=query,
                max_results=1000,
                result_type="core",
                cursor=cursor,
            )
...
            upsert_article(
                conn,
                {
                    "pmid": pmid,
                    "pmcid": pmcid,
                    "doi": doi,
                    ...
                    "sources": ["EuropePMC"],
                },
            )
```

**Phase 17 Modification Anchors (`COMP-01`, `D-01`, `D-02`, `D-03`):**
- Add `resolve_treatment_profile(cfg)` (`surgical` by default; `conservative` only if `treatment_profile: conservative` or `surgical_focus: false`) and `build_complications_queries(cfg)` (uses `cfg["complications_queries"]` when present, otherwise intersects `mesh_terms` / `triage_rules.core_terms` with `SURGICAL_*_COMP_BLOCK` or `CONSERVATIVE_*_COMP_BLOCK` within `date_range`).
- Add `harvest_pubmed_complications(query, raw_dir, conn, max_results=800)` caching into single file `raw_dir / "pubmed_complications.json"` and calling `upsert_article(..., "sources": ["PubMed:Complications"])`.
- Add `harvest_europepmc_complications(query, raw_dir, conn, max_results=1000)` caching into single file `raw_dir / "europepmc_complications.json"` (never `europepmc_page_*.json`!) and calling `upsert_article(..., "sources": ["EuropePMC:Complications"])`.
- Wire both passes into `main()` (lines 632-668) with dual-level `nosology_id` lookup (`cfg.get("nosology_id") or cfg.get("nosology", {}).get("id")`).

---

### `src/triage.py` (service, batch) — MODIFIED

**Analog:** `src/triage.py` (`classify_prisma_status`, `classify_evidence_tier`, `assign_clusters`, `download_fulltexts_tier1_to_3`, `generate_prisma_report`, `main`)

**Rare complication vocabulary & PRISMA screening pattern** (`src/triage.py`, lines 107-126, 158-173):
```python
RARE_COMPLICATION_TERMS = (
    "necrosis",
    "gangrene",
    "amputation",
    "tendon rupture",
    ...
)
...
    combined = f"{title}\n{abstract or ''}".lower()

    if triage_rules:
        for rule in triage_rules.get("exclusion_rules", []):
            triggers = [t.lower() for t in rule.get("trigger_terms", [])]
            unless = [u.lower() for u in rule.get("unless_terms", [])]
            if any(t in combined for t in triggers) and not any(u in combined for u in unless):
                return rule.get("status", "excluded_custom_rule")

        core_terms = [t.lower() for t in triage_rules.get("core_terms", [])]
        ctx_terms = [t.lower() for t in triage_rules.get("context_terms", [])]
        has_core = any(t in combined for t in core_terms) if core_terms else True
        has_ctx = any(t in combined for t in ctx_terms) if ctx_terms else True
        if not has_core or not has_ctx:
            return "excluded_offtopic"
```

**Evidence Tier 1–4 classification & case-report tagging pattern** (`src/triage.py`, lines 194-245):
```python
def classify_evidence_tier(
    title: str,
    abstract: str | None,
    pub_types: list[str],
    rare_complication_terms: tuple[str, ...] | list[str] = RARE_COMPLICATION_TERMS,
) -> tuple[int, list[str]]:
    """Classify included articles into Tier 1-4 per D-05 and D-06."""
    t_lower = title.lower()
    abs_lower = (abstract or "").lower()
    combined = f"{t_lower}\n{abs_lower}"
    pt_lower = [p.lower() for p in pub_types]
    updated_types = list(pub_types)
...
    if any(m in pt_lower for m in tier4_pt_markers):
        if any(rc.lower() in combined for rc in rare_complication_terms):
            if "Rare Complication Case [D-05]" not in updated_types:
                updated_types.append("Rare Complication Case [D-05]")
        return 4, updated_types
```

**Europe PMC Full-Text XML queue & Path Traversal guard pattern** (`src/triage.py`, lines 348-406):
```python
def download_fulltexts_tier1_to_3(
    conn: sqlite3.Connection,
    fulltext_dir: Path,
    max_downloads: int = 1200,
) -> int:
    """Download open-access full-text XML from Europe PMC for Tier 1-3 articles (D-07, T-01-03)."""
    fulltext_dir.mkdir(parents=True, exist_ok=True)
    cur = conn.cursor()

    rows = cur.execute(
        """
        SELECT id, pmcid, sources, is_open_access, evidence_tier
        FROM articles
        WHERE prisma_status = 'included'
          AND evidence_tier IN (1, 2, 3, 4)
          AND pmcid IS NOT NULL
          AND pmcid != ''
        ORDER BY evidence_tier ASC, cited_by_count DESC
        """
    ).fetchall()
...
    for r in candidates:
        row_id = r["id"]
        pmcid = str(r["pmcid"]).strip()
        # T-01-03: Strict regex validation against path traversal
        if not PMCID_RE.match(pmcid):
            continue
```

**PRISMA Markdown report raw-count & cluster table pattern** (`src/triage.py`, lines 453-475, 524-541):
```python
    # Count raw records per source
    raw_pubmed = 0
    pmids_file = raw_dir / "pubmed_pmids.json"
    if pmids_file.exists():
        raw_pubmed = len(json.loads(pmids_file.read_text(encoding="utf-8")))

    raw_epmc = 0
    for f in sorted(raw_dir.glob("europepmc_page_*.json")):
        try:
            raw_epmc += len(json.loads(f.read_text(encoding="utf-8")).get("results") or [])
        except Exception:
            pass
...
    total_raw = raw_pubmed + raw_epmc + raw_oa
    total_unique = cur.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    duplicates_removed = max(0, total_raw - total_unique)
...
    clusters_cfg = cfg.get("clusters") or {}
    cluster_stats: list[tuple[str, str, int, int, int]] = []
    for c_key, c_info in clusters_cfg.items():
        c_name = c_info.get("name_ru", c_key)
        c_total = cur.execute(
            "SELECT COUNT(*) FROM articles WHERE prisma_status = 'included' AND clusters LIKE ?",
            (f'%"{c_key}"%',),
        ).fetchone()[0]
```

**Phase 17 Modification Anchors (`COMP-02`, `D-04`, `D-05`, `D-06`):**
- Add `UNIVERSAL_SURGICAL_COMPLICATION_TERMS` and `UNIVERSAL_CONSERVATIVE_ADVERSE_TERMS`.
- In `classify_prisma_status()`, accept complication terms as valid `context_terms` fallback when `core_terms` match, preventing targeted complication studies from being dropped as `excluded_offtopic`.
- In `classify_evidence_tier()`, enforce two-contour separation (`D-04`): demote clinical case series with explicitly extracted `1 <= n_patients < 20` (unless `n_joints >= 20`, `Tier 1`, or *in vitro*/*ex vivo* basic science) to `Tier 4`, and append `"rare_catastrophic_case"` (while preserving `"Rare Complication Case [D-05]"` for backward-compatible `prisma_stats.md` counters).
- Add `should_tag_complications_safety()` (`D-05`): tag `"complications_safety"` if `sources` has `PubMed:Complications`/`EuropePMC:Complications`, OR text matches universal complication terms, OR text matches `triage_rules.complication_terms` / `rare_complication_terms`. Include `sources` in `SELECT` at line 666 in `main()`.
- In `download_fulltexts_tier1_to_3()` (`D-06`), select `clusters` and update `ORDER BY` so `Tier 1–3` rows with `"complications_safety"` (or `:Complications` in `sources`) precede general `Tier 1–3` rows within `--max-xml`.
- In `generate_prisma_report()`, add `pubmed_complications.json` and `europepmc_complications.json` counts to `total_raw` (Pitfall 2) and always render the `complications_safety` row in Section 3 cluster table.

---

### `tests/test_phase17_complications.py` (test, batch) — CREATED

**Analogs:**
- `src/verify_reports.py` (SQLite integrity & schema assertion pattern, lines 233-243, 312-318)
- `src/universal_schema.py` (`verify_universal_schema` validation assertions, lines 652-715)
- `app.py` (`run_self_test` automated regression runner, lines 1045-1085)

**Schema & SQLite assertion pattern** (`src/verify_reports.py`, lines 233-243, 312-318):
```python
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    inc_cnt = cur.execute("SELECT COUNT(*) FROM articles WHERE prisma_status = 'included'").fetchone()[0]
    ct_cnt = cur.execute("SELECT COUNT(*) FROM clinical_trials").fetchone()[0]

    valid_pmids = {str(r[0]) for r in cur.execute("SELECT pmid FROM articles WHERE pmid IS NOT NULL").fetchall()}
...
    # Verify kb_index.json
    kb_json_path = kb_dir / "kb_index.json"
    assert kb_json_path.exists(), "Missing kb_index.json!"
    kb_data = json.loads(kb_json_path.read_text(encoding="utf-8"))
    assert len(kb_data.get("modules", [])) == 5, "kb_index.json must index 5 modules"
    assert len(kb_data.get("modalities", [])) >= 8, "kb_index.json must include >= 8 treatment modalities"
```

**Universal bundle & export verification pattern** (`app.py`, lines 1052-1057):
```python
    print("[1/3] Running universal schema & export verification...")
    discovered = discover_nosologies()
    active_nos = discovered[0]["id"] if discovered else "prom"
    rc = verify_universal_schema(active_nos)
    if rc != 0:
        return rc
```

**Phase 17 Test Suite Structure (`COMP-01..COMP-04`, `D-01..D-09`):**
- Bootstrap `PROJECT_ROOT` into `sys.path` at top of `tests/test_phase17_complications.py`.
- Group tests by `-k` markers from `17-RESEARCH.md` Validation Architecture:
  1. `test_harvester_*` (`COMP-01`, `D-01..D-03`): default `surgical` profile, `conservative` switch (`surgical_focus: false` / `treatment_profile: conservative`), explicit `complications_queries` override, mocked `load_skill_module` writing `pubmed_complications.json` + `europepmc_complications.json` into `tmp_path`, `upsert_article()` merging `PubMed:Complications` & `EuropePMC:Complications` into `articles.sources`.
  2. `test_triage_*` (`COMP-02`, `D-04..D-06`): 3-source `complications_safety` tagging, `Tier 4` / `N < 20` `rare_catastrophic_case` split, `download_fulltexts_tier1_to_3()` priority ordering with mocked `urllib.request.urlopen`, `generate_prisma_report()` `total_raw` and `complications_safety` row.
  3. `test_schema_and_extractor_*` (`COMP-03`, `D-07`, `D-08`): `init_db()` idempotency, `Clavien–Dindo` + `CTCAE Grade 1–5` normalization, `reversibility` & `event_class` validation, `is_excluded_recurrence_event()` blocking relapse/incomplete release, `extract_complication_frequency()` ignoring `95% CI`, JATS XML table/section parsing.
  4. `test_universal_schema_*` & `test_v1_backward_compat_*` (`COMP-04`, `D-09`): `aggregate_complications_from_sqlite()` median sorting (`>= 1.0%` vs `< 1.0%` red flags, `Tier 4` `100%` exclusion), `validate_kb_complications_v2()`, and live read-only regression on `prom`, `metroplasty_pregnancy`, `trigger_finger` verifying zero file mutation (`sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)` + mtime/table-list check).

---

## Shared Patterns

### 1. PEP 723 Inline Metadata & `PROJECT_ROOT` `sys.path` Bootstrap
**Source:** `src/harvester.py` (lines 1-10, 37-38), `src/triage.py` (lines 1-9, 36-37)
**Apply to:** `src/universal_schema.py`, `src/harvester.py`, `src/triage.py`, `tests/test_phase17_complications.py`
```python
# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = [ ... ]
# ///
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
```
*Note:* Never create a global `pyproject.toml`; run tests via `$env:PATH = "$HOME\.local\bin;" + $env:PATH; uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore pytest tests/test_phase17_complications.py -q`.

### 2. Read-Only `v1.x` Backward Compatibility Gate (`sqlite_master` Guard, ASVS V4)
**Source:** `src/universal_schema.py` (lines 98-145) + `17-RESEARCH.md` Pattern 3/4
**Apply to:** `src/extractor_common.py` (`table_exists`, `fetch_extracted_complications`), `src/universal_schema.py` (`get_sqlite_corpus_stats`, `build_dynamic_fallback_kb`, `query_complications_df`)
```python
def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None
```
*Rule:* Reader/explorer functions MUST NEVER call `init_db()` on existing `data/<id>/literature.db` files, ensuring frozen `v1.x` corpora (`prom`, `metroplasty_pregnancy`, `trigger_finger`) remain untouched on disk.

### 3. Dual-Level YAML Configuration Lookup
**Source:** `src/universal_schema.py` (lines 77-89), `configs/trigger_finger.yaml` (lines 1-25), `app.py` (lines 971-987)
**Apply to:** `src/harvester.py`, `src/triage.py`, `src/universal_schema.py`
```python
meta = cfg.get("nosology") or {}
nosology_id = cfg.get("nosology_id") or meta.get("id") or cfg_path.stem
mesh_terms = cfg.get("mesh_terms") or meta.get("mesh_terms") or []
```

### 4. Parameterized SQLite Queries & Path/YAML Sanitization (ASVS V5)
**Source:** `src/triage.py` (lines 42, 386-390), `src/universal_schema.py` (lines 74, 647)
**Apply to:** All 6 Phase 17 files
```python
PMCID_RE = re.compile(r"^PMC\d+$")
# Always use positional `?` parameters in cur.execute(...) and yaml.safe_load() / yaml.safe_dump()
```

---

## No Analog Found

All 5 modified core files (`src/schema.py`, `src/extractor_common.py`, `src/universal_schema.py`, `src/harvester.py`, `src/triage.py`) have **exact** in-file and cross-module analogs in `src/`.

| File | Role | Data Flow | Reason & Fallback Pattern |
|------|------|-----------|---------------------------|
| `tests/test_phase17_complications.py` *(pytest runner harness only)* | test | batch | `tests/` directory did not exist in `v1.x` (`Wave 0` gap; validation previously lived in CLI scripts `src/verify_reports.py`, `src/universal_schema.py --verify`, and `app.py --self-test`). Combine those assertion patterns (mapped above as `role-match`) with `pytest` `tmp_path` + `monkeypatch` fixtures specified in `17-RESEARCH.md` lines 560-589. |

---

## Metadata

**Analog search scope:** `src/*.py`, `app.py`, `configs/*.yaml`, `.agent/skills/nosology-research-pipeline/`
**Files scanned:** 10 (`src/schema.py`, `src/extractor_common.py`, `src/universal_schema.py`, `src/harvester.py`, `src/triage.py`, `src/verify_reports.py`, `src/extract_trigger_finger.py`, `app.py`, `configs/trigger_finger.yaml`, `.agent/skills/nosology-research-pipeline/SKILL.md`)
**Pattern extraction date:** 2026-11-19
