FROM python:3.11-slim
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
     PYTHONPATH=/app \
     SCRAPPER_SETTINGS_YAML=/app/scrapper/config/settings.yaml

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libxml2-dev libxslt1-dev zlib1g-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY scrapper /app/scrapper

# Default workdir for scrapy project
WORKDIR /app/scrapper/scrapy_app

VOLUME ["/data"]

# Default command lists spiders
CMD ["scrapy", "list", "-s", "SETTINGS_MODULE=scrapper_app.settings"]
