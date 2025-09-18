SHELL := /bin/bash

# Tooling Makefile
# Provides monitoring stack commands (Prometheus + Grafana) for the project.
# This Makefile is intended to be imported by the root Makefile via `-include tooling/Makefile`.

.PHONY: monitor-prep monitor-up monitor-down monitor-logs

monitor-prep:
	python scrapper/tools/apply_common.py \
		--common scrapper/config/common.yaml \
		--prom-template tooling/monitoring/prometheus.yml.tpl \
		--prom-out tooling/monitoring/prometheus.yml \
		--scrapper-env scrapper/docker/.env

monitor-up: monitor-prep
	sudo docker compose -f tooling/monitoring/docker-compose.yml up -d

monitor-down:
	sudo docker compose -f tooling/monitoring/docker-compose.yml down -v

monitor-logs:
	sudo docker compose -f tooling/monitoring/docker-compose.yml logs -f
