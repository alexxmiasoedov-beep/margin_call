"""s280 — продолжение каскада по записи ВЫВОДЫ.md (коммит 45d85de).

Запуск по периодам — в папке периода (свечи и фандинг — s2/k2y.pkl и s2/fund2y.pkl, движок s187/fastbt):
  cd ~/mc_2020  && python3 -I <repo>/research/s280/run.py 2020–2022
  cd ~/mc_oos   && python3 -I <repo>/research/s280/run.py 2022–2024
  cd ~/mc_data  && python3 -I <repo>/research/s280/run.py 2024–2026
Сводка: python3 -I <repo>/research/s280/run.py report. Минутные окна событий — /home/user/mc_data/s280/m1_<период>.pkl,
сделки — /home/user/mc_data/s280/tr_<период>.pkl."""
import io
import os
import pickle
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from freq import events  # noqa: E402

OUT = "/home/user/mc_data/s280"
os.makedirs(OUT, exist_ok=True)
WIN = {"2020–2022": ("2020-10-01", "2022-10-01"), "2022–2024": ("2022-10-01", "2024-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-19")}
NS, SEED = 2500, 280
FEE, SL, SLIP = 0.001, 0.03, 0.002
M, BAR, DAY, WEEK = 60, 900, 86400, 7 * 86400
MONTH = 30.44 * DAY
UA = "research-script/1.0"
BASE = "https://data.binance.vision/data/futures/um/daily/klines"


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


def fetch_day(sym, day):
    """Минутные свечи перпа за сутки UTC: массив [t откр., o, h, l, c] или None (нет файла)."""
    d = pd.Timestamp(day * DAY, unit="s").strftime("%Y-%m-%d")
    url = f"{BASE}/{sym}USDT/1m/{sym}USDT-1m-{d}.zip"
    for k in range(4):
        r = subprocess.run(["curl", "-sS", "-m", "60", "-A", UA, "-w", "%{http_code}", "-o", "-", url], capture_output=True)
        code = r.stdout[-3:].decode(errors="ignore")
        if code == "404":
            return None
        if code == "200":
            try:
                z = zipfile.ZipFile(io.BytesIO(r.stdout[:-3]))
                rows = [ln.split(",") for ln in z.read(z.namelist()[0]).decode().splitlines()]
                a = np.array([[int(p[0]) // 1000, float(p[1]), float(p[2]), float(p[3]), float(p[4])]
                              for p in rows if p and p[0][:1].isdigit()])
                return a if len(a) else None
            except (zipfile.BadZipFile, ValueError, IndexError):
                pass
        import time
        time.sleep(2 + 2 * k)
    return None


def window(sym, T):
    """Минутные свечи с открытием в [T − 5 мин, T + 66 мин)."""
    days = sorted({(T - 5 * M) // DAY, (T + 66 * M) // DAY})
    parts = [x for x in (fetch_day(sym, d) for d in days) if x is not None]
    if not parts:
        return None
    a = np.concatenate(parts)
    a = a[(a[:, 0] >= T - 5 * M) & (a[:, 0] < T + 66 * M)]
    return a[np.argsort(a[:, 0])] if len(a) else None


def m1_windows(per, E):
    f = f"{OUT}/m1_{per}.pkl"
    W = pickle.load(open(f, "rb")) if os.path.exists(f) else {}
    todo = [(r.s, int(r.t)) for r in E.itertuples() if (r.s, int(r.t)) not in W]
    print(per, "минутных окон в кэше", len(W), "докачать", len(todo), flush=True)
    with ThreadPoolExecutor(8) as ex:
        for n, (key, a) in enumerate(zip(todo, ex.map(lambda k: window(*k), todo))):
            W[key] = a
            if n % 500 == 499:
                pickle.dump(W, open(f, "wb"))
                print(" ", n + 1, flush=True)
    pickle.dump(W, open(f, "wb"))
    return W


def trade_m1(a, T, side, delay, hold, fr_t, fr_cs):
    """Сделка по минутным свечам: вход — закрытие свечи с открытием T − 1 мин + delay мин, выход через hold мин."""
    t = a[:, 0].astype(np.int64)
    i0 = np.searchsorted(t, T - M + delay * M)
    i1 = np.searchsorted(t, T - M + (delay + hold) * M)
    if i0 >= len(t) or t[i0] != T - M + delay * M or i1 >= len(t) or t[i1] != T - M + (delay + hold) * M:
        return None
    p0 = a[i0, 4]
    px, stop = a[i1, 4], False
    lvl = p0 * (1 - side * SL)
    for j in range(i0 + 1, i1 + 1):
        if (side < 0 and a[j, 2] >= lvl) or (side > 0 and a[j, 3] <= lvl):
            px = max(lvl, a[j, 1]) * (1 + SLIP) if side < 0 else min(lvl, a[j, 1]) * (1 - SLIP)
            stop = True
            break
    t0, t1 = t[i0] + M, t[min(j, i1)] + M if stop else t[i1] + M
    f = fr_cs[np.searchsorted(fr_t, t1, "right")] - fr_cs[np.searchsorted(fr_t, t0, "right")] if len(fr_t) else 0.0
    return side * (px / p0 - 1) - side * f - FEE, stop


def run(per):
    sys.path.insert(0, os.path.join(HERE, "..", "s187"))
    import fastbt as FB  # noqa: E402
    t0, t1 = ts(WIN[per][0]), ts(WIN[per][1])
    rows = []
    for side, h in ((-1, "Г1"), (1, "Г2")):
        E = events(FB.K, t0, t1, side=side)
        n_all = len(E)
        rng = np.random.default_rng(SEED)
        if len(E) > NS:
            E = E.iloc[np.sort(rng.choice(len(E), NS, replace=False))]
        W = m1_windows(f"{per}_{h}", E)
        for r in E.itertuples():
            a = W.get((r.s, int(r.t)))
            K = FB.K[r.s]
            kt = K["t"].astype(np.int64)
            i = int(np.searchsorted(kt, r.t - BAR))                  # 15-мин свеча, которая кончается в T
            c, qv = K["c"].astype(float), K["qv"].astype(float)
            last15 = c[i] / c[i - 1] - 1 if i >= 1 else np.nan
            liq = qv[max(0, i - 95): i + 1].sum()
            pl = []
            for d in (7, 14, 21):
                j = int(np.searchsorted(kt, r.t - d * DAY - BAR))
                if j + 1 < len(kt) and kt[j] == r.t - d * DAY - BAR and kt[j + 1] == kt[j] + BAR and qv[j + 1] > 0 and qv[j] > 0:
                    pl.append(side * (c[j + 1] / c[j] - 1) - FEE)
            alt = float(FB.alt_mv(np.array([r.t]), np.array([r.t + BAR]))[0])
            fr = FB.funding(r.s)
            fr_t = fr[:, 0].astype(np.int64) if len(fr) else np.zeros(0, np.int64)
            fr_cs = np.r_[0.0, np.cumsum(fr[:, 1])] if len(fr) else np.zeros(1)
            rec = dict(h=h, s=r.s, t=int(r.t), r60=r.r, last15=last15, liq=liq, alt=alt,
                       pl=np.mean(pl) if pl else np.nan, n_all=n_all, m1=a is not None)
            if a is not None:
                for delay in (0, 1):
                    for hold in (5, 15, 30, 60):
                        x = trade_m1(a, r.t, side, delay, hold, fr_t, fr_cs)
                        if x is not None:
                            rec[f"d{delay}_{hold}"] = x[0]
                            rec[f"s{delay}_{hold}"] = x[1]
            rows.append(rec)
    R = pd.DataFrame(rows)
    R.to_pickle(f"{OUT}/tr_{per}.pkl")
    print(per, R.groupby("h").agg(n=("t", "size"), m1=("m1", "mean"), main=("d1_15", "count")).to_dict(), flush=True)


def ct(x, t):
    x = np.asarray(x, float)
    w = (np.asarray(t, np.int64) // WEEK) * WEEK
    ok = np.isfinite(x)
    x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean()
    s = pd.Series(x - m).groupby(w).sum()
    se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def report():
    R = {p: pd.read_pickle(f"{OUT}/tr_{p}.pkl") for p in WIN if os.path.exists(f"{OUT}/tr_{p}.pkl")}
    for h, side in (("Г1", -1), ("Г2", 1)):
        print(f"\n######## {h} ({'шорт после хода ≤ −5%' if side < 0 else 'лонг после хода ≥ +5%'})")
        allx, signs = [], []
        for p, X in R.items():
            x = X[X.h == h]
            mo = (ts(WIN[p][1]) - ts(WIN[p][0])) / MONTH
            n_all = int(x.n_all.iloc[0])
            main = x.dropna(subset=["d1_15"])
            m, t, n = ct(main.d1_15, main.t)
            hed = main.d1_15 + (-side) * main.alt
            mh, th, _ = ct(hed, main.t)
            md, td, _ = ct(main.d1_15 - main.pl, main.t)
            mid = float(np.median(main.t))
            h1, h2 = main[main.t < mid].d1_15.mean(), main[main.t >= mid].d1_15.mean()
            print(f"\n  {p}: событий {n_all} ({n_all / mo:.0f} в мес.), в выборке {len(x)}, с минутками {len(main)}")
            print(f"    ОСНОВНОЙ (вход через 1 мин, 15 мин): {m:+.3%} (t {t:+.1f}); половины {h1:+.3%} / {h2:+.3%}; "
                  f"с хеджем {mh:+.3%} (t {th:+.1f}); сверх плацебо {md:+.3%} (t {td:+.1f}); стопов {main.s1_15.mean():.1%}; "
                  f"плацебо {main.pl.mean():+.3%}")
            for delay in (0, 1):
                s = "  ".join(f"{hold} мин {ct(x[f'd{delay}_{hold}'], x.t)[0]:+.3%} (t {ct(x[f'd{delay}_{hold}'], x.t)[1]:+.1f})"
                              for hold in (5, 15, 30, 60))
                print(f"    вход {'через 1 мин' if delay else 'на T'}: {s}")
            for lab, sub in (("каскад идёт (15 мин ≥ 2%)", main[side * main.last15 >= 0.02]),
                             ("ликвидные (24 ч ≥ 20 млн $)", main[main.liq >= 2e7]),
                             ("ход ≥ 10%", main[side * main.r60 >= 0.10])):
                ms, tsb, nsb = ct(sub.d1_15, sub.t)
                print(f"    {lab}: n={nsb}, {ms:+.3%} (t {tsb:+.1f}); вход на T: {ct(sub.d0_15, sub.t)[0]:+.3%}")
            if p == "2024–2026":
                conds = (("≥ 20 в мес.", n_all / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                         ("сверх плацебо > 0", md > 0), ("с хеджем > 0", mh > 0))
                print("    правило владельца на 2024–2026: " + "; ".join(f"{k} — {'да' if v else 'нет'}" for k, v in conds))
            allx.append(main[["t", "d1_15"]])
            signs.append(m > 0)
        if len(allx) == 3:
            A = pd.concat(allx)
            m, t, n = ct(A.d1_15, A.t)
            print(f"\n  ВМЕСТЕ: {m:+.3%} (t {t:+.1f}, n={n}); плюс во всех периодах — {'да' if all(signs) else 'нет'}; "
                  f"→ {'ПОРОГ ПРОЙДЕН (если выполнено правило владельца)' if all(signs) and t >= 3 else 'порог не пройден'}")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
