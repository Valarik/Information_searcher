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

        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pmid TEXT UNIQUE,
            pmcid TEXT,
            doi TEXT,
            openalex_id TEXT,
            title TEXT NOT NULL,
            norm_title TEXT,
            abstract TEXT,
            journal TEXT,
            pub_year INTEGER,
            pub_date TEXT,
            authors TEXT,
            language TEXT DEFAULT 'eng',
            pub_types TEXT,
            is_preprint INTEGER DEFAULT 0,
            prisma_status TEXT DEFAULT 'included',
            evidence_tier INTEGER DEFAULT 3,
            clusters TEXT,
            cited_by_count INTEGER DEFAULT 0,
            is_open_access INTEGER DEFAULT 0,
            has_fulltext_xml INTEGER DEFAULT 0,
            fulltext_path TEXT,
            sources TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_articles_doi ON articles(doi);
        CREATE INDEX IF NOT EXISTS idx_articles_norm_title ON articles(norm_title);
        CREATE INDEX IF NOT EXISTS idx_articles_pmcid ON articles(pmcid);
        CREATE INDEX IF NOT EXISTS idx_articles_year ON articles(pub_year);
        CREATE INDEX IF NOT EXISTS idx_articles_tier ON articles(evidence_tier);
        CREATE INDEX IF NOT EXISTS idx_articles_prisma ON articles(prisma_status);

        CREATE TABLE IF NOT EXISTS clinical_trials (
            nct_id TEXT PRIMARY KEY,
            brief_title TEXT,
            official_title TEXT,
            overall_status TEXT,
            phase TEXT,
            study_type TEXT,
            interventions TEXT,
            enrollment INTEGER,
            start_date TEXT,
            completion_date TEXT,
            has_results INTEGER DEFAULT 0,
            summary TEXT,
            raw_json TEXT
        );

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

        CREATE TABLE IF NOT EXISTS extracted_mechanisms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER REFERENCES articles(id),
            pmid TEXT,
            doi TEXT,
            first_author_year TEXT,
            category TEXT,
            targets_genes_pathways TEXT,
            study_model TEXT,
            sample_size TEXT,
            quantitative_findings TEXT,
            mechanism_summary TEXT,
            therapeutic_implication TEXT
        );
        """
    )
    conn.commit()
    return conn
