"""Заметка 1 к Г8: фактор «умных денег» при β = 0,1 (RankIC −4,3%, t −4,5) как фильтр для шорт-журналов. Правило задано
заранее: шорт лучше у монет с высоким Q. Сделки — s22/h6_trades.pkl: бэктесты s20 (сигнал канала, 🇰🇷, 🏦, 🇰🇷🆕, 📢,
🆕), 💸 и ↩️ с 10.2024. Q монеты считается на момент входа по 960 15-мин свечам прошлых 10 суток (как в h8_smart.py),
его ранг — среди Q всех монет в ближайший понедельник не позже входа (s22/h8_panel.pkl). Сделки делятся на трети по
рангу; разница верхней и нижней трети — среднее и t с кластеризацией по дню, по журналам и половинам. Запуск из папки
с данными."""
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import CUT, DAY, K, ct


def q_at(s, T, b=0.1):
    a = K.get(s)
    if a is None:
        return np.nan
    t = a["t"].astype(np.int64)
    i1 = np.searchsorted(t, T - 900, "right"); i0 = i1 - 960
    if i0 < 1:
        return np.nan
    c = a["c"].astype(float); qv = a["qv"].astype(float)
    p = (a["h"][i0:i1].astype(float) + a["l"][i0:i1].astype(float) + c[i0:i1]) / 3
    r = c[i0:i1] / c[i0 - 1:i1 - 1] - 1; v = qv[i0:i1]
    ok = np.isfinite(r) & (v > 0)
    if ok.sum() < 900:
        return np.nan
    r, v, p = r[ok], v[ok], p[ok]
    o = np.argsort(-(np.abs(r) / v ** b)); cum = np.cumsum(v[o]); m = o[:int(np.searchsorted(cum, 0.2 * cum[-1])) + 1]
    return (v[m].sum() / (v[m] / p[m]).sum()) / (v.sum() / (v / p).sum())


if __name__ == "__main__":
    T = pd.read_pickle("s22/h6_trades.pkl")
    F = pd.read_pickle("s22/h8_panel.pkl")
    weeks = np.sort(F.w.unique()); byw = {w: np.sort(g["q0.1"].values) for w, g in F.groupby("w")}
    T["q"] = [q_at(s, te) for s, te in zip(T.s, T.te)]
    wk = weeks[np.clip(np.searchsorted(weeks, T.te.values, "right") - 1, 0, len(weeks) - 1)]
    T["qr"] = [np.searchsorted(byw[w], q) / len(byw[w]) if np.isfinite(q) else np.nan for w, q in zip(wk, T.q)]
    T = T[np.isfinite(T.qr)].reset_index(drop=True)
    T["tq"] = pd.cut(T.qr, [-0.01, 1 / 3, 2 / 3, 1.01], labels=["низкий Q", "средний", "высокий Q"])
    print(f"сделок с Q: {len(T)}; доля в верхней трети недели {np.mean(T.qr > 2 / 3):.0%}, в нижней {np.mean(T.qr <= 1 / 3):.0%}")
    hi, lo = T.qr > 2 / 3, T.qr <= 1 / 3
    for nm, g in [("все журналы", T)] + list(T.groupby("journal")):
        h, l = g.net[g.qr > 2 / 3], g.net[g.qr <= 1 / 3]
        if len(h) < 10 or len(l) < 10:
            continue
        x = np.r_[h.values, -l.values]; tt = np.r_[g.te[g.qr > 2 / 3].values, g.te[g.qr <= 1 / 3].values]
        d = pd.DataFrame(dict(x=x, T=tt, grp=np.r_[np.ones(len(h)), np.zeros(len(l))]))
        dd = d.groupby([pd.to_datetime(d["T"], unit="s").dt.date, "grp"]).x.mean().unstack()
        print(f"  {nm:12s}: высокий Q {h.mean() * 100:+.2f}% ({len(h)}), средний {g.net[(g.qr > 1 / 3) & (g.qr <= 2 / 3)].mean() * 100:+.2f}%, "
              f"низкий Q {l.mean() * 100:+.2f}% ({len(l)}); разница {(h.mean() - l.mean()) * 100:+.2f} п.п. "
              f"(t {(h.mean() - l.mean()) / np.sqrt(h.var() / len(h) + l.var() / len(l)):+.1f}); половины "
              f"{(g.net[(g.qr > 2 / 3) & (g.te < CUT)].mean() - g.net[(g.qr <= 1 / 3) & (g.te < CUT)].mean()) * 100:+.2f}/"
              f"{(g.net[(g.qr > 2 / 3) & (g.te >= CUT)].mean() - g.net[(g.qr <= 1 / 3) & (g.te >= CUT)].mean()) * 100:+.2f} п.п.")
    T.to_pickle("s22/n1_trades.pkl")
