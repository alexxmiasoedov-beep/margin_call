"""s177 — выгрузка истории кредитных протоколов DefiLlama (бесплатный api.llama.fi/protocol/<slug>).

Только загрузка. Доходы и цены не считаются. Кэш — <папка данных>/s177/proto/<slug>.json.gz.
Из ответа берутся chainTvls: «<Сеть>» (лежит в пуле = предложение − займ) и «<Сеть>-borrowed» (выдано в займ),
по дням, в единицах токена (tokens) и в $ (tokensInUsd).
Запуск: python3 -I fetch_lend.py [папка данных]
"""
import gzip
import json
import os
import sys
import time
import urllib.request

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
OUT = os.path.join(D, "s177", "proto")
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "research-script/1.0", "Accept-Encoding": "gzip"}

# Кредитные протоколы, где можно занять альткоин (пулы общего типа), включая закрытые и умершие.
# Морфо-оптимизаторы не берём: они кладут в Aave/Compound и дали бы двойной счёт.
SLUGS = [
    "aave-v1", "aave-v2", "aave-v3", "compound-v1", "compound-v2", "cream-lending", "iron-bank",
    "venus-core-pool", "venus-isolated-pools", "radiant-v1", "radiant-v2", "geist-finance", "granary-finance",
    "hundred-finance", "euler-v1", "euler-v2", "strike", "dforce-lending", "inverse-finance-frontier", "save",
    "larix", "port-finance", "apricot-finance", "jet-v1", "marginfi-lending", "kamino-lend", "jupiter-lend",
    "benqi-lending", "justlend-v1", "tectonic", "scream", "wepiggy", "liqee", "lendhub", "channels-finance",
    "qubit", "annex", "green-planet", "apeswap-lending", "fortress-loans", "agave", "sonne-finance",
    "lodestar-v1", "silo-v1", "silo-v2", "seamless-v1", "zerolend-lending", "lendle-pooled-markets",
    "mendi-finance", "moonwell-lending", "moonwell-apollo", "navi-lending", "suilend", "scallop-lend",
    "echelon-market", "aries-markets", "joule-finance", "fluid-lending", "sparklend", "kinza-finance",
    "layerbank", "takara-lend", "yeilend", "hyperlend-pooled", "folks-finance-lending", "hatom-lending",
    "liqwid", "mars-lend", "umee", "ooki", "morpho-blue", "rhea-lend", "nostra-money-market", "zklend",
    "vesu", "orbit-protocol", "klap", "tarot", "kava-lend", "moola-market", "lista-lending", "current",
    "curvance", "dolomite", "project-0", "evaa-protocol", "blend-pools-v2", "rnt-lend",
]


def get(url, tries=4):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return r.status, raw
        except urllib.error.HTTPError as e:
            if e.code in (400, 402, 404):
                return e.code, b""
            print("  HTTP", e.code, url, flush=True)
        except Exception as e:  # сеть: пауза и повтор, без циклов вхолостую
            print("  ошибка", type(e).__name__, str(e)[:80], flush=True)
        time.sleep(10 * (a + 1))
    return None, b""


def main():
    for i, s in enumerate(SLUGS):
        fn = os.path.join(OUT, s + ".json.gz")
        if os.path.exists(fn):
            continue
        t0 = time.time()
        code, raw = get("https://api.llama.fi/protocol/" + s)
        if code == 200 and raw:
            with gzip.open(fn, "wb") as f:
                f.write(raw)
            print(f"{i + 1:3d}/{len(SLUGS)} {s:28s} {len(raw) / 1e6:7.1f} МБ {time.time() - t0:5.1f} с", flush=True)
        else:
            print(f"{i + 1:3d}/{len(SLUGS)} {s:28s} нет ({code})", flush=True)
        time.sleep(1.5)


if __name__ == "__main__":
    main()
