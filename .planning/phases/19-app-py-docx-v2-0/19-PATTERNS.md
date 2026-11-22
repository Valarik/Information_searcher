# Phase 19: Визуализация осложнений и клинических нюансов в app.py, экспорт .docx и автотесты v2.0 - Pattern Map

**Mapped:** 2026-11-22
**Files analyzed:** 5 (4 modified + 1 new)
**Analogs found:** 5 / 5

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app.py` | UI component / controller (Streamlit multi-tab app + `--self-test`) | request-response / read-only SQLite + JSON view / file-export | `app.py` (existing Tabs 1–4, `sub1..sub4`, `run_self_test()`) | exact (in-place extension) |
| `src/docx_exporter.py` | transform service / CLI exporter (Markdown + KB JSON → OpenXML `.docx`) | transform / file-I/O | `src/docx_exporter.py` (`_render_table_xml`, `build_docx_bytes_from_markdown_sections`, `export_nosology_docx_files`) | exact (in-place extension) |
| `src/universal_schema.py` | data-access / schema utility (optional base-dir root-override hook for isolated `AppTest`) | CRUD / read-only SQLite + YAML/JSON I/O | `src/universal_schema.py` (`CONFIGS_DIR`/`DATA_DIR`/`REPORTS_DIR`, `discover_nosologies`, `load_nosology_bundle`, `save_new_nosology_config`) + `src/verify_reports.py:get_nosology_paths(..., base_dir=...)` | exact |
| `src/verify_reports.py` | verification service / CLI linter (small compatibility update for 6-module `v2.0` KB) | batch / file-I/O | `src/verify_reports.py` (`verify_all_reports` lines 823–844) | exact (in-place fix) |
| `tests/test_v2_engine.py` | E2E + regression test suite (`v2.0` full pipeline + `AppTest` + frozen `v1.x` immutability) | batch / transform / headless UI | `tests/test_phase17_complications.py` + `tests/test_phase18_humanizer.py` + `app.py:run_self_test()` | exact |

---

## Critical Integration Pitfalls Discovered During Pattern Mapping

Before reading per-file pattern assignments, note **5 concrete codebase constraints** that would cause test or runtime failures if overlooked:

1. **PEP 723 `truststore` mismatch when `app.py` imports `src/harvester.py`:**
   - `app.py:1-10` declares PEP 723 inline dependencies: `streamlit`, `pandas`, `plotly`, `markdown`, `pyyaml` (**no `truststore`**).
   - `src/harvester.py:32-33` unconditionally runs `import truststore; truststore.inject_into_ssl()` at import time.
   - Running `uv run app.py --self-test` or `uv run streamlit run app.py` after adding `from src.harvester import build_complications_queries` will fail with `ModuleNotFoundError: No module named 'truststore'` unless `"truststore"` is added to `app.py:3-9` (or `truststore` import is made optional in `src/harvester.py:32-33`, or both).

2. **`src/verify_reports.py:830,843` hardcodes 5 KB modules (7 report files), blocking 6-module `v2.0` corpora (D-01, D-08):**
   - `src/verify_reports.py:830`: `assert len(kb_data.get("modules", [])) == 5, "kb_index.json must index 5 modules"`
   - `src/verify_reports.py:843`: `assert len(report_files) == 7, f"Expected 7 Markdown report files for '{nos_id}', found {len(report_files)}"`
   - Phase 19 D-01 & D-08 specify `v2.0` nosologies with **6** KB modules (adding `06_complications_and_safety.md`, yielding 8 total Markdown files). Meanwhile `tests/test_phase18_humanizer.py:552` builds 5 modules for its synthetic `v2.0` fixture and frozen `v1.x` corpora have 5 modules. Updating lines 830 & 843 to accept `len(kb_modules) in (5, 6)` (or `>= 5` matching actual `sorted(kb_dir.glob("*.md"))`) preserves Phase 18 & `v1.x` tests while unblocking Phase 19 D-08.

3. **Actual symbol names in `src/docx_exporter.py` differ from shorthand names in context notes:**
   - XML escaping function is `_xml_escape(text: str) -> str` (`src/docx_exporter.py:23`), NOT `_escape_xml`.
   - Table XML builder is `_render_table_xml(table_lines: List[str], rels: _RelRegistry) -> str` (`src/docx_exporter.py:333`), NOT `_build_table_xml`.
   - `<w:tblHeader/>` is **already emitted** on row 0 (`src/docx_exporter.py:364`), while `<w:cantSplit/>` and conditional severity `<w:shd>` fills are **not yet implemented**.

4. **Incomplete universal keys in Phase 18's `_build_valid_v2_kb()` vs `app.py` / `verify_universal_schema()`:**
   - `tests/test_phase18_humanizer.py:39-167` omitted `staging_and_classification`, `anatomical_or_subtype_distribution`, `etiology_and_risk_factors`, `pathogenesis_phases`, and `natural_history_and_dynamics`.
   - `universal_schema.verify_universal_schema()` (`src/universal_schema.py:1477-1490`) requires all 8 `REQUIRED_UNIVERSAL_KEYS` with minimums `stages >= 3`, `subtypes >= 3`, `factors >= 4`, `phases >= 2`, `modalities >= 8`. The Phase 19 synthetic fixture in `tests/test_v2_engine.py` MUST populate all 8 top-level keys so `verify_universal_schema`, `verify_reports`, `docx_exporter`, and `app.py` Tabs 1–4 all succeed cleanly.

5. **Streamlit `st.form` reactivity caveat for Tab 4 live query preview (D-05.1 & D-05.2):**
   - Widgets placed *inside* `with st.form("new_nosology_form"):` do not trigger reruns until `st.form_submit_button` is clicked.
   - To provide a genuine **live preview** of `harvester.build_complications_queries(...)` when switching `surgical_focus` / `treatment_profile` or editing disease terms, either place the reactive profile/term inputs outside `st.form` (or keep a live preview panel driven by reactive widgets above/alongside `st.form` and pass their values into the submit handler), and verify state transitions inside `AppTest`.

---

## Pattern Assignments

### 1. `app.py` (UI component / controller, request-response & read-only SQLite/JSON view)

**Analog:** `app.py` itself (lines 1–1094) + `src/extractor_common.py:397-409` + `src/universal_schema.py:1053-1131` + `src/harvester.py:80-157`.

#### 1.1 Header, PEP 723 dependencies, and imports (`app.py:1-55`)
```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "streamlit>=1.38.0",
#   "pandas>=2.2.0",
#   "plotly>=5.22.0",
#   "markdown>=3.6",
#   "pyyaml>=6.0.1",
# ]
# ///
...
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yaml

from src.docx_exporter import (
    build_docx_bytes_from_markdown,
    build_docx_bytes_from_markdown_sections,
)
from src.universal_schema import (
    dataframe_to_csv_bytes,
    discover_nosologies,
    load_nosology_bundle,
    query_articles_df,
    query_clinical_evidence_df,
    query_clinical_trials_df,
    query_mechanisms_df,
    render_printable_html,
    save_new_nosology_config,
    split_markdown_sections,
    verify_universal_schema,
)
```
**Phase 19 extension anchors:**
- Add `"truststore"` to PEP 723 `dependencies` (`app.py:3-9`) if importing `src.harvester`.
- Import `build_executive_docx_bytes`, `build_full_dossier_docx_bytes` from `src.docx_exporter` (`app.py:38-41`).
- Import `query_complications_df` from `src.universal_schema` (`app.py:42-54`).
- Import `build_complications_queries` (and optionally `resolve_treatment_profile`) from `src.harvester`.
- Optionally import `VALID_CLAVIEN_DINDO`, `VALID_EVENT_CLASS`, `VALID_REVERSIBILITY` from `src.extractor_common` (`lines 397-409`) to avoid duplicating enum literals.

#### 1.2 `@st.cache_data` wrapper convention (`app.py:57-80`)
Every SQLite query wrapper takes `db_path_str: str` (never `Path`) and uses `show_spinner=False`:
```python
@st.cache_data(show_spinner=False)
def cached_bundle(nosology_id: str) -> dict[str, Any]:
    return load_nosology_bundle(nosology_id)


@st.cache_data(show_spinner=False)
def cached_articles(db_path_str: str, included_only: bool = True) -> pd.DataFrame:
    return query_articles_df(Path(db_path_str), included_only=included_only)


@st.cache_data(show_spinner=False)
def cached_clinical_evidence(db_path_str: str) -> pd.DataFrame:
    return query_clinical_evidence_df(Path(db_path_str))


@st.cache_data(show_spinner=False)
def cached_mechanisms(db_path_str: str) -> pd.DataFrame:
    return query_mechanisms_df(Path(db_path_str))


@st.cache_data(show_spinner=False)
def cached_trials(db_path_str: str) -> pd.DataFrame:
    return query_clinical_trials_df(Path(db_path_str))
```
**Phase 19 exact copy pattern (insert at line 80):**
```python
@st.cache_data(show_spinner=False)
def cached_complications(db_path_str: str, include_casuistry: bool = True) -> pd.DataFrame:
    return query_complications_df(Path(db_path_str), include_casuistry=include_casuistry)
```
*Note on isolated `AppTest` caching:* If `INFO_SEARCHER_BASE_DIR` is used for isolated tests, either pass `base_dir_key: str = ""` into `cached_bundle(nosology_id, base_dir_key)` or call `st.cache_data.clear()` in tests so Streamlit's cache key includes the active workspace root.

#### 1.3 Sidebar KPIs & Quick Downloads (`app.py:95-191`)
```python
        selected_id = st.selectbox(
            "Выберите нозологию (`configs/*.yaml`):",
            options=list(options.keys()),
            format_func=lambda k: options[k],
            key="sidebar_nosology_select",
        )

        bundle = cached_bundle(selected_id)
        kb = bundle["kb_index"]
        meta = kb.get("nosology_meta", {})
        stats = meta.get("corpus_stats", kb.get("corpus_stats", {}))
...
        c5, c6 = st.columns(2)
        c5.metric("Протоколов NCT", f"{stats.get('clinical_trials_nct', 0)}")
        c6.metric("Полнотекстов XML", f"{stats.get('fulltext_xml_count', 233)}")
```
- **D-01 sidebar metric anchor (after line 134):** `load_nosology_bundle` (`src/universal_schema.py:714-717`) already injects `extracted_complications_rows` from `get_sqlite_corpus_stats(db_path)` into `stats`. Show:
  ```python
  comp_rows = int(stats.get("extracted_complications_rows", 0) or 0)
  if comp_rows > 0 or str(kb.get("schema_version", "")) == "2.0":
      st.metric("Строк осложнений", f"{comp_rows:,}".replace(",", " "))
  ```
- **D-06 sidebar download anchors (`app.py:138-167`):**
  - `sb_dl_diss_docx` (`lines 139-146`): unchanged (`build_docx_bytes_from_markdown(bundle["dissertation_md"])`).
  - `sb_dl_exec_docx` (`lines 148-155`): replace `build_docx_bytes_from_markdown(bundle["executive_summary_md"])` with `build_executive_docx_bytes(bundle["executive_summary_md"], kb)`.
  - `sb_dl_full_docx` (`lines 156-167`): replace `build_docx_bytes_from_markdown_sections(full_sections)` with `build_full_dossier_docx_bytes(bundle["executive_summary_md"], bundle["dissertation_md"], [m["content"] for m in bundle.get("kb_modules", []) if m.get("content")], kb)`.

#### 1.4 Tab 1 Report Reader (`app.py:194-344`)
- **Hardcoded `5` module count locations to make dynamic per D-01:**
  - `app.py:208`: `"Режим В — Модульная база знаний (5 тематических модулей)"` → compute `mod_count = len(bundle.get("kb_modules", []))` and format dynamically (e.g., `f"Режим В — Модульная база знаний ({mod_count} тематических модулей)"` — note Russian grammar: `5` and `6` both use `"тематических модулей"`, or use a small pluralizer for `1` / `2-4` / `0,5+`).
  - `app.py:302`: `mod_options["__all__"] = "📚 Показать все 5 модулей базы знаний подряд"` → `f"📚 Показать все {len(modules)} модулей базы знаний подряд"`.
- **D-06 Tab 1 Mode B `.docx` anchor (`app.py:270-276`):**
  - `t1_exec_docx_btn`: replace `build_docx_bytes_from_markdown(md_text)` with `build_executive_docx_bytes(md_text, kb)`.
- **Existing widget keys in Tab 1 (preserve exact keys):** `tab1_report_mode`, `tab1_search_query`, `tab1_diss_sec`, `t1_diss_docx_btn`, `t1_diss_md_btn`, `t1_diss_html_btn`, `t1_exec_docx_btn`, `t1_exec_md_btn`, `t1_exec_html_btn`, `tab1_kb_mod_select`, `t1_kb_docx_btn`, `t1_kb_md_btn`, `t1_kb_html_btn`.

#### 1.5 Tab 2 Clinical Matrix (`app.py:346-703`) — extending `sub1..sub4` with `sub5`, `sub6`
- **Tab declaration (`app.py:353-360`):**
```python
    sub1, sub2, sub3, sub4 = st.tabs(
        [
            "📐 2.1. Стадии тяжести и Локализации/Подтипы",
            "🧬 2.2. Этиология, Факторы риска и Фазы патогенеза",
            "📈 2.3. Естественное течение vs Методики (Ремиссия / Рецидив / Процедив)",
            "⚖️ 2.4. Бок-о-бок сравнение методик + Доказательства SQLite",
        ]
    )
```
Extend to 6 subtabs (D-01):
  - `sub5`: `"⚠️ 2.5. Осложнения (Clavien–Dindo)"`
  - `sub6`: `"🧭 2.6. Клинические компромиссы и серые зоны"`
  - Extract dedicated private render helpers `_render_subtab_complications(bundle)` and `_render_subtab_clinical_nuances(bundle)` to keep `render_tab_clinical_matrix()` clean and testable.
- **Filter + CSV export pattern in Tab 2 (`app.py:459-478`, `504-514`, `624-631`):**
  - Preserve insertion order via `list(dict.fromkeys(...))` for multiselect options (`app.py:507`).
  - Default `default=all_options`, graceful fallback when multiselect is cleared (`app.py:514`).
  - Rename display columns to Russian via `.rename(columns={...})` (`app.py:461-470`, `587-623`), render with `st.dataframe(disp_df, use_container_width=True, hide_index=True)`.
  - CSV button uses `dataframe_to_csv_bytes(disp_df)` (`utf-8-sig` BOM), `mime="text/csv"`, file name `f"{nos_id}_<topic>.csv"`, unique key `dl_csv_<topic>` (e.g., `dl_csv_frequent_complications`).
- **Existing widget keys in Tab 2 (prefix convention `sub<N>_<purpose>`):**
  - `sub3_group_filter`, `sub4_comparator_picks`, `sub4_sql_grp`, `dl_csv_factors`, `dl_csv_modalities`.
  - Recommended Phase 19 keys for `sub5`: `sub5_modality_filter`, `sub5_cd_filter`, `sub5_rev_filter`, `sub5_class_filter`, `sub5_color_mode`, `dl_csv_complications`.
- **Plotly chart styling conventions (`app.py:369-397`, `426-442`, `516-561`, `730-739`):**
  - Horizontal bar (`app.py:426-442`):
    ```python
    fig_sub = px.bar(
        df_sub,
        x="share_num",
        y="locus_or_subtype",
        color="category",
        orientation="h",
        text="share_pct",
        title="...",
        labels={...},
        height=380,
    )
    fig_sub.update_layout(yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig_sub, use_container_width=True)
    ```
  - Grouped / stacked bar (`app.py:369-397`, `516-561`):
    ```python
    fig.update_layout(
        barmode="group",  # or "stack" for sub5 chart (b)
        title="...",
        yaxis_title="...",
        height=380,  # 380–500 range; dynamic max(380, 32 * len(df)) for horizontal bar with many complications
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)
    ```
  - Tailwind-style academic palette already used in `app.py`: green `#16a34a`, blue `#3b82f6`, amber `#f59e0b`, red `#dc2626`, indigo `#6366f1`.
  - For `sub5` chart (a) (`px.bar(..., orientation="h", color=..., color_discrete_map=..., custom_data=[...])`) add `hovertemplate` displaying `frequency_pct`, `time_window`, `sample_size_total`, `evidence_pmids` (D-02.2a).
  - For `sub5` chart (b) stacked bar by `Clavien–Dindo` (`I`, `II`, `IIIa`, `IIIb`, `IV`, `V`) across modalities, use `category_orders={"clavien_dindo_grade": list(VALID_CLAVIEN_DINDO)}` and `barmode="stack"` with horizontal legend matching `app.py:395,559` (D-02.2b).
  - For `sub5` `rare_critical_red_flags` block (D-02.4): visually distinct callout block (`st.error` / bordered container / red-accent banner + `st.dataframe` or structured cards showing `modality`, `complication_name`, `clavien_dindo_grade`, `reversibility`, `frequency_pct`, `anatomical_substrate`, `prevention_and_management`, `evidence_pmids`).
  - For `sub5` `v1.x` fallback (D-02.5): when `not kb.get("frequent_complications")`: render `st.info(...)` noting `v1.x` schema and display `pd.DataFrame([{"Методика": m.get("name", ""), "Класс": m.get("group", ""), "Профиль осложнений (v1.x)": m.get("complications_profile", "—")} for m in kb.get("modalities", [])])` without touching disk.
- **Structured card/expander patterns for `sub6` (`app.py:482-489`, `648-668`):**
  - Follow `with st.expander(f"**{...}**", expanded=True):` (`app.py:483`) or `st.columns` cards (`app.py:648-668`) + `st.info` / `st.warning` / `st.success` callouts (`app.py:495-502`).
  - Read `nuances = kb.get("clinical_decision_nuances") or {}`; check whether any of `universal_workhorse_modalities`, `overlapping_indications_and_gray_zones`, `strict_niche_or_salvage_indications` is non-empty (remember `load_nosology_bundle` normalizes `v1.x` in-memory to empty lists in `src/universal_schema.py:705-712`!).
  - When all three are empty (`v1.x` fallback, D-03.4): render `st.info(...)` directing user to subtab `2.4 «Бок-о-бок сравнение методик»`.

#### 1.6 Tab 3 PRISMA Explorer (`app.py:705-916`) — adding 5th table `extracted_complications`
```python
def render_tab_prisma_explorer(bundle: dict[str, Any]) -> None:
    nos_id = bundle["nosology_id"]
    db_path_str = str(bundle["db_path"])
    df_art = cached_articles(db_path_str, included_only=True)
    df_clin = cached_clinical_evidence(db_path_str)
    df_mech = cached_mechanisms(db_path_str)
    df_trials = cached_trials(db_path_str)
    # Phase 19 (D-04): add df_comp_all = cached_complications(db_path_str, include_casuistry=True)
...
    table_choice = st.radio(
        "Выберите таблицу базы данных SQLite для интерактивного поиска и выгрузки:",
        options=[
            f"1. Включённые статьи PRISMA ({len(df_art)})",
            f"2. Извлечённые клинические доказательства ({len(df_clin)})",
            f"3. Извлечённые этиопатогенетические механизмы ({len(df_mech)})",
            f"4. Реестр клинических исследований ClinicalTrials.gov ({len(df_trials)})",
            f"5. Извлечённые осложнения лечения (extracted_complications) ({len(df_comp_all)})",
        ],
        horizontal=True,
        key="tab3_table_choice",
    )
```
- **Branch guard (`app.py:883`):** Change `else:` (table 4) to `elif table_choice.startswith("4."):` and add `else:` (or `elif table_choice.startswith("5."):`) for option 5.
- **Empty `v1.x` guard (CRITICAL):** `query_complications_df()` returns `pd.DataFrame()` with zero columns on `v1.x` DBs (`src/universal_schema.py:1060`). Always check `if df_comp_all.empty:` first and display a calm `st.info(...)` message (0 records, read-only) before referencing column names!
- **LinkColumn + CSV download pattern (`app.py:810-825`):**
```python
        st.dataframe(
            view[disp_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "pubmed_url": st.column_config.LinkColumn("PubMed", display_text="Открыть PubMed"),
                "doi_url": st.column_config.LinkColumn("DOI", display_text="Открыть DOI"),
            },
        )
        st.download_button(
            "📥 Скачать отфильтрованный список статей (.csv)",
            data=dataframe_to_csv_bytes(view[disp_cols]),
            file_name=f"{nos_id}_articles_filtered.csv",
            mime="text/csv",
            key="dl_csv_articles",
        )
```
- **Widget key convention in Tab 3 (`t3_<table_short>_<field>`):**
  - Existing: `tab3_table_choice`, `t3_art_tiers`, `t3_art_xml`, `t3_art_kw`, `dl_csv_articles`, `t3_clin_grp`, `t3_clin_kw`, `dl_csv_clin`, `t3_mech_cat`, `t3_mech_kw`, `dl_csv_mech`, `t3_tr_status`, `t3_tr_kw`, `dl_csv_trials`.
  - Recommended Phase 19 option 5 keys: `t3_comp_mod`, `t3_comp_cd`, `t3_comp_rev`, `t3_comp_class`, `t3_comp_casuistry`, `t3_comp_kw`, `dl_csv_complications`.
- **Casuistry filter wiring (D-04):** Checkbox `show_casuistry = st.checkbox("Показать редкую казуистику (Tier 4 / N<20)", value=False, key="t3_comp_casuistry")` feeds `df_comp = cached_complications(db_path_str, include_casuistry=show_casuistry)`.
- **Text search pattern (`app.py:786-794`):** Case-insensitive `regex=False` across `complication_name`, `anatomical_substrate`, `prevention_and_management`, plus `modality` / `pmid`.

#### 1.7 Tab 4 Configurator & Audit (`app.py:919-1005`)
- **Audit button (`app.py:926-943`):**
```python
        if st.button("🔄 Запустить повторный аудит `verify_reports.py --verify --read-only`", key="btn_run_verify"):
            res = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "src" / "verify_reports.py"),
                    "--nosology",
                    bundle["nosology_id"],
                    "--verify",
                    "--read-only",  # D-05.4: mandatory read-only flag!
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
```
- **YAML Configurator (`app.py:955-994`):**
  Current stale payload (`app.py:971-987`):
  ```python
            payload = {
                "nosology": {
                    "id": new_id.strip().lower(),
                    "name_ru": new_ru.strip(),
                    "name_en": new_en.strip(),
                    "icd10": icd10_val.strip(),
                    "icd11": icd11_val.strip(),
                    "mesh_terms": [m.strip() for m in mesh_val.split(",") if m.strip()],
                },
                "date_range": {"start_year": 2016, "end_year": 2026},
                "queries": {
                    "pubmed": pubmed_q.strip(),
                    "europepmc": pubmed_q.strip(),
                    "openalex": new_en.strip(),          # BUG: harvester.py:973 expects "openalex_search"
                    "clinicaltrials": ct_cond.strip(),   # BUG: harvester.py:979 expects "clinical_trials_condition"
                },
            }
  ```
  **Phase 19 D-05 alignment (matches `src/harvester.py:86-154, 969-979` & `src/universal_schema.py:1134-1175`):**
  - Profile selector (e.g., `st.radio(..., key="cfg_treatment_profile")` with 2 options: surgical/mixed `surgical_focus=True, treatment_profile="surgical"` vs conservative `surgical_focus=False, treatment_profile="conservative"`).
  - Live preview calls `build_complications_queries(preview_cfg)` where `preview_cfg` passes `nosology: {id, name_en, mesh_terms, surgical_focus, treatment_profile}`, `date_range`, and optional `complications_queries: {pubmed, europepmc}` overrides, and renders the generated `pubmed` & `europepmc` queries via `st.code(..., language="text")`.
  - Keep `st.form("new_nosology_form")` (or place the profile selector + preview reactive controls right above it so live preview updates immediately without waiting for form submit, and form submission reads the selected profile + overrides!).
  - Align `queries` keys strictly to `src/harvester.py:969-979`:
    ```python
    "queries": {
        "pubmed": pubmed_q.strip(),
        "europepmc": pubmed_q.strip(),
        "openalex_search": new_en.strip(),
        "clinical_trials_condition": ct_cond.strip(),
    },
    ```
  - Include `"surgical_focus": is_surgical` and `"treatment_profile": ("surgical" if is_surgical else "conservative")` under `payload["nosology"]` (which `save_new_nosology_config` normalizes cleanly at `src/universal_schema.py:1151-1168`), plus `"complications_queries"` when manual override fields are non-empty.

#### 1.8 `run_self_test()` exact assertions & exit-code pattern (`app.py:1045-1094`)
```python
def run_self_test() -> int:
    import os

    os.environ["INFO_SEARCHER_APPTEST_ACTIVE"] = "1"
    sys.argv = [arg for arg in sys.argv if arg != "--self-test"]

    print("[1/3] Running universal schema & export verification...")
    discovered = discover_nosologies()
    active_nos = discovered[0]["id"] if discovered else "prom"
    rc = verify_universal_schema(active_nos)
    if rc != 0:
        return rc

    print("[2/3] Running headless Streamlit AppTest on `app.py`...")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(Path(__file__).resolve()), default_timeout=60)
    at.run(timeout=60)
    if len(at.exception) > 0:
        ...
        return 1

    # Switch report modes in Tab 1 to ensure Mode B and Mode C also render cleanly
    at.radio(key="tab1_report_mode").set_value("Режим Б — Краткий клинический отчёт (Executive Summary)").run(timeout=60)
    ...
    at.radio(key="tab1_report_mode").set_value("Режим В — Модульная база знаний (5 тематических модулей)").run(timeout=60)
    ...
    return 0


if __name__ == "__main__":
    import os

    if "--self-test" in sys.argv and os.environ.get("INFO_SEARCHER_APPTEST_ACTIVE") != "1":
        sys.exit(run_self_test())
    else:
        render_streamlit_app()
```
**Phase 19 D-08.3 extensions to `run_self_test()`:**
- Iterate through **all** discovered nosologies (`for item in discovered:`), running `verify_universal_schema(item["id"])` and switching `at.selectbox(key="sidebar_nosology_select").set_value(item["id"]).run(timeout=60)` with `assert len(at.exception) == 0`.
- Do NOT hardcode `"5 тематических модулей"` when selecting Mode C; resolve dynamically from `at.radio(key="tab1_report_mode").options` (e.g., `next(opt for opt in opts if opt.startswith("Режим В"))`).
- Verify Tab 2 now exposes **6 subtabs** including `2.5` and `2.6` (check `at.tabs` labels contain `"2.5"` and `"2.6"`).
- Switch Tab 3 radio `at.radio(key="tab3_table_choice")` to option starting with `"5."` (`extracted_complications`), run, and assert `len(at.exception) == 0`.
- Return `0` on full pass, `1` (or `rc`) on any failure; `sys.exit(run_self_test())` preserves CLI exit-code contract.

---

### 2. `src/docx_exporter.py` (transform service / CLI exporter, Markdown + KB JSON → OpenXML `.docx`)

**Analog:** `src/docx_exporter.py` (lines 1–636).

#### 2.1 Existing OpenXML primitives & exact line anchors

| Symbol | Exact Lines | Current Behavior | Phase 19 Action |
|--------|-------------|------------------|-----------------|
| `_xml_escape(text)` | `23–26` | Strips invalid XML 1.0 control chars + escapes `& < > " '` | Reuse unchanged for all new XML fragments |
| `_RelRegistry` | `29–56` | Registers external hyperlinks starting at `rId11` (`rId1` = `styles.xml`) | Reuse unchanged |
| `_build_styles_xml()` | `76–187` | Defines `Normal`, `Heading1..4`, `CalloutQuote` (`2563EB` border, `EFF6FF` fill) | Optionally add `RedFlagQuote` style (`DC2626` border, `FEF2F2` fill) right before `</w:styles>` at line 187 |
| `_render_run(...)` | `199–229` | Builds `<w:r><w:rPr>...</w:rPr><w:t xml:space="preserve">...</w:t></w:r>` | Reuse unchanged |
| `_render_inline_runs(...)` | `232–314` | Parses `[label](url)`, `***`, `**`, `*`, `` ` `` | Reuse unchanged |
| `_split_table_row`, `_is_table_separator` | `317–330` | Splits Markdown pipe rows & detects separator row | Reuse unchanged |
| `_render_table_xml(table_lines, rels)` | `333–389` | Builds `<w:tbl>` with borders, cell margins, `<w:tblHeader/>` on row 0 (`line 364`), alternating zebra fill (`1E3A8A` / `F8FAFC` / `FFFFFF` at `line 363`) | **Modify lines 361–385** (see 2.2 below) |
| `_markdown_to_body_xml(md_text, rels)` | `417–514` | Block parser (`---`, fenced code, pipe tables, `#..####`, `>`, bullets/numbers, paragraphs) | Reuse unchanged (optionally recognize red-flag blockquote marker if desired) |
| `build_docx_bytes_from_markdown_sections(sections)` | `517–571` | Compiles sections with page breaks (`<w:br w:type="page"/>`), A4 margins, **validates all 5 XML parts via `ET.fromstring()`** (`lines 552–562`), zips into `.docx` bytes | Preserve signature & behavior 100% |
| `build_docx_bytes_from_markdown(md_text)` | `574–576` | Delegates to `build_docx_bytes_from_markdown_sections([md_text])` | Preserve signature & behavior 100% |
| `export_nosology_docx_files(nosology_slug, base_dir=None)` | `579–614` | Writes 3 `.docx` files into `root / "reports" / nosology_slug` | **Modify** to load `kb_index.json`, call new `build_executive_docx_bytes` / `build_full_dossier_docx_bytes`, and add frozen `v1.x` overwrite guard (see 2.3–2.4) |
| CLI `__main__` (`argparse`) | `617–636` | `--nosology` (default `"all"`) | Add `--allow-frozen-overwrite` (`action="store_true"`) and pass through (see 2.4) |

#### 2.2 Exact anchor for `<w:tblHeader/>`, `<w:cantSplit/>`, and severity `<w:shd>` (`src/docx_exporter.py:361-386`)
Current code (`lines 361–386`):
```python
    for r_idx, row in enumerate(rows_raw):
        is_header = r_idx == 0
        fill = "1E3A8A" if is_header else ("F8FAFC" if r_idx % 2 == 0 else "FFFFFF")
        tr_pr = "<w:trPr><w:tblHeader/></w:trPr>" if is_header else ""
        xml_parts.append(f"  <w:tr>{tr_pr}")

        padded_row = row + [""] * (num_cols - len(row))
        for cell_text in padded_row:
            runs = _render_inline_runs(
                cell_text,
                rels=rels,
                force_bold=is_header,
                force_color="FFFFFF" if is_header else None,
                size_half_pt=20,
            )
            xml_parts.append(
                "    <w:tc>"
                f'<w:tcPr><w:tcW w:w="{col_pct}" w:type="pct"/>'
                f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>'
                '<w:vAlign w:val="center"/></w:tcPr>'
                f'<w:p><w:pPr><w:spacing w:before="40" w:after="40" w:line="240" w:lineRule="auto"/>'
                f'<w:jc w:val="left"/></w:pPr>{runs}</w:p>'
                "</w:tc>"
            )
        xml_parts.append("  </w:tr>")
```
**Phase 19 D-07 modification pattern at lines 361–386:**
1. **`<w:cantSplit/>` on EVERY row + `<w:tblHeader/>` on header row:**
   ```python
   tr_pr = "<w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>" if is_header else "<w:trPr><w:cantSplit/></w:trPr>"
   ```
   *(Valid OOXML child order inside `<w:trPr>`: `<w:tblHeader/>` and `<w:cantSplit/>` are both valid CT_TrPr children and pass `ET.fromstring()` + Word validation.)*
2. **Conditional academic shading (`<w:shd w:fill="..."/>`) for critical severity (`Clavien–Dindo IIIb / IV / V`) and Red Flags:**
   - Detect header column context (e.g., whether table has a `Clavien–Dindo` / `Тяжесть` / `Красный флаг` column) OR detect cells matching exact severity tokens (e.g. regex `r"(?:^|\b)(?:Clavien[–-]Dindo\s+)?(IIIb|IV[ab]?|V)(?:\b|$)"` / red-flag table header).
   - **Guard against false positives on general tables:** Only trigger critical shading when the table header mentions Clavien–Dindo / осложнен / красн / тяжест (or cell contains `Clavien–Dindo IIIb/IV/V` or standalone grade token inside the Clavien–Dindo column), so ordinary tables containing Roman numeral stage `"IV"` (e.g., Tubiana Stage IV in `v1.x` tables!) are NOT falsely painted red!
   - Recommended pastel academic palette (with dark text for contrast):
     - Critical `IV` / `V` or Red-Flag row: row fill `"FEE2E2"` (soft rose) or cell fill `"FECACA"`, grade text `"991B1B"` (dark crimson, bold).
     - Severe `IIIb` row: row fill `"FEF3C7"` (soft amber) or `"FFEDD5"` (soft peach), grade text `"9A3412"` (dark burnt orange, bold).
     - Moderate `IIIa`: optional subtle `"FEF9C3"` or standard zebra; `I` / `II`: standard zebra (`"F8FAFC"` / `"FFFFFF"`).
   - **Important `v1.x` compatibility note:** Scoping severity shading to complication/red-flag columns guarantees `v1.x` tables (like Tubiana stages I–IV) keep their exact clean zebra styling, while still gaining `<w:cantSplit/>` + `<w:tblHeader/>` pagination protection.

#### 2.3 Exact insertion point for `v2.0` appendix builders (between lines 576 and 579)
Insert new public helpers immediately after `build_docx_bytes_from_markdown` (`line 576`) and before `export_nosology_docx_files` (`line 579`):
1. `is_v2_kb_with_appendices(kb_index: Optional[dict]) -> bool` (helper):
   Returns `True` iff `isinstance(kb_index, dict)` and (`str(kb_index.get("schema_version", "")) == "2.0"` or non-empty `frequent_complications` or non-empty `rare_critical_red_flags` or non-empty any section of `clinical_decision_nuances`).
   *Watch out:* Remember `load_nosology_bundle` adds empty `clinical_decision_nuances` lists in-memory for `v1.x` (`src/universal_schema.py:705-712`)! So check **non-empty** lists inside `clinical_decision_nuances`, NEVER just key presence!
2. `render_v2_kb_appendices_markdown(kb_index: Optional[dict]) -> str` (D-06):
   - Returns `""` for `None` or `v1.x` KBs with empty v2 sections.
   - Emits clean Markdown sections with pipe tables (escaping any literal `|` inside cell values as `\/` or `;` and collapsing `\n` to spaces so `_split_table_row()` never breaks column count!):
     - `## Приложение A. Профиль частых осложнений лечения (Clavien–Dindo)` — Markdown table (`Методика`, `Осложнение`, `Класс события`, `Clavien–Dindo`, `Частота (%)`, `Обратимость и сроки`, `Анатомический субстрат`, `Профилактика и лечение`, `Выборка N`, `PMID`).
     - `### Красные флаги: редкие критические осложнения (<1%)` — dedicated Markdown table (or callout + table) when `rare_critical_red_flags` is non-empty, with `Clavien–Dindo` grades cleanly formatted so `_render_table_xml` applies red-flag `<w:shd>` shading automatically!
     - `## Приложение B. Клинические компромиссы и матрица выбора методики (v2.0)` — 3 subsections/tables from `clinical_decision_nuances`:
       1. `### Сквозные методики («рабочие лошадки»)` (`universal_workhorse_modalities`)
       2. `### Перекрывающиеся показания и «серые зоны»` (`overlapping_indications_and_gray_zones`)
       3. `### Узконишевые показания и методики спасения` (`strict_niche_or_salvage_indications`, rendered when non-empty).
3. `build_executive_docx_bytes(exec_md: str, kb_index: Optional[dict] = None) -> bytes` (D-06):
   - Calls `appendix_md = render_v2_kb_appendices_markdown(kb_index)`.
   - If `appendix_md`: returns `build_docx_bytes_from_markdown_sections([exec_md, appendix_md])`.
   - Else (`v1.x`): returns `build_docx_bytes_from_markdown(exec_md)` (100% identical to `v1.x`).
4. `build_full_dossier_docx_bytes(exec_md: str, diss_md: str, kb_modules_md: List[str], kb_index: Optional[dict] = None) -> bytes` (D-06):
   - Builds `sections = [exec_md, diss_md] + [m for m in kb_modules_md if m]`.
   - If `appendix_md := render_v2_kb_appendices_markdown(kb_index)`: appends `appendix_md`.
   - Returns `build_docx_bytes_from_markdown_sections(sections)`.

#### 2.4 Frozen `v1.x` overwrite guard & CLI flag (`src/docx_exporter.py:579-636`)
Current code (`lines 579–636`):
```python
def export_nosology_docx_files(nosology_slug: str, base_dir: Optional[Path] = None) -> Dict[str, Path]:
    root = base_dir or Path(__file__).resolve().parent.parent
    rep_dir = root / "reports" / nosology_slug
    ...
    diss_docx_path.write_bytes(build_docx_bytes_from_markdown(diss_text))
    exec_docx_path.write_bytes(build_docx_bytes_from_markdown(exec_text))
    ...
    full_docx_path.write_bytes(build_docx_bytes_from_markdown_sections(kb_sections))
```
**Phase 19 D-06 + D-07 pattern:**
- Define module constant:
  ```python
  PROJECT_ROOT = Path(__file__).resolve().parent.parent
  FROZEN_V1_NOSOLOGIES = frozenset({"prom", "metroplasty_pregnancy", "trigger_finger"})
  ```
- Extend signature preserving positional backward compatibility (`verify_reports.py:983` calls `export_nosology_docx_files(nos_id, root_dir)`):
  ```python
  def export_nosology_docx_files(
      nosology_slug: str,
      base_dir: Optional[Path] = None,
      *,
      allow_frozen_overwrite: bool = False,
  ) -> Dict[str, Path]:
  ```
- Guard ONLY when writing into the repository root (`root.resolve() == PROJECT_ROOT.resolve()`) and `nosology_slug in FROZEN_V1_NOSOLOGIES` and `not allow_frozen_overwrite`:
  raise `PermissionError` (or `RuntimeError`) with a clear Russian/English message pointing to `--allow-frozen-overwrite` / `allow_frozen_overwrite=True`.
  *(Exports to any `tmp_path` `base_dir` in tests and in-memory `build_*_docx_bytes()` calls in `app.py` remain completely unrestricted per D-07.3.)*
- Read optional `kb_index.json` at `kb_dir / "kb_index.json"` (if present) and pass `kb_index` to `build_executive_docx_bytes(exec_text, kb_index)` and `build_full_dossier_docx_bytes(exec_text, diss_text, kb_module_texts, kb_index)`, while `dissertation_report.docx` continues using `build_docx_bytes_from_markdown(diss_text)`.
- In `if __name__ == "__main__":` (`lines 617–636`): add `parser.add_argument("--allow-frozen-overwrite", action="store_true", ...)` and pass `allow_frozen_overwrite=args.allow_frozen_overwrite`.

---

### 3. `src/universal_schema.py` (data-access utility — optional root-override hook for isolated `AppTest`)

**Analog:** `src/universal_schema.py:48-50, 181-224, 671-776, 1134-1175` + `src/verify_reports.py:get_nosology_paths(..., base_dir=...)`.

**Current module path constants (`src/universal_schema.py:48-50`):**
```python
CONFIGS_DIR = PROJECT_ROOT / "configs"
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
```
**How existing tests isolate roots (`tests/test_phase17_complications.py:1280-1281`, `tests/test_phase18_humanizer.py:751-753`):**
```python
monkeypatch.setattr(universal_schema, "CONFIGS_DIR", esc_root / "configs")
monkeypatch.setattr(universal_schema, "DATA_DIR", esc_root / "data")
monkeypatch.setattr(universal_schema, "REPORTS_DIR", esc_root / "reports")
```
**Why an optional env-var hook helps isolated `AppTest`:**
- `discover_nosologies(configs_dir: Path = CONFIGS_DIR)` evaluates `CONFIGS_DIR` as a **default argument at function definition time** (`src/universal_schema.py:181`)!
  **SUBTLE BUG ALERT:** Look at line 181: `def discover_nosologies(configs_dir: Path = CONFIGS_DIR)`. Even if a test runs `monkeypatch.setattr(universal_schema, "CONFIGS_DIR", tmp_configs)`, calling `discover_nosologies()` with NO arguments (which `app.py:1016` does!) still uses the **original** `CONFIGS_DIR` bound at import time! (Notice `test_phase17_complications.py:1315` passed `tmp_configs` explicitly, hiding this default-arg binding!)
- **Clean, minimal fix in `src/universal_schema.py`:**
  Change line 181 signature to `def discover_nosologies(configs_dir: Path | None = None) -> list[dict[str, Any]]:` and resolve active roots via a tiny helper:
  ```python
  def _resolve_active_dirs() -> tuple[Path, Path, Path]:
      env_root = os.environ.get("INFO_SEARCHER_BASE_DIR", "").strip()
      if env_root:
          base = Path(env_root).resolve()
          return base / "configs", base / "data", base / "reports"
      return CONFIGS_DIR, DATA_DIR, REPORTS_DIR
  ```
  Use `_resolve_active_dirs()` in `discover_nosologies()` (when `configs_dir is None`), `load_nosology_bundle()`, and `save_new_nosology_config()`.
  - When `INFO_SEARCHER_BASE_DIR` is unset, `monkeypatch.setattr(universal_schema, "CONFIGS_DIR", ...)` works everywhere — **including** `discover_nosologies()` called with no args from `app.py:1016`!
  - When `INFO_SEARCHER_BASE_DIR` is set to `tmp_path`, even subprocess `uv run app.py --self-test` or isolated `AppTest` sees ONLY the synthetic `v2.0` workspace with zero risk of touching real `configs/`, `data/`, or `reports/`.

---

### 4. `src/verify_reports.py` (verification service — 6-module `v2.0` KB compatibility)

**Analog:** `src/verify_reports.py:823-844`.

**Current rigid assertions (`src/verify_reports.py:828-844`):**
```python
    kb_data = json.loads(kb_json_path.read_text(encoding="utf-8"))
    assert isinstance(kb_data, dict), f"kb_index.json must be a JSON object: {kb_json_path}"
    assert len(kb_data.get("modules", [])) == 5, "kb_index.json must index 5 modules"
    assert len(kb_data.get("modalities", [])) >= 8, "kb_index.json must include >= 8 treatment modalities"

    if schema_version == "v2" or (schema_version == "auto" and str(kb_data.get("schema_version", "")) == "2.0"):
        effective_version = "2.0"
    else:
        effective_version = "1.x"

    report_files = [
        diss_path,
        sum_path,
        *sorted(kb_dir.glob("*.md")),
    ]
    assert len(report_files) == 7, f"Expected 7 Markdown report files for '{nos_id}', found {len(report_files)}"
```
**Phase 19 minimal fix pattern:**
- Determine `effective_version` first, then allow `5` modules for `v1.x` and `5` or `6` modules for `v2.0` (so Phase 18's 5-module synthetic test AND Phase 19's 6-module `06_complications_and_safety.md` synthetic test both pass):
  ```python
  kb_md_files = sorted(kb_dir.glob("*.md"))
  allowed_mod_counts = (5, 6) if effective_version == "2.0" else (5,)
  assert len(kb_data.get("modules", [])) in allowed_mod_counts, (
      f"kb_index.json must index {allowed_mod_counts} modules, got {len(kb_data.get('modules', []))}"
  )
  assert len(kb_md_files) == len(kb_data.get("modules", [])), (
      f"Mismatch between KB markdown files ({len(kb_md_files)}) and kb_index modules ({len(kb_data.get('modules', []))})"
  )
  report_files = [diss_path, sum_path, *kb_md_files]
  ```

---

### 5. `tests/test_v2_engine.py` (E2E `v2.0` + frozen `v1.x` regression + headless `AppTest`)

**Analogs:**
- `tests/test_phase17_complications.py` (harvester queries, SQLite `extracted_complications` seeding, `aggregate_complications_from_sqlite`, `v1.x` read-only immutability)
- `tests/test_phase18_humanizer.py` (synthetic `v2.0` KB + prose fixtures, `verify_all_reports(..., schema_version="v2", write_outputs=False, base_dir=tmp_path)`, `v1.x` report & git immutability)
- `app.py:1045-1085` (`AppTest.from_file(...)` headless UI testing pattern).

#### 5.1 Test file header & imports pattern (`tests/test_phase17_complications.py:10-34`, `tests/test_phase18_humanizer.py:14-32`)
```python
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
```

#### 5.2 Synthetic `v2.0` E2E fixture pattern (combining Phase 17 + Phase 18 + full `REQUIRED_UNIVERSAL_KEYS` + 6 KB modules)
Reuse and combine:
1. **YAML config (`surgical_focus: true`):** Write `tmp_path / "configs" / f"{nos_id}.yaml"` with `nosology.surgical_focus: true`, `mesh_terms`, `date_range`, `queries` (`pubmed`, `europepmc`, `openalex_search`, `clinical_trials_condition`), `triage_rules.core_terms`, `verification_rules.required_terms` (`tests/test_phase17_complications.py:60-68` & `tests/test_phase18_humanizer.py:463-473`).
2. **Harvester query generation:** Assert `harvester.build_complications_queries(cfg)` yields `profile == "surgical"`, `surgical_focus is True`, `"Postoperative Complications"[MeSH]`, and date bounds (`tests/test_phase17_complications.py:69-80`).
3. **SQLite seeding (all 5 tables):**
   - `conn = schema.init_db(db_path)`
   - Seed 36 included `articles` (PMIDs `88000001..88000036`, PMCIDs `PMC8800001..`), 1+ `clinical_trials` (`NCT05123456`) (`tests/test_phase18_humanizer.py:478-508`), 2+ `extracted_clinical_evidence`, 2+ `extracted_mechanisms`, and `extracted_complications` rows via `extractor_common.insert_extracted_complication(conn, {...})` covering:
     - `transient_postop_sequela` (`Clavien–Dindo I`, `frequency_num >= 1.0`, `sample_size >= 20`, `time_window`),
     - `true_complication` (`Clavien–Dindo II`, `frequency_num >= 1.0`, `sample_size >= 20`),
     - severe `true_complication` (`Clavien–Dindo IIIb`, `frequency_num >= 1.0` OR `< 1.0` cohort for red flag),
     - `Tier 4` `N = 1` catastrophic case (`is_rare_casuistry = 1`) for red-flag routing & Tab 3 casuistry checkbox (`tests/test_phase17_complications.py:995-1102`).
4. **SQLite → `kb_index.json v2.0` aggregation:**
   - Call `freq_comps, red_flags = universal_schema.aggregate_complications_from_sqlite(db_path)` (`tests/test_phase17_complications.py:1123`).
   - Populate **all 8 `REQUIRED_UNIVERSAL_KEYS`** (`staging_and_classification` with ≥3 stages, `anatomical_or_subtype_distribution` with ≥3 subtypes, `etiology_and_risk_factors` with ≥4 factors, `pathogenesis_phases` with ≥2 phases, `natural_history_and_dynamics`, `modalities` with ≥8 entries, `modules` with **6** entries `01..06` including `06_complications_and_safety.md`) PLUS `schema_version: "2.0"`, `frequent_complications: freq_comps`, `rare_critical_red_flags: red_flags`, and `clinical_decision_nuances` (`tests/test_phase18_humanizer.py:127-166`).
   - Write `dissertation_report.md` (using `_build_good_v2_prose_report` pattern, `> 3500` bytes, ≥35 bib entries), `executive_summary.md` (`> 3500` bytes, with Markdown table), and all 6 KB modules (`01..06`, each `> 3500` bytes) (`tests/test_phase18_humanizer.py:512-560`).
5. **Verification gate (`verify_reports`):**
   - `res = verify_reports.verify_all_reports(nos_id, schema_version="v2", write_outputs=False, base_dir=tmp_path)` → assert `res["passed"] is True`, `res["schema_version"] == "2.0"`, `res["kb_v2_errors"] == []`.
6. **DOCX export & OpenXML `word/document.xml` inspection:**
   - Call `paths = docx_exporter.export_nosology_docx_files(nos_id, base_dir=tmp_path)`.
   - Open `executive_summary.docx`, `full_clinical_dossier.docx`, and `dissertation_report.docx` via `zipfile.ZipFile` + `ET.fromstring(zf.read("word/document.xml"))`.
   - Assert `<w:tblHeader/>` and `<w:cantSplit/>` exist in table rows, `<w:shd w:fill="..."/>` matches critical/red-flag shading on `IIIb`/`IV`/`V`/red-flag rows, `frequent_complications` & `clinical_decision_nuances` text appear in `executive_summary.docx` and `full_clinical_dossier.docx`, and `dissertation_report.docx` does NOT duplicate the KB appendices.
7. **Isolated `Streamlit AppTest` on synthetic `v2.0` workspace:**
   - Set `monkeypatch.setenv("INFO_SEARCHER_BASE_DIR", str(tmp_path))` (and `st.cache_data.clear()`), run `AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=60).run(timeout=60)`.
   - Assert `not at.exception`.
   - Assert Mode C radio option shows `6` modules; switch Tab 1 through Modes A/B/C.
   - Assert Tab 2 has 6 subtabs including `2.5` and `2.6`, plus sidebar metric `"Строк осложнений"`.
   - Switch Tab 3 `tab3_table_choice` to option `"5."`, toggle casuistry checkbox `t3_comp_casuistry`, assert row count changes cleanly with `not at.exception`.
   - Verify Tab 4 `surgical_focus` / `treatment_profile` switch updates live preview without exceptions.

#### 5.3 Frozen `v1.x` regression & SHA-256 / mtime / git immutability pattern (`tests/test_phase17_complications.py:1332-1398`, `tests/test_phase18_humanizer.py:641-697`)
```python
FROZEN_V1_NOSOLOGIES = ("prom", "metroplasty_pregnancy", "trigger_finger")

def _snapshot_tree(root_dirs: list[Path]) -> dict[Path, tuple[int, int, str]]:
    snap: dict[Path, tuple[int, int, str]] = {}
    for d in root_dirs:
        if not d.exists():
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file():
                st = p.stat()
                digest = hashlib.sha256(p.read_bytes()).hexdigest()
                snap[p] = (st.st_mtime_ns, st.st_size, digest)
    return snap
```
Capture `_snapshot_tree([PROJECT_ROOT / "data" / n, PROJECT_ROOT / "reports" / n for n in FROZEN_V1_NOSOLOGIES])` (plus `configs/<n>.yaml`) **before**:
- `universal_schema.load_nosology_bundle(nos_id)`
- `universal_schema.query_complications_df(db_path)` (empty `DataFrame`)
- `universal_schema.verify_universal_schema(nos_id, schema_version="auto")` (`== 0`)
- In-memory `docx_exporter.build_executive_docx_bytes` / `build_full_dossier_docx_bytes` (assert 0 v2 appendix headings appended)
- `with pytest.raises((PermissionError, RuntimeError)): docx_exporter.export_nosology_docx_files(nos_id)` (frozen disk overwrite guard!)
- `Streamlit AppTest` iterating all 3 frozen nosologies across Tab 1 modes, Tab 2 subtabs `2.5`/`2.6` fallbacks, and Tab 3 option `5.` fallback (`0` exceptions)

Then assert `_snapshot_tree(...) == before` AND `git status --porcelain data/prom data/metroplasty_pregnancy data/trigger_finger reports/prom reports/metroplasty_pregnancy reports/trigger_finger` is empty (`tests/test_phase18_humanizer.py:680-697`).

---

## Shared Patterns

### Read-Only SQLite Guard
**Source:** `src/universal_schema.py:168-178` (`_connect_sqlite_readonly`) + `src/universal_schema.py:1053-1131` (`query_complications_df`)
**Apply to:** `app.py` (Tab 3 option 5 & sidebar KPIs), `tests/test_v2_engine.py`
- Always open SQLite via `universal_schema` read-only functions (`query_complications_df`, `get_sqlite_corpus_stats`); never open a direct read-write `sqlite3.connect()` from `app.py`.
- Always check `df.empty` before column indexing because `v1.x` DBs lack `extracted_complications`.

### Canonical v2.0 Enum Constants & Russian Display Labels
**Source:** `src/extractor_common.py:397-409`
**Apply to:** `app.py` (`sub5` filters/charts/tables, Tab 3 option 5) and `src/docx_exporter.py` (`render_v2_kb_appendices_markdown`)
```python
VALID_CLAVIEN_DINDO: tuple[str, ...] = ("I", "II", "IIIa", "IIIb", "IV", "V")

VALID_REVERSIBILITY: tuple[str, ...] = (
    "transient_self_limiting",
    "requires_conservative_therapy",
    "requires_reoperation",
    "permanent_deficit",
)

VALID_EVENT_CLASS: tuple[str, ...] = (
    "true_complication",
    "transient_postop_sequela",
)
```
Use one consistent mapping of Russian display labels across both `app.py` and `src/docx_exporter.py` (e.g., `true_complication` → `"Истинное осложнение"`, `transient_postop_sequela` → `"Транзиторное послеоперационное явление"`, `transient_self_limiting` → `"Саморазрешающееся (транзиторное)"`, `requires_conservative_therapy` → `"Требует консервативной терапии"`, `requires_reoperation` → `"Требует повторного вмешательства"`, `permanent_deficit` → `"Стойкий / необратимый дефицит"`).

### Frozen v1.x Immutability Protection
**Source:** `src/verify_reports.py:805-806, 980, 1066-1070`, `tests/test_phase17_complications.py:1332-1398`, `tests/test_phase18_humanizer.py:641-697`
**Apply to:** `app.py` (Tab 4 `--read-only` audit call, fallback UI rendering), `src/docx_exporter.py` (`export_nosology_docx_files` guard), `tests/test_v2_engine.py`
- Never write to `data/{prom,metroplasty_pregnancy,trigger_finger}` or `reports/{prom,metroplasty_pregnancy,trigger_finger}` by default.
- Always pass `--read-only` when invoking `src/verify_reports.py` from `app.py` Tab 4.

### UTF-8-SIG Excel-Safe CSV Downloads
**Source:** `src/universal_schema.py:918-920` (`dataframe_to_csv_bytes`)
**Apply to:** `app.py` (`sub5` complications table download, Tab 3 option 5 download)
```python
def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialize DataFrame to UTF-8 with BOM (`utf-8-sig`) bytes for Russian Excel compatibility (`D-03`)."""
    return df.to_csv(index=False).encode("utf-8-sig")
```

### Offline `uv` Pytest & Self-Test Execution Commands
**Source:** `.planning/phases/19-app-py-docx-v2-0/19-CONTEXT.md:105`, `app.py:16-17`
**Apply to:** Verification of all Phase 19 tasks
- Pytest suite (offline, includes `streamlit` & `plotly` for `AppTest`):
  `uv run --with pytest --with pyyaml --with pandas --with markdown --with truststore --with streamlit --with plotly pytest tests/ -v`
- Self-test CLI:
  `uv run app.py --self-test`

---

## No Analog Found

None — all 5 files to be created or modified have direct, high-confidence in-repository analogs.

---

## Metadata

**Analog search scope:** `app.py`, `src/docx_exporter.py`, `src/universal_schema.py`, `src/harvester.py`, `src/verify_reports.py`, `src/extractor_common.py`, `configs/trigger_finger.yaml`, `tests/test_phase17_complications.py`, `tests/test_phase18_humanizer.py`
**Files scanned:** 9
**Pattern extraction date:** 2026-11-22
