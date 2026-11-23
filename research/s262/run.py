"""s262 — Г3 s259 «памп при переполненных шортах» у перпов без спота Binance → лонг 48 ч, стоп 25%.
Правило и порог — ВЫВОДЫ.md (записаны до расчёта доходов). Событие — памп перпа (+15% за ≤ 2 ч из покоя, s260/nospot.pumps,
как 🛒 и 🇰🇷), перп без спота Binance на момент закрытия свечи пампа, старше суток; последнее начисление фандинга не позже
закрытия свечи пампа — ставка в пересчёте на 8 ч r8 < 0 (шорты платят; r · 8 / интервал, интервал — разница с прошлым
начислением). Порог s259 (r8 ≤ −0,1%) заменён до расчёта доходов по одной частоте (13,8 в месяц < 20) — строка отчёта;
у монеты не чаще одной сделки за 48 ч. Лонг на закрытии свечи пампа.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s262/run.py [count|main]"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s260"))
import nospot as N  # noqa: E402

HOLD, SL, TH0 = 48, 0.25, -0.001                        # TH0 — исходный порог s259 (для отчёта)


def r8_before(fr, te):
    """Последнее начисление не позже te: ставка на 8 ч и интервал (ч). (nan, nan) — нет двух начислений."""
    k = np.searchsorted(fr[:, 0], te, "right") - 1
    if k < 1:
        return np.nan, np.nan
    iv = (fr[k, 0] - fr[k - 1, 0]) / 3600.0
    iv = min((1, 2, 4, 8), key=lambda x: abs(x - iv))                 # 1, 2, 4 или 8 ч (пропуски в данных — ближайший)
    return fr[k, 1] * 8 / iv, iv


def events(all_pumps=False):
    U = N.universe()
    rows = []
    for s, u in U.items():
        a = N.K[s]
        t = a["t"].astype(np.int64); te = t + N.BAR
        J = N.pumps(a)
        if not len(J):
            continue
        J = J[N.nospot_mask(u, te[J]) & (te[J] >= N.T0) & (te[J] <= N.TB)]
        if not len(J):
            continue
        fr = N.FB.funding(s)
        for j in J:
            r8, iv = r8_before(fr, te[j]) if len(fr) else (np.nan, np.nan)
            rows.append((s, int(j), int(te[j]), r8, iv))
    E = pd.DataFrame(rows, columns=["s", "i", "te", "r8", "iv"])
    E["per"] = N.period(E.te, HOLD)
    E = E[E.per.notna()]
    if not all_pumps:
        E = E[E.r8 < 0]
    out = []
    for s, g in E.sort_values(["s", "te"]).groupby("s"):
        out.append(g.iloc[N.cooldown(g.te.values, HOLD * 3600)])
    return pd.concat(out, ignore_index=True)


def count():
    E = events()
    mA = (N.TA - N.T0) / N.MONTH
    A, B = E[E.per == "А"], E[E.per == "Б"]
    mid = float(np.median(A.te))
    print(f"А — {len(A)} ({len(A) / mA:.1f} в месяц), монет {A.s.nunique()}; середина {pd.Timestamp(mid, unit='s').date()}, "
          f"2-я половина {(A.te >= mid).sum() / ((N.TA - mid) / N.MONTH):.1f} в месяц; Б — {len(B)}, монет {B.s.nunique()}")
    print("по кварталам:", pd.to_datetime(E.te, unit="s").dt.to_period("Q").value_counts().sort_index().to_dict())
    print("интервал начисления:", E.iv.value_counts().to_dict(), "; r8 квантили:", E.r8.quantile([.1, .5, .9]).round(4).to_dict())


def main():
    mA = (N.TA - N.T0) / N.MONTH
    mB = (N.TB - HOLD * 3600 - N.TA) / N.MONTH
    E = events()
    X = N.trades(E, +1, HOLD, SL)
    X.to_pickle("s262_trades.pkl")
    A, B = X[X.per == "А"], X[X.per == "Б"]
    mid = float(np.median(A.te))
    print("### Г3: памп при r8 < 0 → лонг 48 ч")
    print(f"А (10.2024–18.10.2026): {N.line(A, mA, mid)}")
    print(f"  1-я половина: {N.line(A[A.te < mid], mA / 2)}")
    print(f"  2-я половина: {N.line(A[A.te >= mid], mA / 2)}")
    print(f"Б (19.10–19.11.2026): {N.line(B, mB)}")
    print(f"  А, r8 ≤ −0,1% (порог s259): {N.line(A[A.r8 <= TH0], mA, mid)}")
    print(f"  Б, r8 ≤ −0,1%: {N.line(B[B.r8 <= TH0], mB)}")
    print(f"  А, r8 ≤ −0,5%: {N.line(A[A.r8 <= -0.005], mA)}")
    print(f"  А, −0,1% < r8 < 0: {N.line(A[A.r8 > TH0], mA)}")
    print(f"  А, интервал 1 ч: {N.line(A[A.iv == 1], mA)}")
    print(f"  А, интервал 4 ч: {N.line(A[A.iv == 4], mA)}")
    N.verdict(A, B, "Г3")
    print("\n### для отчёта: все пампы перпов без спота, лонг 48 ч (без условия по фандингу)")
    W = N.trades(events(all_pumps=True), +1, HOLD, SL)
    WA = W[W.per == "А"]
    print(f"  А: {N.line(WA, mA, float(np.median(WA.te)))}")
    print(f"  А, r8 ≥ 0: {N.line(WA[WA.r8 >= 0], mA)}")


if __name__ == "__main__":
    {"count": count, "main": main}[sys.argv[1] if len(sys.argv) > 1 else "count"]()
