"""
Scrapper settings
"""

import logging
import os
import yaml

_globals = {}
_settings = {}

def load_globals():
    env_file = os.getenv("SCRAPPER_ENV_FILE", "/app/scrapper/docker/.scrapper.env")
    try:
        # Load .scrapper.env
        with open(env_file, "r") as f:
            for line in f:
                k, v = line.strip().split("=", 1)
                _globals[k] = v
    except FileNotFoundError:
        logging.exception("Failed to load .scrapper.env")
        exit(1)

def load_settings():
    # Load settings
    scrapper_settings = os.getenv(
        "SCRAPPER_SETTINGS_YAML",
        "/app/scrapper/config/settings.yaml",
    )
    try:
        with open(scrapper_settings, "r") as f:
            y = yaml.safe_load(f) or {}
            globals().update({k: v for k, v in y.items() if k.isupper()})
    except FileNotFoundError:
        logging.exception("Failed to load settings.yaml")
        exit(1)

load_globals()
load_settings()

# Define default values
_DEF_REDIS_PORT = int((_globals.get("REDIS_PORT", 6379)))
_DEF_PG_PORT = int((_globals.get("POSTGRES_PORT", 5432)))
_DEF_METRICS_PORT = int((_globals.get("METRICS_PORT", 8000)))

BOT_NAME = "novel_crawler"
SPIDER_MODULES = ["scrapper_app.spiders"]
NEWSPIDER_MODULE = "scrapper_app.spiders"
ROBOTSTXT_OBEY = True

# Concurrency & throttling
CONCURRENT_REQUESTS = int(_settings.get("CONCURRENT_REQUESTS", 32))
CONCURRENT_REQUESTS_PER_DOMAIN = int(_settings.get("CONCURRENT_REQUESTS_PER_DOMAIN", 6))
DOWNLOAD_DELAY = float(_settings.get("DOWNLOAD_DELAY", 0.25))
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.25
AUTOTHROTTLE_MAX_DELAY = 8
AUTOTHROTTLE_TARGET_CONCURRENCY = 4.0

# Timeouts & retries
DOWNLOAD_TIMEOUT = int(_settings.get("DOWNLOAD_TIMEOUT", 30))
RETRY_ENABLED = True
RETRY_TIMES = int(_settings.get("RETRY_TIMES", 3))
RETRY_HTTP_CODES = [429, 500, 502, 503, 504, 522, 524]

# Compression
COMPRESSION_ENABLED = True

# Distributed (Redis)
SCHEDULER = "scrapy_redis.scheduler.Scheduler"
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
SCHEDULER_PERSIST = True
REDIS_URL = f"redis://redis:{_DEF_REDIS_PORT}/0"
REDIS_START_URLS_KEY = _settings.get("REDIS_START_URLS_KEY", "start_urls:novel_toc")

# Pipelines
ITEM_PIPELINES = {
    "scrapper_app.pipelines.validate.ValidateItemPipeline": 250,
    "scrapper_app.pipelines.content_cleanup.CleanChapterPipeline": 300,
    "scrapper_app.pipelines.storage.RollingJSONLPipeline": 500,
    "scrapper_app.pipelines.db_index.PostgresIndexPipeline": 550,
}

# Extensions (Prometheus)
EXTENSIONS = {
    "scrapper_app.extensions.prometheus.PrometheusExtension": 500,
}
METRICS_PORT = _DEF_METRICS_PORT

# Output dirs
RAW_OUT_DIR = _settings.get("RAW_OUT_DIR", "/data/raw/novels")
ROLL_MINUTES = int(_settings.get("ROLL_MINUTES", 60))

# Logging
LOG_LEVEL = _settings.get("LOG_LEVEL", "INFO")
LOG_FORMAT = _settings.get("LOG_FORMAT", "%(asctime)s %(levelname)s %(name)s %(message)s")

# Playwright (optional per-request)
DOWNLOADER_MIDDLEWARES = {
    "scrapy_playwright.middleware.ScrapyPlaywrightDownloaderMiddleware": 543,
}
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000
PLAYWRIGHT_LAUNCH_OPTIONS = {"headless": True}