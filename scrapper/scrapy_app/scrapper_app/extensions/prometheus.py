from scrapy import signals
from prometheus_client import Counter, Gauge, Histogram, start_http_server
import redis
import os

# Global, spider-level metrics (backward-compatible)
REQS = Counter("scrapy_requests_total", "Total requests", ["spider", "code"]) 
ITEMS = Counter("scrapy_items_total", "Total items", ["spider"]) 
BYTES = Counter("scrapy_response_bytes_total", "Bytes fetched", ["spider"]) 
QUEUE = Gauge("scrapy_queue_depth", "Queue depth", ["spider"]) 
LAT = Histogram("scrapy_response_latency_seconds", "Latency", ["spider"]) 

# Per-target metrics
TARGET_REQS = Counter("scrapy_target_requests_total", "Total requests per target and status code", ["spider", "target", "code"]) 
TARGET_BYTES = Counter("scrapy_target_response_bytes_total", "Bytes fetched per target", ["spider", "target"]) 
TARGET_LAT = Histogram("scrapy_target_response_latency_seconds", "Latency per target", ["spider", "target"]) 
CHAPTERS = Counter("scrapy_chapters_scraped_total", "Chapters scraped successfully", ["spider", "target"]) 
FAILURES = Counter("scrapy_target_failures_total", "Failures per target", ["spider", "target", "kind"]) 
NOVELS = Counter("scrapy_novels_discovered_total", "Novels discovered from catalog pages", ["spider", "target"]) 


class PrometheusExtension:
    def __init__(self, port: int, redis_url: str | None):
        self.port = port
        self.redis_url = redis_url
        self.r = None

    @classmethod
    def from_crawler(cls, crawler):
        port = int(crawler.settings.getint("METRICS_PORT", 8000))
        redis_url = crawler.settings.get("REDIS_URL")
        ext = cls(port, redis_url)
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        crawler.signals.connect(ext.item_scraped, signal=signals.item_scraped)
        crawler.signals.connect(ext.response_received, signal=signals.response_received)
        # Additional failure-related signals
        crawler.signals.connect(ext.item_dropped, signal=signals.item_dropped)
        crawler.signals.connect(ext.spider_error, signal=signals.spider_error)
        # request_dropped is not in all versions; guard at runtime
        try:
            crawler.signals.connect(ext.request_dropped, signal=signals.request_dropped)
        except Exception:
            pass
        return ext

    def spider_opened(self, spider):
        # Start Prometheus HTTP server once per process (safe to call multiple times; no-op after started)
        start_http_server(self.port)
        if self.redis_url:
            try:
                self.r = redis.from_url(self.redis_url)
            except Exception:
                self.r = None

    def spider_closed(self, spider):
        pass

    def item_scraped(self, item, response, spider):
        ITEMS.labels(spider=spider.name).inc()
        try:
            target = item.get("target_key") if isinstance(item, dict) else None
            if target is None and response is not None:
                target = getattr(response, "meta", {}).get("target_key")
            if target:
                CHAPTERS.labels(spider=spider.name, target=str(target)).inc()
        except Exception:
            # Avoid breaking the pipeline on metric errors
            pass

    def item_dropped(self, item, response, exception, spider):
        try:
            target = None
            if isinstance(item, dict):
                target = item.get("target_key")
            if target is None and response is not None:
                target = response.meta.get("target_key")
            FAILURES.labels(spider=spider.name, target=str(target or "unknown"), kind="item_dropped").inc()
        except Exception:
            pass

    def spider_error(self, failure, response, spider):
        try:
            target = None
            if response is not None:
                target = response.meta.get("target_key")
            FAILURES.labels(spider=spider.name, target=str(target or "unknown"), kind="spider_error").inc()
        except Exception:
            pass

    def request_dropped(self, request, spider):
        try:
            target = request.meta.get("target_key") if request is not None else None
            FAILURES.labels(spider=spider.name, target=str(target or "unknown"), kind="request_dropped").inc()
        except Exception:
            pass

    def response_received(self, response, request, spider):
        code = getattr(response, 'status', 'NA')
        REQS.labels(spider=spider.name, code=str(code)).inc()
        BYTES.labels(spider=spider.name).inc(len(response.body or b""))
        LAT.labels(spider=spider.name).observe(response.meta.get("download_latency", 0.0))
        # Per-target observations
        try:
            target = response.meta.get("target_key")
            if target:
                TARGET_REQS.labels(spider=spider.name, target=str(target), code=str(code)).inc()
                TARGET_BYTES.labels(spider=spider.name, target=str(target)).inc(len(response.body or b""))
                TARGET_LAT.labels(spider=spider.name, target=str(target)).observe(response.meta.get("download_latency", 0.0))
                # Treat HTTP 4xx/5xx as failures
                if isinstance(code, int):
                    status = code
                else:
                    try:
                        status = int(code)
                    except Exception:
                        status = 0
                if status >= 400:
                    FAILURES.labels(spider=spider.name, target=str(target), kind=f"http_{status}").inc()
        except Exception:
            pass
        # Queue depth from Redis (global per-spider)
        if self.r:
            key = os.environ.get("REDIS_START_URLS_KEY", f"queue:{spider.name}")
            try:
                depth = self.r.llen(key)
                QUEUE.labels(spider=spider.name).set(depth)
            except Exception:
                pass
