SHELL := /bin/bash

# Tooling Makefile
# Provides monitoring stack commands (Prometheus + Grafana) for the project.
# This Makefile is intended to be imported by the root Makefile via `-include tooling/Makefile`.

DOCKER ?= docker

.PHONY: monitor-up monitor-down monitor-clean monitor-logs


monitor-up:
	$(DOCKER) compose -f tooling/monitoring/docker-compose.yml up -d

monitor-down:
	$(DOCKER) compose -f tooling/monitoring/docker-compose.yml down

monitor-clean:
	$(DOCKER) compose -f tooling/monitoring/docker-compose.yml down -v

monitor-logs:
	$(DOCKER) compose -f tooling/monitoring/docker-compose.yml logs -f
