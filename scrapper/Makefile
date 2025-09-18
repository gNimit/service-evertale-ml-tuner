SHELL := /bin/bash

# Paths are relative to repo root; this file is intended to be included by the root Makefile.
SCRAPPER_COMPOSE := scrapper/docker/docker-compose.yml
DATA_DIR := data/raw/novels

.PHONY: scrapper-help scrapper-prep scrapper-build scrapper-up scrapper-down scrapper-logs scrapper-seed

scrapper-help:
	@echo "Scrapper commands:"
	@echo "  make scrapper-build     # Build scrapper image"
	@echo "  make scrapper-up        # Start redis, postgres, crawler"
	@echo "  make scrapper-down      # Stop scrapper stack"
	@echo "  make scrapper-logs      # Tail crawler logs"
	@echo "  make scrapper-seed      # Seed start URLs into Redis"

scrapper-prep:
	python scrapper/tools/apply_common.py --common scrapper/config/common.yaml --scrapper-env scrapper/docker/.env

scrapper-build: scrapper-prep
	sudo docker compose -f $(SCRAPPER_COMPOSE) build

scrapper-up: scrapper-prep
	mkdir -p $(DATA_DIR)
	sudo docker compose -f $(SCRAPPER_COMPOSE) up -d

scrapper-down:
	sudo docker compose -f $(SCRAPPER_COMPOSE) down -v

scrapper-logs:
	sudo docker compose -f $(SCRAPPER_COMPOSE) logs -f crawler

scrapper-seed:
	sudo docker compose -f $(SCRAPPER_COMPOSE) run --rm seeder
