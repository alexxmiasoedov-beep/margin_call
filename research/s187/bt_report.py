"""s187 часть 2 — сводка 120 стратегий-индикаторов по трём периодам из s187_bt_<период>.pkl (сводки по суткам).
Порог кандидата — ВЫВОДЫ.md (записан до расчёта). Запуск: python3 <repo>/research/s187/bt_report.py"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))
import common182 as C  # noqa: E402

OUT = C.OUT
PERS = list(C.PER)


def stat(D, s="s", n="n"):
    """Среднее и t с кластерами по суткам из сводки по суткам (столбцы суммы s и числа n)."""
    N = D[n].sum()
    if N < 5:
        return np.nan, np.nan, int(N)
    m = D[s].sum() / N
    u = D[s].values - D[n].values * m
    G = (D[n] > 0).sum()
    se = np.sqrt((u ** 2).sum() * G / max(G - 1, 1)) / N
    return m, (m / se if se > 0 else np.nan), int(N)


def main():
    B = {per: pickle.load(open(f"{OUT}/s187_bt_{per}.pkl", "rb")) for per in PERS}
    keys = sorted(set().union(*[set(b) for b in B.values()]))
    rows = []
    for k in keys:
        r = dict(script=k[0], tf=k[1], side="лонг" if k[2] > 0 else "шорт")
        allD = []
        ok_all = ok_h = True
        for per in PERS:
            D = B[per].get(k)
            if D is None or D.n.sum() < 5:
                ok_all = ok_h = False
                r[f"m_{per}"] = r[f"t_{per}"] = r[f"h_{per}"] = np.nan
                continue
            allD.append(D)
            m, t, n = stat(D); mh, th, _ = stat(D, "sh", "nh")
            r[f"m_{per}"], r[f"t_{per}"], r[f"n_{per}"], r[f"h_{per}"] = m, t, n, mh
            ok_all &= m > 0; ok_h &= mh > 0
            if per == "2024–2026":
                cut = C.ts(C.PER[per][2])
                h1, h2 = D[D.index < cut], D[D.index >= cut]
                r["pm"] = n / C.months(per)
                r["h1"], r["h2"] = stat(h1)[0], stat(h2)[0]
                r["pl24"], r["tpl24"], _ = stat(D, "sdpl", "npl")
                r["t24"] = t
                r["opp24"], _, _ = stat(D, "so", "no")
                r["stop24"] = D.st.sum() / max(D.n.sum(), 1)
        if allD:
            A = pd.concat(allD)
            r["m_all"], r["t_all"], r["n_all"] = stat(A)
            r["pl_all"], r["tpl_all"], _ = stat(A, "sdpl", "npl")
            r["opp_all"], r["topp_all"], _ = stat(A, "so", "no")
        r["c1"] = ok_all; r["c3"] = ok_h
        r["c2"] = r.get("t_all", np.nan) >= 3.5
        r["c4"] = (r.get("pl_all", np.nan) > 0) and (r.get("tpl_all", np.nan) >= 2)
        r["c5"] = (r.get("pm", 0) >= 20) and (r.get("h1", -1) > 0) and (r.get("h2", -1) > 0) and \
                  (r.get("t24", 0) >= 3) and (r.get("pl24", -1) > 0)
        r["pass"] = r["c1"] and r["c2"] and r["c3"] and r["c4"] and r["c5"]
        rows.append(r)
    R = pd.DataFrame(rows).sort_values("t_all", ascending=False)
    R.to_pickle(f"{OUT}/s187_bt_summary.pkl")
    pd.set_option("display.width", 250)

    def fmt(r):
        per = " | ".join(f"{r[f'm_{p}']:+.2%} ({r[f't_{p}']:+.1f})" if np.isfinite(r[f"m_{p}"]) else "—" for p in PERS)
        hed = " / ".join(f"{r[f'h_{p}']:+.2%}" if np.isfinite(r[f"h_{p}"]) else "—" for p in PERS)
        return (f"{r.script:26s} {r.tf} {r.side:5s} | {per} | вместе {r.m_all:+.2%} (t {r.t_all:+.1f}) | хедж {hed} | "
                f"сверх плацебо {r.pl_all:+.2%} (t {r.tpl_all:+.1f}) | 2024–26: {r.get('pm', np.nan):5.0f}/мес, половины "
                f"{r.get('h1', np.nan):+.2%} / {r.get('h2', np.nan):+.2%}, обратный сигнал {r.get('opp24', np.nan):+.2%} | "
                f"порог {''.join('✓' if r[c] else '·' for c in ('c1', 'c2', 'c3', 'c4', 'c5'))}")
    print("s187 — 120 стратегий-индикаторов: доход на сделку (t) по периодам 2020–22 | 2022–24 | 2024–26, выход 24 бара,"
          " стоп 25%; порог: 1 все периоды > 0, 2 вместе t ≥ 3,5, 3 хедж > 0 везде, 4 сверх плацебо t ≥ 2, 5 правило владельца\n")
    print(f"всего стратегий {len(R)}; в плюсе на всех трёх периодах {int(R.c1.sum())}; вместе t ≥ 3,5 — {int(R.c2.sum())}; "
          f"с хеджем в плюсе везде {int(R.c3.sum())}; прошли весь порог — {int(R['pass'].sum())}\n")
    print("Лучшие 25 по t вместе:")
    for _, r in R.head(25).iterrows():
        print("  " + fmt(r))
    print("\nХудшие 10 (обратная сторона — тоже не стратегия без проверки):")
    for _, r in R.tail(10).iterrows():
        print("  " + fmt(r))
    print("\nПо семействам (среднее по стратегиям, вместе):")
    print(R.groupby(["side", "tf"]).agg(m=("m_all", "mean"), t=("t_all", "mean"), pos3=("c1", "sum"), n=("script", "size")))


if __name__ == "__main__":
    main()
