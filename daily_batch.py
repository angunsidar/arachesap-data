"""
Günlük arabam.com batch scraper.
Bugünün grubunu çeker, listings.json + depr.json üretir.

Kullanım:
    python daily_batch.py              # otomatik: bugünün grubu
    python daily_batch.py --group 3    # belirli grup
    python daily_batch.py --list       # tüm grupları göster
"""
import sys
import json
import argparse
import datetime
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "arabam"))

BRANDS_FILE   = os.path.join(os.path.dirname(__file__), "arabam", "brands_models.json")
NUM_GROUPS    = 14


def load_brands_map():
    with open(BRANDS_FILE, encoding="utf-8") as f:
        return json.load(f)


def build_groups(brands_map: dict) -> list[list]:
    keys   = list(brands_map.keys())
    groups = [[] for _ in range(NUM_GROUPS)]
    for i, key in enumerate(keys):
        groups[i % NUM_GROUPS].append(key)
    return groups


def today_group() -> int:
    return datetime.date.today().timetuple().tm_yday % NUM_GROUPS


def show_plan(brands_map, groups):
    print(f"14 günlük rotation planı ({len(brands_map)} marka):\n")
    for i, g in enumerate(groups):
        total_m = sum(len(brands_map[b]["models"]) for b in g)
        print(f"  Gün {i:2d}: {len(g)} marka, {total_m} model → {', '.join(g)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", type=int, default=None)
    parser.add_argument("--list",  action="store_true")
    args = parser.parse_args()

    brands_map = load_brands_map()
    groups     = build_groups(brands_map)

    if args.list:
        show_plan(brands_map, groups)
        return

    group_idx = args.group if args.group is not None else today_group()
    today_brands = groups[group_idx]

    print(f"=== Gün grubu {group_idx} ({datetime.date.today()}) ===")
    print(f"Markalar: {', '.join(today_brands)}\n")

    # Scrape
    from scraper import run as scrape_run
    tasks = [
        (brand, brands_map[brand]["cat"], brands_map[brand]["models"])
        for brand in today_brands
    ]
    scrape_run(tasks)

    # listings.json üret
    print("\n--- listings.json üretiliyor ---")
    from export import export
    export(output_path="data/listings.json")

    # depr.json üret
    print("\n--- depr.json hesaplanıyor ---")
    try:
        import importlib.util, subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(__file__), "calc_depr.py")],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"calc_depr hata: {result.stderr}", file=sys.stderr)
    except Exception as e:
        print(f"calc_depr çalıştırılamadı: {e}", file=sys.stderr)

    print("\n=== Batch tamamlandı ===")


if __name__ == "__main__":
    main()
