#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Turkiye yakit fiyatlari guncelleyici
--------------------------------------
Guncel benzin/dizel/LPG fiyatlarini cekerek data/prices.json'u gunceller.

Kaynaklar (sirasıyla denenir):
  1. Petrol Ofisi — petrolofisi.com.tr/akaryakit-fiyatlari
     82 sehir, <span class="with-tax"> yapisi, EPDK resmi fiyatlariyla birebir uyumlu
  2. Aytemiz      — aytemiz.com.tr/yakit-fiyatlari (yedek)
     70 sehir, <td> tablosu, kendi marjlariyla biraz yukari kayik
  LPG : Benzin * 0.445 orani (EPDK belirleme yapisi nedeniyle tarihsel olarak stabil)

Calistir:
    python update_prices.py

Her Persembe EPDK guncelledikten sonra calistirin.
"""

import sys, re, json, datetime, statistics
sys.stdout.reconfigure(encoding='utf-8')
from urllib.request import urlopen, Request
from urllib.error   import URLError

OUTPUT_PATH = 'data/prices.json'

# LPG / Benzin orani — EPDK belirleme yapisi nedeniyle tarihsel olarak stabil
LPG_BENZIN_ORANI = 0.445

# Son bilinen degerler — otomatik cekim basarisizsa bunlar kullanilir
FALLBACK = {
    'benzin': 65.59,
    'dizel':  69.24,
    'lpg':    29.20,
}


def _get_html(url, timeout=12):
    req = Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/124.0 Safari/537.36',
        'Accept-Language': 'tr-TR,tr;q=0.9',
    })
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', errors='ignore')


def fetch_petrolofisi():
    """
    petrolofisi.com.tr/akaryakit-fiyatlari — sunucu tarafi HTML, 82 sehir.
    <span class="with-tax">63.88</span> yapisi.
    EPDK resmi fiyatlariyla birebir uyumlu.
    """
    url = 'https://www.petrolofisi.com.tr/akaryakit-fiyatlari'
    try:
        html = _get_html(url)

        # Her satir: <td>SEHIR ADI</td> ... with-tax benzin ... with-tax dizel
        rows = re.findall(
            r'<td>([A-ZA-Za-z\xc0-\xff()İĞÜŞÖÇığüşöç\s]+)</td>'
            r'.*?<span class="with-tax">([\d.]+)</span>'
            r'.*?<span class="with-tax">([\d.]+)</span>',
            html, re.S
        )

        # Satir yoksa veya az ise genel with-tax listesini dene
        if len(rows) < 20:
            # Fallback: tum with-tax degerlerini al, ciftler halinde benzin/dizel
            vals = re.findall(r'<span class="with-tax">([\d.]+)</span>', html)
            floats = []
            for v in vals:
                try:
                    f = float(v)
                    if 30 < f < 200:
                        floats.append(f)
                except ValueError:
                    pass

            if len(floats) < 40:
                print(f'  Petrol Ofisi: yetersiz veri ({len(floats)} deger)')
                return None

            # Degerler ciftler halinde (benzin, dizel) sirali geliyor
            benzinler = floats[0::2]
            dizeller  = floats[1::2]
        else:
            benzinler = []
            dizeller  = []
            for _, b, d in rows:
                try:
                    bv = float(b)
                    dv = float(d)
                    if 30 < bv < 200:
                        benzinler.append(bv)
                    if 30 < dv < 200:
                        dizeller.append(dv)
                except ValueError:
                    pass

        if not benzinler or not dizeller:
            return None

        benzin = round(statistics.median(benzinler), 2)
        dizel  = round(statistics.median(dizeller),  2)
        lpg    = round(benzin * LPG_BENZIN_ORANI,    2)

        print(f'  Petrol Ofisi: {len(benzinler)} sehir islendi')
        return {'benzin': benzin, 'dizel': dizel, 'lpg': lpg}

    except Exception as e:
        print(f'  Petrol Ofisi hatasi: {e}')
        return None


def fetch_aytemiz():
    """
    aytemiz.com.tr/yakit-fiyatlari — yedek kaynak, 70 sehir.
    Benzin ve Motorin icin ulusal medyan.
    """
    url = 'https://www.aytemiz.com.tr/yakit-fiyatlari'
    try:
        html = _get_html(url)

        rows = re.findall(
            r'<td[^>]*>.*?([A-Za-z\xc0-\xff][A-Za-z\xc0-\xff\s]+)'
            r'</a><td>([\d,]+)<td>([\d,]+)',
            html
        )
        if len(rows) < 20:
            print(f'  Aytemiz: cok az sehir ({len(rows)}), sayfa yapisi degismis olabilir')
            return None

        benzinler = []
        dizeller  = []
        for _, b, d in rows:
            bv = float(b.replace(',', '.'))
            dv = float(d.replace(',', '.'))
            if 30 < bv < 200:
                benzinler.append(bv)
            if 30 < dv < 200:
                dizeller.append(dv)

        if not benzinler or not dizeller:
            return None

        benzin = round(statistics.median(benzinler), 2)
        dizel  = round(statistics.median(dizeller),  2)
        lpg    = round(benzin * LPG_BENZIN_ORANI,    2)

        print(f'  Aytemiz: {len(rows)} sehir islendi')
        return {'benzin': benzin, 'dizel': dizel, 'lpg': lpg}

    except Exception as e:
        print(f'  Aytemiz hatasi: {e}')
        return None


def sanity_check(prices):
    b = prices.get('benzin', 0)
    d = prices.get('dizel',  0)
    return 30 < b < 200 and 30 < d < 200


def main():
    print('Yakit fiyatlari guncelleniyor...')
    today = datetime.date.today()

    # 1. Petrol Ofisi (birincil)
    print(f'  [1/2] Petrol Ofisi deneniyor... ({today})')
    prices = fetch_petrolofisi()
    if prices and sanity_check(prices):
        kaynak = 'petrolofisi.com.tr (ulusal medyan)'
    else:
        # 2. Aytemiz (yedek)
        print(f'  [2/2] Aytemiz yedek kaynak deneniyor...')
        prices = fetch_aytemiz()
        if prices and sanity_check(prices):
            kaynak = 'aytemiz.com.tr (ulusal medyan)'
        else:
            print('  Her iki kaynak da basarisiz, son bilinen degerler kullaniliyor.')
            prices = FALLBACK.copy()
            kaynak = 'manuel (fallback)'

    print(f'  Fiyatlar: benzin={prices["benzin"]}, dizel={prices["dizel"]}, lpg={prices["lpg"]}')

    # Mevcut dosyayi oku — EV tarifelerini koru
    try:
        with open(OUTPUT_PATH, encoding='utf-8') as f:
            existing = json.load(f)
    except Exception:
        existing = {}

    output = {
        'benzin':       prices['benzin'],
        'dizel':        prices['dizel'],
        'lpg':          prices['lpg'],
        'elektrik_ev':  existing.get('elektrik_ev', 3.92),
        'elektrik_ac':  existing.get('elektrik_ac', 9.90),
        'elektrik_dc':  existing.get('elektrik_dc', 13.50),
        'guncelleme':   today.isoformat(),
        'kaynak':       kaynak,
    }

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print()
    print('=== prices.json guncellendi ===')
    print(f'  Benzin  : {output["benzin"]:.2f} TL/L')
    print(f'  Dizel   : {output["dizel"]:.2f} TL/L')
    print(f'  LPG     : {output["lpg"]:.2f} TL/L  (benzin * {LPG_BENZIN_ORANI})')
    print(f'  EV (ev) : {output["elektrik_ev"]:.2f} TL/kWh')
    print(f'  EV (AC) : {output["elektrik_ac"]:.2f} TL/kWh')
    print(f'  EV (DC) : {output["elektrik_dc"]:.2f} TL/kWh')
    print(f'  Tarih   : {output["guncelleme"]}')
    print(f'  Kaynak  : {output["kaynak"]}')
    print()
    print('Not: EV tarifelerini guncellemek icin prices.json dosyasini elle duzenleyin.')


if __name__ == '__main__':
    main()
