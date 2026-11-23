"""s259, вопрос 3 — что происходит вокруг пампов и обвалов (s259/events.pkl) у перпов без спота против монет со спотом:
средние пути OI (в монетах), позиций (лонг/шорт всех счетов, топ-счетов, топ-позиций, taker), фандинга, премии к индексу,
индекса (c / (1 + p)), доли агрессивных покупок и оборота, от −24 до +48 ч. Описание, не правило: путь цены перпа после
события показывается только по группам целиком (то, что пампы перпов без спота продолжаются, известно из s256); для
разрезов внутри групп — только механика (OI, позиции, фандинг, премия), без цены после события.
Метрики: перпы без спота — s259/met (сутки −1…+2 вокруг события, fetch_metrics.py) или s228/met; со спотом — s228/met.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s259/study/paths.py"""
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common259 import BAR, DAY, MID, OUT, load_k, TMP  # noqa: E402

KS = np.arange(-24, 49)                     # часы относительно закрытия свечи события
SHOW = (-24, -6, -2, -1, 0, 1, 2, 4, 8, 24, 48)
SNAP0 = int(pd.Timestamp("2026-07-01", tz="UTC").timestamp())
EDGES = [2.3e6, 5.3e6, 12.4e6, 41.5e6]


def metrics(s):
    for path in (f"s259/met/{s}.npz", f"s228/met/{s}.npz"):
        if os.path.exists(path):
            z = np.load(path)
            if "t1" in z.files:
                return z["t1"], z["v1"].astype(float)
            return z["t"], z["v"].astype(float)
    return None


def build():
    K = load_k()
    PR = pickle.load(open("s12/prem.pkl", "rb"))
    E = pd.read_pickle(f"{OUT}/events.pkl")
    U = json.load(open(f"{OUT}/universe.json"))
    F = pd.read_pickle(f"{TMP}/funding_panel.pkl")[["s", "t", "r8"]]
    FF = {s: (g.t.values, g.r8.values) for s, g in F.groupby("s")}
    out = []
    for s, ev in E.groupby("p"):
        a = K[s]; t = a["t"]
        pt, pv = PR.get(s, (np.zeros(0, np.int64), np.zeros(0)))
        M = metrics(s)
        ft, fr = FF.get(s, (np.zeros(0), np.zeros(0)))
        qv = a["qv"].astype(float); tb = a["tb"].astype(float); c = a["c"].astype(float)
        cq = np.r_[0.0, np.cumsum(qv)]; ctb = np.r_[0.0, np.cumsum(tb)]
        for r in ev.itertuples():
            j = r.j
            T = int(t[j]) + BAR
            jj = j + 4 * KS
            ok = (jj >= 3) & (jj < len(t))
            jj = np.clip(jj, 3, len(t) - 1)
            ok &= t[jj] == t[j] + KS * 3600                                     # сетка без разрывов
            cc = np.where(ok, c[jj], np.nan)
            if len(pt):
                ip = np.searchsorted(pt, t[jj]); ip2 = np.minimum(ip, len(pt) - 1)
                pp = np.where(ok & (ip < len(pt)) & (pt[ip2] == t[jj]), pv[ip2], np.nan)
            else:
                pp = np.full(len(KS), np.nan)
            hq = cq[jj + 1] - cq[jj - 3]; htb = ctb[jj + 1] - ctb[jj - 3]
            j7 = max(j - 672, 0)
            base_q = np.median(qv[j7:j - 8]) * 4 if j - 8 > j7 + 96 else np.nan        # обычный часовой оборот
            row = dict(s=s, t=T, kind=r.kind, ns=r.nospot, c=cc, p=pp, q=np.where(ok, hq / base_q, np.nan),
                       tb=np.where(ok & (hq > 0), htb / np.maximum(hq, 1e-9), np.nan),
                       to7=np.median(qv[j7:j]) * 96 if j > j7 else np.nan)
            Tg = T + KS * 3600
            if len(ft):
                k = np.searchsorted(ft, Tg, side="right") - 1
                row["f"] = np.where(k >= 0, fr[np.maximum(k, 0)], np.nan)
            else:
                row["f"] = np.full(len(KS), np.nan)
            if M is not None:
                mt, mv = M
                k = np.searchsorted(mt, Tg, side="right") - 1
                fresh = (k >= 0) & (Tg - mt[np.maximum(k, 0)] <= 3600)
                for ci, nm in enumerate(("oi", "oiv", "topa", "topp", "acc", "tk")):
                    row[nm] = np.where(fresh, mv[np.maximum(k, 0), ci], np.nan)
            else:
                for nm in ("oi", "oiv", "topa", "topp", "acc", "tk"):
                    row[nm] = np.full(len(KS), np.nan)
            u = U[s]
            row.update(self=u.get("self", np.nan), alpha=u.get("alpha", np.nan), snap=u["snap"])
            out.append(row)
    return out


def ix(k):
    return int(np.flatnonzero(KS == k)[0])


def table(R, name, price=True):
    if not R:
        print(f"\n== {name}: нет событий"); return
    i0, ib = ix(0), ix(-2)
    A = lambda key: np.array([r[key] for r in R], float)  # noqa: E731
    c, p = A("c"), A("p")
    lc = np.log(c) - np.log(c[:, [ib]])
    li = (np.log(c) - np.log1p(p)) - (np.log(c[:, [ib]]) - np.log1p(p[:, [ib]]))
    oi = A("oi") / A("oi")[:, [ib]] - 1
    acc = A("acc") - A("acc")[:, [ib]]; topa = A("topa") - A("topa")[:, [ib]]; topp = A("topp") - A("topp")[:, [ib]]
    n_oi = np.isfinite(oi[:, i0]).sum()
    print(f"\n== {name}: событий {len(R)}, с метриками {n_oi}")
    hdr = "  час:              " + " ".join(f"{k:>7}" for k in SHOW)
    print(hdr)

    def line(nm, X, fmt="{:+7.1%}", stat=np.nanmedian):
        vals = [stat(X[:, ix(k)]) if np.isfinite(X[:, ix(k)]).sum() >= 5 else np.nan for k in SHOW]
        print(f"  {nm:<17}" + " ".join(fmt.format(v) if np.isfinite(v) else "      —" for v in vals))
    if price:
        line("перп (медиана)", np.expm1(lc))
        line("индекс (медиана)", np.expm1(li))
    line("премия p (сред.)", p, "{:+7.2%}", np.nanmean)
    line("премия p (мед.)", p, "{:+7.2%}")
    line("фандинг 8ч (сред)", A("f"), "{:+7.3%}", np.nanmean)
    line("фандинг 8ч (мед.)", A("f"), "{:+7.3%}")
    line("оборот / обычный", A("q"), "{:7.1f}")
    line("доля покупок", A("tb"), "{:7.1%}")
    line("OI монет (мед.)", oi)
    line("OI монет (сред.)", np.clip(oi, -0.9, 5), "{:+7.1%}", np.nanmean)
    line("Δ L/S счетов", acc, "{:+7.2f}")
    line("Δ L/S топ-счетов", topa, "{:+7.2f}")
    line("Δ L/S топ-поз.", topp, "{:+7.2f}")
    line("taker L/S", A("tk"), "{:7.2f}")
    d_oi = oi[:, i0]; d_acc = acc[:, i0]
    m = np.isfinite(d_oi)
    if m.sum() >= 10:
        print(f"  за памп/обвал (−2 ч → 0): OI вырос ≥ 10% у {(d_oi[m] >= 0.10).mean():.0%}, упал ≤ −5% у {(d_oi[m] <= -0.05).mean():.0%}; "
              f"L/S всех счетов снизился (больше шортистов) у {(d_acc[m] < 0).mean():.0%}; после (0 → +24 ч) OI вырос у "
              f"{(oi[m, ix(24)] > oi[m, i0]).mean():.0%}")


def main():
    path = f"{TMP}/paths.pkl"
    R = build()
    pickle.dump(R, open(path, "wb"))
    cut = lambda R, f: [r for r in R if f(r)]  # noqa: E731
    for kind in ("pump", "dump"):
        nm = "пампы" if kind == "pump" else "обвалы"
        table(cut(R, lambda r: r["kind"] == kind and r["ns"]), f"{nm}, без спота")
        table(cut(R, lambda r: r["kind"] == kind and not r["ns"]), f"{nm}, со спотом")
        table(cut(R, lambda r: r["kind"] == kind and not r["ns"] and np.isfinite(r["oi"][ix(0)])), f"{nm}, со спотом, с метриками")
        for b in (3, 4):
            table(cut(R, lambda r, b=b: r["kind"] == kind and r["ns"] and np.searchsorted(EDGES, r["to7"]) == b), f"{nm}, без спота, оборот {b + 1}")
            table(cut(R, lambda r, b=b: r["kind"] == kind and not r["ns"] and np.searchsorted(EDGES, r["to7"]) == b), f"{nm}, со спотом, оборот {b + 1}")
        table(cut(R, lambda r: r["kind"] == kind and r["ns"] and r["t"] < MID), f"{nm}, без спота, 1-я половина")
        table(cut(R, lambda r: r["kind"] == kind and r["ns"] and r["t"] >= MID), f"{nm}, без спота, 2-я половина")
        late = lambda r: r["kind"] == kind and r["ns"] and r["snap"] and r["t"] >= SNAP0  # noqa: E731
        table(cut(R, lambda r: late(r) and r["self"] > 0), f"{nm}, без спота 07–10.2026, сам перп в индексе", price=False)
        table(cut(R, lambda r: late(r) and r["self"] == 0), f"{nm}, без спота 07–10.2026, перпа в индексе нет", price=False)
    splits(R)


def splits(R):
    """Разрезы пампов перпов без спота по состоянию до и во время пампа — только механика (без цены после события) и частота
    во 2-й половине (01.10.2025–19.10.2026, 12,6 мес.)."""
    mo2 = 12.6
    i0, ib = ix(0), ix(-2)
    P = [r for r in R if r["kind"] == "pump" and r["ns"]]
    f_pre = np.array([r["f"][ib] for r in P]); p0 = np.array([r["p"][i0] for r in P])
    oi = np.array([r["oi"][i0] / r["oi"][ib] - 1 if r["oi"][ib] > 0 else np.nan for r in P])
    late2 = np.array([r["t"] >= MID for r in P])
    groups = {
        "фандинг до пампа выше базы (≥ +0,02%/8 ч, лонги платят)": f_pre >= 0.0002,
        "фандинг до пампа на базе (0…+0,02%)": (f_pre >= 0) & (f_pre < 0.0002),
        "фандинг до пампа отрицательный (< 0)": f_pre < 0,
        "фандинг до пампа ≤ −0,1%/8 ч": f_pre <= -0.001,
        "премия на свече пампа ≥ +0,5%": p0 >= 0.005,
        "премия на свече пампа ≤ −0,5%": p0 <= -0.005,
        "OI за памп +10% и больше (набор)": oi >= 0.10,
        "OI за памп −5% и меньше (закрытие позиций)": oi <= -0.05,
    }
    for nm, m in groups.items():
        sub = [r for r, k in zip(P, m) if k]
        print(f"\n— {nm}: {len(sub)} пампов, во 2-й половине {np.sum(m & late2) / mo2:.1f} в месяц")
        table(sub, f"пампы без спота: {nm}", price=False)


if __name__ == "__main__":
    main()
