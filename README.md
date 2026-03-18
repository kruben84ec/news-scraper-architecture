# 🗞️ Web Scraping de Noticias — Ecuador

> Scraper en Python para extraer noticias desde sitios web ecuatorianos, transformarlas a JSON y permitir su consumo en aplicaciones frontend.

---

## 📋 Descripción General

Este proyecto implementa un scraper **configurable**, **observable** y **validado**:

- **Configurable** — toda la conducta del scraper se controla a través de variables de entorno en `.env`, sin tocar el código.
- **Observable** — emite logs en consola y en archivo, y calcula métricas de cada ejecución (duración, artículos encontrados, estado HTTP, etc.).
- **Validado** — antes de guardar cualquier dato, verifica la calidad de la respuesta HTTP y del contenido extraído.

---

## 🏗️ Arquitectura

```
.env Config  →  HTTP Request  →  HTML Parser  →  Validación  →  JSON Output
```

El flujo es completamente secuencial y orquestado por `main()`. Adicionalmente, un mecanismo de control basado en `execution_log.json` evita ejecuciones más frecuentes que el intervalo mínimo configurado.

---

## 🛠️ Tecnologías

| Tecnología / Librería | Rol en el Proyecto |
|---|---|
| **Python 3.13** | Lenguaje principal del scraper |
| **requests** | Realiza las solicitudes HTTP al sitio objetivo |
| **BeautifulSoup4** | Parsea el HTML y extrae elementos según selectores CSS |
| **python-dotenv** | Carga la configuración desde el archivo `.env` |
| **pytest** | Framework para pruebas automatizadas del proyecto |

---

## 🚀 Instalación

```bash
# 1. Clonar el repositorio
git clone <repo-url>
cd webscraping_project

# 2. Crear y activar entorno virtual
python -m venv venv
source venv/bin/activate    # Mac / Linux
venv\Scripts\activate       # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env        # editar con tus valores

# 5. Ejecutar
python scraper.py
```

---

## ⚙️ Variables de Entorno

Todas se definen en `.env`. Si no se definen, se usan los valores por defecto indicados.

| Variable | Por Defecto | Descripción |
|---|---|---|
| `SCRAPER_URL` | *(requerido)* | URL del sitio a scrapear. Sin valor, el script falla. |
| `OUTPUT_FILE` | `data/news.json` | Ruta del archivo JSON de salida. |
| `LOG_FILE` | `scraper.log` | Archivo donde se escriben los logs. |
| `LOG_LEVEL` | `INFO` | Nivel de logging: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `REQUEST_TIMEOUT` | `10` | Tiempo límite en segundos para la solicitud HTTP. |
| `USER_AGENT` | `Mozilla/5.0` | Cabecera User-Agent enviada al servidor. |
| `CSS_SELECTOR` | `h2 a` | Selector CSS para extraer los artículos del HTML. |
| `MIN_HTML_SIZE` | `1000` | Tamaño mínimo en bytes del HTML recibido. |
| `MIN_ARTICLES` | `1` | Nº mínimo de artículos para considerar la ejecución válida. |
| `EXECUTION_LOG_FILE` | `execution_log.json` | Historial de ejecuciones en JSON. |
| `MIN_INTERVAL_SECONDS` | `300` | Intervalo mínimo entre ejecuciones (en segundos). |

---

## 📖 Referencia de Funciones

### Control de Ejecución

#### `load_execution_log() → list`
Lee el historial de ejecuciones desde `execution_log.json`. Retorna una lista de entradas previas. Si el archivo no existe o está corrupto, retorna lista vacía y registra el error en el log.

#### `save_execution_log(entry: dict)`
Añade una nueva entrada al historial de ejecuciones. Primero carga el historial existente y luego escribe el archivo completo actualizado.

#### `can_execute() → tuple[bool, str | None]`
Valida si el scraper puede ejecutarse según el intervalo mínimo (`MIN_INTERVAL_SECONDS`). Retorna una tupla `(permitido, mensaje)`. Si la última ejecución fue hace menos del intervalo configurado, bloquea la ejecución con un mensaje descriptivo.

---

### Funciones Principales

#### `validate_env()`
Verifica que la variable `SCRAPER_URL` esté definida. Si no lo está, lanza `ValueError` y detiene el programa inmediatamente, evitando ejecuciones sin objetivo.

#### `get_html(url: str) → str | None`
Realiza la solicitud HTTP GET a la URL configurada con el User-Agent y timeout definidos. Registra el código de estado HTTP y el tamaño del HTML en las métricas. Retorna el texto HTML o `None` si ocurre algún error.

#### `parse_news(html: str) → list`
Usa BeautifulSoup para parsear el HTML y extraer los elementos que coincidan con el selector CSS configurado. Por cada elemento encontrado, extrae el texto del enlace y su URL (`href`), más la marca de tiempo del scraping (`scraped_at`). Actualiza las métricas de artículos encontrados y guardados.

#### `validate_data(data: list) → tuple[bool, str | None]`
Aplica tres validaciones de calidad sobre los datos obtenidos:
1. Que el código HTTP sea `200`.
2. Que el HTML supere el tamaño mínimo configurado (`MIN_HTML_SIZE`).
3. Que se hayan encontrado suficientes artículos (`MIN_ARTICLES`).

Retorna una tupla `(válido, mensaje_de_error)`.

#### `save_json(data: list)`
Guarda la lista de artículos en el archivo JSON de salida. Crea automáticamente los directorios necesarios si no existen. Usa codificación UTF-8 y formato indentado para legibilidad.

#### `print_metrics()`
Imprime todas las métricas acumuladas durante la ejecución a través del sistema de logging: estado HTTP, tamaño del HTML, artículos encontrados/guardados, duración y éxito general.

---

### Función Orquestadora

#### `main()`
Orquesta el flujo completo en orden:

1. Valida variables de entorno (`validate_env`)
2. Verifica el intervalo mínimo de ejecución (`can_execute`)
3. Descarga el HTML (`get_html`)
4. Parsea y extrae artículos (`parse_news`)
5. Valida la calidad de los datos (`validate_data`)
6. Guarda el JSON (`save_json`)
7. Imprime métricas (`print_metrics`)
8. Registra la ejecución en el historial (`save_execution_log`)

En cada paso crítico, si algo falla, detiene el proceso y reporta las métricas antes de terminar.

---

## 📊 Métricas y Logging

Cada ejecución produce las siguientes métricas, impresas en el log y guardadas en el historial:

| Métrica | Descripción |
|---|---|
| `status_code` | Código de respuesta HTTP del sitio objetivo |
| `html_size` | Tamaño en bytes del HTML descargado |
| `articles_found` | Cantidad de elementos que coincidieron con el selector CSS |
| `articles_saved` | Cantidad de artículos con título y enlace válidos guardados |
| `duration_seconds` | Tiempo total de ejecución en segundos |
| `success` | Booleano: indica si la ejecución fue completamente exitosa |

Los logs se emiten simultáneamente a la consola y al archivo definido en `LOG_FILE`. El nivel de detalle se controla con `LOG_LEVEL`.

---

## 📁 Estructura de Archivos

```
webscraping_project/
├── scraper.py              # Script principal
├── .env                    # Variables de entorno (no versionar)
├── requirements.txt        # Dependencias Python
├── scraper.log             # Log de ejecuciones (generado)
├── execution_log.json      # Historial de ejecuciones (generado)
└── data/
    └── news.json           # Artículos extraídos (generado)
```

### Formato de `news.json`

```json
[
  {
    "title": "Título del artículo",
    "link": "https://...",
    "scraped_at": "2025-07-14T12:00:00.000000"
  }
]
```

---

## ✅ Notas y Recomendaciones

- **No versionar `.env`** — contiene URLs potencialmente privadas. Añadirlo a `.gitignore`.
- **Respetar el intervalo mínimo** (`MIN_INTERVAL_SECONDS`) para no sobrecargar el servidor objetivo.
- **Verificar el selector CSS** (`CSS_SELECTOR`) si el sitio cambia su estructura HTML.
- **En producción**, programar la ejecución con `cron` o un job scheduler.
- **El campo `scraped_at` usa UTC** — ajustar según zona horaria si es necesario para el frontend.
