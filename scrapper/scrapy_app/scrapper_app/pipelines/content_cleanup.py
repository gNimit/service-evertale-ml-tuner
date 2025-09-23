import logging
try:
    import trafilatura
except ImportError or ModuleNotFoundError or RuntimeError:
    trafilatura = None
from lxml import html as lxml_html
from itemadapter import ItemAdapter
from ..items import ChapterItem  # type: ignore

class CleanChapterPipeline:
    logger = logging.getLogger(__name__)
    def __init__(self):
        pass

    def process_item(self, item, spider):
        self.logger.debug(f"Processing chapter: {item}")
        ad = ItemAdapter(item)

        html = ad.get("body_html")
        if html:
            body_text = self._extract_main_text(html)
            if body_text is not None:
                ad["body_text"] = body_text.strip()

            # chapter_text defaults to body_text if available, else attempt direct extraction
            if ad.get("chapter_text") is None:
                chapter_text = ad.get("body_text") or self._extract_main_text(html) or ""
                ad["chapter_text"] = chapter_text.strip()
            else :
                ad["chapter_text"] = ad.get("chapter_text").strip()

            # Extract any notes we can heuristically find in the HTML
            notes = self._extract_notes(html)
            if notes:
                ad["chapter_notes"] = notes
        else:
            self.logger.debug("No body_html present; skipping text and notes extraction.")

        return item

    def _extract_main_text(self, html: str) -> str:
        """
        Extract main textual content from HTML.
        Prefer trafilatura when available; fallback to lxml text_content otherwise.
        """
        # Try trafilatura (if available)
        if trafilatura is not None:
            try:
                txt = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
                if txt.strip():
                    return txt
            except Exception as e:
                self.logger.debug(f"trafilatura extraction failed, falling back to lxml: {e}")

        # Fallback using lxml
        try:
            doc = lxml_html.fromstring(html)
            # Remove common non-content elements
            lxml_html.etree.strip_elements(doc, "script", "style", "noscript", with_tail=False)
            return doc.text_content()
        except Exception as e:
            self.logger.debug(f"lxml fallback extraction failed: {e}")
            return ""

    def _extract_notes(self, html: str) -> list[str]:
        """
        Heuristically extract chapter notes from HTML.
        Looks for elements commonly used for footnotes/notes.
        """
        notes: list[str] = []
        try:
            doc = lxml_html.fromstring(html)

            # XPath candidates for footnotes/notes blocks
            candidates = []
            # Elements with class/id containing 'footnote' or class containing 'note'
            candidates.extend(doc.xpath("//*[contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'footnote')]"))
            candidates.extend(doc.xpath("//*[contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'footnote')]"))
            candidates.extend(doc.xpath("//section[contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'footnotes')]"))
            candidates.extend(doc.xpath("//ol[contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'footnotes')]/li"))
            candidates.extend(doc.xpath("//*[@id='footnotes']//li"))
            # Asides or divs marked as 'note'
            candidates.extend(doc.xpath("//aside[contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'note')]"))
            candidates.extend(doc.xpath("//div[contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'note')]"))
            # Superscripts linking to footnotes
            candidates.extend(doc.xpath("//sup[a[@href and starts-with(@href, '#')]]"))

            # Deduplicate by element string and final text
            seen_text: set[str] = set()
            for el in candidates:
                # Clean subtrees for script/style to avoid noisy text
                try:
                    lxml_html.etree.strip_elements(el, "script", "style", "noscript", with_tail=False)
                except ValueError:
                    pass
                txt = el.text_content().strip()
                if not txt:
                    continue
                # Normalize whitespace
                norm = " ".join(txt.split())
                if norm and norm.lower() not in seen_text:
                    seen_text.add(norm.lower())
                    notes.append(norm)

        except Exception as e:
            self.logger.debug(f"Note extraction failed: {e}")

        return notes
