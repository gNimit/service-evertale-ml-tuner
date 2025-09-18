import gzip
import json
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from itemadapter import ItemAdapter


class RollingJSONLPipeline:
    def __init__(self, base_dir: str = "data/raw/novels", roll_minutes: int = 60):
        self.base_dir = Path(base_dir)
        self.roll_minutes = roll_minutes
        self.fp = None
        self.cur_key = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            base_dir=crawler.settings.get("RAW_OUT_DIR", "data/raw/novels"),
            roll_minutes=crawler.settings.getint("ROLL_MINUTES", 60),
        )

    def open_spider(self, spider):
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._roll()

    def close_spider(self, spider):
        if self.fp:
            self.fp.close()

    def _roll(self):
        ts_bucket = int(datetime.utcnow().timestamp() // (self.roll_minutes * 60))
        if ts_bucket != self.cur_key:
            if self.fp:
                self.fp.close()
            ts = datetime.utcnow().strftime("%Y%m%dT%H%MZ")
            path = self.base_dir / f"chapters-{ts}.jsonl.gz"
            self.fp = gzip.open(path, "ab")
            self.cur_key = ts_bucket

    def process_item(self, item, spider):
        self._roll()
        ad = ItemAdapter(item)
        ad.setdefault("id", sha1(ad.get("url", "").encode()).hexdigest())
        line = json.dumps(ad.asdict(), ensure_ascii=False).encode("utf-8") + b"\n"
        self.fp.write(line)
        return item
