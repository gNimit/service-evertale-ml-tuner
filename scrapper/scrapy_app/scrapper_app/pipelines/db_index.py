import logging
import time
from datetime import datetime, timezone
import hashlib
from urllib.parse import urlparse

import psycopg2
from itemadapter import ItemAdapter

from scrapper.scrapy_app.scrapper_app.db.sql import (
    DDL_CREATE_NOVELS,
    DDL_CREATE_CHAPTERS,
    DDL_CREATE_FAILURES,
    DDL_INDEXES,
    SQL_UPSERT_FAILURE,
    SQL_UPSERT_CHAPTER,
    SQL_UPSERT_NOVEL,
)


def _derive_series_slug(url: str) -> str:
    p = urlparse(url)
    parts = [seg for seg in p.path.split("/") if seg]
    # Heuristics: if path like /novel/<slug>/... then take that
    if len(parts) >= 2 and parts[0] in {"novel", "series"}:
        return parts[1]
    # else take first meaningful
    return parts[0] if parts else p.netloc


def _series_url(url: str) -> str:
    p = urlparse(url)
    parts = [seg for seg in p.path.split("/") if seg]
    if len(parts) >= 2 and parts[0] in {"novel", "series"}:
        return f"{p.scheme}://{p.netloc}/{parts[0]}/{parts[1]}"
    # fallback to origin
    return f"{p.scheme}://{p.netloc}/"


class PostgresIndexPipeline:
    logger = logging.getLogger(__name__)

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
        # Create tables and indexes
        self.cur.execute(DDL_CREATE_NOVELS)
        self.cur.execute(DDL_CREATE_CHAPTERS)
        self.cur.execute(DDL_CREATE_FAILURES)
        # Lightweight migrations (idempotent)
        try:
            from scrapper.scrapy_app.scrapper_app.db.sql import MIGRATIONS
        except ImportError:
            self.logger.error("Failed to import MIGRATIONS, using empty migration script")
            MIGRATIONS = ""
        for stmt in (DDL_INDEXES + "\n" + MIGRATIONS).split(";\n"):
            s = stmt.strip()
            if s:
                self.cur.execute(s + ";")

    def process_item(self, item, spider):
        ad = ItemAdapter(item)
        url = ad.get("url")
        status = ad.get("status")
        meta = ad.get("meta") or {}
        # Handle failures as special-case items
        if meta.get("failure"):
            self.logger.info(f"Processing failure for URL: {url}")
            domain = ad.get("source_domain") or urlparse(url).netloc
            reason = meta.get("reason")
            self.cur.execute(
                SQL_UPSERT_FAILURE,
                (url, domain, reason, int(status) if status is not None else None),
            )
            return item

        title = ad.get("title")
        status = int(ad.get("status", 0))
        # Prefer pre-computed content_hash from previous pipeline; fallback to computing it
        content_hash = ad.get("content_hash")
        if not content_hash:
            base = ad.get("body_html") or ad.get("body_text") or ""
            if base:
                content_hash = hashlib.sha256(base.encode("utf-8", errors="ignore")).hexdigest()
        series_slug = ad.get("series") or _derive_series_slug(url)
        chapter_num = ad.get("chapter_num")
        fetched_at = datetime.fromtimestamp(int(ad.get("fetched_at", time.time())), tz=timezone.utc)

        # Upsert chapter
        self.logger.debug(f"Upserting chapter for URL: {url}")
        self.cur.execute(
            SQL_UPSERT_CHAPTER,
            (url, series_slug, chapter_num, title, fetched_at, status, content_hash),
        )

        # Upsert novel row minimally
        self.logger.debug(f"Upserting novel for URL: {url}")
        domain = ad.get("source_domain") or urlparse(url).netloc
        novel_url = _series_url(url)
        self.cur.execute(
            SQL_UPSERT_NOVEL,
            (series_slug, domain, novel_url, None),
        )
        return item
