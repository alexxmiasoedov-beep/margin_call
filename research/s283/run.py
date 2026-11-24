"""s283 — лимитка на прострел (Г1–Г5 s282) по записи ВЫВОДЫ.md (коммит 4da8f5d).

Запуск по периодам — в папке периода (свечи и фандинг — s2/k2y.pkl и s2/fund2y.pkl; движок s187/fastbt даёт фандинг
и индекс альтов), события — таблицы s282 в /dev/shm/s282 (`s282/study/wicks_build.py`):
  cd ~/mc_2020 && python3 -I <repo>/research/s283/run.py 2020–2022
  cd ~/mc_oos  && python3 -I <repo>/research/s283/run.py 2022–2024
  cd ~/mc_data && python3 -I <repo>/research/s283/run.py 2024–2026
Сводка: python3 -I <repo>/research/s283/run.py report. Минутные окна — /dev/shm/s283, сделки — /home/user/mc_data/s283."""
import io
import os
import pickle
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s282", "study"))
from common282 import PER  # noqa: E402
from hyp_freq import universe  # noqa: E402

TMP282 = "/dev/shm/s282"
SHM, OUT = "/dev/shm/s283", "/home/user/mc_data/s283"
os.makedirs(SHM, exist_ok=True)
os.makedirs(OUT, exist_ok=True)
M, BAR, DAY, WEEK = 60, 900, 86400, 7 * 86400
MONTH = 30.44 * DAY
K_SIG, X_FLOOR, PEN, TURN = 8, 0.03, 0.002, 1e6
F_MAKER, F_TAKER, SLIP = 0.0002, 0.0005, 0.002
NS5, NPL, SEED = 2500, 500, 283
PRE, POST = 2, 15 + 242                       # окно минуток кандидата: [t − 2 мин, t + 257 мин)
UA = "research-script/1.0"
BASE = "https://data.binance.vision/data/futures/um/daily/klines"
SIDE = {"Г1": +1, "Г4": -1, "Г5": +1}


# ---------------- минутные свечи ----------------

def fetch_day(sym, day):
    d = pd.Timestamp(day * DAY, unit="s").strftime("%Y-%m-%d")
    url = f"{BASE}/{sym}USDT/1m/{sym}USDT-1m-{d}.zip"
    for k in range(5):
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
        time.sleep(2 + 3 * k)
    return None


def windows(req, cache_file):
    """req — список (ключ, перп, a, b): нужны минутки с открытием в [a, b). Кэш — словарь ключ → массив float64."""
    W = pickle.load(open(cache_file, "rb")) if os.path.exists(cache_file) else {}
    todo = [r for r in req if r[0] not in W]
    by = {}
    for key, sym, a, b in todo:
        by.setdefault(sym, []).append((key, a, b))
    print(f"  окон в кэше {len(W)}, докачать {len(todo)} ({len(by)} перпов)", flush=True)

    def job(sym):
        need = sorted({d for _, a, b in by[sym] for d in range(a // DAY, (b - 1) // DAY + 1)})
        days = {d: fetch_day(sym, d) for d in need}
        out = {}
        for key, a, b in by[sym]:
            parts = [days[d] for d in range(a // DAY, (b - 1) // DAY + 1) if days.get(d) is not None]
            if not parts:
                out[key] = None
                continue
            x = np.concatenate(parts)
            x = x[(x[:, 0] >= a) & (x[:, 0] < b)]
            out[key] = x[np.argsort(x[:, 0])] if len(x) else None
        return out

    n = 0
    with ThreadPoolExecutor(12) as ex:
        for out in ex.map(job, list(by)):
            W.update(out)
            n += 1
            if n % 100 == 0:
                pickle.dump(W, open(cache_file, "wb"))
                print(f"   перпов {n}/{len(by)}", flush=True)
    pickle.dump(W, open(cache_file, "wb"))
    return W


# ---------------- сделка по минуткам ----------------

def exit_path(w, side, f_idx, p0, tp, sl, hold, fund_t, fund_cs, fee_in):
    """Выход со следующей минуты после f_idx: тейк tp (мейкер), стоп sl (тейкер + проскальзывание), иначе закрытие
    минуты f + hold (тейкер). tp или sl = None — без них. Возвращает (доход, причина, время выхода) или None."""
    t = w[:, 0].astype(np.int64)
    tf = t[f_idx]
    end = np.searchsorted(t, tf + hold * M)
    if end >= len(t) or t[end] != tf + hold * M:
        return None
    px, why, j = w[end, 4], "время", end
    for m in range(f_idx + 1, end + 1):
        hi, lo, op = w[m, 2], w[m, 3], w[m, 1]
        adv = sl is not None and ((side > 0 and lo <= sl) or (side < 0 and hi >= sl))
        fav = tp is not None and ((side > 0 and hi >= tp) or (side < 0 and lo <= tp))
        if adv:
            px = (min(sl, op) * (1 - SLIP)) if side > 0 else (max(sl, op) * (1 + SLIP))
            why, j = "стоп", m
            break
        if fav:
            px, why, j = tp, "тейк", m
            break
    fee = fee_in + (F_MAKER if why == "тейк" else F_TAKER)
    t_in, t_out = tf + M, int(t[j]) + M
    f = fund_cs[np.searchsorted(fund_t, t_out, "right")] - fund_cs[np.searchsorted(fund_t, t_in, "right")] if len(fund_t) else 0.0
    return side * (px / p0 - 1) - side * f - fee, why, t_out


def fill_minute(w, t0, side, L, trigger=None):
    """Первая минута внутри 15-мин свечи [t0, t0 + 15 мин), где цена прошла L на PEN (у Г5 — после минуты триггера)."""
    t = w[:, 0].astype(np.int64)
    i0, i1 = np.searchsorted(t, t0), np.searchsorted(t, t0 + BAR)
    start = i0
    if trigger is not None:
        trig = [m for m in range(i0, i1) if (side > 0 and w[m, 4] <= trigger) or (side < 0 and w[m, 4] >= trigger)]
        if not trig:
            return None, "нет триггера"
        start = trig[0] + 1
    for m in range(start, i1):
        if (side > 0 and w[m, 3] <= L * (1 - PEN)) or (side < 0 and w[m, 2] >= L * (1 + PEN)):
            return m, ""
    return None, "минутки не подтвердили" if trigger is None else "не исполнилась после триггера"


# ---------------- период ----------------

def candidates(per):
    E = pd.read_pickle(f"{TMP282}/ev_{per}.pkl")
    X = np.maximum(X_FLOOR, K_SIG * E.sig.values)
    ok = (E.age.values >= 7) & (E.turn.values >= TURN) & np.isfinite(X)
    dn = ok & (-E.dl.values >= 1 - (1 - X) * (1 - PEN))
    up = ok & (E.dh.values >= (1 + X) * (1 + PEN) - 1)
    Ud, Uu = universe(E, -1), universe(E, +1)
    day = E.t.values // DAY
    s = E.s.astype(str).values
    ind = np.array([a in Ud.get(int(d), ()) for a, d in zip(s, day)], bool)
    inu = np.array([a in Uu.get(int(d), ()) for a, d in zip(s, day)], bool)
    E = E.assign(s=s, X=X)
    C = {"Г1": E[dn & ind], "Г4": E[up & inu]}
    g5 = E[dn].sort_values(["s", "t"])
    keep, last = [], {}
    for k, r in enumerate(g5.itertuples()):                   # уточнение: одна позиция — пауза 75 мин от прошлого кандидата
        if r.t - last.get(r.s, -10 ** 12) >= 75 * M:
            keep.append(k)
            last[r.s] = r.t
    g5 = g5.iloc[keep]
    n5 = len(g5)
    rng = np.random.default_rng(SEED)
    if len(g5) > NS5:
        g5 = g5.iloc[np.sort(rng.choice(len(g5), NS5, replace=False))]
    C["Г5"] = g5
    return C, n5


def run(per):
    sys.path.insert(0, os.path.join(HERE, "..", "s187"))
    import fastbt as FB  # noqa: E402
    C, n5 = candidates(per)
    print(per, {h: len(x) for h, x in C.items()}, "кандидатов Г5 всего", n5, flush=True)
    req, info = {}, {}
    for h, X in C.items():
        for r in X.itertuples():
            a = FB.K.get(r.s)
            if a is None:
                continue
            kt = a["t"].astype(np.int64)
            i = int(np.searchsorted(kt, r.t))
            if i < 1 or i >= len(kt) or kt[i] != r.t or kt[i - 1] != r.t - BAR:
                continue
            c0 = float(a["c"][i - 1])
            info[(h, r.s, int(r.t))] = dict(c0=c0, X=float(r.X))
            req[(r.s, int(r.t))] = ((r.s, int(r.t)), r.s, int(r.t) - PRE * M, int(r.t) + POST * M)   # окно одно на свечу
    W = windows(list(req.values()), f"{SHM}/m1_{per}.pkl")
    # BTC для Г2: минутки свечи-события
    bt = sorted({k[2] for k in info if k[0] == "Г1"})
    WB = windows([(("BTC", t), "BTC", t - PRE * M, t + 17 * M) for t in bt], f"{SHM}/btc_{per}.pkl")
    kb = FB.K["BTC"]
    kbt = kb["t"].astype(np.int64)
    rows = []
    for h in ("Г1", "Г4", "Г5"):
        side = SIDE[h]
        last_exit = {}
        keys = sorted((k for k in info if k[0] == h), key=lambda k: (k[1], k[2]))
        for key in keys:
            _, s, t0 = key
            if h != "Г5" and t0 < last_exit.get(s, -1):
                continue                                         # позиция ещё открыта — лимитка не стоит
            w = W.get((s, t0))
            c0, X = info[key]["c0"], info[key]["X"]
            L = c0 * (1 - side * X)
            rec = dict(h=h, s=s, t=t0, X=X, c0=c0, L=L, ok=False, why="")
            if w is None or len(w) < 20:
                rec["why"] = "нет минуток"
                rows.append(rec)
                continue
            f, why = fill_minute(w, t0, side, L, trigger=c0 * (1 - side * X / 2) if h == "Г5" else None)
            if f is None:
                rec["why"] = why
                rows.append(rec)
                continue
            fr = FB.funding(s)
            ft = fr[:, 0].astype(np.int64) if len(fr) else np.zeros(0, np.int64)
            fcs = np.r_[0.0, np.cumsum(fr[:, 1])] if len(fr) else np.zeros(1)
            tp, sl = c0 * (1 - side * X / 2), L * (1 - side * X)
            main = exit_path(w, side, f, L, tp, sl, 60, ft, fcs, F_MAKER)
            if main is None:
                rec["why"] = "нет минуток для выхода"
                rows.append(rec)
                continue
            tf = int(w[f, 0])
            rec.update(ok=True, tf=tf, net=main[0], exit=main[1], t_out=main[2])
            last_exit[s] = main[2]
            for frac in (0.25, 0.75, 1.0):                    # тейк на долю пути от L к c0
                x = exit_path(w, side, f, L, L + frac * (c0 - L), sl, 60, ft, fcs, F_MAKER)
                rec[f"tp{int(frac * 100)}"] = x[0] if x else np.nan
            for hold in (15, 240):
                x = exit_path(w, side, f, L, tp, sl, hold, ft, fcs, F_MAKER)
                rec[f"h{hold}"] = x[0] if x else np.nan
            x = exit_path(w, side, f, L, tp, None, 60, ft, fcs, F_MAKER)
            rec["nostop"] = x[0] if x else np.nan
            # контроль: по рынку на закрытии свечи-события, те же относительные тейк и стоп от цены входа
            tw = w[:, 0].astype(np.int64)
            e = np.searchsorted(tw, t0 + BAR - M)
            if e < len(tw) and tw[e] == t0 + BAR - M:
                pe = w[e, 4]
                x = exit_path(w, side, e, pe, pe * tp / L, pe * sl / L, 60, ft, fcs, F_TAKER)
                rec["ctrl"] = x[0] if x else np.nan
            # Г3: прострел — минимум минуты исполнения ≤ закрытие прошлой минуты · (1 − X/2)
            if f >= 1 and tw[f - 1] == tf - M:
                rec["g3"] = bool((w[f, 3] <= w[f - 1, 4] * (1 - X / 2)) if side > 0 else (w[f, 2] >= w[f - 1, 4] * (1 + X / 2)))
            # Г2: BTC в минуте исполнения ≤ закрытие прошлой 15-мин свечи BTC · 0,99
            if h == "Г1":
                wb = WB.get(("BTC", t0))
                ib = int(np.searchsorted(kbt, t0))
                if wb is not None and 1 <= ib < len(kbt) and kbt[ib] == t0:
                    cb0 = float(kb["c"][ib - 1])
                    jb = np.searchsorted(wb[:, 0].astype(np.int64), tf)
                    if jb < len(wb) and int(wb[jb, 0]) == tf:
                        rec["g2_mkt"] = bool(wb[jb, 3] <= cb0 * 0.99)
            te, tend = t0, int(np.ceil(main[2] / BAR) * BAR)
            rec["alt"] = float(FB.alt_mv(np.array([te]), np.array([tend]))[0])
            rows.append(rec)
    R = pd.DataFrame(rows)
    # плацебо: выборка до NPL сделок на гипотезу, та же монета и минута суток 7/14/21 сут раньше
    rng = np.random.default_rng(SEED)
    preq = []
    for h in ("Г1", "Г4", "Г5"):
        x = R[(R.h == h) & R.ok]
        idx = np.sort(rng.choice(len(x), min(NPL, len(x)), replace=False)) if len(x) else []
        for r in x.iloc[idx].itertuples():
            for d in (7, 14, 21):
                tf = int(r.tf) - d * DAY
                preq.append(((h, r.s, int(r.t), d), r.s, tf - M, tf + 62 * M))
    WP = windows(preq, f"{SHM}/pl_{per}.pkl")
    pl = {}
    for (h, s, t0, d), w in WP.items():
        if w is None:
            continue
        r = R[(R.h == h) & (R.s == s) & (R.t == t0)].iloc[0]
        side = SIDE[h]
        tw = w[:, 0].astype(np.int64)
        f = np.searchsorted(tw, int(r.tf) - d * DAY)
        if f >= len(tw) or tw[f] != int(r.tf) - d * DAY:
            continue
        pe = w[f, 4]
        tp, sl = r.c0 * (1 - side * r.X / 2), r.L * (1 - side * r.X)
        fr = FB.funding(s)
        ft = fr[:, 0].astype(np.int64) if len(fr) else np.zeros(0, np.int64)
        fcs = np.r_[0.0, np.cumsum(fr[:, 1])] if len(fr) else np.zeros(1)
        x = exit_path(w, side, f, pe, pe * tp / r.L, pe * sl / r.L, 60, ft, fcs, F_MAKER)
        if x:
            pl.setdefault((h, s, t0), []).append(x[0])
    R["pl"] = [np.mean(pl[(h, s, t)]) if (h, s, t) in pl else np.nan for h, s, t in zip(R.h, R.s, R.t)]
    R.attrs["n5"] = n5
    R.to_pickle(f"{OUT}/tr_{per}.pkl")
    pd.Series({"n5": n5}).to_pickle(f"{OUT}/n5_{per}.pkl")
    print(per, R[R.ok].groupby("h").size().to_dict(), R[~R.ok].groupby(["h", "why"]).size().to_dict(), flush=True)


# ---------------- сводка ----------------

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


def fmt(x, t):
    m, tt, n = ct(x, t)
    return f"{m:+.3%} (t {tt:+.1f}, n={n})"


def report():
    pers = [p for p in PER if os.path.exists(f"{OUT}/tr_{p}.pkl")]
    R = {p: pd.read_pickle(f"{OUT}/tr_{p}.pkl") for p in pers}
    res = {}
    for h, sub, lab in (("Г1", None, "Г1 — лимитка на покупку у 20 «прострельных» перпов"),
                        ("Г1", ("g2_mkt", False), "Г2 одиночный (BTC в минуте исполнения > −1%)"),
                        ("Г1", ("g2_mkt", True), "Г2 рыночный (BTC ≤ −1%)"),
                        ("Г1", ("g3", True), "Г3 прострел (минута ≥ X/2)"),
                        ("Г1", ("g3", False), "Г3 сползание"),
                        ("Г4", None, "Г4 — шорт-лимитка на прострел вверх"),
                        ("Г5", None, "Г5 — все перпы, лимитка по триггеру (выборка)")):
        print(f"\n### {lab}")
        for p in pers:
            X = R[p]
            x = X[(X.h == h) & X.ok]
            if sub is not None:
                x = x[x[sub[0]].astype(object) == sub[1]] if sub[0] in x else x.iloc[:0]
            cfg = PER[p]
            mo = (cfg["t1"] - cfg["t0"]) / MONTH
            if h == "Г5":
                n5 = float(pd.read_pickle(f"{OUT}/n5_{p}.pkl")["n5"])
                share = (X[(X.h == "Г5")].ok.mean())
                pm = n5 * share / mo
            else:
                pm = len(x) / mo
            m, t, n = ct(x.net, x.tf)
            mid = float(np.median(x.tf)) if len(x) else 0
            h1, h2 = x[x.tf < mid].net.mean(), x[x.tf >= mid].net.mean()
            md, td, nd = ct(x.net - x.pl, x.tf)
            hed = x.net - SIDE[h] * x.alt
            days = x.tf // DAY
            top = days.value_counts().index[:10]
            res[(lab, p)] = dict(m=m, t=t, n=n, pm=pm, h1=h1, h2=h2, md=md)
            print(f"  {p}: {pm:.1f} в мес.; {m:+.3%} (t {t:+.1f}, n={n}); половины {h1:+.3%} / {h2:+.3%}; "
                  f"сверх плацебо {md:+.3%} (t {td:+.1f}, n={nd}); плацебо {x.pl.mean():+.3%}; "
                  f"тейк/стоп/время {(x.exit == 'тейк').mean():.0%}/{(x.exit == 'стоп').mean():.0%}/{(x.exit == 'время').mean():.0%}")
            if sub is None:
                print(f"     контроль (по рынку на закрытии свечи): {fmt(x.ctrl, x.tf)}; с хеджем {fmt(hed, x.tf)}; "
                      f"без 10 главных суток {fmt(x[~days.isin(top)].net, x[~days.isin(top)].tf)}")
                print(f"     тейк 25/75/100%: {fmt(x.tp25, x.tf)} / {fmt(x.tp75, x.tf)} / {fmt(x.tp100, x.tf)}; "
                      f"выход 15 / 240 мин: {fmt(x.h15, x.tf)} / {fmt(x.h240, x.tf)}; без стопа {fmt(x.nostop, x.tf)}")
                if h == "Г1":
                    print(f"     причины без сделки: {X[(X.h == h) & ~X.ok].why.value_counts().to_dict()}")
    print("\n## Порог")
    for lab, worse in (("Г1 — лимитка на покупку у 20 «прострельных» перпов", None),
                       ("Г2 одиночный (BTC в минуте исполнения > −1%)", "Г2 рыночный (BTC ≤ −1%)"),
                       ("Г3 прострел (минута ≥ X/2)", "Г3 сползание"),
                       ("Г4 — шорт-лимитка на прострел вверх", None),
                       ("Г5 — все перпы, лимитка по триггеру (выборка)", None)):
        r3 = res.get((lab, "2024–2026"))
        if r3 is None:
            continue
        conds = [("≥ 20 в мес.", r3["pm"] >= 20), ("t ≥ 3", r3["t"] >= 3), ("обе половины > 0", r3["h1"] > 0 and r3["h2"] > 0),
                 ("сверх плацебо > 0", r3["md"] > 0)]
        for p in ("2020–2022", "2022–2024"):
            if (lab, p) in res:
                conds.append((f"{p} > 0", res[(lab, p)]["m"] > 0))
        if worse:
            for p in pers:
                if (worse, p) in res:
                    conds.append((f"разница {p} > 0", res[(lab, p)]["m"] - res[(worse, p)]["m"] > 0))
        ok = all(c for _, c in conds)
        print(f"  {lab}: " + "; ".join(f"{k} — {'да' if c else 'нет'}" for k, c in conds) + f" → {'ПРОЙДЕН' if ok else 'не пройден'}")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
