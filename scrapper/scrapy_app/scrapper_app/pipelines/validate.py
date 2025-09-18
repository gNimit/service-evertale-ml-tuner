from itemadapter import ItemAdapter
from pydantic import ValidationError
from scrapper.scrapy_app.scrapper_app.items import ChapterItem


class ValidateItemPipeline:
    def process_item(self, item, spider):
        ad = ItemAdapter(item)
        meta = ad.get("meta") or {}
        # Skip validation for failure items that intentionally lack fields
        if meta.get("failure"):
            return item
        try:
            ChapterItem(**ad.asdict())
        except ValidationError as e:
            spider.logger.warning("Validation error: %s", e)
            raise
        return item
