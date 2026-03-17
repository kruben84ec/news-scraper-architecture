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
        assert html is not None, "HTML debe no ser None"
        assert len(html) > 1000, "HTML debe tener más de 1000 caracteres"

        log_result("test_get_html_success", "PASS")

    except AssertionError as e:
        log_result("test_get_html_success", "FAIL", str(e))
        raise


# ========================
# TEST 2: PARSING
# ========================
def test_parse_news():
    html = get_html(TEST_URL)
    
    try:
        assert html is not None, "HTML debe no ser None para poder parsear"
        
        data = parse_news(html)
        
        assert isinstance(data, list), "El resultado debe ser una lista"
        assert len(data) > 0, "Debe haber al menos un artículo"

        log_result("test_parse_news", "PASS")

    except AssertionError as e:
        log_result("test_parse_news", "FAIL", str(e))
        raise


# ========================
# TEST 3: DATA STRUCTURE
# ========================
def test_data_structure():
    html = get_html(TEST_URL)
    
    try:
        assert html is not None, "HTML debe no ser None"
        
        data = parse_news(html)
        assert len(data) > 0, "Debe haber al menos un artículo"

        sample = data[0]

        assert "title" in sample, "Cada artículo debe tener 'title'"
        assert "link" in sample, "Cada artículo debe tener 'link'"
        assert "scraped_at" in sample, "Cada artículo debe tener 'scraped_at'"

        log_result("test_data_structure", "PASS")

    except AssertionError as e:
        log_result("test_data_structure", "FAIL", str(e))
        raise


# ========================
# TEST 4: VALIDATION OK
# ========================
def test_validate_data_success():
    html = get_html(TEST_URL)

    try:
        assert html is not None, "HTML debe no ser None"
        
        data = parse_news(html)
        valid, error = validate_data(data)

        assert valid is True, f"Validación debe ser exitosa. Error: {error}"
        assert error is None, "No debe haber error si la validación es exitosa"

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
        assert valid is False, "Validación debe fallar con datos vacíos"
        assert error is not None, "Debe haber un mensaje de error"

        log_result("test_validate_data_fail", "PASS")

    except AssertionError as e:
        log_result("test_validate_data_fail", "FAIL", str(e))
        raise


# ========================
# TEST 6: GET HTML NONE
# ========================
def test_get_html_returns_none_on_invalid_url():
    """Prueba que get_html retorna None con URL inválida."""
    invalid_url = "https://invalid-url-that-does-not-exist-12345.com/"
    
    html = get_html(invalid_url)
    
    try:
        assert html is None, "Debe retornar None para URL inválida"
        
        log_result("test_get_html_returns_none_on_invalid_url", "PASS")
    
    except AssertionError as e:
        log_result("test_get_html_returns_none_on_invalid_url", "FAIL", str(e))
        raise