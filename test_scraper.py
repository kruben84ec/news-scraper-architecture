import pytest
import logging
from scraper import get_html, parse_news, validate_data

# ========================
# CONFIG LOG TESTS
# ========================
logging.basicConfig(
    filename="test_results.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

TEST_URL = "https://www.eluniverso.com/noticias/"


def log_result(test_name, status, detail=""):
    logging.info(f"{test_name} | {status} | {detail}")


# ========================
# TEST 1: HTTP RESPONSE
# ========================
def test_get_html_success():
    html = get_html(TEST_URL)

    try:
        assert html is not None
        assert len(html) > 1000

        log_result("test_get_html_success", "PASS")

    except AssertionError as e:
        log_result("test_get_html_success", "FAIL", str(e))
        raise


# ========================
# TEST 2: PARSING
# ========================
def test_parse_news():
    html = get_html(TEST_URL)
    data = parse_news(html)

    try:
        assert isinstance(data, list)
        assert len(data) > 0

        log_result("test_parse_news", "PASS")

    except AssertionError as e:
        log_result("test_parse_news", "FAIL", str(e))
        raise


# ========================
# TEST 3: DATA STRUCTURE
# ========================
def test_data_structure():
    html = get_html(TEST_URL)
    data = parse_news(html)

    try:
        sample = data[0]

        assert "title" in sample
        assert "link" in sample

        log_result("test_data_structure", "PASS")

    except Exception as e:
        log_result("test_data_structure", "FAIL", str(e))
        raise


# ========================
# TEST 4: VALIDATION OK
# ========================
def test_validate_data_success():
    html = get_html(TEST_URL)
    data = parse_news(html)

    valid, error = validate_data(data)

    try:
        assert valid is True
        assert error is None

        log_result("test_validate_data_success", "PASS")

    except AssertionError as e:
        log_result("test_validate_data_success", "FAIL", str(e))
        raise


# ========================
# TEST 5: VALIDATION FAIL
# ========================
def test_validate_data_fail():
    fake_data = []

    valid, error = validate_data(fake_data)

    try:
        assert valid is False
        assert error is not None

        log_result("test_validate_data_fail", "PASS")

    except AssertionError as e:
        log_result("test_validate_data_fail", "FAIL", str(e))
        raise