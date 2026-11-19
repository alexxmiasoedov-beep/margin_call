"""s187 часть 2 — доход 120 стратегий-индикаторов (30 скриптов × 1h/4h × лонг/шорт) на одном периоде; правила —
ВЫВОДЫ.md (записаны до расчёта). Сигналы — /home/user/mc_data/s187/signals_<период>_<tf>.pkl
({скрипт: {монета: (времена buy, времена sell)}}, время — закрытие бара). Вход — закрытие 15-мин свечи, кончающейся
в закрытие бара; основной выход — 24 бара, стоп 25% (fastbt); выход для отчёта — до обратного сигнала, ≤ 7 сут, без
стопа; неперекрытие по скрипту, tf, стороне и монете. Хранится сводка по суткам: число, суммы дохода, хеджа, разности
с плацебо, выхода по обратному сигналу и стопов — этого хватает для t с кластерами по дню.
Запуск из /home/user/mc_data: [MC_K=… MC_F=…] python3 <repo>/research/s187/bt.py <период>  → s187_bt_<период>.pkl"""
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fastbt as FB  # noqa: E402

DAY, OUT, FEE = 86400, "/home/user/mc_data", 0.001
TF = {"1h": 3600, "4h": 14400}
HOLD_BARS = 24
MAX_OPP = 7 * DAY


def opp_exit(coin, t, c, I, T, opp, side, ft, cs):
    """Выход по обратному сигналу (≤ 7 сут) без стопа: доход после комиссии и фандинга; NaN — нет свечи выхода."""
    opp = np.sort(np.asarray(opp, np.int64))
    k = np.searchsorted(opp, T, "right")
    To = np.where(k < len(opp), opp[np.minimum(k, max(len(opp) - 1, 0))] if len(opp) else T + MAX_OPP, T + MAX_OPP)
    To = np.where(To - T > MAX_OPP, T + MAX_OPP, To)
    j = np.searchsorted(t, To - 900)
    ok = (j < len(t)) & (t[np.minimum(j, len(t) - 1)] == To - 900)
    lo, hi = FB.live(coin)
    ok &= (To - 900 <= hi)
    out = np.full(len(I), np.nan)
    if not ok.any():
        return out
    jj = j[ok]; ii = I[ok]
    price = side * (c[jj] / c[ii] - 1)
    if len(ft):
        f = cs[np.searchsorted(ft, To[ok], "right")] - cs[np.searchsorted(ft, t[ii] + 900, "right")]
    else:
        f = 0.0
    out[ok] = price - side * f - FEE
    return out


def run(per):
    K = FB.K
    rec = {}
    t_start = time.time()
    for tf, sec in TF.items():
        S = pickle.load(open(f"{OUT}/s187/signals_{per}_{tf}.pkl", "rb"))
        hold_h = HOLD_BARS * sec / 3600
        for si, (script, coins) in enumerate(S.items()):
            for coin, (bts, sts) in coins.items():
                if coin not in K:
                    continue
                a = K[coin]
                t = a["t"].astype(np.int64); c = a["c"].astype(float)
                fr = FB.funding(coin)
                ft = fr[:, 0].astype(np.int64) if len(fr) else np.zeros(0, np.int64)
                cs = np.r_[0.0, np.cumsum(fr[:, 1])] if len(fr) else np.zeros(1)
                for side, times, opp in ((1, bts, sts), (-1, sts, bts)):
                    if times is None or not len(times):
                        continue
                    T = np.sort(np.asarray(times, np.int64))
                    I = np.searchsorted(t, T - 900)
                    ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == T - 900) & (I >= 96)
                    T, I = T[ok], I[ok]
                    if not len(T):
                        continue
                    keep, last = [], -1
                    step = int(hold_h * 3600)
                    for k_, x in enumerate(T):
                        if x >= last:
                            keep.append(k_); last = x + step
                    T, I = T[keep], I[keep]
                    okt, net, stp, bars, tend = FB.trades(coin, I, 0.25, hold_h, side)
                    if not okt.any():
                        continue
                    T, I, net, stp, tend = T[okt], I[okt], net[okt], stp[okt], tend[okt]
                    mv = FB.alt_mv(t[I] + 900, tend)
                    hed = net - side * mv
                    pl = FB.placebo(coin, I, 0.25, hold_h, side)
                    oe = opp_exit(coin, t, c, I, T, opp, side, ft, cs)
                    d = (T // DAY) * DAY
                    key = (script, tf, side)
                    df = pd.DataFrame(dict(d=d, n=1, s=net, s2=net * net, st=stp.astype(int),
                                           nh=np.isfinite(hed).astype(int), sh=np.nan_to_num(hed),
                                           npl=np.isfinite(pl).astype(int), sdpl=np.nan_to_num(net - pl),
                                           no=np.isfinite(oe).astype(int), so=np.nan_to_num(oe)))
                    rec.setdefault(key, []).append(df.groupby("d").sum())
            print(f"{per} {tf} {si + 1}/{len(S)} {script} за {time.time() - t_start:.0f} с", flush=True)
    out = {k: pd.concat(v).groupby(level=0).sum() for k, v in rec.items()}
    pickle.dump(out, open(f"{OUT}/s187_bt_{per}.pkl", "wb"))
    print(per, "стратегий", len(out), "готово за", round(time.time() - t_start), "с", flush=True)


if __name__ == "__main__":
    run(sys.argv[1])
