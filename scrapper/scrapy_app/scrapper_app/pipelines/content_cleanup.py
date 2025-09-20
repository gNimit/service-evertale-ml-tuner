import logging
import trafilatura

from itemadapter import ItemAdapter

class CleanChapterPipeline:
    logger = logging.getLogger(__name__)
    def __init__(self):
        pass

    def process_item(self, item, spider):
        self.logger.debug(f"Processing chapter: {item}")
        ad = ItemAdapter(item)
        html = ad.get("body_html")
        if html:
            txt = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
            ad["body_text"] = txt.strip()
        return item
