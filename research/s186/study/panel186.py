"""s186 — панель «монета × сутки × час-якорь» из 15-мин свечей перпов Binance USDT-M (только данные до якоря T,
кроме оборота самой 15-мин свечи [T, T+15 мин) — он нужен как след ребаланса, без цены и знака).

Якоря: 00, 04, 08, 12, 16, 20 UTC (00 — FTX 00:02, KuCoin, Bybit; 16 — Gate, MEXC, Pionex 00:00 UTC+8; прочие — контроль).
Поля строки (монета b, сутки D, час H; T = D + H):
- r24 — ход за 24 ч до T (закрытие свечи, кончающейся в T, к закрытию сутки назад);
- up_* / dn_* — номер первой 15-мин свечи окна [T − 24 ч, T), где максимум (минимум) прошёл порог от цены в T − 24 ч
  (−1 — не прошёл): пороги 6,67 / 10 / 11,1 / 12 / 15 / 20% — пороги внутридневного ребаланса FTX, Gate, MEXC;
- v7 — средний суточный оборот перпа за 7 сут до T; q_slot — оборот свечи [T, T+15 мин); q_base — медиана оборота
  той же свечи суток за 14 предыдущих сут; q_pre — оборот свечи [T − 15 мин, T); q_pre_base — её медиана за 14 сут.
Кроме того — счётчик событий r24 ≥ 5/10/15/20% по всем 24 часам (для частоты в другие часы).
Итог: /home/user/mc_data/s186/cd_<период>.pkl; лог — panel186_<период>.log. Доходы после T не считаются."""
import pickle
import sys

import numpy as np
import pandas as pd

import common186 as C

HOURS = (0, 4, 8, 12, 16, 20)
UPS = (0.0667, 0.10, 0.111, 0.12, 0.15, 0.20)
RTH = (0.05, 0.10, 0.15, 0.20)


def first_cross(win, ref, thr, up=True):
    """win — [n, 96] максимумы (минимумы) окна; ref — [n] цена в начале окна → номер первой свечи пересечения или −1."""
    with np.errstate(invalid="ignore", divide="ignore"):
        x = win / ref[:, None] - 1.0
    hit = (x >= thr) if up else (x <= -thr)
    hit &= np.isfinite(x)
    any_ = hit.any(axis=1)
    return np.where(any_, hit.argmax(axis=1), -1).astype(np.int16)


def run(per):
    L = C.Log(f"panel186_{per}")
    cfg = C.PER[per]
    t0, t1 = C.ts(cfg["t0"]), C.ts(cfg["t1"])
    K = pickle.load(open(cfg["k"], "rb"))
    bad = C.C3.bad_set()
    # одна запись на базовый актив — перп с наибольшим оборотом
    best = {}
    for sym, a in K.items():
        b = C.C3.base(sym)
        if sym in bad or b in bad or b in ("BTC", "ETH"):
            continue
        q = float(np.nansum(np.asarray(a["qv"], np.float64)))
        if q > 0 and (b not in best or q > best[b][1]):
            best[b] = (sym, q)
    L(per, "монет:", len(best))
    gmin = (t0 - 16 * C.DAY) // 900
    ng = (t1 + C.DAY) // 900 - gmin
    nd = (t1 - t0) // C.DAY
    days = t0 + np.arange(nd) * C.DAY
    rows = []
    allh = {h: {thr: 0 for thr in RTH} for h in range(24)}
    allh_n = {h: 0 for h in range(24)}
    for b, (sym, _) in sorted(best.items()):
        a = K[sym]
        t = np.asarray(a["t"], np.int64)
        qv = np.asarray(a["qv"], np.float64)
        ok = (qv > 0) & (t >= gmin * 900) & (t < (gmin + ng) * 900)
        if ok.sum() < 96 * 20:
            continue
        g = t[ok] // 900 - gmin
        cg = np.full(ng, np.nan)
        hg = np.full(ng, np.nan)
        lg = np.full(ng, np.nan)
        qg = np.zeros(ng)
        cg[g] = np.asarray(a["c"], np.float64)[ok]
        hg[g] = np.asarray(a["h"], np.float64)[ok]
        lg[g] = np.asarray(a["l"], np.float64)[ok]
        qg[g] = qv[ok]
        live = np.zeros(ng, bool)
        live[g] = True
        cq = np.r_[0.0, np.cumsum(qg)]
        # все 24 часа: частота r24 ≥ порога
        for h in range(24):
            s = (days + h * 3600) // 900 - gmin
            c_now, c_prev = cg[s - 1], cg[s - 97]
            with np.errstate(invalid="ignore", divide="ignore"):
                r = c_now / c_prev - 1
            fin = np.isfinite(r)
            allh_n[h] += int(fin.sum())
            for thr in RTH:
                allh[h][thr] += int((r[fin] >= thr).sum())
        for h in HOURS:
            T = days + h * 3600
            s = T // 900 - gmin
            c_now, c_prev = cg[s - 1], cg[s - 97]
            with np.errstate(invalid="ignore", divide="ignore"):
                r24 = c_now / c_prev - 1
            idx = s[:, None] - 96 + np.arange(96)[None, :]
            hw, lw = hg[idx], lg[idx]
            rec = dict(b=b, D=days, H=np.full(nd, h, np.int8), r24=r24.astype(np.float32),
                       v7=((cq[s] - cq[s - 672]) / 7).astype(np.float32),
                       q_slot=np.where(live[s], qg[s], np.nan).astype(np.float32),
                       q_pre=np.where(live[s - 1], qg[s - 1], np.nan).astype(np.float32))
            base_idx = s[:, None] - 96 * np.arange(1, 15)[None, :]
            qb = np.where(live[base_idx], qg[base_idx], np.nan)
            qpb = np.where(live[base_idx - 1], qg[base_idx - 1], np.nan)
            with np.errstate(all="ignore"):
                rec["q_base"] = np.nanmedian(qb, axis=1).astype(np.float32)
                rec["q_pre_base"] = np.nanmedian(qpb, axis=1).astype(np.float32)
            rec["nlive"] = live[idx].sum(axis=1).astype(np.int16)
            for thr in UPS:
                k = f"{thr * 100:.4g}".replace(".", "_")
                rec[f"up_{k}"] = first_cross(hw, c_prev, thr, True)
                rec[f"dn_{k}"] = first_cross(lw, c_prev, thr, False)
            df = pd.DataFrame(rec)
            df = df[np.isfinite(df.r24)]
            rows.append(df)
    cd = pd.concat(rows, ignore_index=True)
    cd["b"] = cd.b.astype("category")
    pickle.dump(dict(cd=cd, allh=allh, allh_n=allh_n), open(f"{C.OUT}/cd_{per}.pkl", "wb"))
    L("строк:", len(cd), "монет:", cd.b.nunique(), "суток:", cd.D.nunique())
    L("доля r24 ≥ 5/10/15/20% по часу UTC (все монеты):")
    for h in range(24):
        n = max(allh_n[h], 1)
        L(f"  {h:02d}: " + " ".join(f"{allh[h][thr] / n * 100:.2f}%" for thr in RTH) + f"  (n={allh_n[h]})")


if __name__ == "__main__":
    for per in (sys.argv[1:] or C.PERS):
        run(per)
