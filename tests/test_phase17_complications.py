"""Comprehensive offline unit, integration, security, and backward-compatibility tests for Phase 17.

Covers:
- COMP-01, D-01..D-03, T-17-03: src/harvester.py (surgical/conservative profile, hybrid queries, raw caches, provenance merge)
- COMP-02, D-04..D-06, T-17-04: src/triage.py (3-signal complications_safety, N>=20 vs Tier 4 casuistry, priority XML queue & PMCID_RE)
- COMP-03, D-04, D-07, D-08, T-17-01: src/schema.py & src/extractor_common.py (dual-axis Clavien-Dindo/CTCAE, recurrence guard, JATS XML, SQL injection)
"""

from __future__ import annotations

import json
import sys
import types
import urllib.request
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.extractor_common as extractor_common
import src.harvester as harvester
import src.schema as schema
import src.triage as triage


# ===========================================================================
# 1. Harvester tests (COMP-01, D-01, D-02, D-03, T-17-03)
# ===========================================================================


def test_harvester_profile_and_hybrid_queries() -> None:
    """Verify D-01 surgical default vs conservative switch and D-02 hybrid query resolution."""
    # D-01: surgical default for empty, surgical, and mixed configs
    assert harvester.resolve_treatment_profile({}) == "surgical"
    assert harvester.resolve_treatment_profile({"treatment_profile": "surgical"}) == "surgical"
    assert harvester.resolve_treatment_profile({"treatment_profile": "mixed"}) == "surgical"
    assert harvester.resolve_treatment_profile({"nosology": {"treatment_profile": "mixed"}}) == "surgical"
    assert harvester.resolve_treatment_profile({"surgical_focus": True}) == "surgical"

    # D-01: explicit conservative switches at root or nested nosology: level
    assert harvester.resolve_treatment_profile({"surgical_focus": False}) == "conservative"
    assert harvester.resolve_treatment_profile({"nosology": {"surgical_focus": False}}) == "conservative"
    assert harvester.resolve_treatment_profile({"treatment_profile": "conservative"}) == "conservative"
    assert (
        harvester.resolve_treatment_profile({"nosology": {"treatment_profile": "conservative"}})
        == "conservative"
    )

    # D-02: auto-generated surgical queries bounded by date_range
    surgical_cfg: dict[str, Any] = {
        "nosology": {
            "id": "mock_trigger",
            "name_en": "Trigger Finger",
            "mesh_terms": ["Trigger Finger Disorder"],
        },
        "date_range": {"start_year": 2018, "end_year": 2025},
        "triage_rules": {"core_terms": ["trigger finger", "A1 pulley"]},
    }
    res_surg = harvester.build_complications_queries(surgical_cfg)
    assert harvester.resolve_complications_queries is harvester.build_complications_queries
    assert res_surg["profile"] == "surgical"
    assert res_surg["surgical_focus"] is True
    assert '"Trigger Finger Disorder"[MeSH]' in res_surg["pubmed"]
    assert '"trigger finger"[tiab]' in res_surg["pubmed"]
    assert '"Postoperative Complications"[MeSH]' in res_surg["pubmed"]
    assert '"2018/01/01"[Date - Publication]' in res_surg["pubmed"]
    assert '"2025/12/31"[Date - Publication]' in res_surg["pubmed"]
    assert '"postoperative complications"' in res_surg["europepmc"]
    assert "FIRST_PDATE:[2018-01-01 TO 2025-12-31]" in res_surg["europepmc"]

    # D-01 / D-02: conservative switch auto-generates drug/adverse reaction query block
    conservative_cfg = {
        **surgical_cfg,
        "nosology": {**surgical_cfg["nosology"], "surgical_focus": False},
    }
    res_cons = harvester.build_complications_queries(conservative_cfg)
    assert res_cons["profile"] == "conservative"
    assert res_cons["surgical_focus"] is False
    assert '"Drug-Related Side Effects and Adverse Reactions"[MeSH]' in res_cons["pubmed"]
    assert '"Postoperative Complications"[MeSH]' not in res_cons["pubmed"]
    assert '"CTCAE"' in res_cons["europepmc"]
    assert "FIRST_PDATE:[2018-01-01 TO 2025-12-31]" in res_cons["europepmc"]

    # D-02: explicit complications_queries override takes precedence over auto-generation
    override_cfg = {
        **surgical_cfg,
        "complications_queries": {
            "pubmed": '("Trigger Finger Disorder"[MeSH]) AND ("bowstringing"[tiab] OR "nerve injury"[tiab])',
            "europepmc": '("trigger finger") AND ("bowstringing" OR "nerve injury")',
            "pubmed_max_results": 250,
            "europepmc_max_results": 350,
        },
    }
    res_ovr = harvester.build_complications_queries(override_cfg)
    assert res_ovr["pubmed"] == override_cfg["complications_queries"]["pubmed"]
    assert res_ovr["europepmc"] == override_cfg["complications_queries"]["europepmc"]
    assert res_ovr["pubmed_max_results"] == 250
    assert res_ovr["europepmc_max_results"] == 350


def test_harvester_complications_cache_and_provenance_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify D-03 separate raw JSON caches, provenance merging via upsert_article, and cache reuse (T-17-03)."""
    db_path = tmp_path / "literature.db"
    raw_dir = tmp_path / "raw"
    conn = schema.init_db(db_path)

    # Seed existing article from main PubMed harvesting pass
    harvester.upsert_article(
        conn,
        {
            "pmid": "39000001",
            "doi": "10.1000/main.39000001",
            "title": "Open A1 pulley release outcomes and postoperative morbidity in 120 patients",
            "abstract": "Prospective study of 120 patients.",
            "journal": "Journal of Hand Surgery",
            "pub_year": 2023,
            "pub_date": "2023-05-01",
            "authors": ["Smith J"],
            "language": "eng",
            "pub_types": ["Journal Article"],
            "sources": ["PubMed"],
        },
    )
    conn.commit()

    call_counts = {"pm_search": 0, "pm_abs": 0, "pm_sum": 0, "epmc_search": 0}

    fake_pubmed_mod = types.SimpleNamespace()

    def _fake_search_pubmed(query: str, max_results: int = 800, sort_by: str = "relevance") -> list[str]:
        call_counts["pm_search"] += 1
        return ["39000001", "39000002"]

    def _fake_fetch_abstracts(batch: list[str]) -> list[dict[str, Any]]:
        call_counts["pm_abs"] += 1
        return [
            {
                "pmid": "39000001",
                "doi": "10.1000/main.39000001",
                "title": "Open A1 pulley release outcomes and postoperative morbidity in 120 patients",
                "abstract": "Prospective study of 120 patients reporting postoperative wound infection in 6/120 (5.0%).",
                "journal": "Journal of Hand Surgery",
                "pubdate": "2023 May",
                "authors": ["Smith J", "Doe A"],
            },
            {
                "pmid": "39000002",
                "doi": "10.1000/comp.39000002",
                "title": "Iatrogenic digital nerve injury after percutaneous trigger finger release",
                "abstract": "Cohort of 64 patients evaluating Clavien-Dindo IIIb complications.",
                "journal": "Hand Clinics",
                "pubdate": "2024 Feb",
                "authors": ["Lee K"],
            },
        ]

    def _fake_fetch_summary(db_name: str, batch: list[str]) -> list[dict[str, Any]]:
        call_counts["pm_sum"] += 1
        return [
            {
                "uid": "39000001",
                "pubtype": ["Journal Article"],
                "lang": ["eng"],
                "articleids": [{"idtype": "doi", "value": "10.1000/main.39000001"}],
            },
            {
                "uid": "39000002",
                "pubtype": ["Journal Article"],
                "lang": ["eng"],
                "articleids": [
                    {"idtype": "pmc", "value": "9900002"},
                    {"idtype": "doi", "value": "10.1000/comp.39000002"},
                ],
            },
        ]

    fake_pubmed_mod.search_pubmed = _fake_search_pubmed
    fake_pubmed_mod.fetch_article_abstracts = _fake_fetch_abstracts
    fake_pubmed_mod.fetch_database_summary = _fake_fetch_summary

    fake_epmc_mod = types.SimpleNamespace()

    def _fake_epmc_search(
        query: str, max_results: int = 1000, result_type: str = "core", cursor: str = "*"
    ) -> dict[str, Any]:
        call_counts["epmc_search"] += 1
        return {
            "hitCount": 2,
            "results": [
                {
                    "pmid": "39000001",
                    "pmcid": "PMC9900001",
                    "doi": "10.1000/main.39000001",
                    "title": "Open A1 pulley release outcomes and postoperative morbidity in 120 patients",
                    "abstractText": "Longer open-access abstract with Clavien-Dindo complication breakdown.",
                    "journalTitle": "Journal of Hand Surgery",
                    "pubYear": "2023",
                    "firstPublicationDate": "2023-05-01",
                    "authorString": "Smith J, Doe A",
                    "language": "eng",
                    "pubTypeList": {"pubType": ["Journal Article"]},
                    "citedByCount": 14,
                    "isOpenAccess": "Y",
                },
                {
                    "pmid": "39000003",
                    "pmcid": "PMC9900003",
                    "doi": "10.1000/comp.39000003",
                    "title": "Scar tenderness and postoperative stiffness after endoscopic carpal release",
                    "abstractText": "Retrospective cohort of 88 patients with transient scar pain resolving within 3 months.",
                    "journalTitle": "BMC Musculoskeletal Disorders",
                    "pubYear": "2024",
                    "firstPublicationDate": "2024-06-15",
                    "authorString": "Patel R",
                    "language": "eng",
                    "pubTypeList": {"pubType": ["Journal Article"]},
                    "citedByCount": 3,
                    "isOpenAccess": "Y",
                },
            ],
        }

    fake_epmc_mod.search = _fake_epmc_search

    def _fake_load_skill_module(name: str, script_path: Path):
        if name == "pubmed_api":
            return fake_pubmed_mod
        if name == "europepmc_api":
            return fake_epmc_mod
        raise AssertionError(f"Unexpected skill module requested: {name}")

    monkeypatch.setattr(harvester, "load_skill_module", _fake_load_skill_module)

    try:
        n_pm = harvester.harvest_pubmed_complications(
            "mock pubmed complications query", raw_dir, conn, profile="surgical", max_results=50
        )
        n_epmc = harvester.harvest_europepmc_complications(
            "mock epmc complications query", raw_dir, conn, profile="surgical", max_results=50
        )

        assert n_pm == 2
        assert n_epmc == 2

        # Separate fixed raw caches exist; zero main-pass europepmc_page_*.json files created
        assert (raw_dir / "pubmed_complications.json").exists()
        assert (raw_dir / "europepmc_complications.json").exists()
        assert list(raw_dir.glob("europepmc_page_*.json")) == []

        # Deduplicated into 3 unique articles
        total_rows = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        assert total_rows == 3

        row_merged = conn.execute(
            "SELECT pmid, pmcid, cited_by_count, sources FROM articles WHERE pmid = ?",
            ("39000001",),
        ).fetchone()
        assert row_merged is not None
        assert row_merged["pmcid"] == "PMC9900001"
        assert row_merged["cited_by_count"] == 14
        merged_sources = json.loads(row_merged["sources"])
        assert merged_sources == ["PubMed", "PubMed:Complications", "EuropePMC:Complications"]

        row_pm_only = conn.execute(
            "SELECT pmcid, sources FROM articles WHERE pmid = ?", ("39000002",)
        ).fetchone()
        assert row_pm_only["pmcid"] == "PMC9900002"
        assert json.loads(row_pm_only["sources"]) == ["PubMed:Complications"]

        row_epmc_only = conn.execute(
            "SELECT pmcid, sources FROM articles WHERE pmid = ?", ("39000003",)
        ).fetchone()
        assert row_epmc_only["pmcid"] == "PMC9900003"
        assert json.loads(row_epmc_only["sources"]) == ["EuropePMC:Complications"]

        # Second invocation MUST read from disk cache without re-invoking mocked skill APIs
        n_pm_cached = harvester.harvest_pubmed_complications(
            "mock pubmed complications query", raw_dir, conn, profile="surgical", max_results=50
        )
        n_epmc_cached = harvester.harvest_europepmc_complications(
            "mock epmc complications query", raw_dir, conn, profile="surgical", max_results=50
        )
        assert n_pm_cached == 2
        assert n_epmc_cached == 2
        assert call_counts == {"pm_search": 1, "pm_abs": 1, "pm_sum": 1, "epmc_search": 1}

        # Re-upsert did not duplicate rows or provenance labels
        assert conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 3
        recheck_sources = json.loads(
            conn.execute("SELECT sources FROM articles WHERE pmid = ?", ("39000001",)).fetchone()[0]
        )
        assert recheck_sources == ["PubMed", "PubMed:Complications", "EuropePMC:Complications"]
    finally:
        conn.close()


# ===========================================================================
# 2. PRISMA Triage & XML Priority Queue tests (COMP-02, D-04..D-06, T-17-04)
# ===========================================================================


def test_triage_complications_safety_three_triggers_and_context() -> None:
    """Verify D-05 3-source complications_safety tagging and complication-aware PRISMA inclusion."""
    clusters_cfg = {
        "surgical_outcomes": {"keywords": ["pulley release", "open surgery"]},
    }
    triage_rules = {
        "core_terms": ["trigger finger", "stenosing tenosynovitis"],
        "context_terms": ["corticosteroid injection", "splinting"],
        "complication_terms": ["pillar pain", "flexor bowstringing"],
        "rare_complication_terms": ["digital artery pseudoaneurysm"],
    }

    # (a) Trigger 1: :Complications provenance tag alone
    assert triage.should_tag_complications_safety(
        "Long-term functional outcomes after A1 pulley release",
        "Follow-up assessment of grip strength over 24 months.",
        sources=["PubMed:Complications"],
    )
    assert triage.should_tag_complications_safety(
        "Functional follow-up study",
        "No explicit safety keywords in abstract.",
        sources='["EuropePMC:Complications"]',
    )
    assert not triage.should_tag_complications_safety(
        "Functional follow-up study",
        "Grip strength and patient satisfaction scores after splinting.",
        sources=["PubMed"],
    )

    # (b) Trigger 2: Built-in universal surgical / conservative safety terms
    assert triage.should_tag_complications_safety(
        "Clavien-Dindo grade II wound dehiscence after hand surgery",
        "Surgical site management in routine practice.",
    )
    assert triage.should_tag_complications_safety(
        "Systemic toxicity graded by CTCAE during pharmacotherapy",
        "Adverse events recorded over 12 weeks.",
    )

    # (c) Trigger 3: YAML complication_terms and rare_complication_terms
    assert triage.should_tag_complications_safety(
        "Postoperative pillar pain after release",
        "Prospective evaluation of palmar discomfort.",
        triage_rules=triage_rules,
    )
    assert triage.should_tag_complications_safety(
        "Digital artery pseudoaneurysm following percutaneous procedure",
        "Rare vascular event managed surgically.",
        triage_rules=triage_rules,
    )

    # assign_clusters combines YAML clusters + complications_safety without duplication
    assigned = triage.assign_clusters(
        "Open surgery pulley release and Clavien-Dindo wound dehiscence",
        "Postoperative complication profile evaluated in 90 patients.",
        clusters_cfg,
        sources=["PubMed:Complications"],
        triage_rules=triage_rules,
    )
    assert "surgical_outcomes" in assigned
    assert "complications_safety" in assigned
    assert assigned.count("complications_safety") == 1

    # PRISMA status retains core_terms + complication vocabulary even if context_terms absent
    status_comp_vocab = triage.classify_prisma_status(
        "Wound dehiscence and Clavien-Dindo morbidity in trigger finger release",
        "Retrospective cohort of 84 patients assessing postoperative wound complications.",
        pub_year=2024,
        language="eng",
        start_year=2016,
        end_year=2026,
        triage_rules=triage_rules,
        sources=["PubMed"],
    )
    assert status_comp_vocab == "included"

    status_comp_prov = triage.classify_prisma_status(
        "Trigger finger release functional follow-up",
        "Evaluated outcomes after surgery in 55 adults.",
        pub_year=2024,
        language="eng",
        start_year=2016,
        end_year=2026,
        triage_rules=triage_rules,
        sources=["EuropePMC:Complications"],
    )
    assert status_comp_prov == "included"

    status_offtopic = triage.classify_prisma_status(
        "Trigger finger anatomy in healthy volunteers",
        "Ultrasound measurement of normal tendon thickness without therapy.",
        pub_year=2024,
        language="eng",
        start_year=2016,
        end_year=2026,
        triage_rules=triage_rules,
        sources=["PubMed"],
    )
    assert status_offtopic == "excluded_offtopic"


def test_triage_two_contour_casuistry_vs_cohorts() -> None:
    """Verify D-04 separation between Tier 1-3 (N >= 20) cohorts and Tier 4 / N < 20 casuistry."""
    # Case Report -> Tier 4 + rare_catastrophic_case
    t_case, types_case = triage.classify_evidence_tier(
        "Iatrogenic digital nerve injury after percutaneous release: a case report",
        "We describe a single patient with complete digital nerve transection requiring microsurgical repair.",
        ["Case Reports"],
    )
    assert t_case == 4
    assert "rare_catastrophic_case" in types_case
    assert "Rare Complication Case [D-05]" in types_case

    # Small clinical series (1 <= N < 20) -> Tier 4 + rare_catastrophic_case
    t_small, types_small = triage.classify_evidence_tier(
        "Complications of revision pulley surgery in a small clinical series",
        "We retrospectively analyzed 12 patients treated for iatrogenic nerve injury after open release across two clinics.",
        ["Journal Article"],
    )
    assert t_small == 4
    assert "rare_catastrophic_case" in types_small

    # Prospective cohort (N = 85 >= 20) -> stays in Tier 2 cohort contour
    t_cohort, types_cohort = triage.classify_evidence_tier(
        "Prospective cohort of 85 patients comparing open versus percutaneous release",
        "A prospective cohort of 85 patients was followed for 24 months to quantify wound infection and scar tenderness.",
        ["Journal Article"],
    )
    assert t_cohort == 2
    assert "rare_catastrophic_case" not in types_cohort

    # Threshold boundary N = 20 stays in cohort contour (Tier 3)
    t_boundary, types_boundary = triage.classify_evidence_tier(
        "Postoperative scar tenderness after release",
        "Retrospective series of 20 patients evaluated for scar pain and transient stiffness over 12 months.",
        ["Journal Article"],
    )
    assert t_boundary == 3
    assert "rare_catastrophic_case" not in types_boundary

    # Basic science in vitro study of 6 cell lines -> exempt from N < 20 clinical demotion, stays Tier 3
    t_basic, types_basic = triage.classify_evidence_tier(
        "Collagen remodeling in tendon sheath fibroblasts",
        "An in vitro study of 6 cell lines evaluating TGF-beta signaling and extracellular matrix deposition.",
        ["Journal Article"],
    )
    assert t_basic == 3
    assert "rare_catastrophic_case" not in types_basic


def test_triage_xml_priority_queue_and_prisma_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify D-06 priority XML queue, T-17-04 PMCID_RE blocking, and COMP-02 prisma_stats.md reporting."""
    db_path = tmp_path / "literature.db"
    raw_dir = tmp_path / "raw"
    fulltext_dir = raw_dir / "fulltext_xml"
    report_path = tmp_path / "reports" / "prisma_stats.md"
    conn = schema.init_db(db_path)

    try:
        # 1. High-citation general Tier 2 article
        conn.execute(
            """
            INSERT INTO articles (
                pmid, pmcid, title, norm_title, pub_year, prisma_status,
                evidence_tier, clusters, cited_by_count, is_open_access, sources, pub_types
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "40000001",
                "PMC100001",
                "High-citation general prospective cohort study",
                "highcitationgeneralprospectivecohortstudy",
                2023,
                "included",
                2,
                json.dumps(["clinical_treatment"]),
                200,
                1,
                json.dumps(["EuropePMC"]),
                json.dumps(["Journal Article"]),
            ),
        )
        # 2. Lower-citation Tier 3 complication article (MUST be prioritized first per D-06)
        conn.execute(
            """
            INSERT INTO articles (
                pmid, pmcid, title, norm_title, pub_year, prisma_status,
                evidence_tier, clusters, cited_by_count, is_open_access, sources, pub_types
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "40000002",
                "PMC100002",
                "Postoperative wound complications after surgical release",
                "postoperativewoundcomplicationsaftersurgicalrelease",
                2024,
                "included",
                3,
                json.dumps(["complications_safety"]),
                5,
                1,
                json.dumps(["EuropePMC:Complications"]),
                json.dumps(["Journal Article"]),
            ),
        )
        # 3. Malicious path-traversal PMCID (T-17-04) — even with Tier 1 & cited_by_count=999
        conn.execute(
            """
            INSERT INTO articles (
                pmid, pmcid, title, norm_title, pub_year, prisma_status,
                evidence_tier, clusters, cited_by_count, is_open_access, sources, pub_types
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "40000003",
                "../evil",
                "Adversarial traversal PMCID record",
                "adversarialtraversalpmcidrecord",
                2024,
                "included",
                1,
                json.dumps(["complications_safety"]),
                999,
                1,
                json.dumps(["EuropePMC:Complications"]),
                json.dumps(["Meta-Analysis"]),
            ),
        )
        # 4. Tier 4 rare catastrophic case (lower priority than Tier 1-3, counted in PRISMA report)
        conn.execute(
            """
            INSERT INTO articles (
                pmid, pmcid, title, norm_title, pub_year, prisma_status,
                evidence_tier, clusters, cited_by_count, is_open_access, sources, pub_types
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "40000004",
                "PMC100004",
                "Catastrophic nerve transection: a case report",
                "catastrophicnervetransectionacasereport",
                2024,
                "included",
                4,
                json.dumps(["complications_safety"]),
                150,
                1,
                json.dumps(["EuropePMC:Complications"]),
                json.dumps(["Case Reports", "rare_catastrophic_case"]),
            ),
        )
        conn.commit()

        requested_urls: list[str] = []
        valid_xml_payload = (
            b"<article><body><sec><title>Adverse Events</title>"
            b"<p>" + (b"Detailed postoperative complications table text. " * 10) + b"</p>"
            b"</sec></body></article>"
        )
        assert len(valid_xml_payload) > 250

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self) -> bytes:
                return valid_xml_payload

        def _fake_urlopen(req, timeout=8):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            requested_urls.append(url)
            return _FakeResponse()

        monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

        downloaded = triage.download_fulltexts_tier1_to_3(conn, fulltext_dir, max_downloads=1)
        assert downloaded == 1
        assert (fulltext_dir / "PMC100002.xml").exists()
        assert not (fulltext_dir / "PMC100001.xml").exists()
        assert not (fulltext_dir / "PMC100004.xml").exists()
        assert not (raw_dir / "evil.xml").exists()
        assert len(requested_urls) == 1
        assert "PMC100002" in requested_urls[0]
        assert all("evil" not in u for u in requested_urls)

        ft_row = conn.execute(
            "SELECT has_fulltext_xml, fulltext_path FROM articles WHERE pmcid = ?",
            ("PMC100002",),
        ).fetchone()
        assert ft_row["has_fulltext_xml"] == 1
        assert Path(ft_row["fulltext_path"]).name == "PMC100002.xml"

        # Seed raw JSON caches and verify generate_prisma_report() totals & complications_safety row
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "pubmed_pmids.json").write_text(json.dumps(["40000001", "40000002"]), encoding="utf-8")
        (raw_dir / "pubmed_complications.json").write_text(
            json.dumps({"pmids": ["40000002", "40000003", "40000005"], "records": []}),
            encoding="utf-8",
        )
        (raw_dir / "europepmc_complications.json").write_text(
            json.dumps({"results": [{"pmid": "40000002"}, {"pmid": "40000006"}]}),
            encoding="utf-8",
        )

        cfg = {
            "nosology": {"id": "mock_nosology", "name_ru": "Тестовая нозология"},
            "date_range": {"start_year": 2016, "end_year": 2026},
            "clusters": {"clinical_treatment": {"name_ru": "Клиническое лечение"}},
        }
        triage.generate_prisma_report(conn, cfg, raw_dir, report_path)

        report_md = report_path.read_text(encoding="utf-8")
        # total_raw = 2 (pubmed) + 3 (pubmed_comp) + 2 (epmc_comp) = 7
        assert "N = 7" in report_md
        assert "PubMed:Complications: 3 | EuropePMC:Complications: 2" in report_md
        assert "| `complications_safety` |" in report_md
        assert "| `complications_safety` | Безопасность лечения и хирургические осложнения (D-05) | 3 | 1 | 1 |" in report_md
    finally:
        conn.close()


# ===========================================================================
# 3. Schema & Extractor tests (COMP-03, D-04, D-07, D-08, T-17-01)
# ===========================================================================


def test_schema_and_extractor_dual_axis_and_recurrence_guard(tmp_path: Path) -> None:
    """Verify idempotent DDL, dual-axis Clavien-Dindo/CTCAE, recurrence exclusion, casuistry guard, and SQL safety."""
    db_path = tmp_path / "complications.db"

    # Idempotent init_db()
    conn1 = schema.init_db(db_path)
    conn1.close()
    conn = schema.init_db(db_path)

    try:
        for expected_tbl in (
            "articles",
            "clinical_trials",
            "extracted_clinical_evidence",
            "extracted_mechanisms",
            "extracted_complications",
        ):
            assert extractor_common.table_exists(conn, expected_tbl) is True

        cols = [r[1] for r in conn.execute("PRAGMA table_info(extracted_complications)").fetchall()]
        assert len(cols) == 20
        assert set(cols) == {
            "id",
            "article_id",
            "pmid",
            "doi",
            "first_author_year",
            "evidence_tier",
            "modality",
            "complication_name",
            "event_class",
            "timing_category",
            "clavien_dindo_grade",
            "ctcae_grade",
            "frequency_pct",
            "frequency_num",
            "reversibility",
            "time_window",
            "anatomical_substrate",
            "prevention_and_management",
            "sample_size",
            "is_rare_casuistry",
        }
        indexes = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'extracted_complications'"
            ).fetchall()
        }
        assert {
            "idx_ext_comp_article",
            "idx_ext_comp_modality",
            "idx_ext_comp_grade",
            "idx_ext_comp_class",
        }.issubset(indexes)

        # Dual-axis Clavien-Dindo + CTCAE normalization (D-07)
        assert extractor_common.normalize_clavien_dindo("I") == ("I", None)
        assert extractor_common.normalize_clavien_dindo("Clavien-Dindo Grade II") == ("II", None)
        assert extractor_common.normalize_clavien_dindo("IIIa") == ("IIIa", None)
        assert extractor_common.normalize_clavien_dindo("IIIb") == ("IIIb", None)
        assert extractor_common.normalize_clavien_dindo("III", requires_reoperation=False) == ("IIIa", None)
        assert extractor_common.normalize_clavien_dindo("III", requires_reoperation=True) == ("IIIb", None)
        assert extractor_common.normalize_clavien_dindo("IVa") == ("IV", None)
        assert extractor_common.normalize_clavien_dindo("IVb") == ("IV", None)
        assert extractor_common.normalize_clavien_dindo("V") == ("V", None)
        assert extractor_common.normalize_clavien_dindo(ctcae_grade=1) == ("I", "Grade 1")
        assert extractor_common.normalize_clavien_dindo(ctcae_grade="Grade 2") == ("II", "Grade 2")
        assert extractor_common.normalize_clavien_dindo(ctcae_grade="CTCAE Grade 3") == ("IIIa", "Grade 3")
        assert extractor_common.normalize_clavien_dindo(ctcae_grade="4") == ("IV", "Grade 4")
        assert extractor_common.normalize_clavien_dindo(ctcae_grade="G5") == ("V", "Grade 5")
        assert extractor_common.normalize_clavien_dindo("CTCAE Grade 3") == ("IIIa", "Grade 3")

        with pytest.raises(ValueError):
            extractor_common.normalize_clavien_dindo("VI")
        with pytest.raises(ValueError):
            extractor_common.normalize_clavien_dindo(ctcae_grade="Grade 6")
        with pytest.raises(ValueError):
            extractor_common.normalize_clavien_dindo(None, None)

        # D-08: Recurrence / incomplete release exclusion guard
        for excluded_name in (
            "true recurrence",
            "True Recurrence",
            "disease recurrence",
            "incomplete release",
            "Incomplete division of A1 pulley",
            "persistent triggering",
            "истинный рецидив",
            "рецидив заболевания",
            "неполный релиз",
        ):
            assert extractor_common.is_excluded_recurrence_event(excluded_name) is True
        assert extractor_common.is_excluded_recurrence_event("Wound dehiscence") is False
        assert extractor_common.is_excluded_recurrence_event("Scar tenderness") is False

        # Invalid enum rejections
        with pytest.raises(ValueError, match="reversibility"):
            extractor_common.insert_extracted_complication(
                conn,
                {
                    "modality": "Open release",
                    "complication_name": "Wound infection",
                    "clavien_dindo_grade": "II",
                    "reversibility": "unknown_status",
                },
            )
        with pytest.raises(ValueError, match="event_class"):
            extractor_common.insert_extracted_complication(
                conn,
                {
                    "modality": "Open release",
                    "complication_name": "Wound infection",
                    "clavien_dindo_grade": "II",
                    "event_class": "bogus_class",
                    "reversibility": "requires_conservative_therapy",
                },
            )
        with pytest.raises(ValueError, match="D-08"):
            extractor_common.insert_extracted_complication(
                conn,
                {
                    "modality": "Open release",
                    "complication_name": "True recurrence",
                    "clavien_dindo_grade": "IIIb",
                    "reversibility": "requires_reoperation",
                },
            )
        assert (
            extractor_common.insert_extracted_complication(
                conn,
                {
                    "modality": "Open release",
                    "complication_name": "истинный рецидив",
                    "clavien_dindo_grade": "IIIb",
                    "reversibility": "requires_reoperation",
                },
                skip_recurrence=True,
            )
            is None
        )

        # D-08: transient_postop_sequela auto-populates time_window (extracted or default)
        seq_id = extractor_common.insert_extracted_complication(
            conn,
            {
                "pmid": "50000001",
                "evidence_tier": 2,
                "modality": "Open release",
                "complication_name": "Scar tenderness",
                "event_class": "transient_postop_sequela",
                "clavien_dindo_grade": "I",
                "frequency_pct": "18.0%",
                "frequency_num": 18.0,
                "reversibility": "transient_self_limiting",
                "prevention_and_management": "Scar massage; typically resolves within 3–6 months.",
                "sample_size": 100,
            },
        )
        assert seq_id is not None

        seq_default_id = extractor_common.insert_extracted_complication(
            conn,
            {
                "pmid": "50000002",
                "evidence_tier": 2,
                "modality": "Open release",
                "complication_name": "Local postoperative edema",
                "event_class": "transient_postop_sequela",
                "clavien_dindo_grade": "I",
                "frequency_pct": "12.0%",
                "frequency_num": 12.0,
                "reversibility": "transient_self_limiting",
                "sample_size": 80,
            },
        )
        assert seq_default_id is not None

        # D-04: Tier 4 1/1 (100%) sets is_rare_casuistry = 1 and frequency_num = None
        cas_id = extractor_common.insert_extracted_complication(
            conn,
            {
                "pmid": "50000003",
                "evidence_tier": 4,
                "modality": "Percutaneous release",
                "complication_name": "Complete radial digital nerve transection",
                "event_class": "true_complication",
                "clavien_dindo_grade": "III",
                "frequency_pct": "1/1 (100%)",
                "frequency_num": 100.0,
                "reversibility": "requires_reoperation",
                "sample_size": 1,
            },
        )
        assert cas_id is not None

        # T-17-01: Parameterized SQL injection safety in table_exists() and insert/fetch
        assert extractor_common.table_exists(conn, "extracted_complications' OR '1'='1") is False
        assert extractor_common.table_exists(conn, "articles; DROP TABLE articles;--") is False

        sqli_payload = "Scar pain'); DROP TABLE extracted_complications;--"
        sqli_id = extractor_common.insert_extracted_complication(
            conn,
            {
                "pmid": "50000004",
                "evidence_tier": 3,
                "modality": "Open release",
                "complication_name": sqli_payload,
                "event_class": "true_complication",
                "clavien_dindo_grade": "I",
                "frequency_pct": "4.0%",
                "frequency_num": 4.0,
                "reversibility": "transient_self_limiting",
                "sample_size": 50,
            },
        )
        assert sqli_id is not None
        assert extractor_common.table_exists(conn, "extracted_complications") is True

        all_rows = extractor_common.fetch_extracted_complications(conn)
        by_id = {r["id"]: r for r in all_rows}
        assert by_id[seq_id]["time_window"] == "within 3–6 months"
        assert by_id[seq_default_id]["time_window"] == extractor_common.DEFAULT_SEQUELA_TIME_WINDOW
        assert by_id[cas_id]["is_rare_casuistry"] == 1
        assert by_id[cas_id]["frequency_num"] is None
        assert by_id[cas_id]["clavien_dindo_grade"] == "IIIb"
        assert by_id[sqli_id]["complication_name"] == sqli_payload

        # Parameterized modality filter and casuistry filter
        assert extractor_common.fetch_extracted_complications(conn, modality="Open' OR '1'='1") == []
        cohort_only = extractor_common.fetch_extracted_complications(conn, include_casuistry=False)
        assert all(r["is_rare_casuistry"] == 0 for r in cohort_only)
        assert cas_id not in {r["id"] for r in cohort_only}
    finally:
        conn.close()


def test_schema_and_extractor_jats_xml_and_frequency_regex(tmp_path: Path) -> None:
    """Verify JATS XML safety section/table parsing and CI-safe rate/grade/time-window regexes."""
    xml_path = tmp_path / "PMC777777.xml"
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<article>
  <front>
    <article-meta>
      <abstract>
        <p>Prospective cohort evaluating postoperative complications after open surgical release.</p>
      </abstract>
    </article-meta>
  </front>
  <body>
    <sec>
      <title>Methods</title>
      <p>A total of 76 patients underwent open release under local anesthesia with standardized follow-up.</p>
    </sec>
    <sec>
      <title>Adverse Events and Morbidity</title>
      <p>Postoperative wound complications occurred in 14/76 (18.4%), 95% CI 10.2–28.1%, classified as Clavien-Dindo grade II requiring oral antibiotics. Transient scar tenderness resolved within 3–6 months in all patients.</p>
    </sec>
    <table-wrap id="T2">
      <label>Table 2</label>
      <caption><p>Postoperative adverse events</p></caption>
      <table>
        <thead>
          <tr><th>Complication</th><th>Incidence</th><th>Grade</th></tr>
        </thead>
        <tbody>
          <tr><td>Superficial wound infection</td><td>14/76 (18.4%)</td><td>Clavien-Dindo grade II</td></tr>
        </tbody>
      </table>
    </table-wrap>
  </body>
</article>
"""
    xml_path.write_text(xml_content, encoding="utf-8")

    parsed = extractor_common.parse_jats_xml(xml_path)
    assert parsed["has_xml"] is True
    assert "14/76 (18.4%)" in parsed["results_text"]
    assert "Clavien-Dindo grade II" in parsed["results_text"]
    assert len(parsed["tables"]) == 1
    assert "Superficial wound infection | 14/76 (18.4%) | Clavien-Dindo grade II" in parsed["tables"][0]

    # Frequency extraction ignores 95% CI decoys
    freq_str, freq_num, denom = extractor_common.extract_complication_frequency(parsed["results_text"])
    assert freq_str == "18.4% (14/76)"
    assert freq_num == 18.4
    assert denom == 76

    assert extractor_common.extract_complication_frequency("95% CI 10.2–28.1%") == (None, None, None)
    assert extractor_common.extract_complication_frequency("Rate was 12.5% (95% CI 8.1–17.2%)") == (
        "12.5%",
        12.5,
        None,
    )
    assert extractor_common.extract_complication_frequency("Incidence 18.4% (14/76) overall") == (
        "18.4% (14/76)",
        18.4,
        76,
    )
    assert extractor_common.extract_complication_frequency("Observed range 5–15% across cohorts") == (
        "5–15%",
        10.0,
        None,
    )

    # Clavien-Dindo / CTCAE text extraction
    assert extractor_common.extract_clavien_dindo_grade(parsed["results_text"]) == ("II", None)
    assert extractor_common.extract_clavien_dindo_grade(
        "Complication classified as Clavien-Dindo grade III required reoperation"
    ) == ("IIIb", None)
    assert extractor_common.extract_clavien_dindo_grade("Systemic event scored CTCAE grade 3") == (
        "IIIa",
        "Grade 3",
    )
    assert extractor_common.extract_clavien_dindo_grade("No adverse grading mentioned here.") == (None, None)

    # Resolution time window extraction (EN + RU)
    assert extractor_common.extract_resolution_time_window(parsed["results_text"]) == "within 3–6 months"
    assert (
        extractor_common.extract_resolution_time_window(
            "Локальный отек и болезненность рубца регрессируют в течение 2–4 месяцев."
        )
        == "в течение 2–4 месяцев"
    )
    assert extractor_common.extract_resolution_time_window("No temporal duration reported.") is None
