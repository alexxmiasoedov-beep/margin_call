"""s271 Г8 — частота «обвала рынка с перелётом альтов»: час, когда BTC упал на ≥ X% и совокупные позиции перпов (OI в монетах
по цене начала часа, все монеты с метриками) сократились на ≥ 1%; в этот час ликвидные альты (100 по обороту за 30 сут),
упавшие сверх своей беты к BTC: остаток e = r − β·r_BTC ≤ −3% и r ≤ −4% (β — по часовым ходам за прошлые 30 сут), до пяти
монет с наибольшим |e| на час; рыночные часы — не чаще раза в 6 ч. Доходы не считаются. Запуск из /home/user/mc_data."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common271 import DAY, H, PER, TMP, cooldown, crypto_perps, fmt, freq_line, hourly_close, liquid_rank, load_k, met  # noqa: E402


def build(per):
    K = load_k(per)
    P = crypto_perps(K)
    if "BTC" not in P:
        P = P + ["BTC"]
    px = {}
    for p in P:
        T, c, _ = hourly_close(K[p])
        live = K[p]["qv"] > 0
        px[p] = pd.Series(c, index=T)
    PX = pd.DataFrame(px).sort_index()
    # совокупное изменение позиций: Σ oi(T)·p(T−1ч) / Σ oi(T−1ч)·p(T−1ч) − 1 по монетам с метриками на обоих концах
    num = pd.Series(0.0, index=PX.index); den = pd.Series(0.0, index=PX.index)
    for p in P:
        m = met(per, p)
        if m is None:
            continue
        t, oi, usd = m
        s_oi = pd.Series(oi, index=t); s_px = pd.Series(np.where(oi > 0, usd / np.where(oi > 0, oi, 1), np.nan), index=t)
        s_oi = s_oi[~s_oi.index.duplicated()]; s_px = s_px[~s_px.index.duplicated()]
        o1 = s_oi.reindex(PX.index); o0 = s_oi.reindex(PX.index - H).values; p0 = s_px.reindex(PX.index - H).values
        ok = np.isfinite(o1.values) & np.isfinite(o0) & np.isfinite(p0) & (o0 > 0)
        num[ok] += (o1.values * p0)[ok]; den[ok] += (o0 * p0)[ok]
    doi = (num / den - 1).where(den > 0)
    cache = f"{TMP}/liq100_{per}.pkl"
    LR = pickle.load(open(cache, "rb")) if os.path.exists(cache) else liquid_rank(K, P, per)
    return PX, doi, LR


def run(per):
    cfg = PER[per]
    cache = f"{TMP}/mflush_{per}.pkl"
    if os.path.exists(cache):
        PX, doi, LR = pickle.load(open(cache, "rb"))
    else:
        PX, doi, LR = build(per)
        pickle.dump((PX, doi, LR), open(cache, "wb"))
    R = PX.pct_change(fill_method=None)
    adj = PX.index.to_series().diff().values == H                       # только соседние часы
    R[~adj] = np.nan
    rb = R["BTC"]
    var = rb.rolling(720, min_periods=480).var().shift(1)
    print(f"\n== {per}: часов {len(PX)}, монет {PX.shape[1]}")
    for xb in (0.01, 0.015, 0.02, 0.03):
        for need_oi in (False, True):
            mk = (rb <= -xb)
            if need_oi:
                mk &= (doi <= -0.01)
            Tm = np.array(PX.index[mk.fillna(False).values], np.int64)
            Tm = Tm[cooldown(Tm, 6 * H)]
            coin_ev = []
            for T in Tm:
                d = (int(T) - H) // DAY * DAY
                uni = LR.get(d, set()) - {"BTC"}
                if not uni:
                    continue
                k = PX.index.get_loc(T)
                lo = max(0, k - 720)
                rr = R.iloc[lo:k]
                cols = [c for c in uni if c in R.columns]
                cov = rr[cols].apply(lambda s: s.cov(rr["BTC"]))
                beta = cov / var.iloc[k]
                r_now = R.iloc[k][cols]
                e = r_now - beta * rb.iloc[k]
                sel = e[(e <= -0.03) & (r_now <= -0.04)].sort_values()[:5]
                coin_ev += [int(T)] * len(sel)
            tag = f"BTC ≤ −{xb:.1%}" + (", позиции ≤ −1%" if need_oi else "")
            print(f"{tag}: рыночных часов {fmt(freq_line(Tm, cfg['t0'], cfg['t1'], cfg['mid'], cfg['tb']))}")
            print(f"      монета-событий (e ≤ −3%, r ≤ −4%, ≤ 5 на час): {fmt(freq_line(coin_ev, cfg['t0'], cfg['t1'], cfg['mid'], cfg['tb']))}")


if __name__ == "__main__":
    for per in PER:
        run(per)
