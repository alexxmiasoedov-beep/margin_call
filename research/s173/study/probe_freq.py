"""s173 — частота кандидатов (без расчёта доходов!). Только счёт событий в месяц на 15-мин свечах k2y (10.2024–10.2026),
часовых свечах спота s23/spot1h и ставках маржи s11/rates. Запуск: python3 -I probe_freq.py <папка данных>.

H1 «возврат в зону застрявших покупателей» (объём по цене): цена вернулась снизу в полосу [цена, +3%], где лежит
   плотная доля агрессивных покупок 3–30 сут назад; за 24 ч рост ≥ 5%; 72 ч до этого цена была ниже полосы.
H2 «выбор площадки» (Johnson–So): оборот перпа к споту за 24 ч в ≥ 3 раза выше своей медианы 30 сут при ходе ≤ ±3%.
H3 «эндогенный / экзогенный памп»: +15% за ≤ 2 ч из покоя; число сделок за 24 ч до пампа к своей норме.
"""
import os
import pickle
import sys
from collections import Counter

import numpy as np
import pandas as pd

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
NONCRYPTO = {"XAU", "XAG", "XPT", "XPD", "COPPER", "NATGAS", "CL", "BZ", "AAPL", "MSFT", "AMD", "QQQ", "SPY", "TSM",
             "BABA", "AMC", "CVX", "DIA", "AVGO", "QCOM", "ANET", "PAXG", "USDC", "FDUSD", "TUSD", "USDP", "BTCDOM",
             "DEFI", "BLUEBIRD", "HUT", "APLD", "GPRO", "SKHY", "OPENAI", "ANTHROPIC", "SPCX", "POPMART", "UNITREE",
             "MARSCOIN", "USAR", "SLX", "ESP"}


def hourly(k):
    t = np.asarray(k["t"], np.int64)
    h = t // 3600
    st = np.r_[0, np.flatnonzero(np.diff(h)) + 1]
    H = h[st]
    hi = np.maximum.reduceat(np.asarray(k["h"], np.float64), st)
    lo = np.minimum.reduceat(np.asarray(k["l"], np.float64), st)
    en = np.r_[st[1:], len(t)] - 1
    c = np.asarray(k["c"], np.float64)[en]
    qv = np.add.reduceat(np.asarray(k["qv"], np.float64), st)
    tb = np.add.reduceat(np.asarray(k["tb"], np.float64), st)
    n = np.add.reduceat(np.asarray(k["n"], np.float64), st)
    # сплошная сетка часов
    T = np.arange(H[0], H[-1] + 1)
    idx = H - H[0]
    out = {}
    for nm, a, fill in (("hi", hi, np.nan), ("lo", lo, np.nan), ("c", c, np.nan), ("qv", qv, 0.0), ("tb", tb, 0.0),
                        ("n", n, 0.0)):
        z = np.full(len(T), fill); z[idx] = a; out[nm] = z
    out["c"] = pd.Series(out["c"]).ffill().values
    out["hi"] = np.where(np.isnan(out["hi"]), out["c"], out["hi"])
    out["lo"] = np.where(np.isnan(out["lo"]), out["c"], out["lo"])
    return T, out


def roll_sum(a, w):
    cs = np.cumsum(np.r_[0.0, a])
    r = np.full(len(a), np.nan)
    r[w - 1:] = cs[w:] - cs[:-w]
    return r


def month(Th):
    return pd.to_datetime(Th * 3600, unit="s").to_period("M")


def h1_events(T, x, dens_min=0.15, rise=0.05):
    c, qv, tb = x["c"], x["qv"], x["tb"]
    ok = qv > 0
    if ok.sum() < 24 * 40:
        return []
    p = (x["hi"] + x["lo"] + c) / 3
    lb = np.log(1.01)
    with np.errstate(divide="ignore", invalid="ignore"):
        b = np.floor(np.log(np.where(p > 0, p, np.nan)) / lb)
        bc = np.floor(np.log(np.where(c > 0, c, np.nan)) / lb)
    good = np.isfinite(b) & np.isfinite(bc)
    if good.sum() < 24 * 40:
        return []
    bmin = int(np.nanmin(b[good])) - 3; bmax = int(np.nanmax(b[good])) + 4
    nb = bmax - bmin + 1
    if nb > 2000:
        return []
    M = np.zeros((len(T), nb), np.float32)
    ii = np.flatnonzero(good)
    M[ii, (b[ii] - bmin).astype(int)] = tb[ii]
    C = np.cumsum(M, axis=0)
    del M
    v24 = roll_sum(qv, 24)
    first = np.flatnonzero(ok)[0]
    cs = pd.Series(c)
    rise_ok = (cs / cs.shift(24) - 1).values >= rise
    prevmax = cs.shift(1).rolling(72, min_periods=72).max().values
    lower = 1.01 ** bc
    cand = np.flatnonzero(good & (v24 >= 5e6) & rise_ok & (prevmax < lower))
    cand = cand[cand >= max(720, first + 720)]
    ev, last = [], -10 ** 9
    for i in cand:
        k0 = int(bc[i] - bmin)
        W = C[i - 72] - C[i - 720]
        tot = W.sum()
        if tot <= 0:
            continue
        dz = W[k0:k0 + 3].sum() / tot
        if dz < dens_min:
            continue
        if i - last < 72:
            continue
        last = i
        pump = c[i] / np.nanmin(x["lo"][i - 1:i + 1]) - 1 >= 0.15
        ev.append((T[i], dz, pump))
    return ev


def main():
    with open(os.path.join(D, "s2/k2y.pkl"), "rb") as f:
        K = pickle.load(f)
    kind = pd.read_pickle(os.path.join(D, "s12/perp_kind.pkl"))
    bad = set(kind.get("tradfi", set())) | NONCRYPTO
    syms = [s for s in K if s not in bad and not s.endswith("USDC")]
    print("криптоперпов", len(syms))
    sp = pd.read_pickle(os.path.join(D, "s23/spot1h.pkl"))
    rates_dir = os.path.join(D, "s11/rates")
    have_rate = {f[:-4] for f in os.listdir(rates_dir) if f.endswith(".csv")}

    H1 = {0.10: [], 0.15: [], 0.20: []}
    H2, H2m, H2nm, H3 = [], [], [], []
    univ = Counter()
    for s in syms:
        T, x = hourly(K[s])
        if len(T) < 24 * 40:
            continue
        v24 = roll_sum(x["qv"], 24)
        # размер вселенной: часы 00 UTC с оборотом ≥ 5 млн $
        d0 = (T % 24 == 0) & (v24 >= 5e6)
        for m, cnt in Counter(month(T[d0])).items():
            univ[m] += cnt
        # H1 при трёх порогах плотности
        evs = h1_events(T, x, dens_min=0.10)
        for th in H1:
            H1[th] += [(s, t, dz, pmp) for t, dz, pmp in evs if dz >= th]
        # H3 пампы
        c, lo, hi, n = x["c"], x["lo"], x["hi"], x["n"]
        n24 = roll_sum(n, 24)
        lo2 = np.minimum(lo, np.r_[lo[0], lo[:-1]])
        hs, ls = pd.Series(hi), pd.Series(lo)
        rng = (hs.shift(2).rolling(24, min_periods=24).max() / ls.shift(2).rolling(24, min_periods=24).min() - 1).values
        cand = np.flatnonzero((c / lo2 - 1 >= 0.15) & (v24 >= 2e6) & (rng <= 0.10))
        last = -10 ** 9
        for i in cand:
            if i < 24 * 9 or i - last < 24:
                continue
            pre = n24[i - 2]
            norm = np.nanmedian(n24[i - 24 * 8:i - 24 * 2:24])
            if not np.isfinite(norm) or norm <= 0:
                continue
            last = i
            H3.append((s, T[i], pre / norm))
        # H2 выбор площадки — нужен спот
        if s in sp:
            a = np.asarray(sp[s])
            Hs = (a[:, 0].astype(np.int64)) // 3600
            sq = np.zeros(len(T)); m_ = (Hs >= T[0]) & (Hs <= T[-1])
            sq[(Hs[m_] - T[0]).astype(int)] = a[m_, 1]
            s24 = roll_sum(sq, 24)
            with np.errstate(divide="ignore", invalid="ignore"):
                lps = np.log(v24 / s24)
            rate = None
            if s in have_rate:
                r = pd.read_csv(os.path.join(rates_dir, s + ".csv"), header=None, names=["t", "r"])
                rr = pd.Series(r.r.values, index=(r.t.values // 3600)).sort_index()
                rr = rr[~rr.index.duplicated()].reindex(T).ffill()
                p10 = rr.rolling(720, min_periods=240).quantile(0.10)
                rate = (rr / p10).values
            last = -10 ** 9
            for i in np.flatnonzero(T % 24 == 0):
                if i < 24 * 31 or v24[i] < 5e6 or s24[i] <= 0 or not np.isfinite(lps[i]):
                    continue
                hist = lps[i - 24 * 30:i - 24:24]
                hist = hist[np.isfinite(hist)]
                if len(hist) < 20:
                    continue
                z = lps[i] - np.median(hist)
                if z < np.log(3) or abs(c[i] / c[i - 24] - 1) > 0.03 or i - last < 24 * 7:
                    continue
                last = i
                H2.append((s, T[i], z))
                if rate is not None and np.isfinite(rate[i]) and rate[i] >= 2:
                    H2m.append((s, T[i]))
                if rate is None:
                    H2nm.append((s, T[i]))
    del K

    def per_month(rows, col=1):
        if not rows:
            return "нет событий"
        m = pd.Series([month(np.int64(r[col])) for r in rows]).value_counts().sort_index()
        full = m.iloc[1:-1] if len(m) > 3 else m
        return f"{len(rows)} всего, в месяц: медиана {full.median():.1f}, среднее {full.mean():.1f}, мин {full.min()}, макс {full.max()}"

    um = pd.Series(univ).sort_index()
    print("вселенная (перпы с оборотом ≥ 5 млн $ в 00 UTC): в среднем в день",
          f"{(um / um.index.days_in_month).iloc[1:-1].mean():.0f}")
    for th, rows in H1.items():
        pumps = sum(1 for r in rows if r[3])
        print(f"H1 плотность полосы ≥ {th:.0%}: {per_month(rows)}; из них пампов +15% за 2 ч: {pumps}")
    print("H2 перп/спот ×3, ход ≤ ±3%:", per_month(H2))
    print("   из них монета с маржой и загрузкой пула ≥ ×2:", per_month(H2m, 1))
    print("   из них монета без займа на марже:", per_month(H2nm, 1))
    r3 = np.array([r[2] for r in H3])
    print("H3 пампы +15% из покоя:", per_month(H3))
    if len(r3):
        print(f"   доля с ростом сделок ≥ ×1,5 до пампа: {np.mean(r3 >= 1.5):.0%}; ≤ ×1,0 (внезапные): {np.mean(r3 <= 1.0):.0%}")
    pd.to_pickle({"H1": H1, "H2": H2, "H2m": H2m, "H2nm": H2nm, "H3": H3},
                 os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe_freq.pkl"))


if __name__ == "__main__":
    main()
