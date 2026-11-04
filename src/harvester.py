# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "pyyaml",
# ]
# ///
"""Universal literature harvester for nosologies (Phase 1, Plan 01-01).

Harvests publications (2016-2026) from PubMed, Europe PMC, OpenAlex, and
clinical trials from ClinicalTrials.gov using the official Science Skill CLI
wrappers with rate limiting and local JSON caching.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.schema import init_db

SKILLS_ROOT = Path.home() / ".gemini" / "config" / "plugins" / "science" / "skills"
PUBMED_SCRIPT = SKILLS_ROOT / "pubmed_database" / "scripts" / "pubmed_api.py"
EPMC_SCRIPT = SKILLS_ROOT / "literature_search_europepmc" / "scripts" / "europepmc_api.py"
OPENALEX_SCRIPT = SKILLS_ROOT / "literature_search_openalex" / "scripts" / "openalex_cli.py"
CT_SCRIPT = SKILLS_ROOT / "clinical_trials_database" / "scripts" / "clinical_trials_api.py"


def get_uv_bin() -> str:
    uv_in_path = shutil.which("uv")
    if uv_in_path:
        return uv_in_path
    local_uv = Path.home() / ".local" / "bin" / ("uv.exe" if os.name == "nt" else "uv")
    if local_uv.exists():
        return str(local_uv)
    raise RuntimeError("uv executable not found on PATH or ~/.local/bin")


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d.strip() or None


def normalize_title(title: str | None) -> str:
    if not title:
        return ""
    clean = re.sub(r"<[^>]+>", " ", title.lower())
    clean = re.sub(r"[^a-z0-9а-яё]+", "", clean)
    return clean[:180]


def extract_year(date_str: str | int | None, default_year: int | None = None) -> int | None:
    if isinstance(date_str, int):
        return date_str
    if not date_str:
        return default_year
    m = re.search(r"\b(201[6-9]|202[0-6])\b", str(date_str))
    if m:
        return int(m.group(1))
    m2 = re.search(r"\b(19\d\d|20\d\d)\b", str(date_str))
    return int(m2.group(1)) if m2 else default_year


def reconstruct_openalex_abstract(inv_idx: dict[str, list[int]] | None) -> str | None:
    if not inv_idx or not isinstance(inv_idx, dict):
        return None
    pos_map: dict[int, str] = {}
    for word, positions in inv_idx.items():
        if isinstance(positions, list):
            for p in positions:
                if isinstance(p, int):
                    pos_map[p] = word
    if not pos_map:
        return None
    return " ".join(pos_map[k] for k in sorted(pos_map.keys()))


def upsert_article(conn: sqlite3.Connection, rec: dict[str, Any]) -> None:
    """Insert or merge an article record into SQLite with deduplication (D-01, D-02)."""
    cur = conn.cursor()
    pmid = str(rec.get("pmid") or "").strip() or None
    pmcid = str(rec.get("pmcid") or "").strip() or None
    doi = normalize_doi(rec.get("doi"))
    openalex_id = str(rec.get("openalex_id") or "").strip() or None
    title = (rec.get("title") or "").strip()
    if not title:
        return
    norm_t = normalize_title(title)
    if not norm_t:
        return

    existing = None
    if pmid:
        existing = cur.execute("SELECT * FROM articles WHERE pmid = ?", (pmid,)).fetchone()
    if not existing and doi:
        existing = cur.execute("SELECT * FROM articles WHERE doi = ?", (doi,)).fetchone()
    if not existing and norm_t and len(norm_t) >= 20:
        existing = cur.execute("SELECT * FROM articles WHERE norm_title = ?", (norm_t,)).fetchone()

    new_pub_types = rec.get("pub_types") or []
    is_preprint = 1 if rec.get("is_preprint") else 0
    if is_preprint and "[Preprint]" not in new_pub_types:
        new_pub_types = ["[Preprint]"] + list(new_pub_types)

    new_sources = rec.get("sources") or []

    if existing is None:
        cur.execute(
            """
            INSERT INTO articles (
                pmid, pmcid, doi, openalex_id, title, norm_title, abstract,
                journal, pub_year, pub_date, authors, language, pub_types,
                is_preprint, cited_by_count, is_open_access, sources
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pmid,
                pmcid,
                doi,
                openalex_id,
                title,
                norm_t,
                rec.get("abstract"),
                rec.get("journal"),
                rec.get("pub_year"),
                rec.get("pub_date"),
                json.dumps(rec.get("authors") or [], ensure_ascii=False),
                rec.get("language") or "eng",
                json.dumps(list(dict.fromkeys(new_pub_types)), ensure_ascii=False),
                is_preprint,
                int(rec.get("cited_by_count") or 0),
                1 if rec.get("is_open_access") else 0,
                json.dumps(list(dict.fromkeys(new_sources)), ensure_ascii=False),
            ),
        )
    else:
        row_id = existing["id"]
        merged_pmid = existing["pmid"] or pmid
        merged_pmcid = existing["pmcid"] or pmcid
        merged_doi = existing["doi"] or doi
        merged_oa_id = existing["openalex_id"] or openalex_id

        old_abs = existing["abstract"] or ""
        new_abs = rec.get("abstract") or ""
        merged_abs = new_abs if len(new_abs) > len(old_abs) else (old_abs or None)

        merged_journal = existing["journal"] or rec.get("journal")
        merged_year = existing["pub_year"] or rec.get("pub_year")
        merged_date = existing["pub_date"] or rec.get("pub_date")
        merged_lang = existing["language"] or rec.get("language") or "eng"

        try:
            old_authors = json.loads(existing["authors"] or "[]")
        except Exception:
            old_authors = []
        new_authors = rec.get("authors") or []
        merged_authors = new_authors if len(new_authors) > len(old_authors) else old_authors

        try:
            old_types = json.loads(existing["pub_types"] or "[]")
        except Exception:
            old_types = []
        merged_types = list(dict.fromkeys(old_types + list(new_pub_types)))

        # D-02: If merged with a published journal article, clear is_preprint flag
        has_journal_type = any(
            t.lower() in ("journal article", "review", "randomized controlled trial", "meta-analysis")
            for t in merged_types
        )
        merged_preprint = 0 if (has_journal_type and merged_pmid) else (existing["is_preprint"] and is_preprint)
        if not merged_preprint and "[Preprint]" in merged_types:
            merged_types.remove("[Preprint]")

        merged_citations = max(int(existing["cited_by_count"] or 0), int(rec.get("cited_by_count") or 0))
        merged_oa = 1 if (existing["is_open_access"] or rec.get("is_open_access") or merged_pmcid) else 0

        try:
            old_sources = json.loads(existing["sources"] or "[]")
        except Exception:
            old_sources = []
        merged_sources = list(dict.fromkeys(old_sources + list(new_sources)))

        cur.execute(
            """
            UPDATE articles SET
                pmid = ?, pmcid = ?, doi = ?, openalex_id = ?,
                abstract = ?, journal = ?, pub_year = ?, pub_date = ?,
                authors = ?, language = ?, pub_types = ?, is_preprint = ?,
                cited_by_count = ?, is_open_access = ?, sources = ?
            WHERE id = ?
            """,
            (
                merged_pmid,
                merged_pmcid,
                merged_doi,
                merged_oa_id,
                merged_abs,
                merged_journal,
                merged_year,
                merged_date,
                json.dumps(merged_authors, ensure_ascii=False),
                merged_lang,
                json.dumps(merged_types, ensure_ascii=False),
                merged_preprint,
                merged_citations,
                merged_oa,
                json.dumps(merged_sources, ensure_ascii=False),
                row_id,
            ),
        )


def harvest_pubmed(uv_bin: str, query: str, raw_dir: Path, conn: sqlite3.Connection) -> int:
    print("[1/4] Harvesting PubMed via pubmed_api.py...")
    pmids_file = raw_dir / "pubmed_pmids.json"
    if not pmids_file.exists():
        cmd = [
            uv_bin,
            "run",
            str(PUBMED_SCRIPT),
            str(pmids_file),
            "search_pubmed",
            query,
            "--max_results",
            "5000",
            "--sort_by",
            "pub_date",
        ]
        subprocess.run(cmd, check=True)

    pmids: list[str] = json.loads(pmids_file.read_text(encoding="utf-8"))
    print(f"  -> Found {len(pmids)} PMIDs in PubMed (2016-2026).")

    batch_size = 180
    total_batches = (len(pmids) + batch_size - 1) // batch_size

    for b_idx in range(total_batches):
        batch = pmids[b_idx * batch_size : (b_idx + 1) * batch_size]
        abs_file = raw_dir / f"pubmed_abstracts_{b_idx:03d}.json"
        sum_file = raw_dir / f"pubmed_summaries_{b_idx:03d}.json"

        if not abs_file.exists():
            print(f"  -> Fetching PubMed abstracts batch {b_idx + 1}/{total_batches} ({len(batch)} PMIDs)...")
            subprocess.run(
                [
                    uv_bin,
                    "run",
                    str(PUBMED_SCRIPT),
                    str(abs_file),
                    "fetch_article_abstracts",
                    ",".join(batch),
                ],
                check=True,
            )

        if not sum_file.exists():
            print(f"  -> Fetching PubMed summaries batch {b_idx + 1}/{total_batches} ({len(batch)} PMIDs)...")
            subprocess.run(
                [
                    uv_bin,
                    "run",
                    str(PUBMED_SCRIPT),
                    str(sum_file),
                    "fetch_database_summary",
                    "pubmed",
                    ",".join(batch),
                ],
                check=True,
            )

        abs_list = json.loads(abs_file.read_text(encoding="utf-8"))
        sum_list = json.loads(sum_file.read_text(encoding="utf-8"))
        sum_by_uid: dict[str, dict[str, Any]] = {}
        if isinstance(sum_list, list):
            for s in sum_list:
                if isinstance(s, dict) and s.get("uid"):
                    sum_by_uid[str(s["uid"])] = s

        if isinstance(abs_list, list):
            for item in abs_list:
                if not isinstance(item, dict):
                    continue
                pmid = str(item.get("pmid") or "").strip()
                if not pmid:
                    continue
                s_info = sum_by_uid.get(pmid, {})
                pub_types = s_info.get("pubtype") or []
                langs = s_info.get("lang") or ["eng"]
                lang = langs[0] if isinstance(langs, list) and langs else "eng"
                pmcid = None
                doi = item.get("doi")
                for aid in s_info.get("articleids") or []:
                    if isinstance(aid, dict):
                        if aid.get("idtype") == "pmc" and aid.get("value"):
                            val = str(aid["value"]).strip()
                            pmcid = val if val.startswith("PMC") else f"PMC{val}"
                        elif aid.get("idtype") == "doi" and not doi:
                            doi = aid.get("value")

                pubdate = item.get("pubdate") or s_info.get("pubdate") or ""
                pub_year = extract_year(pubdate)

                upsert_article(
                    conn,
                    {
                        "pmid": pmid,
                        "pmcid": pmcid,
                        "doi": doi,
                        "title": item.get("title") or s_info.get("title") or "",
                        "abstract": item.get("abstract"),
                        "journal": item.get("journal") or s_info.get("fulljournalname") or s_info.get("source"),
                        "pub_year": pub_year,
                        "pub_date": pubdate,
                        "authors": item.get("authors") or [],
                        "language": lang,
                        "pub_types": pub_types,
                        "is_preprint": "Preprint" in pub_types,
                        "is_open_access": bool(pmcid),
                        "sources": ["PubMed"],
                    },
                )
        conn.commit()

    return len(pmids)


def harvest_europepmc(uv_bin: str, query: str, raw_dir: Path, conn: sqlite3.Connection) -> int:
    print("[2/4] Harvesting Europe PMC (Open Access + Preprints) via europepmc_api.py...")
    cursor = "*"
    page_idx = 0
    total_fetched = 0

    while True:
        page_file = raw_dir / f"europepmc_page_{page_idx:03d}.json"
        if not page_file.exists():
            print(f"  -> Fetching Europe PMC page {page_idx + 1} (cursor={cursor})...")
            subprocess.run(
                [
                    uv_bin,
                    "run",
                    str(EPMC_SCRIPT),
                    "search",
                    query,
                    "--max_results",
                    "1000",
                    "--result_type",
                    "core",
                    "--cursor",
                    cursor,
                    "--output",
                    str(page_file),
                ],
                check=True,
            )

        data = json.loads(page_file.read_text(encoding="utf-8"))
        results = data.get("results") or []
        if not results:
            break

        for r in results:
            if not isinstance(r, dict):
                continue
            pmid = str(r.get("pmid") or "").strip() or None
            pmcid = str(r.get("pmcid") or "").strip() or None
            doi = r.get("doi")
            title = r.get("title") or ""
            abstract = r.get("abstractText")
            journal = (
                r.get("journalInfo", {}).get("journal", {}).get("title")
                or r.get("journalTitle")
                or r.get("bookOrReportDetails", {}).get("publisher")
            )
            pub_year = extract_year(r.get("pubYear") or r.get("firstPublicationDate"))
            pub_date = r.get("firstPublicationDate") or str(r.get("pubYear") or "")
            author_str = r.get("authorString") or ""
            authors = [a.strip() for a in author_str.split(",") if a.strip()]
            lang = r.get("language") or "eng"
            pt_list = r.get("pubTypeList", {}).get("pubType") or []
            if isinstance(pt_list, str):
                pt_list = [pt_list]
            is_preprint = (r.get("source") == "PPR") or any("preprint" in str(t).lower() for t in pt_list)
            cited_by = int(r.get("citedByCount") or 0)
            is_oa = r.get("isOpenAccess") == "Y" or bool(pmcid)

            upsert_article(
                conn,
                {
                    "pmid": pmid,
                    "pmcid": pmcid,
                    "doi": doi,
                    "title": title,
                    "abstract": abstract,
                    "journal": journal,
                    "pub_year": pub_year,
                    "pub_date": pub_date,
                    "authors": authors,
                    "language": lang,
                    "pub_types": pt_list,
                    "is_preprint": is_preprint,
                    "cited_by_count": cited_by,
                    "is_open_access": is_oa,
                    "sources": ["EuropePMC"],
                },
            )
            total_fetched += 1

        conn.commit()
        next_cursor = data.get("nextCursorMark")
        if not next_cursor or next_cursor == cursor or len(results) < 1000:
            break
        cursor = next_cursor
        page_idx += 1

    print(f"  -> Processed {total_fetched} records from Europe PMC.")
    return total_fetched


def harvest_openalex(uv_bin: str, search_term: str, start_year: int, end_year: int, raw_dir: Path, conn: sqlite3.Connection) -> int:
    print("[3/4] Harvesting OpenAlex via openalex_cli.py...")
    total_fetched = 0
    max_pages = 30  # up to 3000 records at 100/page

    for page in range(1, max_pages + 1):
        page_file = raw_dir / f"openalex_page_{page:03d}.json"
        if not page_file.exists():
            print(f"  -> Fetching OpenAlex page {page}...")
            filter_expr = f"title_and_abstract.search:{search_term},publication_year:{start_year}-{end_year}"
            select_fields = (
                "id,doi,ids,display_name,publication_year,publication_date,"
                "type,cited_by_count,is_oa,primary_location,authorships,abstract_inverted_index,language"
            )
            cmd = [
                uv_bin,
                "run",
                str(OPENALEX_SCRIPT),
                "filter",
                "works",
                "--filter",
                filter_expr,
                "--select",
                select_fields,
                "--sort",
                "cited_by_count:desc",
                "--per-page",
                "100",
                "--page",
                str(page),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if res.returncode != 0:
                print(f"  -> OpenAlex stopped at page {page} (status {res.returncode}): {res.stderr.strip()[:200]}")
                break
            page_file.write_text(res.stdout, encoding="utf-8")

        try:
            data = json.loads(page_file.read_text(encoding="utf-8"))
        except Exception:
            break

        results = data.get("results") or []
        if not results:
            break

        for w in results:
            if not isinstance(w, dict):
                continue
            oa_id = w.get("id")
            ids_block = w.get("ids") or {}
            pmid_url = ids_block.get("pmid") or ""
            pmid = pmid_url.split("/")[-1].strip() if pmid_url else None
            pmcid_url = ids_block.get("pmcid") or ""
            pmcid = pmcid_url.split("/")[-1].strip() if pmcid_url else None
            doi = w.get("doi") or ids_block.get("doi")
            title = w.get("display_name") or ""
            abstract = reconstruct_openalex_abstract(w.get("abstract_inverted_index"))

            prim_loc = w.get("primary_location") or {}
            source_obj = prim_loc.get("source") or {}
            journal = source_obj.get("display_name")

            pub_year = extract_year(w.get("publication_year"))
            pub_date = w.get("publication_date") or str(pub_year or "")

            authors = []
            for auth in w.get("authorships") or []:
                a_name = (auth.get("author") or {}).get("display_name")
                if a_name:
                    authors.append(a_name)

            w_type = w.get("type") or "article"
            is_preprint = w_type == "preprint" or source_obj.get("type") == "repository"
            cited_by = int(w.get("cited_by_count") or 0)
            is_oa = bool(w.get("is_oa"))
            lang = w.get("language") or "en"

            upsert_article(
                conn,
                {
                    "pmid": pmid,
                    "pmcid": pmcid,
                    "doi": doi,
                    "openalex_id": oa_id,
                    "title": title,
                    "abstract": abstract,
                    "journal": journal,
                    "pub_year": pub_year,
                    "pub_date": pub_date,
                    "authors": authors,
                    "language": lang,
                    "pub_types": [w_type],
                    "is_preprint": is_preprint,
                    "cited_by_count": cited_by,
                    "is_open_access": is_oa,
                    "sources": ["OpenAlex"],
                },
            )
            total_fetched += 1

        conn.commit()
        if len(results) < 100:
            break

    print(f"  -> Processed {total_fetched} records from OpenAlex.")
    return total_fetched


def harvest_clinical_trials(uv_bin: str, condition: str, raw_dir: Path, conn: sqlite3.Connection) -> int:
    print("[4/4] Harvesting ClinicalTrials.gov via clinical_trials_api.py...")
    ct_file = raw_dir / "clinical_trials.json"
    if not ct_file.exists():
        fields = (
            "NCTId,BriefTitle,OfficialTitle,OverallStatus,Phase,StudyType,"
            "StartDate,CompletionDate,EnrollmentCount,BriefSummary,"
            "ConditionsModule,ArmsInterventionsModule,HasResults"
        )
        cmd = [
            uv_bin,
            "run",
            str(CT_SCRIPT),
            "search",
            "--condition",
            condition,
            "--limit",
            "1000",
            "--count-total",
            "--fields",
            fields,
            "--output",
            str(ct_file),
        ]
        subprocess.run(cmd, check=True)

    data = json.loads(ct_file.read_text(encoding="utf-8"))
    studies = data.get("studies") or []
    cur = conn.cursor()
    count = 0

    for st in studies:
        if not isinstance(st, dict):
            continue
        proto = st.get("protocolSection") or {}
        id_mod = proto.get("identificationModule") or {}
        nct_id = id_mod.get("nctId")
        if not nct_id:
            continue
        brief_title = id_mod.get("briefTitle") or ""
        official_title = id_mod.get("officialTitle") or ""
        status_mod = proto.get("statusModule") or {}
        overall_status = status_mod.get("overallStatus") or ""
        start_date = (status_mod.get("startDateStruct") or {}).get("date") or ""
        comp_date = (status_mod.get("completionDateStruct") or {}).get("date") or ""

        design_mod = proto.get("designModule") or {}
        study_type = design_mod.get("studyType") or ""
        phases = design_mod.get("phases") or []
        phase_str = ", ".join(phases) if isinstance(phases, list) else str(phases)
        enrollment = (design_mod.get("enrollmentInfo") or {}).get("count")

        arms_mod = proto.get("armsInterventionsModule") or {}
        interventions = []
        for intr in arms_mod.get("interventions") or []:
            if isinstance(intr, dict):
                i_type = intr.get("type") or ""
                i_name = intr.get("name") or ""
                interventions.append(f"{i_type}: {i_name}".strip(": "))

        desc_mod = proto.get("descriptionModule") or {}
        summary = desc_mod.get("briefSummary") or ""
        has_results = 1 if st.get("hasResults") else 0

        cur.execute(
            """
            INSERT OR REPLACE INTO clinical_trials (
                nct_id, brief_title, official_title, overall_status,
                phase, study_type, interventions, enrollment,
                start_date, completion_date, has_results, summary, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nct_id,
                brief_title,
                official_title,
                overall_status,
                phase_str,
                study_type,
                json.dumps(interventions, ensure_ascii=False),
                int(enrollment) if isinstance(enrollment, int) else None,
                start_date,
                comp_date,
                has_results,
                summary,
                json.dumps(st, ensure_ascii=False),
            ),
        )
        count += 1

    conn.commit()
    print(f"  -> Imported {count} clinical trials from ClinicalTrials.gov.")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Universal nosology literature harvester (2016-2026).")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/dupuytren.yaml",
        help="Path to nosology YAML configuration file",
    )
    args = parser.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        print(f"Error: Config file not found: {cfg_path}", file=sys.stderr)
        sys.exit(1)

    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    nosology_id = cfg["nosology_id"]
    queries = cfg["queries"]
    date_range = cfg["date_range"]

    data_dir = Path("data") / nosology_id
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "literature.db"

    conn = init_db(db_path)
    uv_bin = get_uv_bin()

    n_pubmed = harvest_pubmed(uv_bin, queries["pubmed"], raw_dir, conn)
    n_epmc = harvest_europepmc(uv_bin, queries["europepmc"], raw_dir, conn)
    n_oa = harvest_openalex(
        uv_bin,
        queries["openalex_search"],
        int(date_range["start_year"]),
        int(date_range["end_year"]),
        raw_dir,
        conn,
    )
    n_ct = harvest_clinical_trials(uv_bin, queries["clinical_trials_condition"], raw_dir, conn)

    cur = conn.cursor()
    unique_articles = cur.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    unique_trials = cur.execute("SELECT COUNT(*) FROM clinical_trials").fetchone()[0]
    preprints = cur.execute("SELECT COUNT(*) FROM articles WHERE is_preprint = 1").fetchone()[0]
    oa_count = cur.execute("SELECT COUNT(*) FROM articles WHERE is_open_access = 1").fetchone()[0]

    print("\n=== HARVEST SUMMARY ===")
    print(f"Raw records processed -> PubMed: {n_pubmed} | EuropePMC: {n_epmc} | OpenAlex: {n_oa} | ClinicalTrials: {n_ct}")
    print(f"Deduplicated SQLite corpus ({db_path}):")
    print(f"  - Unique articles: {unique_articles} (Open Access: {oa_count}, Preprints: {preprints})")
    print(f"  - Clinical trials: {unique_trials}")


if __name__ == "__main__":
    main()
