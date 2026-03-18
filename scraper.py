import requests
from bs4 import BeautifulSoup
import json
import os
import logging
import time
import uuid
import base64
from urllib.parse import urljoin, urlparse
from datetime import datetime, UTC
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
IMAGE_SELECTOR = os.getenv("IMAGE_SELECTOR", "img")   # selector CSS para la imagen dentro del artículo
MIN_HTML_SIZE = int(os.getenv("MIN_HTML_SIZE", 1000))
MIN_ARTICLES = int(os.getenv("MIN_ARTICLES", 1))

# Control de ejecución
EXECUTION_LOG_FILE = os.getenv("EXECUTION_LOG_FILE", "data/execution_log.json")
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
    "images_fetched": 0,
    "images_failed": 0,
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
    os.makedirs(os.path.dirname(EXECUTION_LOG_FILE), exist_ok=True)
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
    now = datetime.now(UTC)
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
# Funciones de imagen
# =========================

def fetch_image_as_base64(image_url: str) -> str | None:
    """
    Descarga una imagen desde su URL y la convierte a base64 data URI.

    El data URI resultante puede usarse directamente en un <img src="...">,
    sin depender de servidores externos ni CORS.

    Retorna la cadena 'data:<mimetype>;base64,...' o None si falla.
    """
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(image_url, headers=headers, timeout=TIMEOUT, stream=True)

        if response.status_code != 200:
            logging.debug(f"Imagen no descargada ({response.status_code}): {image_url}")
            return None

        content_type = response.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()

        # Solo aceptar tipos imagen
        if not content_type.startswith("image/"):
            logging.debug(f"Content-Type no es imagen: {content_type}")
            return None

        raw = response.content

        # Limitar peso: ignorar imágenes mayores a 500 KB para no inflar el JSON
        if len(raw) > 500 * 1024:
            logging.debug(f"Imagen demasiado grande ({len(raw)} bytes): {image_url}")
            return None

        encoded = base64.b64encode(raw).decode("utf-8")
        return f"data:{content_type};base64,{encoded}"

    except Exception as e:
        logging.debug(f"Error descargando imagen {image_url}: {e}")
        return None


def extract_article_image(article_tag, base_url: str) -> str | None:
    """
    Busca la URL de la imagen más relevante asociada a un artículo.

    Estrategia en orden de prioridad:
      1. og:image en la página del artículo (más confiable, imagen editorial)
      2. <img> hermano o ancestro cercano del enlace en el listado
      3. Primer <img> con src válido encontrado en el contenedor padre

    'base_url' se usa para resolver rutas relativas a URLs absolutas.
    Retorna la URL absoluta de la imagen o None si no se encuentra ninguna.
    """
    # Estrategia 1: buscar <img> en el mismo contenedor del enlace
    container = article_tag.parent
    for _ in range(3):  # subir hasta 3 niveles
        if container is None:
            break
        img = container.find("img")
        if img:
            # img.get() devuelve _AttributeValue — normalizar a str | None
            raw_src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            src: str | None = (
                raw_src[0] if isinstance(raw_src, list) and raw_src
                else str(raw_src) if raw_src is not None
                else None
            )
            if src and not src.startswith("data:"):
                return urljoin(base_url, src)
        container = container.parent

    return None


def resolve_link(link: str, base_url: str) -> str:
    """
    Convierte un href relativo en URL absoluta usando la URL base del sitio.

    Ejemplos:
      /noticias/123  →  https://www.eluniverso.com/noticias/123
      https://...    →  sin cambios
    """
    if not link:
        return link
    return urljoin(base_url, link)


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
    """
    Parsea HTML y extrae noticias con enlace absoluto e imagen.

    Para cada artículo encontrado:
      - Resuelve el href relativo a URL absoluta usando URL como base
      - Busca la imagen más relevante en el contenedor del artículo
      - Registra la URL de la imagen (la descarga base64 ocurre en enrich_with_images)
    """
    soup = BeautifulSoup(html, "html.parser")
    articles = soup.select(SELECTOR)

    results = []

    for article in articles:
        title = article.get_text(strip=True)

        # article.get() devuelve _AttributeValue (str | list | None en BeautifulSoup).
        # Normalizamos a str | None para que resolve_link reciba siempre un tipo seguro.
        raw_link_attr = article.get("href")
        if isinstance(raw_link_attr, list):
            # Caso raro: href con múltiples valores; tomar el primero
            raw_link: str | None = raw_link_attr[0] if raw_link_attr else None
        else:
            raw_link = str(raw_link_attr) if raw_link_attr is not None else None

        if not title or not raw_link:
            continue

        # Resolver URL relativa → absoluta
        absolute_link = resolve_link(raw_link, URL)

        # Buscar imagen asociada en el DOM del listado
        image_url = extract_article_image(article, URL)

        results.append({
            "title": title,
            "link": absolute_link,
            "image_url": image_url,      # URL original (puede ser None)
            "image_b64": None,           # se rellena en enrich_with_images()
            "scraped_at": datetime.now(UTC).isoformat()
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


def enrich_with_images(articles: list) -> list:
    """
    Descarga las imágenes de los artículos nuevos y las embebe como base64.

    Solo procesa artículos que:
      - Tienen image_url definida
      - Aún no tienen image_b64 (evita re-descargar en ejecuciones sucesivas)

    Actualiza las métricas images_fetched e images_failed.
    Retorna la lista modificada in-place.
    """
    pending = [a for a in articles if a.get("image_url") and not a.get("image_b64")]
    logging.info(f"Descargando imágenes para {len(pending)} artículos nuevos...")

    for article in pending:
        b64 = fetch_image_as_base64(article["image_url"])
        if b64:
            article["image_b64"] = b64
            metrics["images_fetched"] += 1
            logging.debug(f"Imagen OK: {article['image_url'][:80]}")
        else:
            article["image_b64"] = None
            metrics["images_failed"] += 1
            logging.debug(f"Imagen fallida: {article['image_url'][:80]}")

    return articles


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

    # Descargar imágenes solo para los artículos nuevos
    merged = enrich_with_images(merged)

    save_json(merged)

    metrics["success"] = True
    metrics["duration_seconds"] = round(time.time() - start_time, 2)

    print_metrics()

    execution_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "metrics": metrics
    }
    save_execution_log(execution_entry)


if __name__ == "__main__":
    main()