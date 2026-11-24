"""s279 — Г1 s278 (скачок в 16 UTC при доле OKX + Bitget + KuCoin + Gate) по записи ВЫВОДЫ.md (коммит a235435).

  cd /home/user/mc_data && python3 -I <repo>/research/s279/run.py events     # события из кэша s278 (/dev/shm/s278)
  cd /home/user/mc_data && python3 -I <repo>/research/s279/run.py trades P1  # 2024–2026, свечи s2/k2y.pkl папки
  cd ~/mc_oos           && python3 -I <repo>/research/s279/run.py trades P0  # 2022–2024
  python3 -I <repo>/research/s279/run.py report
События — /home/user/mc_data/s279_events.pkl, сделки — /home/user/mc_data/s279_trades_<период>.pkl."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D = "/home/user/mc_data"
RULES = {"Г1": dict(hour=16, group="CN4", kr="max10"),       # основная
         "Г1а": dict(hour=16, group="CN3", kr="max10"),      # без Gate
         "Г2": dict(hour=0, group="CN4", kr="none")}         # сравнение «UTC против UTC+8»
THR, JUMP = 0.10, 0.05
EXITS = (("8 ч", 0.10, 8), ("24 ч", 0.10, 24))
PNAME = {"P1": "2024–2026", "P0": "2022–2024"}
BAR, WEEK = 900, 7 * 86400


def events():
    sys.path.insert(0, os.path.join(HERE, "..", "s278", "study"))
    from hours import GROUPS, group_volume  # noqa: E402
    from panel278 import DAY, H, MONTH, PER, panel  # noqa: E402
    rows, months = [], {}
    for per in ("P1", "P0"):
        cfg = PER[per]
        P, C, Q, F, VV, INFO = panel(per)
        VV = {v: x for v, x in VV.items() if INFO[v]["matched"] > 0}
        t0, n = cfg["t0"], C.shape[1]
        T = t0 + np.arange(n) * H                                    # начало часа k
        hod = (T // H) % 24
        Qd = Q.astype(np.float64)
        R = np.full_like(C, np.nan)
        R[:, 1:] = C[:, 1:] / C[:, :-1] - 1
        live = (Q > 0) & np.roll(Q > 0, 1, axis=1) & ((T[None, :] - F[:, None]) >= DAY)
        live[:, 0] = False
        jmp = live & np.isfinite(R) & (R >= JUMP)
        KR, _ = group_volume(VV, GROUPS["KR"])
        SK = KR / np.maximum(KR + Qd, 1.0) if KR is not None else None
        for code, r in RULES.items():
            G, act = group_volume(VV, GROUPS[r["group"]])
            if G is None or act.sum() < 24 * 20:
                print(per, code, "нет данных группы")
                continue
            S = G / np.maximum(G + Qd, 1.0)
            cond = jmp & act[None, :] & np.isfinite(G) & (S >= THR)
            if SK is not None and r["kr"] == "none":
                cond &= ~np.isfinite(KR)
            elif SK is not None and r["kr"] == "max10":
                cond &= ~(np.nan_to_num(SK) >= 0.10)
            months[(per, code)] = act.sum() / (MONTH / H)
            for dh in (-2, -1, 0, 1, 2):
                ii, kk = np.nonzero(cond & (hod[None, :] == (r["hour"] + dh) % 24))
                for i, k in zip(ii.tolist(), kk.tolist()):
                    rows.append(dict(per=per, h=code, dh=dh, s=P[i], t=int(T[k] + H), r=float(R[i, k]), share=float(S[i, k])))
            print(per, code, f"мес. {months[(per, code)]:.1f}", "событий в час R:", int((cond & (hod[None, :] == r["hour"])).sum()))
    E = pd.DataFrame(rows)
    E.attrs["months"] = {f"{p}|{c}": m for (p, c), m in months.items()}
    E.to_pickle(f"{D}/s279_events.pkl")
    pd.Series({f"{p}|{c}": m for (p, c), m in months.items()}).to_pickle(f"{D}/s279_months.pkl")


def trades(per):
    sys.path.insert(0, os.path.join(HERE, "..", "s187"))
    import fastbt as FB  # noqa: E402  (свечи периода — s2/k2y.pkl в текущей папке)
    E = pd.read_pickle(f"{D}/s279_events.pkl")
    E = E[E.per == per]
    rows, miss = [], 0
    for s, g in E.groupby("s"):
        if s not in FB.K:
            miss += len(g)
            continue
        t = FB.K[s]["t"].astype(np.int64)
        I = np.searchsorted(t, g.t.values - BAR)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == g.t.values - BAR)
        miss += int((~ok).sum())
        g, I = g[ok], I[ok]
        if not len(I):
            continue
        te = t[I] + BAR
        for lab, sl, hold in EXITS:
            okt, net, stp, bars, tend = FB.trades(s, I, sl, hold, -1)
            alt = FB.alt_mv(te, np.where(okt, tend, te))
            pl = FB.placebo(s, I, sl, hold, -1, days=(7, 14, 21))
            for j, r in enumerate(g.itertuples()):
                if okt[j]:
                    rows.append(dict(h=r.h, dh=r.dh, ex=lab, s=s, te=int(te[j]), net=float(net[j]), stop=bool(stp[j]),
                                     hed=float(net[j] + alt[j]), pl=float(pl[j])))
    R = pd.DataFrame(rows)
    R.to_pickle(f"{D}/s279_trades_{per}.pkl")
    print(PNAME[per], "сделок", len(R), "без свечей", miss, R[(R.ex == "8 ч") & (R.dh == 0)].groupby("h").size().to_dict())


def ct(x, t):
    x = np.asarray(x, float)
    w = (np.asarray(t, np.int64) // WEEK) * WEEK
    ok = np.isfinite(x)
    x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x), np.nan
    m = x.mean()
    s = pd.Series(x - m).groupby(w).sum()
    se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x), se


def report():
    M = pd.read_pickle(f"{D}/s279_months.pkl")
    passed = {}
    for per in ("P1", "P0"):
        f = f"{D}/s279_trades_{per}.pkl"
        if not os.path.exists(f):
            continue
        X = pd.read_pickle(f)
        for h in RULES:
            if f"{per}|{h}" not in M:
                continue
            mo = M[f"{per}|{h}"]
            for lab, _, _ in EXITS:
                x = X[(X.h == h) & (X.ex == lab) & (X.dh == 0)]
                c = X[(X.h == h) & (X.ex == lab) & (X.dh != 0)]
                if len(x) < 5:
                    print(f"{PNAME[per]} {h} {lab}: n={len(x)} — мало")
                    continue
                m, t, n, se = ct(x.net, x.te)
                mh, th, _, _ = ct(x.hed, x.te)
                md, td, _, _ = ct(x.net - x.pl, x.te)
                mc, tc, nc, sec = ct(c.net, c.te)
                dif = m - mc
                tdif = dif / np.sqrt(se ** 2 + sec ** 2)
                mid = float(np.median(x.te))
                h1, h2 = x[x.te < mid].net.mean(), x[x.te >= mid].net.mean()
                byh = " / ".join(f"{dh:+d}: {c[c.dh == dh].net.mean():+.2%} ({(c.dh == dh).sum()})" for dh in (-2, -1, 1, 2))
                print(f"{PNAME[per]} {h} выход {lab}: n={n} ({n / mo:.1f} в мес., окно {mo:.1f} мес.), {m:+.2%} (t {t:+.1f}); "
                      f"половины {h1:+.2%} / {h2:+.2%}; с хеджем {mh:+.2%} (t {th:+.1f}); сверх плацебо {md:+.2%} (t {td:+.1f}); "
                      f"стопов {x.stop.mean():.0%}\n    соседние часы {mc:+.2%} (n={nc}, t {tc:+.1f}); разница {dif:+.2%} (t {tdif:+.1f}); "
                      f"по часам {byh}")
                if lab == "8 ч" and per == "P1" and h == "Г1":
                    conds = (("≥ 20 в мес.", n / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                             ("сверх плацебо > 0", md > 0), ("лучше соседних часов", dif > 0))
                    passed["P1"] = all(v for _, v in conds)
                    print("    порог на 2024–2026: " + "; ".join(f"{k} — {'да' if v else 'нет'}" for k, v in conds))
                if lab == "8 ч" and per == "P0" and h == "Г1а":
                    passed["P0"] = m > 0
                    print(f"    знак Г1а на 2022–2024: {'плюс' if m > 0 else 'минус'}")
    print("\nИТОГ:", "ПОРОГ ПРОЙДЕН" if passed.get("P1") and passed.get("P0") else "порог не пройден", passed)


if __name__ == "__main__":
    a = sys.argv[1]
    events() if a == "events" else trades(sys.argv[2]) if a == "trades" else report()
