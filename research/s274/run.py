"""s274 — Г3 (разгрузка после пампа перпа), Г5 (ход первого часа суток UTC) и сделки у уровней вне s272 по записи ВЫВОДЫ.md
(коммит c0bd9d1; события — код изучения s271). Запуск из /home/user/mc_data:
  python3 -I <repo>/research/s274/run.py 2020–2022 | 2022–2024 | 2024–2026     — сделки периода → s274_<период>.pkl
  python3 -I <repo>/research/s274/run.py report                                 — сводка трёх периодов"""
import os
import pickle
import sys

PER = sys.argv[1]
CFG = {"2020–2022": ("s117/k_2020.pkl", "s117/fund_2020.pkl"), "2022–2024": ("s117/k_oos.pkl", "s117/fund_oos.pkl"),
       "2024–2026": ("s224/k_d.pkl", "s224/fund_d.pkl")}
if PER in CFG:
    os.environ["MC_K"], os.environ["MC_F"] = CFG[PER]
HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s187", os.path.join("s271", "study")):
    sys.path.insert(0, os.path.join(HERE, "..", p))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

DAY, WEEK, BAR, H = 86400, 7 * 86400, 900, 3600
FEE, SLIP = 0.001, 0.002
WIN = {"2020–2022": ("2020-10-01", "2022-10-01"), "2022–2024": ("2022-10-01", "2024-10-01"), "2024–2026": ("2024-10-01", "2026-10-19")}
MAIN = ("Г3 разгрузка после пампа перпа → шорт 4 ч", "Г5 ход первого часа ≥ 3% → 23–24 UTC",
        "У3 ретест с удержанием после пробоя вверх 1 ч", "У3 ретест с удержанием после пробоя вниз 1 ч",
        "У3 ретест с удержанием после пробоя вверх 15 мин", "У3 ретест с удержанием после пробоя вниз 15 мин", "У4 пробой максимума узкого дня (NR7) 1 ч", "У4 пробой минимума узкого дня (NR7) 1 ч",
        "У4 пробой максимума (неделя) 1 ч", "У4 пробой минимума (неделя) 1 ч", "У1 пробой вверх 15 мин", "У1 пробой вниз 15 мин",
        "У2 ложный пробой вверх за 1 свечу 15 мин", "У2 ложный пробой вниз за 1 свечу 15 мин",
        "У2 ложный пробой вверх за 2 свечи 15 мин", "У2 ложный пробой вниз за 2 свечи 15 мин")


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


def sim(K, fr, p, I, side, stop, nb):
    """Вход на закрытии 15-мин свечи I, стоп по цене stop (худшая из стопа и открытия ± 0,2%), выход через nb свечей."""
    a = K[p]; c, h, l, o, t = a["c"], a["h"], a["l"], a["o"], a["t"]
    if I < 0 or I + nb >= len(c):
        return None
    p0 = float(c[I])
    if stop is not None and not ((p0 - stop) * side > 0):
        return None
    st = False; px = float(c[I + nb]); xi = I + nb
    if stop is not None:
        adv = (l[I + 1:I + nb + 1].astype(float) <= stop) if side > 0 else (h[I + 1:I + nb + 1].astype(float) >= stop)
        if adv.any():
            k = int(np.argmax(adv)); ok_ = float(o[I + 1 + k])
            px = min(stop, ok_) * (1 - SLIP) if side > 0 else max(stop, ok_) * (1 + SLIP)
            xi, st = I + 1 + k, True
    t0, t1 = int(t[I]) + BAR, int(t[xi]) + BAR
    ft, cs = fr
    f = (cs[np.searchsorted(ft, t1, "right")] - cs[np.searchsorted(ft, t0, "right")]) if len(ft) else 0.0
    return side * (px / p0 - 1) - side * f - FEE, st, t1


def run():
    import fastbt as FB  # noqa: E402
    import common as CM  # noqa: E402
    from common271 import crypto_perps, spot_start, base  # noqa: E402
    import freq_distrib as FD  # noqa: E402
    K = FB.K
    t0, t1 = (ts(x) for x in WIN[PER])
    FR = {}

    def fr(p):
        if p not in FR:
            f = CM.funding(p)
            FR[p] = (f[:, 0].astype(np.int64), np.r_[0.0, np.cumsum(f[:, 1])]) if len(f) else (np.zeros(0, np.int64), np.zeros(1))
        return FR[p]

    rows = []

    def add(setup, p, I, side, stop, nb):
        r = sim(K, fr(p), p, I, side, stop, nb)
        if r is None:
            return
        te = int(K[p]["t"][I]) + BAR
        if not (t0 <= te < t1):
            return
        net, st, tend = r
        p0 = float(K[p]["c"][I]); rel = (p0 - stop) * side / p0 if stop is not None else None
        pls = []
        for w in (7, 14, 21):
            J = I - w * 96
            if J > 96:
                pj = float(K[p]["c"][J])
                rp = sim(K, fr(p), p, J, side, pj * (1 - side * rel) if rel is not None else None, nb)
                if rp:
                    pls.append(rp[0])
        alt = FB.alt_mv(np.array([te]), np.array([tend]))[0]
        rows.append(dict(setup=setup, s=p, te=te, side=side, net=net, stop=st, hed=net - side * alt,
                         pl=np.mean(pls) if pls else np.nan, risk=rel if rel is not None else np.nan))

    P = crypto_perps(K)
    # Г3 — 2022–2024 и 2024–2026 гг.
    if PER in ("2022–2024", "2024–2026"):
        ss = spot_start(P)
        SP = pickle.load(open("s23/spot1h.pkl", "rb")) if PER == "2024–2026" else {}
        for p in P:
            a = K[p]
            J = FD.pumps(a)
            if not len(J):
                continue
            t = a["t"].astype(np.int64); c = a["c"].astype(float); lo = a["l"].astype(float); hi = a["h"].astype(float)
            q = a["qv"].astype(float); tb = a["tb"].astype(float)
            sp = SP.get(p) if p in SP else SP.get(base(p))
            st_ = sp[:, 0].astype(np.int64) if sp is not None and len(sp) else None
            s0 = ss.get(p)
            for j in J:
                te = int(t[j]) + BAR; hend = te // H * H
                if s0 is None or s0 > te:
                    led = True
                elif st_ is not None:
                    k = np.searchsorted(st_, hend - H)
                    if k < len(st_) and st_[k] == hend - H:
                        pv = q[(t >= hend - H) & (t < hend)].sum(); sv = float(sp[k, 1])
                        led = sv + pv > 0 and sv / (sv + pv) < 0.10
                    else:
                        led = False
                else:
                    led = False
                if not led:
                    continue
                b = np.nanmin(c[max(0, j - 8):j]) if j >= 1 else c[j]
                for k in range(j + 1, min(j + 25, len(c))):
                    if q[k] <= 0 or t[k] != t[j] + (k - j) * BAR:
                        break
                    if tb[k] / q[k] <= 0.45 and c[k] < lo[k - 1] and c[k] >= b * 1.08:
                        pmax = float(np.max(hi[max(0, j - 8):k + 1]))
                        add(MAIN[0], p, k, -1, min(pmax * 1.02, c[k] * 1.15), 16)
                        break
    # Г5 — три периода
    LR = pickle.load(open(f"/dev/shm/s271/liq100_{PER}.pkl", "rb"))
    for p in P:
        a = K[p]; t = a["t"].astype(np.int64); c = a["c"].astype(float); q = a["qv"]
        i = np.flatnonzero(t % DAY == 45 * 60)
        i = i[(i >= 4) & (i + 92 < len(t))]
        i = i[(t[i - 4] == t[i] - 4 * BAR) & (t[i + 92] == t[i] + 92 * BAR)]
        i = i[(q[i] > 0) & (q[i - 4] > 0) & (c[i - 4] > 0)]
        r1 = c[i] / c[i - 4] - 1
        for ii, r in zip(i, r1):
            D = int(t[ii]) - 45 * 60
            if abs(r) >= 0.03 and p in LR.get(D, ()):
                add(MAIN[1], p, int(ii) + 88, 1 if r > 0 else -1, None, 4)
    # уровни — таблицы s271
    import freq_levels as FL  # noqa: E402
    path = f"/dev/shm/s271/levels_{PER}.pkl"
    X = pd.read_pickle(path) if os.path.exists(path) else FL.collect(PER)
    HA = {}

    def hatr(p):
        """ATR часовых свечей за 14 прошлых часов (как У5 и s272): в таблице s271 у У4 в столбце atr — размах прошлых
        суток или недели, а в записи s274 стоп — уровень ∓ 0,5·ATR."""
        if p not in HA:
            b = FL.to_hour(K[p]); c = b["c"]; pc = np.r_[c[0], c[:-1]]
            tr = np.maximum(b["h"], pc) - np.minimum(b["l"], pc)
            HA[p] = (b["t"], np.r_[np.nan, FL.roll_mean(tr, 14)[:-1]])
        return HA[p]

    for r in X.itertuples():
        kd = r.kind
        if "ложный" in kd:
            side = -1 if "вверх" in kd else 1
        elif any(w in kd for w in ("вверх", "максимума", "поддержка")):
            side = 1
        else:
            side = -1
        if r.s not in K:
            continue
        t = K[r.s]["t"]
        I = int(np.searchsorted(t, r.t - BAR))
        if I >= len(t) or int(t[I]) != r.t - BAR:
            continue
        nb = 32 if r.tf == "1 ч" else 8
        A = r.atr
        if kd.startswith("У4"):
            add(f"{kd} {r.tf}, стоп 0,5 размаха прошлого периода", r.s, I, side, r.level - side * 0.5 * r.atr, nb)
            th, ah = hatr(r.s)
            k = int(np.searchsorted(th, r.t - H))
            A = float(ah[k]) if k < len(th) and th[k] == r.t - H else np.nan
            if not A > 0:
                continue
        add(f"{kd} {r.tf}", r.s, I, side, r.level - side * 0.5 * A, nb)
    R = pd.DataFrame(rows)
    R.to_pickle(f"s274_{PER}.pkl")
    print(PER, "сделок", len(R), R.groupby("setup").size().to_dict(), flush=True)


def ct(x, t):
    x = np.asarray(x, float); w = (np.asarray(t, np.int64) // WEEK) * WEEK; ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def report():
    R = {p: pd.read_pickle(f"s274_{p}.pkl") for p in WIN if os.path.exists(f"s274_{p}.pkl")}
    setups = sorted(set().union(*[set(X.setup) for X in R.values()]), key=lambda s: (s not in MAIN, MAIN.index(s) if s in MAIN else 0, s))
    for st in setups:
        print(f"\n### {st}{'' if st in MAIN else ' (для отчёта)'}")
        allx, signs = [], []
        for p, X in R.items():
            x = X[X.setup == st]
            if len(x) < 5:
                continue
            a0, a1 = (ts(v) for v in WIN[p]); mo = (a1 - a0) / (30.44 * DAY)
            m, t, n = ct(x.net, x.te); mh, th, _ = ct(x.hed, x.te); md, td, _ = ct(x.net - x.pl, x.te)
            mid = float(np.median(x.te)); h1, h2 = x[x.te < mid].net.mean(), x[x.te >= mid].net.mean()
            print(f"  {p}: n={n} ({n / mo:.0f} в мес.), {m:+.2%} (t {t:+.1f}); половины {h1:+.2%} / {h2:+.2%}; "
                  f"с хеджем {mh:+.2%} (t {th:+.1f}); сверх плацебо {md:+.2%} (t {td:+.1f}); стопов {x.stop.mean():.0%}; "
                  f"риск до стопа (медиана) {x.risk.median():.1%}")
            if p == "2024–2026" and st in MAIN:
                conds = (("≥ 20 в месяц", n / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                         ("сверх плацебо > 0", md > 0), ("с хеджем > 0", mh > 0))
                print("    правило владельца: " + "; ".join(f"{k} — {'да' if c else 'нет'}" for k, c in conds)
                      + f" → {'выполнено' if all(c for _, c in conds) else 'не выполнено'}")
            allx.append(x); signs.append(m > 0)
        if allx:
            A = pd.concat(allx); m, t, n = ct(A.net, A.te); mh, th, _ = ct(A.hed, A.te)
            ok = all(signs) and t >= 3
            print(f"  вместе: {m:+.2%} (t {t:+.1f}, n={n}); с хеджем {mh:+.2%} (t {th:+.1f}); "
                  f"знак плюс во всех периодах — {'да' if all(signs) else 'нет'} → {'ПОРОГ ПРОЙДЕН' if ok else 'не пройден'}")


if __name__ == "__main__":
    report() if PER == "report" else run()
