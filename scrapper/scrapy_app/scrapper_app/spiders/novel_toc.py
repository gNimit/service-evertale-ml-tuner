import hashlib
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml
from scrapy import Request
from scrapy.http import Response
from scrapy_redis.spiders import RedisSpider

from scrapper.config.config import get_targets


class NovelTocSpider(RedisSpider):
    name = "novel_toc"
    redis_key = "start_urls:novel_toc"

    def __init__(self, target, *args, **kwargs):
        super().__init__(*args, **kwargs)

        targets = get_targets()
        if target not in targets:
            raise ValueError(f"Unknown target {target}")
        self.t = targets[target]

    def parse(self, response: Response):
        # Treat response as ToC page and enqueue chapters
        chapter_selectors = self.t["toc"].get("chapter_links", []) or []
        if isinstance(chapter_selectors, str):
            chapter_selectors = [chapter_selectors]
        links = []
        for sel in chapter_selectors:
            links.extend(response.css(sel).getall())
        # Deduplicate
        seen = set()
        for href in links:
            if not href:
                continue
            url = urljoin(response.url, href)
            if url in seen:
                continue
            seen.add(url)
            yield Request(url, callback=self.parse_chapter, errback=self.on_error, meta={"via": "http"})

        # Optional: next page in ToC
        next_sel = self.t["toc"].get("next_page")
        if next_sel:
            nxt = response.css(next_sel).get()
            if nxt:
                yield response.follow(nxt, callback=self.parse)

    def parse_chapter(self, response: Response):
        title_sel = self.t["chapter"].get("title", "h1::text")
        body_sel = self.t["chapter"].get("body", "article")
        series_sel = self.t["chapter"].get("series")

        title = (response.css(title_sel).get() or "").strip()
        body_html = response.css(body_sel).get() or response.text
        series = (response.css(series_sel).get(default="").strip() if series_sel else "")
        chapter_num = self._guess_chapter_num(title) or self._guess_chapter_num(response.url)

        item = {
            "id": hashlib.sha1(response.url.encode()).hexdigest(),
            "url": response.url,
            "source_domain": urlparse(response.url).netloc,
            "series": series or self._derive_series_slug(response.url),
            "chapter_num": chapter_num,
            "title": title,
            "body_html": body_html,
            "fetched_at": int(time.time()),
            "status": response.status,
            "meta": {"via": response.meta.get("via", "http")},
        }
        yield item

    def on_error(self, failure):
        request = failure.request
        url = getattr(request, 'url', '')
        status = getattr(getattr(failure.value, 'response', None), 'status', None)
        self.logger.error("Request failed: %s", url)
        from urllib.parse import urlparse as _up
        return {
            "id": hashlib.sha1(url.encode()).hexdigest(),
            "url": url,
            "source_domain": _up(url).netloc,
            "fetched_at": int(time.time()),
            "status": status if status is not None else -1,
            "meta": {"failure": True, "reason": repr(failure.value)},
        }

    @staticmethod
    def _guess_chapter_num(text: str):
        m = re.search(r"chapter\s*(\d+)", text.lower())
        return int(m.group(1)) if m else None

    @staticmethod
    def _derive_series_slug(url: str) -> str:
        p = urlparse(url)
        parts = [seg for seg in p.path.split("/") if seg]
        if len(parts) >= 2 and parts[0] in {"novel", "series"}:
            return parts[1]
        return parts[0] if parts else p.netloc
