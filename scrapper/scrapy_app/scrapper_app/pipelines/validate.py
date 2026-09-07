import hashlib
import logging
import time
from urllib.parse import urlparse
from scrapy.exceptions import DropItem
from itemadapter import ItemAdapter
from pydantic import ValidationError

from scrapper.scrapy_app.scrapper_app.items import ChapterItem



class ParseAndValidateItemPipeline:
    logger = logging.getLogger(__name__)

    def process_item(self, item, spider):
        ad = ItemAdapter(item)
        meta = ad.get("meta") or {}
        if not isinstance(meta, dict):
            self.logger.warning("Missing or invalid meta: %s", meta)
            meta = {}
        if meta.get("failure"):
            self.logger.warning("Item already failed validation: %s", item)
            return item

        try:
            parsed = self.parse_item(item)
        except Exception as e:
            self.logger.exception("Error parsing item: %s", item)
            spider.logger.warning("Pre-validation parse failed: %s", e)
            meta["failure"] = True
            meta["error"] = {"stage": "parse", "detail": str(e)}
            ad["meta"] = meta
            raise DropItem(f"Parse failed: {e}")

        # Validate using Pydantic model
        try:
            validated = ChapterItem(**ItemAdapter(parsed).asdict())
        except ValidationError as e:
            self.logger.exception("Error validating item: %s", parsed)
            spider.logger.warning("Validation error: %s", e)
            meta = ItemAdapter(parsed).get("meta") or {}
            if not isinstance(meta, dict):
                meta = {}
            meta["failure"] = True
            meta["error"] = {"stage": "validate", "detail": str(e)}
            ItemAdapter(parsed)["meta"] = meta
            raise DropItem(f"Validation failed: {e}")

        return validated.model_dump(mode="json")

    def parse_item(self, item):
        """
        Normalize and enrich raw item fields for ChapterItem.
        - Ensures meta is a dict
        - Derives source_domain from url if missing/incorrect
        - Computes content_hash from body_html/body_text
        - Coerces chapter_num to int when possible
        - Ensures fetched_at is present (UTC epoch seconds)
        - Extracts author from meta.toc_meta as fallback
        - Normalizes series_tags to list[str]
        """
        ad = ItemAdapter(item)
        data = ad.asdict()

        meta = data.get("meta") or {}
        if not isinstance(meta, dict):
            self.logger.warning("Missing or invalid meta: %s", meta)
            meta = {}
        if meta.get("failure"):
            self.logger.warning("Item already failed validation: %s", item)
            data["meta"] = meta
            return data

        series_data = meta.get("series_data") or {}

        # Extract url and source_domain
        url = data.get("url")
        if not url or not isinstance(url, str):
            raise ValueError("Missing or invalid url")

        parsed_url = urlparse(url)
        source_domain = data.get("source_domain")
        if not source_domain or source_domain == url:
            source_domain = parsed_url.netloc or source_domain
        data["source_domain"] = source_domain

        if not data.get("id"):
            data["id"] = url

        # Extract and normalize chapter_num
        chap_num = data.get("chapter_num")
        if chap_num is not None:
            try:
                data["chapter_num"] = int(chap_num)
            except (TypeError, ValueError):
                # Leave as None if it cannot be parsed
                data["chapter_num"] = None

        # Extract and normalize series_title and series_tags
        series_title = data.get("series_title")
        if not series_title:
            series_title = series_data.get("title")
            if series_title is None:
                series_title = series_data.get("toc_title")
            if series_title is None:
                series_title = "unknown"
        data["series"] = series_title

        series_tags = data.get("series_tags")
        if series_tags is None:
            if isinstance(series_data, dict):
                series_tags = series_data.get("tags")
                if series_tags is None:
                    series_tags = series_data.get("toc_tags")
                    if series_tags is None:
                        series_tags = []
        elif isinstance(series_tags, str):
            series_tags = [series_tags]
        elif isinstance(series_tags, (set, tuple)):
            series_tags = list(series_tags)
        elif not isinstance(series_tags, list):
            series_tags = []

        series_tags = [str(t).strip() for t in series_tags if t is not None]
        data["series_tags"] = series_tags

        # Extract and normalize author
        author = data.get("author")
        if not author:
            toc_author = series_data.get("author")
            if isinstance(toc_author, list):
                author = next((a for a in toc_author if a), None)
            else:
                author = toc_author
        if not author:
            author = "unknown"
        data["author"] = author

        # Extract and normalize status
        status = data.get("series_status")
        if status is None:
            status = series_data.get("status")
            if status is None:
                status = "unknown"
        else :
            status = str(status).strip()

        data["series_status"] = status
        data["status"] = status

        # Preserve and normalize http_status
        http_status = data.get("http_status")
        try:
            data["http_status"] = int(http_status) if http_status is not None else 200
        except (ValueError, TypeError):
            data["http_status"] = 200

        # Add fetched_at and content_hash
        fetched_at = data.get("fetched_at")
        if not isinstance(fetched_at, int):
            try:
                data["fetched_at"] = int(fetched_at)
            except ValueError:
                data["fetched_at"] = int(time.time())

        content_hash = data.get("content_hash")
        if not content_hash:
            body_html = data.get("body_html") or ""
            body_text = data.get("body_text") or ""
            base = body_html if body_html else body_text
            if base:
                content_hash = hashlib.sha256(base.encode("utf-8", errors="ignore")).hexdigest()
                data["content_hash"] = content_hash

        data["meta"] = meta

        return data
