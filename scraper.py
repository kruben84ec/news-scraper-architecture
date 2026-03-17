import requests
from bs4 import BeautifulSoup
import json
import os
import logging
import time
from datetime import datetime, UTC
from dotenv import load_dotenv

# =========================
# Configuración inicial
# =========================

load_dotenv()

URL = os.getenv("SCRAPER_URL")
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "data/news.json")
LOG_FILE = os.getenv("LOG_FILE", "scraper.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 10))
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0")
SELECTOR = os.getenv("CSS_SELECTOR", "h2 a")
MIN_HTML_SIZE = int(os.getenv("MIN_HTML_SIZE", 1000))
MIN_ARTICLES = int(os.getenv("MIN_ARTICLES", 1))

# =========================
# Logging
# =========================

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# =========================
# Métricas
# =========================

metrics = {
    "status_code": None,
    "html_size": 0,
    "articles_found": 0,
    "articles_saved": 0,
    "duration_seconds": 0,
    "success": False
}

# =========================
# Funciones
# =========================

def validate_env():
    """Valida que las variables críticas estén definidas."""
    if not URL:
        raise ValueError("SCRAPER_URL no está definido en .env")


def get_html(url: str) -> str | None:
    """Obtiene el HTML desde la URL."""
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, timeout=TIMEOUT)

        metrics["status_code"] = response.status_code

        if response.status_code == 200:
            html = response.text
            metrics["html_size"] = len(html)
            return html

        logging.error(f"HTTP error: {response.status_code}")
        return None

    except Exception as e:
        logging.error(f"Error en get_html: {e}")
        return None


def parse_news(html: str) -> list:
    """Parsea el HTML y extrae noticias."""
    soup = BeautifulSoup(html, "html.parser")
    articles = soup.select(SELECTOR)

    results = []

    for article in articles:
        title = article.get_text(strip=True)
        link = article.get("href")

        if title and link:
            results.append({
                "title": title,
                "link": link,
                "scraped_at": datetime.now(UTC).isoformat()
            })

    metrics["articles_found"] = len(articles)
    metrics["articles_saved"] = len(results)

    return results


def validate_data(data: list) -> tuple:
    """Valida calidad de los datos."""
    if metrics["status_code"] != 200:
        return False, "HTTP status inválido"

    if metrics["html_size"] < MIN_HTML_SIZE:
        return False, "HTML demasiado pequeño"

    if metrics["articles_found"] < MIN_ARTICLES:
        return False, "No se encontraron suficientes artículos"

    if not data:
        return False, "Lista de datos vacía"

    return True, None


def save_json(data: list):
    """Guarda los datos en JSON."""
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logging.info(f"Datos guardados en {OUTPUT_FILE}")


def print_metrics():
    """Imprime métricas."""
    logging.info("===== MÉTRICAS =====")
    for key, value in metrics.items():
        logging.info(f"{key}: {value}")


# =========================
# Main
# =========================

def main():
    """Orquesta el proceso completo."""
    start_time = time.time()

    validate_env()

    if URL is None:
        logging.error("URL no está disponible")
        metrics["duration_seconds"] = round(time.time() - start_time, 2)
        print_metrics()
        return

    html = get_html(URL)
    if html is None:
        metrics["duration_seconds"] = round(time.time() - start_time, 2)
        print_metrics()
        return

    data = parse_news(html)

    valid, error = validate_data(data)
    if not valid:
        logging.error(f"Validación fallida: {error}")
        return

    save_json(data)

    metrics["success"] = True
    metrics["duration_seconds"] = round(time.time() - start_time, 2)

    print_metrics()


if __name__ == "__main__":
    main()