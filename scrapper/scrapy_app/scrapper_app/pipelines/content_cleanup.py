from itemadapter import ItemAdapter
import trafilatura


class CleanChapterPipeline:
    def process_item(self, item, spider):
        ad = ItemAdapter(item)
        html = ad.get("body_html")
        if html:
            txt = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
            ad["body_text"] = txt.strip()
        return item
