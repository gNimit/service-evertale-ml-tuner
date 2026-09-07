"""
Scrapper spider to scrape novels from various sources.
"""
import logging
import re
import time
from urllib.parse import urljoin, urlparse

from scrapy.http import Response, Request
from scrapy_redis.spiders import RedisSpider

from scrapper.config.config import get_targets, get_setting
try:
    from ..extensions.prometheus import NOVELS
except Exception:
    NOVELS = None


class NovelSpider(RedisSpider):
    name = "novels"
    redis_key = get_setting("REDIS_START_URLS_KEY")
    logger = logging.getLogger(__name__)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.targets_cfg = get_targets()

    async def start(self):
        async for request in super().start():
            yield request

    # Helper to support str or list of CSS selectors; returns the first non-empty result (string)
    def _first_css_get(self, response: Response, selectors):
        if not selectors:
            return None
        if isinstance(selectors, (list, tuple)):
            for sel in selectors:
                if not sel:
                    continue
                val = response.css(sel).get()
                if val:
                    return val
            return None
        return response.css(selectors).get()

    def _resolve_next_url(self, base_url: str, href: str) -> str | None:
        """Sanitize and resolve a next-page href against a base URL.
        Ensures root path '/' before query, strips fragments, and supports '?', '&', and 'key=val' hrefs.
        Skips non-navigable hrefs like '#' or 'javascript:...'.
        """
        if href is None:
            return None
        href = str(href).strip()
        if not href:
            return None
        low = href.lower()
        if low == "#" or low.startswith("javascript:") or low.startswith("mailto:") or low.startswith("tel:"):
            self.logger.debug(f"Ignoring non-navigable next_page href '{href}' on {base_url}")
            return None
        try:
            if "#" in href:
                href = href.split("#", 1)[0]

            parsed_href = urlparse(href)

            # Absolute URL: ensure it has '/' path before query
            if parsed_href.scheme and parsed_href.netloc:
                if not parsed_href.path:
                    parsed_href = parsed_href._replace(path="/")
                # Also ensure fragment is removed (already handled above, but keep consistent)
                parsed_href = parsed_href._replace(fragment="")
                return parsed_href.geturl()

            # Relative URL cases
            # Convert '&page=3' to '?page=3' and ensure base has '/' path
            if href.startswith("?") or href.startswith("&"):
                parsed_base = urlparse(base_url)
                base_url_norm = base_url
                if not parsed_base.path:
                    base_url_norm = base_url.rstrip("/") + "/"
                if href.startswith("&"):
                    href = "?" + href.lstrip("&")
                return urljoin(base_url_norm, href)

            if re.match(r"^[a-z0-9_\-]+=", href, re.IGNORECASE):
                return self._resolve_next_url(base_url, "?" + href)

            return urljoin(base_url, href)
        except Exception as e:
            self.logger.warning(f"Failed to resolve next_page URL from base '{base_url}' and href '{href}': {e}")
            return None

    def parse(self, response: Response, **kwargs):
        meta = response.meta
        t_key = meta.get("target_key")
        if not t_key or t_key not in self.targets_cfg:
            self.logger.error(f"Missing/unknown target key in meta: {meta}")
            return
        cfg = self.targets_cfg[t_key]

        page_type = meta.get("page_type", "landing")
        if page_type == "landing":
            landing_kind = meta.get("landing_kind", cfg.get("landing_kind", "catalog"))
            if landing_kind == "catalog":
                yield from self.parse_catalog(response)
            else:
                yield from self.parse_toc(response)
        elif page_type == "toc":
            response.meta["target_key"] = t_key
            yield from self.parse_toc(response)
        elif page_type == "chapter":
            yield from self.parse_chapter(response)
        else:
            self.logger.error(f"Unknown page type: {page_type}")

    """
    Parse catalog pages.
    """
    def parse_catalog(self, response: Response):
        t_key = response.meta.get("target_key")
        cfg = self.targets_cfg[t_key]

        self.logger.debug(f"Parsing catalog page for target {t_key}")
        cat = cfg.get("catalog", {})
        novel_selectors = cat.get("novel_links", [])
        novel_title_sel = cat.get("novel_title", [])
        links = []
        titles = []
        for index, sel in enumerate(novel_selectors):
            links_per_sel = response.css(sel).getall()

            if links_per_sel:
                links.extend(links_per_sel)

        for index, href in enumerate(links):
            url = urljoin(response.url, href)
            try:
                if NOVELS is not None:
                    NOVELS.labels(spider=self.name, target=str(t_key)).inc()
            except Exception:
                pass
            yield Request(
                url,
                callback=self.parse_toc,
                meta={
                    "target_key": t_key,
                    "landing_kind": "catalog",
                    "page_type": "catalog",
                },
            )

        # Catalog pagination
        next_page_sel = cat.get("next_page")
        if next_page_sel:
            # Support next_page being a string or a list of selectors
            next_page_href = self._first_css_get(response, next_page_sel)
            url = self._resolve_next_url(response.url, next_page_href) if next_page_href else None
            if url:
                yield Request(
                    url,
                    callback=self.parse_catalog,
                    meta={
                        "target_key": t_key,
                        "page_type": "catalog",
                    },
                )

    """
    Parse TOC pages.
    """
    def parse_toc(self, response: Response):
        t_key = response.meta.get("target_key")
        cfg = self.targets_cfg[t_key]

        self.logger.debug(f"Parsing TOC page for target {t_key}")
        toc = cfg.get("novel_toc", {})
        title_sel = toc.get("title")
        tags_sel = toc.get("tags")
        language_sel = toc.get("language")
        author_sel = toc.get("author")
        status_sel = toc.get("status")
        chapter_selectors = toc.get("chapter_links", [])

        existing_toc_meta = response.meta.get("toc_meta") or {}
        title = (response.css(title_sel).get() if title_sel else None) or existing_toc_meta.get("title")
        tags = (response.css(tags_sel).getall() if tags_sel else None) or existing_toc_meta.get("tags") or []
        language = (response.css(language_sel).get() if language_sel else None) or existing_toc_meta.get("language")
        author = (response.css(author_sel).getall() if author_sel else None) or existing_toc_meta.get("author")
        status = (response.css(status_sel).get() if status_sel else None) or existing_toc_meta.get("status")

        toc_meta = {
            "title": title,
            "tags": tags,
            "language": language,
            "author": author,
            "status": status,
            "catalog_novel_title": title,
        }

        links = []
        for sel in chapter_selectors:
            links = response.css(sel).getall()
            if links:
                break

        for href in links:
            url = urljoin(response.url, href)
            yield Request(
                url,
                callback=self.parse_chapter,
                meta={"target_key": t_key, "page_type": "toc", "toc_meta": toc_meta},
            )

        # TOC pagination
        next_page_sel = toc.get("next_page")
        if next_page_sel:
            # Support next_page being a string or a list of selectors
            next_page_href = self._first_css_get(response, next_page_sel)
            url = self._resolve_next_url(response.url, next_page_href) if next_page_href else None
            if url:
                yield Request(
                    url,
                    callback=self.parse_toc,
                    meta={"target_key": t_key, "page_type": "toc", "toc_meta": toc_meta},
                )


    """
    Parse chapter pages.
    """
    def parse_chapter(self, response: Response):
        t_key = response.meta.get("target_key")
        cfg = self.targets_cfg[t_key]

        self.logger.debug(f"Parsing chapter page for target {t_key}")
        chap = cfg.get("chapter", {})
        title_sel = chap.get("title")
        body_sel = chap.get("body")
        series_sel = chap.get("series")
        chapter_num_sel = chap.get("chapter_num")

        title = response.css(title_sel).get() if title_sel else None
        series_slug = response.css(series_sel).get() if series_sel else None

        # Extract chapter text using configured selector (text-only)
        chapter_text = None
        if body_sel:
            try:
                parts = response.css(body_sel).getall()
                if parts:
                    chapter_text = "\n".join(p for p in parts if p is not None)
            except Exception as e:
                self.logger.warning(f"Failed to extract chapter_text with selector '{body_sel}' on {response.url}: {e}")

        # Use the entire page body for body_html (outer HTML of <body>, fallback to full response)
        body_html = response.css("body").get() or response.text

        chapter_num = None
        if chapter_num_sel and isinstance(chapter_num_sel, dict):
            if chapter_num_sel.get("extract_from") == "url" and "pattern" in chapter_num_sel:
                pattern = chapter_num_sel["pattern"]
                url = response.url
                match = re.search(pattern, url)
                if match and match.group(1):
                    try:
                        chapter_num = int(match.group(1))
                    except ValueError:
                        self.logger.warning(f"Failed to parse chapter number from URL: {url}")
        elif chapter_num_sel:
            chapter_num = response.css(chapter_num_sel).get()

        yield {
            "url": response.url,
            "http_status": getattr(response, "status", 200),
            "source_domain": urlparse(response.url).netloc,
            "target_key": t_key,
            "title": title,
            "body_html": body_html,
            "chapter_text": chapter_text,
            "series": series_slug,
            "chapter_num": chapter_num,
            "fetched_at": int(time.time()),
            "meta": {
                "series_data": response.meta.get("toc_meta"),
            },
        }
