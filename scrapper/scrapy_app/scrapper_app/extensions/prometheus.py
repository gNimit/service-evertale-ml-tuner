from scrapy import signals
from prometheus_client import Counter, Gauge, Histogram, start_http_server
import redis
import os

REQS = Counter("scrapy_requests_total", "Total requests", ["spider", "code"]) 
ITEMS = Counter("scrapy_items_total", "Total items", ["spider"]) 
BYTES = Counter("scrapy_response_bytes_total", "Bytes fetched", ["spider"]) 
QUEUE = Gauge("scrapy_queue_depth", "Queue depth", ["spider"]) 
LAT = Histogram("scrapy_response_latency_seconds", "Latency", ["spider"]) 


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
        return ext

    def spider_opened(self, spider):
        start_http_server(self.port)
        if self.redis_url:
            try:
                self.r = redis.from_url(self.redis_url)
            except Exception:
                self.r = None

    def spider_closed(self, spider):
        pass

    def item_scraped(self, item, spider):
        ITEMS.labels(spider=spider.name).inc()

    def response_received(self, response, request, spider):
        code = getattr(response, 'status', 'NA')
        REQS.labels(spider=spider.name, code=str(code)).inc()
        BYTES.labels(spider=spider.name).inc(len(response.body or b""))
        LAT.labels(spider=spider.name).observe(response.meta.get("download_latency", 0.0))
        if self.r:
            key = os.environ.get("REDIS_START_URLS_KEY", f"queue:{spider.name}")
            try:
                depth = self.r.llen(key)
                QUEUE.labels(spider=spider.name).set(depth)
            except Exception:
                pass
