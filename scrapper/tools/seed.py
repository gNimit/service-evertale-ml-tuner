"""
Seeding Script for scrapper through redis.
"""

import argparse
import json
import logging
import redis
from scrapper.config.config import get_setting, get_targets

def main():
    default_redis = get_setting("REDIS_URL") or f"redis://{get_setting('REDIS_HOST', 'localhost')}:{get_setting('REDIS_PORT', 6379)}/0"
    parser.add_argument("--redis", default=default_redis)
    parser.add_argument("--key", default=get_setting("REDIS_START_URLS_KEY", "start_urls:novel_toc"))
    parser.add_argument("--targets", default=",".join(get_targets().keys()))  # Defaults to all targets as comma-separated string
    parser.add_argument("--targets_yaml", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    if args.targets_yaml:
        import os
        os.environ["SCRAPPER_TARGETS_YAML"] = args.targets_yaml

    try:
        r = redis.from_url(args.redis)
        r.ping()
        logging.info(f"Connected to Redis at {args.redis}")
    except Exception as e:
        logging.error(f"Failed to connect to Redis at {args.redis}: {e}")
        raise


    targets = get_targets()
    total = 0
    for t in [x.strip() for x in args.targets.split(",") if x.strip()]:
        cfg = targets.get(t)
        if not cfg:
            logging.warning(f"Target {t} not found in targets.yaml")
            continue

        start_urls = cfg.get("start_urls", [])
        if not start_urls:
            logging.warning(f"No start_urls found for target {t}")
            continue

        # Decide landing_kind per target; if you have a flag in YAML, use it.
        page_type = cfg.get("page_type", "landing")
        landing_kind = cfg.get("landing_kind", "catalog")
        use_pw = bool(cfg.get("use_playwright", False))

        for u in start_urls:
            payload = {
                "url": u,
                "meta": {
                    "target_key": t,
                    "page_type": page_type,
                    "landing_kind": landing_kind,
                    "use_playwright": use_pw,
                },
            }
            r.lpush(args.key, json.dumps(payload))
            total += 1
        logging.info(f"Seeded {len(start_urls)} entries into {args.key} for target {t}")

    logging.info(f"Done. Total seeded: {total} into {args.key}")

if __name__ == "__main__":
    main()
