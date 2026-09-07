"""
SQL literals for Postgres schema and upsert operations used by PostgresIndexPipeline.
Separated to keep pipeline logic free from embedded SQL strings.
"""

# DDL statements
DDL_CREATE_NOVELS = (
    """
    CREATE TABLE IF NOT EXISTS novels (
        series_slug TEXT,
        source_domain TEXT,
        url TEXT PRIMARY KEY,
        title TEXT,
        created_at TIMESTAMPTZ DEFAULT now()
    );
    """
)

DDL_CREATE_CHAPTERS = (
    """
    CREATE TABLE IF NOT EXISTS chapters (
        url TEXT PRIMARY KEY,
        series_slug TEXT,
        chapter_num INTEGER,
        title TEXT,
        fetched_at TIMESTAMPTZ,
        status INTEGER,
        content_hash TEXT
    );
    """
)

DDL_CREATE_FAILURES = (
    """
    CREATE TABLE IF NOT EXISTS failures (
        url TEXT PRIMARY KEY,
        source_domain TEXT,
        reason TEXT,
        status INTEGER,
        last_seen TIMESTAMPTZ DEFAULT now(),
        tries INTEGER DEFAULT 1
    );
    """
)

DDL_INDEXES = (
    """
    CREATE INDEX IF NOT EXISTS idx_chapters_series ON chapters(series_slug);
    CREATE INDEX IF NOT EXISTS idx_chapters_fetched_at ON chapters(fetched_at);
    CREATE INDEX IF NOT EXISTS idx_chapters_status ON chapters(status);
    CREATE INDEX IF NOT EXISTS idx_failures_status ON failures(status);
    """
)

# Lightweight, idempotent migrations for backward compatibility
MIGRATIONS = (
    """
    ALTER TABLE chapters ADD COLUMN IF NOT EXISTS content_hash TEXT;
    """
)

# DML UPSERT statements
SQL_UPSERT_FAILURE = (
    """
    INSERT INTO failures (url, source_domain, reason, status, last_seen, tries)
    VALUES (%s, %s, %s, %s, now(), 1)
    ON CONFLICT (url) DO UPDATE SET
        reason = EXCLUDED.reason,
        status = EXCLUDED.status,
        last_seen = now(),
        tries = failures.tries + 1
    ;
    """
)

SQL_UPSERT_CHAPTER = (
    """
    INSERT INTO chapters (url, series_slug, chapter_num, title, fetched_at, status, content_hash)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (url) DO UPDATE SET
        series_slug = EXCLUDED.series_slug,
        chapter_num = COALESCE(EXCLUDED.chapter_num, chapters.chapter_num),
        title = COALESCE(EXCLUDED.title, chapters.title),
        fetched_at = EXCLUDED.fetched_at,
        status = EXCLUDED.status,
        content_hash = COALESCE(EXCLUDED.content_hash, chapters.content_hash)
    ;
    """
)

SQL_UPSERT_NOVEL = (
    """
    INSERT INTO novels (series_slug, source_domain, url, title)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (url) DO UPDATE SET
        title = COALESCE(EXCLUDED.title, novels.title)
    ;
    """
)
