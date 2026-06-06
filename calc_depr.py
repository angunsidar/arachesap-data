#!/usr/bin/env python3
"""
Araç reel değer kaybı hesaplayıcı
─────────────────────────────────
Yöntem: listings.json'daki farklı model yıllarının GÜNCEL (2026 TL) satış
        fiyatlarını karşılaştırarak reel (enflasyondan arındırılmış) yıllık
        değer kaybı oranlarını çıkarır.

        Örnek: 2022 Passat bugün 1.916 TL → 2020 Passat bugün 1.775 TL
               İkisi de aynı para biriminde olduğundan fark = reel kayıp.

Çıktı:  data/depr.json
        { "Volkswagen|Passat": { "rates": [0.09, 0.07, ...], "quality": "high", "n": 8 }, ... }

Çalıştır:
    cd C:\\Users\\Sidar\\Desktop\\arac-hesaplama
    python calc_depr.py
"""

import json, math

LISTINGS_PATH = 'data/listings.json'
OUTPUT_PATH   = 'data/depr.json'
MIN_COUNT     = 3      # güvenilir kabul için minimum ilan sayısı
MIN_YEARS     = 3      # en az 3 farklı model yılı olsun
CURRENT_YEAR  = 2026
MAX_AGE       = 14     # 14 yaş üstü araçları dışarıda bırak (pazar çok ince)

# Yakıt tipine göre genel fallback oranları (hesaplama yapılamazsa kullanılır)
FALLBACK = {
    'benzin':   [0.17, 0.11, 0.09, 0.08, 0.07],
    'dizel':    [0.19, 0.12, 0.10, 0.09, 0.07],
    'hybrid':   [0.14, 0.10, 0.08, 0.07, 0.06],
    'elektrik': [0.23, 0.14, 0.11, 0.09, 0.08],
    'lpg':      [0.19, 0.12, 0.10, 0.08, 0.07],
}


def fit_depr(year_prices: list[tuple]) -> tuple[list | None, str]:
    """
    year_prices: [(model_yili, median_fiyat, ilan_sayisi), ...]

    Log-lineer regresyon: log(fiyat) = a + b × yaş
    b negatif olursa değer kaybı var: yıllık_oran = 1 - e^b

    Birinci yıl kaybı genel olarak daha yüksek (yeni → ikinci el geçişi),
    sonraki yıllar daha düz bir eğri izler.
    """
    valid = [
        (CURRENT_YEAR - yr, price)
        for yr, price, cnt in year_prices
        if cnt >= MIN_COUNT and 0 < CURRENT_YEAR - yr <= MAX_AGE and price > 0
    ]

    if len(valid) < MIN_YEARS:
        return None, 'insufficient'

    valid.sort()          # yaşa göre sırala
    ages   = [x[0] for x in valid]
    prices = [x[1] for x in valid]

    # log-lineer fit
    n      = len(ages)
    sx     = sum(ages)
    sy     = sum(math.log(p) for p in prices)
    sxy    = sum(a * math.log(p) for a, p in zip(ages, prices))
    sxx    = sum(a * a for a in ages)
    denom  = n * sxx - sx ** 2

    if abs(denom) < 1e-9:
        return None, 'insufficient'

    b = (n * sxy - sx * sy) / denom
    annual_raw = 1.0 - math.exp(b)

    # Kalite ve geçerlilik kontrolü
    if annual_raw < 0.01:
        # Fiyat yaşla artıyor (Türkiye piyasası anomalisi) → temkinli tahmini kullan
        quality = 'low'
        annual  = 0.05
    elif annual_raw > 0.40:
        quality = 'low'
        annual  = 0.40
    else:
        quality = 'high' if n >= 6 else 'medium'
        annual  = annual_raw

    # Yıla göre şekillendirme: 1. yıl daha yüksek, sonraki yıllar düşer
    # (ikinci ele geçiş şokunu yansıtır)
    shape = [1.40, 1.05, 0.90, 0.78, 0.68]
    rates = [round(min(0.40, max(0.02, annual * s)), 4) for s in shape]

    return rates, quality


def main():
    with open(LISTINGS_PATH, encoding='utf-8') as f:
        listings = json.load(f)

    result = {}
    stats  = {'high': 0, 'medium': 0, 'low': 0, 'insufficient': 0, 'no_fiyat': 0}

    for key, entry in listings.items():
        fiyat = entry.get('fiyat')
        if not fiyat:
            stats['no_fiyat'] += 1
            continue

        year_prices = []
        for yr_str, data in fiyat.items():
            try:
                yr     = int(yr_str)
                median = data.get('median', 0)
                count  = data.get('count', 0)
                if median > 0:
                    year_prices.append((yr, median, count))
            except Exception:
                continue

        rates, quality = fit_depr(year_prices)
        stats[quality] += 1

        if rates:
            n_valid = sum(1 for _, _, c in year_prices if c >= MIN_COUNT)
            result[key] = {'rates': rates, 'quality': quality, 'n': n_valid}

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False)

    total = sum(stats.values())
    print(f'\n✅ Tamamlandı — {total} model işlendi')
    print(f'   Yüksek kalite : {stats["high"]}')
    print(f'   Orta kalite   : {stats["medium"]}')
    print(f'   Düşük kalite  : {stats["low"]}')
    print(f'   Yetersiz veri : {stats["insufficient"]}')
    print(f'   Fiyat yok     : {stats["no_fiyat"]}')
    print(f'\n📄 Çıktı: {OUTPUT_PATH}')

    # Örnek çıktı: Passat
    if 'Volkswagen|Passat' in result:
        p = result['Volkswagen|Passat']
        print(f'\nÖrnek — VW Passat: rates={p["rates"]}  quality={p["quality"]}  n={p["n"]}')


if __name__ == '__main__':
    main()
