"""Royal Road hides an anti-theft notice with in-page CSS; the scraper drops it by markup, not wording."""

from bs4 import BeautifulSoup

from src.scraper.royal_road import RoyalRoadScraper

NOTICE = "Enjoying the story? Show your support by reading it on the official site."


def _page(style: str, notice_tag: str = "span") -> BeautifulSoup:
    return BeautifulSoup(
        f"""<html><head><style>{style}</style></head><body>
        <div class="chapter-inner chapter-content">
          <p class="cnAbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdefg">The ball rolled wide.</p>
          <{notice_tag} class="cjAxM2JmNmQ5Mzk1YTRmZmZiM2Q2MWQ5YTNlMmQxNTU2">{NOTICE}</{notice_tag}>
          <p class="cnZyXwVuTsRqPoNmLkJiHgFeDcBa9876543210zyxwvut">The crowd groaned.</p>
        </div></body></html>""",
        "html.parser",
    )


def _extract(soup: BeautifulSoup) -> tuple[int, str]:
    scraper = RoyalRoadScraper()
    div = soup.find("div", class_="chapter-content")
    removed = scraper._remove_hidden_watermarks(soup, div)
    return removed, scraper._html_to_text(div)


def test_hidden_notice_span_is_removed_and_story_paragraphs_kept():
    removed, text = _extract(_page(".cjAxM2JmNmQ5Mzk1YTRmZmZiM2Q2MWQ5YTNlMmQxNTU2{ display: none; speak: never; }"))
    assert removed == 1
    assert NOTICE not in text
    assert "The ball rolled wide." in text and "The crowd groaned." in text


def test_speak_never_alone_still_marks_the_notice_hidden():
    removed, text = _extract(_page(".cjAxM2JmNmQ5Mzk1YTRmZmZiM2Q2MWQ5YTNlMmQxNTU2 {speak:never}", notice_tag="p"))
    assert removed == 1
    assert NOTICE not in text


def test_page_without_a_hiding_rule_is_left_whole():
    removed, text = _extract(_page(".chapter-inner { font-size: 1.1em; }"))
    assert removed == 0
    assert NOTICE in text
