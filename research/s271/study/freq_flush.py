"""s271 Г1 (и зеркало) — частота «выносов» на перпе, подтверждённых падением OI: за час цена ±X% и OI в монетах −Y% (позиции
закрываются на ходе: на падении — ликвидации и стопы лонгов, на росте — шортов), первое у монеты и стороны за 24 ч,
перп старше 7 сут. Фильтр «ведёт перп» (2024–2026 гг.): премия перпа к индексу на конце часа ≤ −0,3% (вынос лонгов) или
≥ +0,3% (вынос шортов) — `s12/prem.pkl`; запасной — перп за час ушёл дальше спота Binance на ≥ 1 п. п. (`s23/spot1h.pkl`).
Для сравнения — «набор»: цена ±X%, OI +Y%. Доходы не считаются. Запуск из /home/user/mc_data."""
import os
import pickle
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common271 import DAY, H, PER, base, cooldown, crypto_perps, fmt, freq_line, hourly_close, live_idx, load_k, met, spot_start  # noqa: E402

XS, YS = (0.03, 0.05, 0.08), (0.03, 0.05, 0.10)


def panel(per):
    """Часы × монеты: T, монета, dp, doi, премия, ход спота, есть ли спот."""
    K = load_k(per)
    P = crypto_perps(K)
    PR = pickle.load(open("s12/prem.pkl", "rb")) if per == "2024–2026" else {}
    SP = pickle.load(open("s23/spot1h.pkl", "rb")) if per == "2024–2026" else {}
    ss = spot_start(P) if per == "2024–2026" else {}
    out = []
    for p in P:
        m = met(per, p)
        if m is None:
            continue
        tm, oi, _ = m
        a = K[p]
        i0, _ = live_idx(a)
        if i0 is None:
            continue
        t_live = int(a["t"][i0])
        T, px, _ = hourly_close(a)
        ok = np.isfinite(oi) & (oi > 0)
        tm, oi = tm[ok], oi[ok]
        # пары часов T−1ч → T, где есть цена и OI на обоих концах
        ip = {int(x): k for k, x in enumerate(T)}
        io = {int(x): k for k, x in enumerate(tm)}
        Ts = np.array([x for x in T if (x - H) in ip and x in io and (x - H) in io and x - t_live >= 7 * DAY], np.int64)
        if not len(Ts):
            continue
        p1 = px[[ip[x] for x in Ts]]; p0 = px[[ip[x - H] for x in Ts]]
        o1 = oi[[io[x] for x in Ts]]; o0 = oi[[io[x - H] for x in Ts]]
        good = (p0 > 0) & (p1 > 0)
        Ts, dp, doi = Ts[good], (p1 / p0 - 1)[good], (o1 / o0 - 1)[good]
        prem = np.full(len(Ts), np.nan); ds = np.full(len(Ts), np.nan)
        if p in PR:
            pt, pv = PR[p]
            k = np.searchsorted(pt, Ts - 900)
            k2 = np.minimum(k, len(pt) - 1)
            hit = (k < len(pt)) & (pt[k2] == Ts - 900)
            prem[hit] = pv[k2[hit]]
        sp = SP.get(p) if p in SP else SP.get(base(p))
        if sp is not None and len(sp):
            st = sp[:, 0].astype(np.int64); sc = sp[:, 4].astype(float)
            ks1 = np.searchsorted(st, Ts - H); ks0 = np.searchsorted(st, Ts - 2 * H)
            k1 = np.minimum(ks1, len(st) - 1); k0 = np.minimum(ks0, len(st) - 1)
            hit = (ks1 < len(st)) & (st[k1] == Ts - H) & (st[k0] == Ts - 2 * H) & (sc[k0] > 0)
            ds[hit] = sc[k1[hit]] / sc[k0[hit]] - 1
        s0 = ss.get(p)
        has_spot = np.array([s0 is not None and s0 <= x for x in Ts]) if per == "2024–2026" else np.zeros(len(Ts), bool)
        out.append((p, Ts, dp, doi, prem, ds, has_spot))
    return out


def events(rows, side, X, Y, mode):
    """mode: 'oi' — только цена и OI; 'lead' — плюс «ведёт перп»; 'build' — набор (OI растёт)."""
    allT, spotT = [], []
    for p, Ts, dp, doi, prem, ds, hs in rows:
        m = (side * dp >= X)
        m &= (doi >= Y) if mode == "build" else (doi <= -Y)
        if mode == "lead":
            lead = np.where(np.isfinite(prem), side * prem >= 0.003, np.isfinite(ds) & (side * (dp - ds) >= 0.01))
            m &= lead
        if not m.any():
            continue
        Tm = Ts[m]
        keep = cooldown(Tm, DAY)
        allT += list(Tm[keep]); spotT += list(Tm[keep][hs[m][keep]])
    return np.array(allT, np.int64), np.array(spotT, np.int64)


def run(per):
    cfg = PER[per]
    cache = f"/dev/shm/s271/flush_{per}.pkl"
    if os.path.exists(cache):
        rows = pickle.load(open(cache, "rb"))
    else:
        rows = panel(per)
        pickle.dump(rows, open(cache, "wb"))
    n_h = sum(len(r[1]) for r in rows)
    print(f"\n== {per}: монет с метриками {len(rows)}, монето-часов {n_h}")
    for side, nm in ((-1, "вынос лонгов (Г1, лонг)"), (1, "вынос шортов (зеркало Г1, шорт)")):
        for X in XS:
            for Y in YS:
                a, s = events(rows, side, X, Y, "oi")
                line = f"{nm} цена {side * X:+.0%}, OI −{Y:.0%}: {fmt(freq_line(a, cfg['t0'], cfg['t1'], cfg['mid'], cfg['tb']))}"
                if per == "2024–2026":
                    al, sl = events(rows, side, X, Y, "lead")
                    line += f"\n      + ведёт перп: {fmt(freq_line(al, cfg['t0'], cfg['t1'], cfg['mid']))}"
                    line += f"; из них у монет со спотом {freq_line(sl, cfg['t0'], cfg['t1'], cfg['mid'])['pm']:.1f}"
                print(line)
        for X in (0.05,):
            a, _ = events(rows, side, X, 0.10, "build")
            print(f"  для сравнения «набор» цена {side * X:+.0%}, OI +10%: {fmt(freq_line(a, cfg['t0'], cfg['t1'], cfg['mid'], cfg['tb']))}")


if __name__ == "__main__":
    for per in PER:
        run(per)
