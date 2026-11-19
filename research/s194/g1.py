"""s194 Г1 — «продавец запаса на споте» → шорт перпа 24 ч (правило и пороги — ВЫВОДЫ.md, записаны до расчёта).

Прогоны спота — `scan_spot.py` (`/home/user/mc_data/s194/parts/<период>_*.pkl.gz`). Событие — первый за сутки прогон
продаж спота (D1/D1n), который в момент своего обнаружения проходит: часть ≥ 100 $, доля в продажах тейкеров спота
от начала ≥ 10%, исполнено (часть × число частей) ≥ 10 тыс. $, не двусторонний в реальном времени. Шорт перпа на закрытии
первой 15-мин свечи после обнаружения, 24 ч, стоп 15%; новая сделка по монете — только после закрытия прошлой.
Контроль той же формы — прогоны покупок → лонг перпа. Плацебо — та же монета 7 сут назад (и 45/90/135 сут); хедж — индекс
альтов s103. Разрезы — отчёт.

Запуск из /home/user/mc_data: [MC_K=… MC_F=…] python3 <repo>/research/s194/g1.py <период>  → s194/g1_<период>.pkl;
сводка: … g1.py report [период …]"""
import gzip
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))
sys.path.insert(0, HERE)

DAY, OUT = 86400, "/home/user/mc_data"
D194 = f"{OUT}/s194"


def spot_runs(per):
    days, R = [], []
    for f in sorted(os.listdir(f"{D194}/parts")):
        if not (f.startswith(per) and f.endswith(".pkl.gz")):
            continue
        with gzip.open(f"{D194}/parts/{f}", "rb") as g:
            for r in pickle.load(g):
                s, d = r["key"]
                days.append(dict(s=s, d=d, ok=int(r.get("ok", 0)), code=str(r.get("code", "")),
                                 vol=r.get("vol", np.nan), volb=r.get("volb", np.nan), n_ord=r.get("n_ord", 0)))
                if r.get("ok"):
                    for x in r["runs"]:
                        x = dict(x)
                        x["s"], x["d"] = s, d
                        R.append(x)
    Dy = pd.DataFrame(days).drop_duplicates(["s", "d"])
    R = pd.DataFrame(R).reset_index(drop=True)
    R["v_det"] = R.vchild * R.n_det
    return Dy, R


def events(per):
    from screen import two_rt  # noqa: E402
    Dy, R = spot_runs(per)
    entry = ((np.floor(R.det_t.values / 9e5) + 1) * 9e5).astype(np.int64)
    R["two_rt"] = two_rt(R, entry)
    R["entry"] = entry
    q = (R.vchild >= 100) & (R.sh_det >= 0.10) & (R.v_det >= 1e4) & ~R.two_rt
    E = R[q].sort_values("det_t").groupby(["s", "d", "side"]).head(1).copy()
    return Dy, R, E


def near(per):
    """Монеты и сутки с разлоком 🔑⁺ (s142) или заводом 🐋 (s167lv, правило бота B, |r24| ≤ 5%)."""
    out = {}
    try:
        u = pd.read_pickle(f"{OUT}/s142_{per}.pkl")[["s", "T"]]
        for s, T in zip(u.s, u["T"]):
            out.setdefault(s, []).append(int(T))
    except FileNotFoundError:
        pass
    try:
        w = pd.read_pickle(f"{OUT}/s167lv_{per}.pkl")[["s", "t", "B", "r24"]]
        w = w[w.B.astype(bool) & (w.r24.abs() <= 0.05)]
        for s, t in zip(w.s, w.t):
            out.setdefault(s, []).append(int(t))
    except FileNotFoundError:
        pass
    return {k: np.sort(np.array(v)) for k, v in out.items()}


def run(per):
    import fastbt as FB  # noqa: E402
    K = FB.K
    Dy, R, E = events(per)
    NB = near(per)
    rows = []
    for (s, side), g in E.groupby(["s", "side"]):
        if s not in K:
            continue
        t = K[s]["t"].astype(np.int64)
        T = (g.entry.values // 1000 - 900).astype(np.int64)
        I = np.searchsorted(t, T)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == T) & (I >= 96)
        if not ok.any():
            continue
        gg = g[ok].sort_values("entry").copy()
        I = np.searchsorted(t, (gg.entry.values // 1000 - 900).astype(np.int64))
        tside = -1 if side < 0 else 1                    # продажи спота → шорт перпа, покупки → лонг (контроль)
        okt, net, stp, bars, tend = FB.trades(s, I, 0.15, 24, tside)
        # новая сделка по монете — только после закрытия прошлой
        keep = np.zeros(len(I), bool)
        last_end = -1
        for j in range(len(I)):
            if not okt[j]:
                continue
            if t[I[j]] + 900 >= last_end:
                keep[j] = True
                last_end = tend[j]
        if not keep.any():
            continue
        gg, I = gg[keep].copy(), I[keep]
        net, stp, tend = net[keep], stp[keep], tend[keep]
        mv = FB.alt_mv(t[I] + 900, tend)
        gg["net"], gg["stop"], gg["hed"] = net, stp, net - tside * mv
        gg["pl"] = FB.placebo(s, I, 0.15, 24, tside, days=(7,))
        gg["plL"] = FB.placebo(s, I, 0.15, 24, tside)
        ok0, net0, *_ = FB.trades(s, I, 0, 24, tside)
        gg["nos"] = np.where(ok0, net0, np.nan)
        ok4, net4, *_ = FB.trades(s, I, 0.15, 4, tside)
        gg["net4"] = np.where(ok4, net4, np.nan)
        gg["t"] = t[I] + 900
        gg["tside"] = tside
        base = s.lstrip("0123456789") if s[:1].isdigit() else s
        ev = NB.get(s, NB.get(base, np.zeros(0)))
        gg["near"] = [bool(len(ev)) and bool(np.any(np.abs(ev - x) <= 3 * DAY)) for x in gg.t.values]
        rows.append(gg)
    X = pd.concat(rows, ignore_index=True)
    X["per"] = per
    X.attrs["days_ok"] = int(Dy.ok.sum())
    X.attrs["days_all"] = len(Dy)
    X.to_pickle(f"{D194}/g1_{per}.pkl")
    print(per, "монето-суток со спотом", int(Dy.ok.sum()), "из", len(Dy), "| событий (до учёта 24 ч):",
          E.groupby("side").size().to_dict(), "| сделок:", X.groupby("tside").size().to_dict(), flush=True)


def report(pers):
    import common182 as C  # noqa: E402
    print("Г1 — «продавец запаса на споте»: прогон продаж спота (часть ≥ 100 $, доля в продажах спота ≥ 10%, ≥ 10 тыс. $)"
          " → шорт перпа 24 ч, стоп 15%; контроль той же формы — покупки → лонг\n")
    parts_h, ok_all = [], True
    for per in pers:
        X = pd.read_pickle(f"{D194}/g1_{per}.pkl")
        X["why"] = np.where(X.stop, "стоп", "время")
        print(f"== {per} (монето-суток со спотом {X.attrs['days_ok']}) ==")
        for ts_, name in ((-1, "продажи спота → шорт перпа"), (1, "покупки спота → лонг перпа (контроль)")):
            x = X[X.tside == ts_]
            print(f"  {name}: {C.line(x, per)}")
            print(f"     плацебо 45/90/135 сут: сверх {(x.net - x.plL).mean():+.2%}; без стопа {x.nos.mean():+.2%}; "
                  f"4 ч {x.net4.mean():+.2%}; медиана {x.net.median():+.2%}; в плюсе {np.mean(x.net > 0):.0%}")
        x = X[X.tside == -1]
        m, t, n = C.ct(x.net, x.t)
        mh, th, _ = C.ct(x.hed, x.t)
        cut = C.ts(C.PER[per][2])
        h1, h2 = x[x.t < cut].net.mean(), x[x.t >= cut].net.mean()
        mp = (x.net - x.pl).mean()
        mo = n / C.months(per)
        parts_h.append((mh, abs(mh / th) if th else np.nan, n))
        if per == "2024–2026":
            crit = [("≥ 20 в месяц", mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                    ("сверх плацебо > 0", mp > 0), ("с хеджем > 0", mh > 0)]
            print("  порог 2024–2026 гг.: " + "; ".join(f"{a} — {'да' if b else 'НЕТ'}" for a, b in crit))
            ok_all &= all(b for _, b in crit)
        else:
            ok_all &= (m > 0) and (mh > 0)
            print(f"  период: доход > 0 — {'да' if m > 0 else 'НЕТ'}; с хеджем > 0 — {'да' if mh > 0 else 'НЕТ'}")
        print("  разрезы (продажи → шорт):")
        sl = [("доля 10–25%", (x.sh_det < 0.25)), ("доля 25–50%", (x.sh_det >= 0.25) & (x.sh_det < 0.5)),
              ("доля ≥ 50%", x.sh_det >= 0.5), ("шаг ≥ 10 с", x.med_det >= 10), ("шаг < 10 с", x.med_det < 10),
              ("таймер 60 с", (x.med >= 59.5) & (x.med <= 60.5) & (x.smode >= 0.5)),
              ("исполнено 10–50 тыс. $", x.v_det < 5e4), ("исполнено ≥ 50 тыс. $", x.v_det >= 5e4),
              ("🔑⁺ или 🐋 в ±3 сут", x.near), ("прочие", ~x.near)]
        for nm, msk in sl:
            y = x[msk]
            mm, tt, nn = C.ct(y.net, y.t)
            print(f"    {nm}: n={nn} {mm:+.2%} (t {tt:+.1f}), с хеджем {y.hed.mean():+.2%}, сверх плацебо "
                  f"{(y.net - y.pl).mean():+.2%}")
        print()
    if len(pers) == 3:
        m, t = C.combine(parts_h)
        ok_all &= t >= 3
        print(f"шесть лет вместе с хеджем: {m:+.2%} (t {t:+.1f})")
    print("ИТОГ:", "порог пройден" if ok_all else "порог не пройден")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report(sys.argv[2:] or ["2024–2026"])
    else:
        run(sys.argv[1])
