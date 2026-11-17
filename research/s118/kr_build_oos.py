"""s118 — корейские свечи 2022–2024 гг. для s15/kr_panel.py: из кэша s88/oos/kc/<биржа>/KRW-*.pkl (кэш s88/oos_fetch.py)
собираются s15/kr_candles_upbit.pkl и s15/kr_candles_bithumb.pkl в рабочей папке ~/mc_oos. Курса KRW-USDT в кэше нет:
«USDT» строится как KRW-BTC Upbit ÷ BTCUSDT фьючерса Binance (s117/k_oos.pkl) по часам — для обеих бирж.
Запуск из ~/mc_oos: MC_K=… python3 <repo>/research/s118/kr_build_oos.py (2020–2022: из ~/mc_2020 с MC_KC=…/s88/oos2020/kc)"""
import glob
import os
import pickle

import numpy as np

SRC = os.environ.get("MC_KC", "/home/user/mc_data/s88/oos/kc")       # s130: …/s88/oos2020/kc
K = pickle.load(open(os.environ["MC_K"], "rb"))


def main():
    b = K["BTC"]; t = b["t"]; hc = {int(x) + 900: float(c) for x, c in zip(t, b["c"]) if (int(x) + 900) % 3600 == 0}
    up = pickle.load(open(f"{SRC}/upbit/KRW-BTC.pkl", "rb"))
    hh = up["t"].astype(np.int64)
    rate = np.array([float(c) / hc.get(int(h) + 3600, np.nan) for h, c in zip(hh, up["c"])])   # закрытие часа h → BTC на конец часа
    ok = np.isfinite(rate)
    usdt = {"t": hh[ok], "c": rate[ok].astype(np.float32), "v": np.zeros(ok.sum(), np.float32)}
    for ex in ("upbit", "bithumb"):
        C = {}
        for f in sorted(glob.glob(f"{SRC}/{ex}/KRW-*.pkl")):
            x = pickle.load(open(f, "rb"))
            if x is not None and len(x["t"]):
                C[os.path.basename(f)[4:-4]] = x
        C["USDT"] = usdt
        os.makedirs("s15", exist_ok=True)
        pickle.dump(C, open(f"s15/kr_candles_{ex}.pkl", "wb"))
        print(ex, "рынков со свечами:", len(C) - 1, "| курс USDT часов:", len(usdt["t"]), "медиана", float(np.median(usdt["c"])))


if __name__ == "__main__":
    main()
