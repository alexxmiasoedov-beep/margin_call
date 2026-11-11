"""Г3. Сдвиг спроса на займ: ставка и количество займа растут вместе (Cohen, Diether & Malloy 2007: −2,98% в следующий
месяц; чистый шок предложения цену не двигает). На монето-часах канала (s21/panel.pkl, монета в канале в час T):
  - ставка: дневная ставка займа монеты в момент T ≥ ×1,5 к медиане почасовых значений за [T − 8 сут, T − 1 сут) (s11/rates);
  - займ: BOR в T ≥ ×1,5 к BOR сутки назад (пост монеты не старше 30 мин к T − 24 ч).
Ячейки: оба растут; ставка без займа; займ без ставки; ставка растёт, а сутки назад монеты в канале не было.
Исключены ±3 суток вокруг любого объявления Binance, где упомянута монета (листинги, делистинги, аирдропы, Launchpool,
HODLer и пр., s10/ann.pkl). Исход — шорт фьючерса к рынку на 7/14/30 суток, с фандингом и комиссией, сделки 7 суток со
стопом 50%; плацебо — минус средний исход той же монеты по всем её часам в канале и минус средний исход монет канала
того же дня. Одно наблюдение на монету за сутки; t — с кластеризацией по дню. Запуск из папки с данными."""
import re
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import COIN_OF, DAY, G, H, ct, fwd, rate_jump, summ, thin
from borrow_trades import sims


def ann_windows():
    """Монета → массив времён объявлений, где она упомянута (тикер в скобках или отдельным словом заглавными)."""
    A = pd.read_pickle("s10/ann.pkl"); out = {}
    for a in A.values():
        t = int(a["ts"]) / 1000
        for tok in set(re.findall(r"\b[A-Z0-9]{2,15}\b", a.get("title", ""))):
            out.setdefault(tok, []).append(t)
    return {k: np.sort(v) for k, v in out.items()}


def bor_back(coin, T, lag=DAY):
    g = G.get(coin)
    if g is None:
        return np.nan
    k = np.searchsorted(g[:, 0], T - lag, "right") - 1
    return float(g[k, 1]) if k >= 0 and T - lag - g[k, 0] <= 1800 else np.nan


if __name__ == "__main__":
    D = pd.read_pickle("s21/panel.pkl").reset_index(drop=True)
    D["coin"] = [COIN_OF.get(s, s) for s in D.s]
    W = ann_windows()
    near = np.array([bool(len(w := W.get(c, ()))) and bool(np.any(np.abs(np.asarray(w) - T) <= 3 * DAY))
                     for c, T in zip(D.coin, D["T"])])
    D = D[~near].reset_index(drop=True)
    print(f"монето-часов в канале вне ±3 суток от объявлений по монете: {len(D):,} (убрано {near.mean():.0%})")
    D["rj"] = [rate_jump(c, T, lo_d=8, hi_d=1) for c, T in zip(D.coin, D["T"])]
    D["b24"] = [bor_back(c, T) for c, T in zip(D.coin, D["T"])]
    rate = D.rj >= 1.5; known = np.isfinite(D.rj); pres24 = np.isfinite(D.b24)
    bj = pres24 & (D.bor >= 1.5 * D.b24) & (D.bor >= 50e3)
    print(f"ставка известна у {known.mean():.0%}; рост ставки ×1,5 у {rate.mean():.1%}; монета в канале сутки назад у "
          f"{pres24.mean():.0%}; рост займа ×1,5 у {bj.mean():.1%}")
    B = thin(D)
    hs = (168, 336, 720)
    bx = {h: np.array([fwd(s, T, h) for s, T in zip(B.s, B["T"])]) for h in hs}
    cmean = {h: pd.Series(bx[h]).groupby(B.s.values).mean() for h in hs}
    dmean = {h: pd.Series(bx[h]).groupby(pd.to_datetime(B["T"].values, unit="s").date).mean() for h in hs}
    print("База (одно наблюдение на монету за сутки): " + " | ".join(f"{h // 24} сут {np.nanmean(bx[h]) * 100:+.2f}%" for h in hs))
    for nm, m in (("ставка и займ растут вместе", rate & bj), ("ставка растёт, займ нет", rate & pres24 & ~bj),
                  ("займ растёт, ставка нет", known & ~rate & bj), ("ставка растёт, сутки назад монеты в канале не было",
                                                                    rate & ~pres24)):
        d = thin(D[m]); print(f"\n{nm}: {len(d)} событий")
        for h in hs:
            x = np.array([fwd(s, T, h) for s, T in zip(d.s, d["T"])])
            xc = x - cmean[h].reindex(d.s.values).values
            xd = x - dmean[h].reindex(pd.to_datetime(d["T"].values, unit="s").date).values
            xn = np.array([fwd(s, T, h, net=True) for s, T in zip(d.s, d["T"])])
            print(f"  {h // 24:2d} сут: к рынку {summ(x, d['T'].values)} | минус та же монета {np.nanmean(xc) * 100:+.2f}% "
                  f"(t {ct(xc, d['T'])[1]:+.1f}) | минус монеты того же дня {np.nanmean(xd) * 100:+.2f}% (t {ct(xd, d['T'])[1]:+.1f}) | "
                  f"цена+фандинг {np.nanmean(xn) * 100:+.2f}%")
        R = sims(d, sl=0.5, hold_h=168)
        if len(R):
            print(f"  сделки 7 сут, стоп 50%: {summ(R.net.values, R['T'].values)}; с хеджем BTC {np.nanmean(R.hedged) * 100:+.2f}%")
