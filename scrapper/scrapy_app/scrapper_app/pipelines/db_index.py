import os
import time
from datetime import datetime, timezone
from hashlib import sha1
from urllib.parse import urlparse

import psycopg2
from itemadapter import ItemAdapter


class PostgresIndexPipeline:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.conn = None
        self.cur = None

    @classmethod
    def from_crawler(cls, crawler):
        dsn = crawler.settings.get("POSTGRES_DSN")
        return cls(dsn)

    def open_spider(self, spider):
        self.conn = psycopg2.connect(self.dsn)
        self.conn.autocommit = True
        self.cur = self.conn.cursor()
        self._ensure_tables()

    def close_spider(self, spider):
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()

    def _ensure_tables(self):
        self.cur.execute(
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
        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chapters (
                url TEXT PRIMARY KEY,
                series_slug TEXT,
                chapter_num INTEGER,
                title TEXT,
                fetched_at TIMESTAMPTZ,
                status INTEGER,
                content_sha1 TEXT
            );
            """
        )
        self.cur.execute(
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

    def process_item(self, item, spider):
        ad = ItemAdapter(item)
        url = ad.get("url")
        status = ad.get("status")
        meta = ad.get("meta") or {}
        # Handle failures as special-case items
        if meta.get("failure"):
            domain = ad.get("source_domain") or urlparse(url).netloc
            reason = meta.get("reason")
            self.cur.execute(
                """
                INSERT INTO failures (url, source_domain, reason, status, last_seen, tries)
                VALUES (%s, %s, %s, %s, now(), 1)
                ON CONFLICT (url) DO UPDATE SET
                    reason = EXCLUDED.reason,
                    status = EXCLUDED.status,
                    last_seen = now(),
                    tries = failures.tries + 1
                ;
                """,
                (url, domain, reason, int(status) if status is not None else None),
            )
            return item

        title = ad.get("title")
        status = int(ad.get("status", 0))
        body_html = ad.get("body_html") or ""
        content_hash = sha1(body_html.encode("utf-8")).hexdigest() if body_html else None
        series_slug = ad.get("series") or self._derive_series_slug(url)
        chapter_num = ad.get("chapter_num")
        fetched_at = datetime.fromtimestamp(int(ad.get("fetched_at", time.time())), tz=timezone.utc)

        # Upsert chapter
        self.cur.execute(
            """
            INSERT INTO chapters (url, series_slug, chapter_num, title, fetched_at, status, content_sha1)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE SET
                series_slug = EXCLUDED.series_slug,
                chapter_num = COALESCE(EXCLUDED.chapter_num, chapters.chapter_num),
                title = COALESCE(EXCLUDED.title, chapters.title),
                fetched_at = EXCLUDED.fetched_at,
                status = EXCLUDED.status,
                content_sha1 = COALESCE(EXCLUDED.content_sha1, chapters.content_sha1)
            ;
            """,
            (url, series_slug, chapter_num, title, fetched_at, status, content_hash),
        )

        # Upsert novel row minimally
        domain = ad.get("source_domain") or urlparse(url).netloc
        novel_url = self._series_url(url)
        self.cur.execute(
            """
            INSERT INTO novels (series_slug, source_domain, url, title)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE SET
                title = COALESCE(EXCLUDED.title, novels.title)
            ;
            """,
            (series_slug, domain, novel_url, None),
        )
        return item

    def _derive_series_slug(self, url: str) -> str:
        p = urlparse(url)
        parts = [seg for seg in p.path.split("/") if seg]
        # Heuristics: if path like /novel/<slug>/... then take that
        if len(parts) >= 2 and parts[0] in {"novel", "series"}:
            return parts[1]
        # else take first meaningful
        return parts[0] if parts else p.netloc

    def _series_url(self, url: str) -> str:
        p = urlparse(url)
        parts = [seg for seg in p.path.split("/") if seg]
        if len(parts) >= 2 and parts[0] in {"novel", "series"}:
            return f"{p.scheme}://{p.netloc}/{parts[0]}/{parts[1]}"
        # fallback to origin
        return f"{p.scheme}://{p.netloc}/"
