# Evertale ML Tuner (Novel Crawler & Dataset Ingestion)

A distributed web crawling and data preparation pipeline designed to scrape web novels, extract clean chapter prose and metadata, and store partitioned datasets for training and fine-tuning machine learning models.

---

## System Architecture

The pipeline consists of:
- **Distributed Crawler**: Powered by [Scrapy](https://scrapy.org/) and [Scrapy-Redis](https://github.com/rmax/scrapy-redis) for shared URL queues and deduplication across worker nodes.
- **Content Cleaning & Text Extraction**: [Trafilatura](https://trafilatura.readthedocs.io/) and [lxml](https://lxml.de/) heuristic extraction pipelines to strip advertisements, navigation boilerplate, and footers while capturing notes and comments.
- **Data Validation**: Strict [Pydantic v2](https://docs.pydantic.dev/) schemas defining clean chapter entities (`ChapterItem`).
- **Partitioned Storage**: Gzip-compressed series archives (`data/raw/novels/<series_slug>/chapters.jsonl.gz`) with accompanying `metadata.json` manifests.
- **Relational Metadata Index**: [PostgreSQL 16](https://www.postgresql.org/) for indexing crawled series, chapters, status codes, and failure logs.
- **Observability**: [Prometheus](https://prometheus.io/) metrics exporter (port `8000`) and pre-provisioned [Grafana](https://grafana.com/) dashboards (port `3000`).

---

## Directory Layout

```
├── Makefile                           # Unified entry point for crawler and monitoring
├── requirements.txt                   # Python dependencies
├── .env.example                       # Documented environment variables template
├── scrapper/
│   ├── Makefile                       # Crawler stack lifecycle commands
│   ├── config/
│   │   ├── config.py                  # Hierarchical configuration loader
│   │   ├── settings.yaml              # Default crawler parameters
│   │   ├── targets.yaml               # Target websites, selectors, and crawling rules
│   │   └── prometheus.yaml            # Prometheus scrape targets
│   ├── docker/
│   │   ├── Dockerfile                 # Crawler container image
│   │   ├── docker-compose.yml         # Core services: Redis, Postgres, Crawler, Seeder
│   │   └── docker-compose.development.yml
│   ├── scrapy_app/                    # Scrapy project root
│   │   ├── scrapy.cfg
│   │   └── scrapper_app/
│   │       ├── items.py               # Pydantic data schemas
│   │       ├── settings.py            # Scrapy pipeline, extension, and throttle settings
│   │       ├── spiders/novels.py      # Multi-stage catalog, TOC, and chapter spider
│   │       ├── pipelines/             # Content cleanup -> validation -> storage -> DB
│   │       ├── extensions/            # Prometheus metrics extension
│   │       └── db/sql.py              # PostgreSQL schema and upsert statements
│   └── tools/seed.py                  # Seed start URLs into Redis
└── tooling/
    ├── Makefile                       # Monitoring stack commands
    └── monitoring/                    # Prometheus and Grafana Docker Compose stack
```

---

## Quickstart Guide

### 1. Environment Setup
Copy the example environment file and adjust variables as needed:
```bash
cp .env.example .env
```

### 2. Start the Crawler Stack
Build and launch Redis, PostgreSQL, and the Crawler worker:
```bash
make scrapper-build
make scrapper-up
```

### 3. Seed Target URLs
Populate Redis with the initial catalog/start URLs configured in `scrapper/config/targets.yaml`:
```bash
make scrapper-seed
```

### 4. Monitor Crawl Progress
Tail crawler logs:
```bash
make scrapper-logs
```

Start Prometheus and Grafana to view live ingestion metrics and queues:
```bash
make monitor-up
```
- **Grafana Dashboard**: [http://localhost:3000](http://localhost:3000) (Default login: `admin` / `admin`)
- **Prometheus UI**: [http://localhost:9090](http://localhost:9090)
- **Crawler Metrics Endpoint**: [http://localhost:8000](http://localhost:8000)

---

## Stopping & Teardown

- **Safe Stop (Preserves Database & Redis Volumes)**:
  ```bash
  make scrapper-down
  make monitor-down
  ```

- **Clean Reset (Wipes Volumes & Re-initializes Storage)**:
  ```bash
  make scrapper-clean
  make monitor-clean
  ```

---

## Adding New Targets

Add new scraping targets to `scrapper/config/targets.yaml`:
```yaml
site_example:
  landing_kind: catalog        # 'catalog' or 'single'
  use_playwright: false
  start_urls:
    - https://example.com/novels
  catalog:
    novel_links:
      - .novel-item a::attr(href)
    next_page: .pagination .next a::attr(href)
  novel_toc:
    title: h1.novel-title::text
    author: span.author::text
    tags: a.genre::text
    chapter_links:
      - ul.chapter-list a::attr(href)
  chapter:
    title: h2.chapter-title::text
    body: .chapter-content p::text
```
After editing `targets.yaml`, run `make scrapper-seed` to push new URLs into the crawl queue.
