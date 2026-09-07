SHELL := /bin/bash

# Paths are relative to repo root; this file is intended to be included by the root Makefile.
SCRAPPER_COMPOSE := scrapper/docker/docker-compose.yml
DATA_DIR := data/raw/novels

DOCKER ?= docker

.PHONY: scrapper-help scrapper-build scrapper-up scrapper-down scrapper-clean scrapper-logs scrapper-seed

scrapper-help:
	@echo "Scrapper commands:"
	@echo "  make scrapper-build     # Build scrapper image"
	@echo "  make scrapper-up        # Start redis, postgres, crawler"
	@echo "  make scrapper-down      # Stop scrapper stack (preserves volumes)"
	@echo "  make scrapper-clean     # Stop scrapper stack and remove volumes"
	@echo "  make scrapper-logs      # Tail crawler logs"
	@echo "  make scrapper-seed      # Seed start URLs into Redis"

scrapper-build:
	rm -f build.log
	$(DOCKER) compose -f $(SCRAPPER_COMPOSE) build --no-cache --progress=plain 2>&1 | tee build.log

scrapper-up:
	mkdir -p $(DATA_DIR)
	$(DOCKER) compose -f $(SCRAPPER_COMPOSE) up -d

scrapper-down:
	$(DOCKER) compose -f $(SCRAPPER_COMPOSE) down

scrapper-clean:
	$(DOCKER) compose -f $(SCRAPPER_COMPOSE) down -v

scrapper-logs:
	$(DOCKER) compose -f $(SCRAPPER_COMPOSE) logs -f crawler

scrapper-seed:
	$(DOCKER) compose -f $(SCRAPPER_COMPOSE) run --rm seeder
