"""s190 Г3 — отдача маржинальных шортов Bitfinex на росте (проверка механизма 💸; гипотеза — ВЫВОДЫ.md, записана до
расчёта). Ряды s188 (часовые шорты пар Bitfinex в монетах и цена пары, `s188/study/bfx_probe.series`). Событие — шорты
за 4 ч ≤ ×0,8 при росте цены за 4 ч ≥ +5% и шортах 4 ч назад ≥ 0,25 млн $; контроль — тот же рост при шортах
×0,95…×1,05; по одному событию вида на монету за 72 ч. Шорт перпа Binance с закрытия 15-мин свечи после закрытия часа,
7 сут, стоп 50%. Запуск из /home/user/mc_data: [MC_K=… MC_F=…] python3 <repo>/research/s190/g3.py <период>;
сводка: … g3.py report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))
sys.path.insert(0, os.path.join(HERE, "..", "s188", "study"))

DAY, H, OUT = 86400, 3600, "/home/user/mc_data"


def events():
    import json
    import bfx_probe as BP  # noqa: E402
    pairs = [p for p in json.load(open(f"{BP.D}/pairs.json")) if p not in BP.SKIP]
    ev = []
    for p in pairs:
        if not os.path.exists(f"{BP.D}/px_{p.replace(':', '')}.json"):
            continue
        df = BP.series(p)
        if df.short.notna().sum() < 1000:
            continue
        b = BP.base(p)
        sn = df.short * df.px
        r4 = df.px / df.px.shift(4) - 1
        s4 = df.short / df.short.shift(4)
        big = (sn.shift(4) >= 0.25e6).fillna(False)
        for kind, c in (("event", (s4 <= 0.8) & (r4 >= 0.05) & big),
                        ("ctl", (s4 >= 0.95) & (s4 <= 1.05) & (r4 >= 0.05) & big)):
            for t in BP.first_in(list(df.index[c.fillna(False).astype(bool)]), 72 * H):
                ev.append((kind, b, int(t) + H))                    # закрытие часа
    return pd.DataFrame(ev, columns=["kind", "b", "T"])


def run(per):
    import fastbt as FB  # noqa: E402
    import common182 as C  # noqa: E402
    from common import fut_of  # noqa: E402
    K = FB.K
    E = events()
    t0, t1 = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
    E = E[(E["T"] >= t0) & (E["T"] < t1)]
    rows = []
    for b, g in E.groupby("b"):
        s, _ = fut_of(b)
        if s is None or s not in K:
            continue
        t = K[s]["t"].astype(np.int64)
        lo, hi = FB.live(s)
        I = np.searchsorted(t, g["T"].values)                     # свеча, начинающаяся в закрытие часа
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == g["T"].values) & (g["T"].values >= lo + DAY)
        if not ok.any():
            continue
        gg = g[ok].copy(); I = I[ok]
        okt, net, stp, bars, tend = FB.trades(s, I, 0.50, 168, -1)
        gg["net"] = np.where(okt, net, np.nan)
        mv = FB.alt_mv(t[I] + 900, tend)
        gg["hed"] = np.where(okt, net + mv, np.nan)
        gg["pl"] = FB.placebo(s, I, 0.50, 168, -1)
        gg["s"] = s
        rows.append(gg)
    X = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    X["per"] = per
    X.to_pickle(f"{OUT}/s190_g3_{per}.pkl")
    print(per, X.groupby("kind").size().to_dict() if len(X) else 0, flush=True)


def report():
    import common182 as C  # noqa: E402
    print("Г3 — отдача шортов Bitfinex на росте (шорт 7 сут, стоп 50%) против роста без отдачи\n")
    for per in C.PER:
        X = pd.read_pickle(f"{OUT}/s190_g3_{per}.pkl")
        if not len(X):
            print(per, "событий нет"); continue
        X = X[X.net.notna()].rename(columns={"T": "t"})
        X["why"] = ""
        e, c = X[X.kind == "event"], X[X.kind == "ctl"]
        d, se = C.diff(X.net, X.kind == "event", X.t) if len(e) >= 5 and len(c) >= 5 else (np.nan, np.nan)
        print(f"{per}: событие n={len(e)} {e.net.mean():+.2%} | контроль n={len(c)} {c.net.mean():+.2%} | "
              f"Δ {d:+.2%} (t {d / se:+.1f}) | с хеджем: {e.hed.mean():+.2%} / {c.hed.mean():+.2%}")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
