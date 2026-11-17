"""Tests for finding a creator's campaign id in a Patreon creator page."""
from src.scraper.patreon import extract_campaign_id


def test_reads_the_legacy_unescaped_campaign_id():
    page = '<script>{"campaign_id": 1234567, "name": "x"}</script>'

    assert extract_campaign_id(page) == "1234567"


def test_reads_the_campaign_id_from_escaped_json_self_link():
    page = (
        '<script>self.__next_f.push([1,"{\\"links\\":{\\"self\\":'
        '\\"https://www.patreon.com/api/campaigns/7654321\\"}}"])</script>'
    )

    assert extract_campaign_id(page) == "7654321"


def test_returns_none_when_the_page_has_no_campaign_id():
    assert extract_campaign_id("<html><body>Log in</body></html>") is None
