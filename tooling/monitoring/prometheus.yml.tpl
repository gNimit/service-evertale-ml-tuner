global:
  scrape_interval: 10s

scrape_configs:
  - job_name: "scrapper"
    static_configs:
      - targets: ["host.docker.internal:${METRICS_PORT}", "localhost:${METRICS_PORT}"]
