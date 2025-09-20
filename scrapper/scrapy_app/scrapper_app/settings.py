"""
Scrapper settings
"""
from scrapper.config.config import get_setting

# Define default values
_DEF_REDIS_PORT = int((get_setting("REDIS_PORT", 6379)))
_DEF_PG_PORT = int((get_setting("POSTGRES_PORT", 5432)))
_DEF_METRICS_PORT = int((get_setting("METRICS_PORT", 8000)))

BOT_NAME = "novel_crawler"
SPIDER_MODULES = ["scrapper_app.spiders"]
NEWSPIDER_MODULE = "scrapper_app.spiders"
ROBOTSTXT_OBEY = True

# Concurrency & throttling
CONCURRENT_REQUESTS = int(get_setting("CONCURRENT_REQUESTS", 32))
CONCURRENT_REQUESTS_PER_DOMAIN = int(get_setting("CONCURRENT_REQUESTS_PER_DOMAIN", 6))
DOWNLOAD_DELAY = float(get_setting("DOWNLOAD_DELAY", 0.25))
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.25
AUTOTHROTTLE_MAX_DELAY = 8
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0

# Timeouts & retries
DOWNLOAD_TIMEOUT = int(get_setting("DOWNLOAD_TIMEOUT", 30))
RETRY_ENABLED = True
RETRY_TIMES = int(get_setting("RETRY_TIMES", 3))
RETRY_HTTP_CODES = [429, 500, 502, 503, 504, 522, 524]

# Compression
COMPRESSION_ENABLED = True

# Distributed (Redis)
SCHEDULER = "scrapy_redis.scheduler.Scheduler"
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
SCHEDULER_PERSIST = True
REDIS_URL = f"redis://{get_setting('REDIS_HOST', 'localhost')}:{_DEF_REDIS_PORT}/0"
REDIS_START_URLS_KEY = get_setting("REDIS_START_URLS_KEY", "start_urls:novel_toc")

# Pipelines
ITEM_PIPELINES = {
    "scrapper_app.pipelines.validate.ParseAndValidateItemPipeline": 250,
    # "scrapper_app.pipelines.content_cleanup.CleanSeriesMetaPipeline": 275,
    # "scrapper_app.pipelines.content_cleanup.CleanChapterPipeline": 300,
    # "scrapper_app.pipelines.storage.RollingJSONLPipeline": 500,
    # "scrapper_app.pipelines.db_index.PostgresIndexPipeline": 550,
}

# Extensions (Prometheus)
EXTENSIONS = {
    "scrapper_app.extensions.prometheus.PrometheusExtension": 500,
}
METRICS_PORT = _DEF_METRICS_PORT

# Output dirs
RAW_OUT_DIR = get_setting("RAW_OUT_DIR", "./data/raw/novels")
ROLL_MINUTES = int(get_setting("ROLL_MINUTES", 60))

# Logging
LOG_LEVEL = get_setting("LOG_LEVEL", "INFO")
LOG_FORMAT = get_setting("LOG_FORMAT", "%(asctime)s %(levelname)s %(name)s %(message)s")