import gzip
import json
import re
import time
import os
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Dict, Optional, Set
import logging
from itemadapter import ItemAdapter
from scrapy.exceptions import CloseSpider

from scrapper.config.config import get_setting


def _slugify(text: Optional[str]) -> str:
    if not text:
        return "unknown"
    text = text.strip().lower()
    text = re.sub(r"[ \t/|]+", "_", text)
    text = re.sub(r"[^a-z0-9_\-.]+", "", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class RollingJSONLPipeline:
    """
    Series-centric storage:
      - Base path: {base_dir}/{series_slug}/
      - Metadata: {series}/metadata.json
      - Data file: {series}/chapters.jsonl.gz (one line per chapter)
      - Each JSONL line contains content, notes, and reader comments
      - Enforces storage quota (configurable via STORAGE_MAX_GB, default 5GB)
    """

    logger = logging.getLogger(__name__)
    
    def __init__(
        self,
        base_dir: str = "../data/raw/novel",
        storage_max_gb: float = 5.0,
        jsonl_name: str = "chapters.jsonl.gz",
        quota_check_interval_s: float = 30.0,
        quota_item_interval: int = 50,
        fsync_item_interval: int = 50,
        max_open_fps: int = 64,
    ):
        raw_dir = base_dir or get_setting("RAW_OUT_DIR", "../data/raw/novel")
        self.base_dir = Path(raw_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.storage_max_gb = float(storage_max_gb)
        self.storage_max_bytes = int(self.storage_max_gb * (1024**3))
        self.jsonl_name = jsonl_name

        # Throttling/flush controls
        self._quota_last_check_ts = 0.0
        self._quota_check_interval_s = float(quota_check_interval_s)
        self._items_since_quota_check = 0
        self._quota_item_interval = int(quota_item_interval)
        self._items_written = 0
        self._fsync_item_interval = max(0, int(fsync_item_interval))
        self._max_open_fps = int(get_setting("STORAGE_MAX_OPEN_FILES", max_open_fps))
        self._current_size_bytes = 0

        # Open file handles per series (append mode) with LRU eviction; closed on spider close
        self._fps: Dict[str, gzip.GzipFile] = {}
        # Track per-series chapter keys to avoid overcounting in the same run
        self._seen_keys: Dict[str, Set[str]] = {}
        # Cached chapter counts per series reflected in metadata
        self._series_counts: Dict[str, int] = {}

        self.logger.info(
            "Initialized RollingJSONLPipeline base_dir=%s storage_max_gb=%.2f jsonl_name=%s quota_check_interval_s=%.1f quota_item_interval=%d fsync_item_interval=%d max_open_fps=%d",
            str(self.base_dir), self.storage_max_gb, self.jsonl_name,
            self._quota_check_interval_s, self._quota_item_interval, self._fsync_item_interval, self._max_open_fps
        )

    @classmethod
    def from_crawler(cls, crawler):
        base_dir = crawler.settings.get("RAW_OUT_DIR", "../data/raw/novel")
        storage_max_gb = crawler.settings.getfloat("STORAGE_MAX_GB", 5.0)
        jsonl_name = crawler.settings.get("SERIES_JSONL_NAME", "chapters.jsonl.gz")
        quota_check_interval_s = crawler.settings.getfloat("QUOTA_CHECK_INTERVAL_S", 30.0)
        quota_item_interval = crawler.settings.getint("QUOTA_ITEM_INTERVAL", 50)
        fsync_item_interval = crawler.settings.getint("FSYNC_ITEM_INTERVAL", 50)
        max_open_fps = crawler.settings.getint("STORAGE_MAX_OPEN_FILES", 64)
        return cls(
            base_dir=base_dir,
            storage_max_gb=storage_max_gb,
            jsonl_name=jsonl_name,
            quota_check_interval_s=quota_check_interval_s,
            quota_item_interval=quota_item_interval,
            fsync_item_interval=fsync_item_interval,
            max_open_fps=max_open_fps,
        )

    def open_spider(self, spider):
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info("Opening storage pipeline for spider=%s base_dir=%s", getattr(spider, "name", "unknown"), str(self.base_dir))
        if self.storage_max_gb <= 0:
            self.logger.error("Invalid STORAGE_MAX_GB=%.3f; must be > 0", self.storage_max_gb)
            raise CloseSpider("STORAGE_MAX_GB must be > 0")
        try:
            self._current_size_bytes = self._get_dir_size_bytes(self.base_dir)
            self._enforce_quota(force_recount=False)
        except CloseSpider as e:
            self.logger.error("Storage quota enforcement failed on open: %s", e)
            raise

    def close_spider(self, spider):
        self.logger.info("Closing storage pipeline for spider=%s", getattr(spider, "name", "unknown"))
        for key, fp in list(self._fps.items()):
            try:
                fp.close()
                self.logger.debug("Closed file handle: %s", key)
            except OSError as e:
                self.logger.error("Error closing file %s: %s", key, e)
        self._fps.clear()

    def _get_dir_size_bytes(self, path: Path) -> int:
        total = 0
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    continue
        return total

    def _enforce_quota(self, force_recount: bool = False):
        if force_recount:
            self._current_size_bytes = self._get_dir_size_bytes(self.base_dir)
        used = self._current_size_bytes
        self.logger.debug(
            "Quota check: used=%d bytes (%.2f GB), limit=%d bytes (%.2f GB)",
            used, used / (1024**3), self.storage_max_bytes, self.storage_max_bytes / (1024**3)
        )
        if used > self.storage_max_bytes:
            self.logger.warning(
                "Storage quota exceeded: used=%d > limit=%d (%.2f GB > %.2f GB)",
                used, self.storage_max_bytes, used / (1024**3), self.storage_max_bytes / (1024**3)
            )
            raise CloseSpider(
                f"Storage quota exceeded: {used} bytes used > {self.storage_max_bytes} bytes allowed"
            )

    def _enforce_quota_throttled(self):
        self._items_since_quota_check += 1
        if self._items_since_quota_check >= self._quota_item_interval:
            now = time.time()
            force = (now - self._quota_last_check_ts) >= (self._quota_check_interval_s * 10)
            self._enforce_quota(force_recount=force)
            if force:
                self._quota_last_check_ts = now
            self._items_since_quota_check = 0

    def _series_paths(self, series_name: Optional[str]) -> Dict[str, Path]:
        slug = _slugify(series_name)
        series_dir = self.base_dir / slug
        return {
            "slug": slug,
            "series_dir": series_dir,
            "meta_path": series_dir / "metadata.json",
            "jsonl_path": series_dir / self.jsonl_name,
        }

    def _ensure_series(self, paths: Dict[str, Path]):
        paths["series_dir"].mkdir(parents=True, exist_ok=True)

    def _open_series_fp(self, jsonl_path: Path) -> gzip.GzipFile:
        key = str(jsonl_path)
        fp = self._fps.get(key)
        if fp is not None:
            # Refresh LRU position (delete and re-insert)
            del self._fps[key]
            self._fps[key] = fp
            return fp

        # Evict oldest file handle if capacity reached
        while len(self._fps) >= self._max_open_fps:
            oldest_key, oldest_fp = next(iter(self._fps.items()))
            del self._fps[oldest_key]
            try:
                oldest_fp.close()
                self.logger.debug("Evicted oldest open file handle: %s", oldest_key)
            except OSError as e:
                self.logger.warning("Error closing evicted file %s: %s", oldest_key, e)

        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger.debug("Opening gzip append handle for: %s", key)
        fp = gzip.open(jsonl_path, "ab")
        self._fps[key] = fp
        return fp

    def _chapter_key(self, ad: ItemAdapter) -> str:
        ch_num = ad.get("chapter_num")
        if ch_num is not None:
            try:
                # Normalize common forms like "1", "1.0", Decimal-like strings
                return f"{int(float(str(ch_num))):05d}"
            except Exception:
                pass
        base = ad.get("id") or ad.get("url") or ""
        if not base:
            base = f"{ad.get('series','')}-{ad.get('fetched_at',0)}"
        return sha1(str(base).encode("utf-8")).hexdigest()[:16]

    def _load_metadata(self, meta_path: Path) -> Dict:
        if meta_path.exists():
            try:
                with meta_path.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.debug("Failed to load %s: %r", str(meta_path), e)
                return {}
        return {}

    def _update_metadata(self, ad: ItemAdapter, paths: Dict[str, Path], created_new_chapter: bool):
        meta_path = paths["meta_path"]
        current = self._load_metadata(meta_path)

        series_name = ad.get("series")
        author = ad.get("author")
        tags = ad.get("series_tags") or []
        language = ad.get("series_language")
        status = ad.get("series_status")

        if not current:
            current = {
                "series_name": series_name,
                "author": author,
                "tags": sorted(set(tags)),
                "language": language,
                "status": status,
                "chapters_count": 0,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "source_domains": sorted({ad.get("source_domain")} - {None}),
            }

        if series_name and not current.get("series_name"):
            current["series_name"] = series_name
        if author and not current.get("author"):
            current["author"] = author

        merged_tags = set(current.get("tags", []))
        merged_tags.update(tags or [])
        current["tags"] = sorted(merged_tags)

        if language:
            current["language"] = language
        if status:
            current["status"] = status

        domains = set(current.get("source_domains", []))
        if ad.get("source_domain"):
            domains.add(ad.get("source_domain"))
        current["source_domains"] = sorted(domains)

        series_slug = paths["slug"]
        if series_slug not in self._series_counts:
            # Initialize from existing stored value to avoid rescan
            self._series_counts[series_slug] = int(current.get("chapters_count", 0) or 0)
        if created_new_chapter:
            self._series_counts[series_slug] += 1
        current["chapters_count"] = int(self._series_counts[series_slug])

        current["updated_at"] = _now_iso()

        tmp_path = meta_path.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        tmp_path.replace(meta_path)
        self.logger.debug(
            "Updated metadata for series_slug=%s at %s (chapters_count=%d, new_chapter=%s)",
            paths["slug"], str(meta_path), current.get("chapters_count", 0), created_new_chapter
        )

    def process_item(self, item, spider):
        self._enforce_quota_throttled()

        ad = ItemAdapter(item)

        if not ad.get("id"):
            ad["id"] = sha1(ad.get("url", "").encode("utf-8")).hexdigest()

        paths = self._series_paths(ad.get("series"))
        self._ensure_series(paths)

        # Determine a unique key for chapter within series for counting
        chapter_key = self._chapter_key(ad)
        seen = self._seen_keys.setdefault(paths["slug"], set())
        created_new_chapter = chapter_key not in seen
        self.logger.debug(
            "Processing item id=%s url=%s series_slug=%s chapter_num=%s new_chapter=%s",
            ad.get("id"), ad.get("url"), paths["slug"], ad.get("chapter_num"), created_new_chapter
        )

        # Compose single JSONL record containing content + notes + comments
        record = {
            "id": ad.get("id"),
            "target_key": ad.get("target_key"),
            "url": ad.get("url"),
            "source_domain": ad.get("source_domain"),
            "series": ad.get("series"),
            "series_tags": ad.get("series_tags") or [],
            "series_language": ad.get("series_language"),
            "series_status": ad.get("series_status"),
            "author": ad.get("author"),
            "chapter_num": ad.get("chapter_num"),
            "title": ad.get("title"),
            "content_hash": ad.get("content_hash"),
            "body_html": ad.get("body_html"),
            "body_text": ad.get("body_text"),
            "chapter_text": ad.get("chapter_text"),
            "chapter_notes": ad.get("chapter_notes") or [],
            "chapter_reader_comments": ad.get("chapter_reader_comments") or [],
            "fetched_at": ad.get("fetched_at"),
            "meta": ad.get("meta") or {},
        }

        # Append to the series JSONL (gz) file
        fp = self._open_series_fp(paths["jsonl_path"])
        line = json.dumps(record, ensure_ascii=False).encode("utf-8") + b"\n"
        try:
            fp.write(line)
            fp.flush()
            self._current_size_bytes += len(line)
            self.logger.debug("Wrote %d bytes to %s", len(line), str(paths["jsonl_path"]))
        except OSError as e:
            self.logger.error("Failed writing to %s: %s", str(paths["jsonl_path"]), e)
            raise

        # Periodic durability sync (bounded loss)
        self._items_written += 1
        if self._fsync_item_interval and (self._items_written % self._fsync_item_interval == 0):
            try:
                # GzipFile wraps a fileobj; try syncing the underlying file descriptor
                fileobj = getattr(fp, "fileobj", None) or getattr(fp, "_fp", None)
                if fileobj and hasattr(fileobj, "fileno"):
                    os.fsync(fileobj.fileno())
            except Exception as e:
                self.logger.debug("fsync failed (ignored): %r", e)

        # Update metadata only when a new chapter is observed in this run
        if created_new_chapter:
            seen.add(chapter_key)
            self._update_metadata(ad, paths, created_new_chapter)

        return item