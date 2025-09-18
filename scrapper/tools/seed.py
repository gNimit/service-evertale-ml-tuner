import argparse
import logging
import redis
from scrapper.config.config import get_setting, get_targets

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--redis", default=f"redis://{get_setting('REDIS_HOST')}:{get_setting('REDIS_PORT')}")
    parser.add_argument("--key", default=get_setting("REDIS_START_URLS_KEY"))
    parser.add_argument("--target", default=",".join(get_targets().keys()))  # Defaults to all targets as comma-separated string
    parser.add_argument("--targets_yaml", default="/app/scrapper/config/targets.yaml")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    try:
        r = redis.client.Redis.from_url(args.redis)
        logging.info(f"Connected to Redis at {args.redis}")
    except Exception as e:
        logging.error(f"Failed to connect to Redis: {e}")
        raise logging.exception("Failed to connect to Redis")


    targets = get_targets()
    if not targets:
        logging.error("No targets found in targets.yaml")
        return

    if args.target:
        for t in args.target.split(","):
            if t not in targets:
                logging.warning(f"Target {t} not found in targets.yaml")
                continue
            urls = targets.get(t, {}).get("start_urls", [])
            if not urls:
                logging.warning(f"No start_urls found for target {t}")
                continue
            for u in urls:
                r.lpush(f"{args.key}:{t}", u)
            logging.info(f"Seeded {len(urls)} urls into {args.key} for target {t}")

if __name__ == "__main__":
    main()
