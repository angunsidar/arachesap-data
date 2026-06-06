"""
Minimal SQLite yöneticisi — sadece listings tablosu.
"""
import sqlite3
from datetime import datetime

DB_PATH = "listings.db"


def get_conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = get_conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS listings (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id    TEXT,
            brand        TEXT NOT NULL,
            model        TEXT NOT NULL,
            package_name TEXT,
            year         INTEGER,
            km           INTEGER,
            price_try    INTEGER,
            fuel_type    TEXT,
            transmission TEXT,
            color        TEXT,
            url          TEXT,
            scraped_at   TEXT,
            UNIQUE(source_id)
        );
        CREATE INDEX IF NOT EXISTS idx_brand_model ON listings(brand, model);
        CREATE INDEX IF NOT EXISTS idx_year        ON listings(year);
    """)
    c.commit()
    c.close()


def clear_brand(brand: str):
    """Bir markanın eski ilanlarını sil (yeniden scrape öncesi)."""
    c = get_conn()
    deleted = c.execute("DELETE FROM listings WHERE brand=?", (brand,)).rowcount
    c.commit()
    c.close()
    return deleted


def save_listing(lst: dict) -> bool:
    """İlanı kaydet. Zaten varsa (source_id) güncelle. True = yeni kayıt."""
    c = get_conn()
    try:
        c.execute("""
            INSERT INTO listings
                (source_id, brand, model, package_name, year, km,
                 price_try, fuel_type, transmission, color, url, scraped_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_id) DO UPDATE SET
                price_try  = excluded.price_try,
                scraped_at = excluded.scraped_at
        """, (
            lst.get("source_id"),
            lst.get("brand", ""),
            lst.get("model", ""),
            lst.get("package_name"),
            lst.get("year"),
            lst.get("km"),
            lst.get("price_try"),
            lst.get("fuel_type"),
            lst.get("transmission"),
            lst.get("color"),
            lst.get("url"),
            datetime.now().isoformat(),
        ))
        is_new = c.execute("SELECT changes()").fetchone()[0] > 0
        c.commit()
        return is_new
    except Exception:
        return False
    finally:
        c.close()


def count_brand(brand: str) -> int:
    c = get_conn()
    n = c.execute("SELECT COUNT(*) FROM listings WHERE brand=?", (brand,)).fetchone()[0]
    c.close()
    return n
