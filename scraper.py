import requests
from bs4 import BeautifulSoup
import json
import os
import logging
import time
import uuid
from datetime import datetime
from typing import cast
from dotenv import load_dotenv

# =========================
# Configuración
# =========================

load_dotenv()

URL = cast(str, os.getenv("SCRAPER_URL"))
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "data/news.json")
LOG_FILE = os.getenv("LOG_FILE", "scraper.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 10))
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0")
SELECTOR = os.getenv("CSS_SELECTOR", "h2 a")
MIN_HTML_SIZE = int(os.getenv("MIN_HTML_SIZE", 1000))
MIN_ARTICLES = int(os.getenv("MIN_ARTICLES", 1))

# Control de ejecución
EXECUTION_LOG_FILE = os.getenv("EXECUTION_LOG_FILE", "execution_log.json")
MIN_INTERVAL = int(os.getenv("MIN_INTERVAL_SECONDS", 300))

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
    "articles_new": 0,
    "articles_duplicated": 0,
    "articles_total_stored": 0,
    "duration_seconds": 0,
    "success": False
}

# =========================
# Funciones de control
# =========================

def load_execution_log():
    """Carga historial de ejecuciones desde JSON."""
    if not os.path.exists(EXECUTION_LOG_FILE):
        return []
    try:
        with open(EXECUTION_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error leyendo log de ejecución: {e}")
        return []


def save_execution_log(entry: dict):
    """Guarda una nueva ejecución en la bitácora."""
    log = load_execution_log()
    log.append(entry)
    with open(EXECUTION_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)


def can_execute() -> tuple:
    """Valida si se puede ejecutar según intervalo mínimo."""
    log = load_execution_log()
    if not log:
        return True, None

    last_execution = log[-1]
    last_time = datetime.fromisoformat(last_execution["timestamp"])
    now = datetime.utcnow()
    diff = (now - last_time).total_seconds()

    if diff < MIN_INTERVAL:
        return False, f"Ejecutado hace {round(diff, 2)}s. Esperar {MIN_INTERVAL}s"

    return True, None


# =========================
# Funciones de persistencia
# =========================

def load_existing_news() -> tuple[list, set]:
    """
    Carga las noticias ya guardadas en el JSON de salida.

    Retorna una tupla con:
      - lista completa de artículos existentes
      - set de links ya almacenados (para deduplicación rápida O(1))
    """
    if not os.path.exists(OUTPUT_FILE):
        return [], set()

    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f)
        known_links = {article["link"] for article in existing if "link" in article}
        logging.info(f"Noticias existentes cargadas: {len(existing)}")
        return existing, known_links
    except Exception as e:
        logging.error(f"Error cargando noticias existentes: {e}")
        return [], set()


def merge_news(existing: list, new_articles: list) -> tuple[list, int, int]:
    """
    Combina noticias existentes con las nuevas, evitando duplicados por link.

    La deduplicación usa el campo 'link' como clave única natural.
    Cada artículo nuevo recibe un UUID v4 único e irrepetible.

    Retorna:
      - lista combinada final
      - cantidad de artículos nuevos agregados
      - cantidad de artículos ignorados por duplicado
    """
    known_links = {article["link"] for article in existing if "link" in article}

    added = 0
    duplicated = 0

    for article in new_articles:
        link = article.get("link")

        if not link or link in known_links:
            duplicated += 1
            logging.debug(f"Duplicado ignorado: {link}")
            continue

        article["id"] = str(uuid.uuid4())
        existing.append(article)
        known_links.add(link)
        added += 1
        logging.debug(f"Nuevo artículo agregado [{article['id']}]: {article.get('title', '')[:60]}")

    return existing, added, duplicated


# =========================
# Funciones principales
# =========================

def validate_env():
    """Valida variables críticas."""
    if not URL:
        raise ValueError("SCRAPER_URL no está definido en .env")


def get_html(url: str) -> str | None:
    """Obtiene HTML desde la URL."""
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
    """Parsea HTML y extrae noticias."""
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
                "scraped_at": datetime.utcnow().isoformat()
                # Nota: 'id' se asigna en merge_news() solo si es artículo nuevo
            })

    metrics["articles_found"] = len(articles)
    return results


def validate_data(data: list) -> tuple:
    """Valida calidad de datos."""
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
    """Guarda la lista completa de noticias en el JSON de salida."""
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logging.info(f"JSON guardado en {OUTPUT_FILE} ({len(data)} artículos en total)")


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

    allowed, reason = can_execute()
    if not allowed:
        logging.warning(f"Ejecución bloqueada: {reason}")
        return

    html = get_html(URL)
    if html is None:
        metrics["duration_seconds"] = round(time.time() - start_time, 2)
        print_metrics()
        return

    scraped = parse_news(html)

    valid, error = validate_data(scraped)
    if not valid:
        logging.error(f"Validación fallida: {error}")
        metrics["duration_seconds"] = round(time.time() - start_time, 2)
        print_metrics()
        return

    # Cargar histórico, fusionar y guardar
    existing, _ = load_existing_news()
    merged, added, duplicated = merge_news(existing, scraped)

    metrics["articles_new"] = added
    metrics["articles_duplicated"] = duplicated
    metrics["articles_total_stored"] = len(merged)

    save_json(merged)

    metrics["success"] = True
    metrics["duration_seconds"] = round(time.time() - start_time, 2)

    print_metrics()

    execution_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "metrics": metrics
    }
    save_execution_log(execution_entry)


if __name__ == "__main__":
    main()