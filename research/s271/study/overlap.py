"""s271 — описательные пересечения событий (до расчёта доходов, цены после события не смотрятся):
- Г1 «вынос лонгов, ведёт перп» (цена −5% и OI −5% за час, премия ≤ −0,3% или перп ниже спота на ≥ 1 п. п.): доля событий
  в часы, когда BTC за тот же час упал на ≥ 2% (общий обвал), и доля перпов без спота;
- пересечение Г1 с Г2 «внезапный дисконт перпа к споту ≥ 1%» (та же монета, ±2 ч);
Нужны кэши /dev/shm/s271 от freq_flush.py. Запуск из /home/user/mc_data."""
import os
import pickle
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common271 import DAY, H, PER, base, cooldown, crypto_perps, hourly_close, live_idx, load_k  # noqa: E402


def main():
    per = "2024–2026"
    cfg = PER[per]
    rows = pickle.load(open(f"/dev/shm/s271/flush_{per}.pkl", "rb"))
    K = load_k(per)
    T, px, _ = hourly_close(K["BTC"])
    rb = dict(zip(T[1:].tolist(), (px[1:] / px[:-1] - 1).tolist()))
    ev = []
    for p, Ts, dp, doi, prem, ds, hs in rows:
        lead = np.where(np.isfinite(prem), -prem >= 0.003, np.isfinite(ds) & (-(dp - ds) >= 0.01))
        m = (dp <= -0.05) & (doi <= -0.05) & lead
        Tm = Ts[m]
        keep = cooldown(Tm, DAY)
        for k in keep:
            ev.append((p, int(Tm[k]), bool(hs[m][k])))
    ev = [e for e in ev if cfg["t0"] <= e[1] < cfg["t1"]]
    mk = np.array([rb.get(e[1], np.nan) <= -0.02 for e in ev])
    print(f"Г1 (−5% / OI −5% / ведёт перп): событий {len(ev)}; в часы BTC ≤ −2%: {mk.mean():.0%}; "
          f"у монет со спотом: {np.mean([e[2] for e in ev]):.0%}")
    # Г2 — те же правила, что freq_gap.py (внезапный дисконт ≥ 1%)
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    g2 = {}
    for p in crypto_perps(K):
        sp = SP.get(p) if p in SP else SP.get(base(p))
        if sp is None or not len(sp):
            continue
        i0, _ = live_idx(K[p])
        if i0 is None:
            continue
        Tp, pp, _ = hourly_close(K[p])
        st = sp[:, 0].astype(np.int64) + H
        k = np.searchsorted(st, Tp); k2 = np.minimum(k, len(st) - 1)
        hit = (k < len(st)) & (st[k2] == Tp)
        Tp, pp, k2 = Tp[hit], pp[hit], k2[hit]
        sc = sp[k2, 4].astype(float); sv = sp[k2, 1].astype(float)
        ok = (sc > 0) & (pp > 0) & (sv >= 5e4) & (Tp - int(K[p]["t"][i0]) >= 7 * DAY)
        if not ok.any():
            continue
        mult = 10.0 ** np.round(np.log10(np.nanmedian(pp[ok] / sc[ok])))
        g = np.where(ok, pp / (sc * mult) - 1, np.nan)
        med = np.full(len(g), np.nan)
        if len(g) > 4:
            w = np.lib.stride_tricks.sliding_window_view(np.abs(g), 4)[:-1]
            with np.errstate(all="ignore"):
                med[4:] = np.nanmedian(w, axis=1)
        m = ok & (med <= 0.003) & (g <= -0.01)
        Tm = Tp[m]
        g2[p] = Tm[cooldown(Tm, DAY)]
    n2 = sum(((x >= cfg["t0"]) & (x < cfg["t1"])).sum() for x in g2.values())
    both = sum(1 for p, t, _ in ev if p in g2 and np.any(np.abs(g2[p] - t) <= 2 * H))
    print(f"Г2 (внезапный дисконт к споту ≥ 1%): событий {n2}; из событий Г1 рядом (±2 ч) есть событие Г2: {both / max(len(ev), 1):.0%}")


if __name__ == "__main__":
    main()
