"""
listings.db → listings.json (arachesap formatında)
"""
import json
import sqlite3
import statistics
from collections import defaultdict

DB_PATH = "listings.db"
OUTPUT  = "data/listings.json"


def export(output_path: str = OUTPUT):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT brand, model, package_name, year, price_try, fuel_type
        FROM listings
        WHERE price_try IS NOT NULL AND price_try > 100000
        ORDER BY brand, model, year
    """).fetchall()
    conn.close()

    # { "BMW|3 Serisi": { fiyat: {yil: {median,min,max,count}}, paketler: {...} } }
    data = defaultdict(lambda: {"fiyat": defaultdict(list), "paketler": defaultdict(lambda: {"yillar": [], "yakit": None, "count": 0})})

    for r in rows:
        key   = f"{r['brand']}|{r['model']}"
        yr    = str(r["year"]) if r["year"] else None
        price = r["price_try"]

        if yr:
            data[key]["fiyat"][yr].append(price)

        pkg = r["package_name"]
        if pkg:
            p = data[key]["paketler"][pkg]
            if yr and int(yr) not in p["yillar"]:
                p["yillar"].append(int(yr))
            p["count"] += 1
            if not p["yakit"] and r["fuel_type"]:
                p["yakit"] = r["fuel_type"].capitalize()

    # Medyan hesapla
    result = {}
    for key, val in data.items():
        fiyat_out = {}
        for yr, prices in val["fiyat"].items():
            if prices:
                fiyat_out[yr] = {
                    "median": int(statistics.median(prices)),
                    "min":    min(prices),
                    "max":    max(prices),
                    "count":  len(prices),
                }

        paket_out = {}
        for pkg, p in val["paketler"].items():
            paket_out[pkg] = {
                "yillar": sorted(p["yillar"]),
                "yakit":  p["yakit"],
                "count":  p["count"],
            }

        if fiyat_out:
            result[key] = {"fiyat": fiyat_out, "paketler": paket_out}

    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)

    print(f"listings.json: {len(result)} model, {output_path}'e yazıldı")
    return len(result)


if __name__ == "__main__":
    export()
