"""s183 — дневная панель «перп × сутки UTC» за период: цена и оборот перпа (из 15-мин свечей), агрессивные покупки,
число сделок, внутридневная дисперсия (из 15-мин доходностей), фандинг за сутки, спот Binance (оборот, покупки, цена),
оборот Upbit + Bithumb к воне в $ и цена в Корее. Доходы не считаются — это сырьё для признаков на срезах.

Запуск: python3 -I panel.py <период>   (периоды: 2020–2022, 2022–2024, 2024–2026)
Итог: /home/user/mc_data/s183/daily_<период>.pkl"""
import gc
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common183 as C  # noqa: E402


def main(per):
    t_start = time.time()
    cfg = C.PER[per]
    bad = C.bad_set()
    K = pickle.load(open(cfg["k"], "rb"))
    print(per, "свечей перпов в файле", len(K), f"({time.time() - t_start:.0f} с)", flush=True)
    # часовые закрытия BTC — для курса воны в старых периодах (KRW-BTC Upbit / BTCUSDT)
    b = K["BTC"]
    tb_ = np.asarray(b["t"], np.int64); cb_ = np.asarray(b["c"], float)
    m = (tb_ + 900) % 3600 == 0
    btc_h = pd.Series(cb_[m], index=tb_[m] + 900 - 3600)            # начало часа → закрытие часа
    rows = []
    for s in sorted(K):
        if s in bad or C.base(s) in bad:
            continue
        x = C.daily_from_15m(K[s])
        if x is None:
            continue
        x["s"] = s
        rows.append(x)
    del K
    gc.collect()
    P = pd.concat(rows).reset_index()
    print(per, "перпов", P.s.nunique(), "строк", len(P), f"({time.time() - t_start:.0f} с)", flush=True)

    # фандинг
    F = pickle.load(open(cfg["f"], "rb"))
    fr = []
    for s, a in F.items():
        if s in P.s.values and len(a):
            z = C.fund_daily(a); z["s"] = s
            fr.append(z.reset_index())
    FD = pd.concat(fr)
    P = P.merge(FD, on=["s", "d"], how="left")
    print(per, "фандинг: перпов", FD.s.nunique(), flush=True)

    # спот Binance
    S = C.spot_hourly(per)
    sr = []
    for s, a in S.items():
        key = s
        if key not in set(P.s):
            continue
        z = C.spot_daily(a); z["s"] = key
        sr.append(z.reset_index())
    if sr:
        SD = pd.concat(sr)
        P = P.merge(SD, on=["s", "d"], how="left")
        print(per, "спот: перпов с парой", SD.s.nunique(), flush=True)
    del S
    gc.collect()

    # Корея: оборот Upbit + Bithumb к воне в $ и цена в $ (Upbit, иначе Bithumb)
    KC, rates = C.kr_hourly(per)
    if cfg["kmap"] is None:
        def rate(ex, H):
            r = rates.get(ex)
            if r is None:
                return np.full(len(H), np.nan)
            return r.reindex(np.union1d(r.index, H)).ffill().bfill().reindex(H).values
        coin2perp = {}
        perps = set(P.s)
        for ex in KC:
            for bse in KC[ex]:
                if bse == "USDT":
                    continue
                for p in ("", "1000", "1000000", "1M"):
                    if p + bse in perps:
                        coin2perp[bse] = p + bse
                        break
    else:
        kb = KC["upbit"].get("BTC")
        kr_rate = pd.Series(np.asarray(kb["c"], float), index=np.asarray(kb["t"], np.int64)) / btc_h
        kr_rate = kr_rate.dropna()

        def rate(ex, H):
            return kr_rate.reindex(np.union1d(kr_rate.index, H)).ffill().bfill().reindex(H).values
        mp = pickle.load(open(cfg["kmap"], "rb"))
        coin2perp = {bse: (p[:-4] if p.endswith("USDT") else p) for bse, p in mp.items()}
    kr = []
    for bse, p in coin2perp.items():
        parts = []
        for ex in ("upbit", "bithumb"):
            x = KC.get(ex, {}).get(bse)
            if x is None or not len(x["t"]):
                continue
            H = np.asarray(x["t"], np.int64)
            r = rate(ex, H)
            v = np.asarray(x["v"], float) / r
            cu = np.asarray(x["c"], float) / r
            parts.append(pd.DataFrame({"d": (H // C.DAY) * C.DAY, "v_" + ex: v, "c_" + ex: cu}))
        if not parts:
            continue
        z = pd.concat(parts)
        g = z.groupby("d")
        out = pd.DataFrame({"krv": g[[c for c in z.columns if c.startswith("v_")]].sum().sum(axis=1)})
        for ex in ("upbit", "bithumb"):
            if "v_" + ex in z.columns:
                out["krv_" + ex] = g["v_" + ex].sum()
                out["krc_" + ex] = g["c_" + ex].last()
        out["s"] = p
        kr.append(out.reset_index())
    if kr:
        KD = pd.concat(kr)
        KD = KD.groupby(["s", "d"], as_index=False).sum(min_count=1)
        P = P.merge(KD, on=["s", "d"], how="left")
        print(per, "Корея: перпов с рынком к воне", KD.s.nunique(), flush=True)
    P = P.sort_values(["s", "d"]).reset_index(drop=True)
    os.makedirs(C.OUT, exist_ok=True)
    P.to_pickle(f"{C.OUT}/daily_{per}.pkl")
    print(per, "готово:", len(P), "строк,", P.s.nunique(), "перпов,", f"{time.time() - t_start:.0f} с", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
