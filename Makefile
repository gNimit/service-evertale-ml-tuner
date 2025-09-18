SHELL := /bin/bash

# Root Makefile aggregator
# Convention: Each component defines its own Makefile under its directory
# (e.g., scrapper/Makefile, tooling/Makefile) and they are imported here
# using `-include <dir>/Makefile`. Component-specific targets should live
# close to their code; the root Makefile provides a unified entry point.

# Import component-specific targets
-include scrapper/Makefile
-include tooling/Makefile

.PHONY: help monitor-up monitor-down monitor-logs

help:
	@echo "Scrapper commands:"
	@echo "  make scrapper-build     # Build scrapper image"
	@echo "  make scrapper-up        # Start redis, postgres, crawler"
	@echo "  make scrapper-down      # Stop scrapper stack"
	@echo "  make scrapper-logs      # Tail crawler logs"
	@echo "  make scrapper-seed      # Seed start URLs into Redis"
	@echo "Monitoring commands:"
	@echo "  make monitor-up         # Start Prometheus + Grafana"
	@echo "  make monitor-down       # Stop monitoring stack"
	@echo "  make monitor-logs       # Tail monitoring stack logs"

