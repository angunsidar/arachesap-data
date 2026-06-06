"""
Arabam.com ilan scraper — JSON-LD tabanlı, Selenium gerekmez.
"""
import re
import sys
import time
import json
import random
import requests
from bs4 import BeautifulSoup

from db import init_db, clear_brand, save_listing, count_brand

BASE_URL  = "https://www.arabam.com"
DELAY_MIN = 1.2
DELAY_MAX = 2.8
MAX_PAGES = 5   # her model için maksimum sayfa (GitHub Actions'da kontrollü kal)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

session = requests.Session()
session.headers.update(HEADERS)


def slugify(text: str) -> str:
    s = text.lower()
    for src, dst in [("ş","s"),("ğ","g"),("ü","u"),("ö","o"),("ç","c"),("ı","i"),
                     ("İ","i"),("Ş","s"),("Ğ","g"),("Ü","u"),("Ö","o"),("Ç","c")]:
        s = s.replace(src, dst)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def arabam_url(category_slug: str, brand: str, model: str, page: int = 1) -> str:
    path = f"/ikinci-el/{category_slug}/{slugify(brand)}-{slugify(model)}"
    url  = BASE_URL + path
    if page > 1:
        url += f"?page={page}"
    return url


def _extract_source_id(url: str):
    m = re.search(r"/(\d+)$", url)
    return m.group(1) if m else None


def _extract_package(url: str, brand: str, model: str):
    m = re.search(r"/ilan/([^/]+)/", url)
    if not m:
        return None
    slug = m.group(1).lower()
    slug = re.sub(r"^(galeriden|sahibinden|acil|hizli|kisisel|galeri)-satilik-", "", slug)
    for prefix in [slugify(brand) + "-", slugify(model) + "-"]:
        if slug.startswith(prefix):
            slug = slug[len(prefix):]
    slug = slug.strip("-")
    if not slug or slug == slugify(model):
        return None
    return slug.replace("-", " ").title()


def fetch_page(url: str):
    try:
        r = session.get(url, timeout=15)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        print(f"  [!] {url[:70]}: {e}", file=sys.stderr)
        return None


def parse_listings(html: str, brand: str, model: str) -> list:
    soup     = BeautifulSoup(html, "lxml")
    vehicles = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get("@type") != "Vehicle":
                continue
            url    = item.get("url", "")
            offer  = item.get("offers", {})
            engine = item.get("vehicleEngine", {})
            odo    = item.get("mileageFromOdometer", {})
            sid    = _extract_source_id(url)
            price  = offer.get("price") if isinstance(offer, dict) else None
            if not sid or not price:
                continue
            vehicles.append({
                "source_id":    sid,
                "brand":        item.get("manufacturer") or brand,
                "model":        item.get("model") or model,
                "package_name": _extract_package(url, brand, model),
                "year":         item.get("vehicleModelDate") or item.get("productionDate"),
                "km":           odo.get("value") if isinstance(odo, dict) else None,
                "price_try":    price,
                "fuel_type":    (engine.get("fuelType") if isinstance(engine, dict)
                                 else item.get("fuelType")),
                "transmission": item.get("vehicleTransmission"),
                "color":        item.get("color"),
                "url":          url,
            })
    return vehicles


def has_next_page(html: str, current_page: int) -> bool:
    soup = BeautifulSoup(html, "lxml")
    nxt  = soup.find("a", attrs={"aria-label": re.compile(r"next|sonraki|ileri", re.I)})
    if nxt:
        return True
    pages = soup.find_all("a", href=re.compile(rf"\?page={current_page+1}"))
    return bool(pages)


def scrape_model(category_slug: str, brand: str, model: str) -> int:
    saved = 0
    for page in range(1, MAX_PAGES + 1):
        url  = arabam_url(category_slug, brand, model, page)
        html = fetch_page(url)
        if not html:
            break
        listings = parse_listings(html, brand, model)
        if not listings:
            break
        for lst in listings:
            if save_listing(lst):
                saved += 1
        print(f"    sayfa {page}: {len(listings)} ilan")
        if len(listings) < 18 or not has_next_page(html, page):
            break
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
    return saved


def scrape_brand(brand: str, category_slug: str, models: list) -> int:
    """Bir markanın tüm modellerini scrape et. Önce eski ilanları temizle."""
    deleted = clear_brand(brand)
    if deleted:
        print(f"  Eski ilanlar temizlendi: {deleted} kayıt")

    total = 0
    for model in models:
        print(f"  → {brand} / {model}")
        n     = scrape_model(category_slug, brand, model)
        total += n
        if n == 0:
            time.sleep(0.5)   # 404'ler için kısa bekleme yeter
        else:
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    print(f"  {brand}: toplam {total} ilan, DB'de {count_brand(brand)} kayıt")
    return total


def run(brands_to_scrape: list[tuple]):
    """
    brands_to_scrape: [(brand_name, category_slug, [model_names]), ...]
    """
    init_db()
    grand_total = 0
    for i, (brand, cat, models) in enumerate(brands_to_scrape, 1):
        print(f"\n[{i}/{len(brands_to_scrape)}] {brand} ({cat}) — {len(models)} model")
        grand_total += scrape_brand(brand, cat, models)

    print(f"\n=== Toplam {grand_total} ilan kaydedildi ===")
    return grand_total
