"""s177 — замена платным мостам DefiLlama: L2BEAT (ethbeat.org) отдаёт по L2 стоимость, защищённую мостами,
по дням: canonical (через родной мост с Ethereum), external (сторонние мосты), native (выпущено в самой L2).
Без ключа. Доходы и цены не считаются; в $ ряды «грязные» (цена ETH и токенов), поэтому событие считается
по canonical в ETH (делим на цену ETH из того же ряда). Частота: недельный отток canonical ≥ 10% (в ETH).
Кэш — <папка данных>/s177/l2beat/. Запуск: python3 -I l2beat_probe.py [папка данных]
"""
import gzip
import json
import os
import sys
import time
import urllib.request

import pandas as pd

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
OUT = os.path.join(D, "s177", "l2beat")
os.makedirs(OUT, exist_ok=True)
SLUGS = ["arbitrum", "base", "optimism", "zksync2", "starknet", "linea", "scroll", "blast", "mantle", "mode",
         "zora", "taiko", "unichain", "ink", "worldchain", "abstract", "soneium", "katana", "metis", "manta"]
PERIODS = [("2020–2022", "2020-10-01", "2022-10-01"), ("2022–2024", "2022-10-01", "2024-10-01"),
           ("2024–2026", "2024-10-01", "2026-11-01")]


def get(slug):
    fn = os.path.join(OUT, slug + ".json.gz")
    if os.path.exists(fn):
        return json.load(gzip.open(fn))
    url = f"https://ethbeat.org/api/scaling/tvs/{slug}?range=max"
    for a in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research-script/1.0"})
            raw = urllib.request.urlopen(req, timeout=60).read()
            with gzip.open(fn, "wb") as f:
                f.write(raw)
            time.sleep(1)
            return json.loads(raw)
        except Exception as e:  # сеть: пауза и повтор
            print("  ", slug, type(e).__name__, str(e)[:60])
            time.sleep(5 * (a + 1))
    return None


def main():
    ev = []
    print("L2 | первый день canonical > 1 млн $ | canonical / всего сейчас")
    for s in SLUGS:
        d = get(s)
        if not d or not d.get("success"):
            print(f"  {s}: нет данных")
            continue
        ch = d["data"]["chart"]
        df = pd.DataFrame(ch["data"], columns=ch["types"])
        df["t"] = pd.to_datetime(df.timestamp, unit="s")
        df = df.set_index("t")
        tot = df.native + df.canonical + df.external
        f1 = df.index[df.canonical > 1e6].min()
        share = df.canonical.iloc[-1] / max(tot.iloc[-1], 1)
        print(f"  {s:11s} {str(f1.date()) if f1 is not pd.NaT else '-':10s} {share:.0%}")
        w = (df.canonical / df.ethPrice).resample("W-SUN").last()
        usd_prev = df.canonical.resample("W-SUN").last().shift(1)
        g = w / w.shift(1) - 1
        for t in g.index[((usd_prev >= 5e7) & (g <= -0.10)).fillna(False).values]:
            ev.append((s, t))
    e = pd.DataFrame(ev, columns=["l2", "t"])
    print("\nНедельный отток canonical (в ETH) ≥ 10% при ≥ 50 млн $, событий L2 в месяц:")
    for pn, a, z in PERIODS:
        m = (e.t >= a) & (e.t < z)
        months = (pd.Timestamp(z) - pd.Timestamp(a)).days / 30.44
        print(f"  {pn}: {m.sum() / months:.2f}  ({', '.join(f'{k} {v}' for k, v in e[m].l2.value_counts().head(5).items())})")


if __name__ == "__main__":
    main()
