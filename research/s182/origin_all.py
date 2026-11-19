"""s182 Г2 — происхождение токенов у всех заводов на Binance ≥ 0,5% обращения (s160_events.pkl, первый у монеты за 48 ч
среди заводов на Binance — правило бота 🐋 до фильтра спокойного рынка). Шаг 1 — кэш s160/cache_hop.json, шаги 2–3 —
eth_getLogs через публичный RPC (функции и кэш s181/study/whale_origin.py, классы те же). Итог — s182_origin.pkl
в папке данных: событие (perp, tx, li, t, block) → класс конца цепочки и число шагов.
Запуск: python3 <repo>/research/s182/origin_all.py [count]"""
import json
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s181", "study"))
import common181 as C  # noqa: E402
import treasury_outflows as T  # noqa: E402
import whale_origin as W  # noqa: E402

DAY = 86400
OUT = f"{C.D}/s182_origin.pkl"
NOT_MARKET = ["выпуск (0x0)", "казначейство DefiLlama", "инсайдерская метка", "ММ"]
MARKET = ["биржа", "DEX/роутер"]
LONG = "долгий держатель (нет притока 7 сут)"


def classifier():
    S = json.load(open(f"{C.D}/s160/sets.json"))
    CEX = set(S["cex"])
    TRE = {a for r in json.load(open(f"{C.OUT}/dla_treasury.json")) for a in r["owners"]}
    MM = {a.lower() for a in json.load(open(f"{C.D}/s168/work/mm_core.json"))}
    L = T.labels()

    def cls(a):
        if not a:
            return LONG
        if a in W.MINT:
            return "выпуск (0x0)"
        if a in CEX:
            return "биржа"
        if a in TRE:
            return "казначейство DefiLlama"
        if a in MM:
            return "ММ"
        lab = L.get(a, "")
        if lab and W.DEX.search(lab):
            return "DEX/роутер"
        if lab and W.INS.search(lab):
            return "инсайдерская метка"
        return None
    return cls


def events():
    E = pd.read_pickle(f"{C.D}/s160_events.pkl")
    E = E[(E.exch == "Binance") & (E.frac >= 0.005)].sort_values("t")
    return T.one_per(E, "perp", 2 * DAY).reset_index(drop=True)


def main(count_only=False):
    cls = classifier()
    E = events()
    hc0 = json.load(open(f"{C.D}/s160/cache_hop.json"))
    cache = json.load(open(W.CACHE)) if os.path.exists(W.CACHE) else {}
    st = []
    for r in E.itertuples():
        h = hc0.get(f"{r.tok}:{r.frm}:{int(r.block)}")
        s = dict(perp=r.perp, tx=r.tx, li=r.li, t=r.t, block=int(r.block), tok=r.tok, frm=r.frm, frac=r.frac,
                 src1=(h or [None])[0], end=None, hops=0)
        if s["src1"] is None:
            s["end"] = "не определено"
        else:
            s["hops"] = 1
            s["end"] = cls(s["src1"])
        st.append(s)
    print(f"событий: {len(st)}; классов на шаге 1: {sum(s['end'] is not None for s in st)}", flush=True)
    for hop in (2, 3):
        todo = []
        for s in st:
            if s["end"] is None:
                prev = s["src1"] if hop == 2 else s["src2"]
                pb = s["block"] if hop == 2 else s["b2"]
                s[f"key{hop}"] = f"{s['tok']}:{prev}:{max(pb, 1)}"
                if s[f"key{hop}"] not in cache:
                    todo.append(s[f"key{hop}"])
        todo = sorted(set(todo))
        print(f"шаг {hop}: новых запросов {len(todo)}", flush=True)
        if count_only:
            return
        t0 = time.time()
        for i in range(0, len(todo), 10):
            W.hop_batch(todo[i:i + 10], cache)
            if i % 200 == 0:
                json.dump(cache, open(W.CACHE, "w"))
                print(f"  {i}/{len(todo)} за {time.time() - t0:.0f} с", flush=True)
            time.sleep(0.2)
        json.dump(cache, open(W.CACHE, "w"))
        for s in st:
            if s["end"] is None:
                h = cache.get(s.get(f"key{hop}"))
                if h is None:
                    s["end"] = "не определено"
                    continue
                s[f"src{hop}"], s[f"b{hop}"] = h[0], (h[1] if h[1] else s["block"])
                s["hops"] = hop
                s["end"] = cls(h[0])
        if hop == 2:
            for s in st:
                s.setdefault("b2", s["block"])
    for s in st:
        if s["end"] is None:
            s["end"] = "безымянный адрес после 3 шагов"
    X = pd.DataFrame(st)
    X["grp"] = "прочее"
    X.loc[X.end.isin(NOT_MARKET), "grp"] = "не с рынка"
    X.loc[X.end == LONG, "grp"] = "долгий держатель"
    X.loc[X.end.isin(MARKET), "grp"] = "с рынка"
    X.to_pickle(OUT)
    print(X.grp.value_counts().to_dict())


if __name__ == "__main__":
    main(count_only=len(sys.argv) > 1 and sys.argv[1] == "count")
