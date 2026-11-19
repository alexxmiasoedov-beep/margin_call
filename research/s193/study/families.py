"""s193 — «семьи» алгоритмов: эпизоды с одним шагом (0,1 с) и одной суммой части (ячейки ±10%) на разных монетах —
вероятно, один оператор. Для каждой семьи: монет, суток, доля продаж, совпадение покупок и продаж одной монеты по времени
(рисование объёма), годы. Только описание ленты."""
import numpy as np
import pandas as pd

D = "/home/user/mc_data/s193"


def main():
    E = pd.read_pickle(f"{D}/episodes.pkl")
    E = E[E.mkt == "um"].copy()
    E["cad"] = E.med.round(1)
    E["vb"] = np.round(np.log(E.vchild) / np.log(1.2)).astype(int)
    E["year"] = pd.to_datetime(E.d, unit="s").dt.year
    rows = []
    for (cad, vb), g in E.groupby(["cad", "vb"]):
        if g.s.nunique() < 5:
            continue
        both = 0
        for (s, d), h in g.groupby(["s", "d"]):
            b, sl = h[h.side > 0], h[h.side < 0]
            if len(b) and len(sl):
                ov = any(min(x.t1, y.t1) > max(x.t0, y.t0) for x in b.itertuples() for y in sl.itertuples())
                both += ov
        rows.append(dict(cad=cad, vchild=float(np.exp(vb * np.log(1.2))), n=len(g), coins=g.s.nunique(),
                         days=g.d.nunique(), sell=float(np.mean(g.side < 0)), both_days=both,
                         dur=float(g.dur.median()), share=float(g.sh_side.median()), smode=float(g.smode.median()),
                         years=dict(g.year.value_counts().sort_index()), top=dict(g.s.value_counts().head(5))))
    F = pd.DataFrame(rows).sort_values("coins", ascending=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 80)
    print("== Семьи: один шаг и одна сумма части на ≥ 5 монетах (фьючерсы, все сутки выборки) ==")
    print(F.head(25).to_string(index=False))
    F.to_pickle(f"{D}/families.pkl")


if __name__ == "__main__":
    main()
