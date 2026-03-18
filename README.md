# Web Scraping de Noticias – Ecuador

## Descripción

Este proyecto implementa un scraper en Python para extraer noticias desde el sitio de El Universo, transformarlas en formato JSON y permitir su consumo en aplicaciones frontend.

El sistema está diseñado como un componente:
- Configurable (.env)
- Observable (logs y métricas)
- Validado (tests automatizados)

---

## Arquitectura

Scraper → Parser → Validación → JSON → Frontend

---

## Tecnologías

- Python 3.13
- requests
- BeautifulSoup
- python-dotenv
- pytest

---

## Instalación

```bash
git clone <repo>
cd webscraping_project

python -m venv venv
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

pip install -r requirements.txt

crear servidor
python3 -m http.server 8000

abrir 
http://localhost:8000/dashboard.html