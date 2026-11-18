"""s154 — отбор признаков на первой половине (входы до 01.12.2025) и проверка на второй (протокол — ВЫВОДЫ.md).
Непрерывные признаки — по медиане журнала на первой половине, бинарные — по флагу; на журнал не больше двух сочетаний
с t ≥ 2,5 на первой половине. Запуск из /home/user/mc_data после feat.py."""
import numpy as np
import pandas as pd

CUT = int(pd.Timestamp("2025-12-01", tz="UTC").timestamp())
BIN = {"F4", "F5", "F7"}
FEAT = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8"]
NAME = {"F1": "верхняя тень", "F2": "дельта свечи", "F3": "дельта 4 свечей", "F4": "расхождение", "F5": "поглощение",
        "F6": "отрыв от VWAP", "F7": "снятие ликвидности", "F8": "до разрыва FVG"}


def diff(a, b):
    if len(a) < 10 or len(b) < 10:
        return np.nan, np.nan
    da = a.groupby(pd.to_datetime(a.te, unit="s").dt.date).net.mean()
    db = b.groupby(pd.to_datetime(b.te, unit="s").dt.date).net.mean()
    d = a.net.mean() - b.net.mean(); se = np.sqrt(da.var() / len(da) + db.var() / len(db))
    return d, d / se if se > 0 else np.nan


def split(x, f, side, thr):
    keep = (x[f] >= 0.5) if f in BIN else ((x[f] >= thr) if side == "выше" else (x[f] < thr))
    if f in BIN and side == "нет":
        keep = ~keep
    return x[keep], x[~keep]


def main():
    F = pd.read_pickle("s154_feat.pkl")
    pd.set_option("display.width", 250)
    for j, X in F.groupby("j"):
        A, B = X[X.te < CUT], X[X.te >= CUT]
        res = []
        for f in FEAT:
            thr = A[f].median()
            for side in (("есть", "нет") if f in BIN else ("выше", "ниже")):
                k1, d1 = split(A, f, side, thr)
                d, t = diff(k1, d1)
                res.append((f, side, thr, len(k1), k1.net.mean(), d, t))
        R = pd.DataFrame(res, columns=["f", "side", "thr", "n1", "keep1", "d1", "t1"]).sort_values("t1", ascending=False)
        print(f"\n{j}: первая половина {len(A)} сделок, {A.net.mean():+.2%}; вторая {len(B)}, {B.net.mean():+.2%}")
        top = R[R.t1 >= 2.5].head(2)
        for r in R.head(4).itertuples():
            mark = "★" if r.Index in top.index else " "
            print(f"  {mark} {NAME[r.f]:18s} {r.side:4s} (порог {r.thr:+.3f}): 1-я пол. оставлено {r.n1}, {r.keep1:+.2%}, "
                  f"лучше отброшенных на {r.d1:+.2%} (t {r.t1:+.1f})")
        for r in top.itertuples():
            k2, d2 = split(B, r.f, r.side, r.thr)
            d, t = diff(k2, d2)
            ok = d > 0 and t >= 2 and k2.net.mean() > 0
            print(f"    ПРОВЕРКА {NAME[r.f]} {r.side}: 2-я пол. оставлено {len(k2)}, {k2.net.mean():+.2%}, отброшено {d2.net.mean():+.2%}, "
                  f"разница {d:+.2%} (t {t:+.1f}) → {'ПРОШЛО' if ok else 'нет'}")


if __name__ == "__main__":
    main()
