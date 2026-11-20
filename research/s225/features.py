"""s225 — 12 признаков «относительно своей истории монеты» за прошлые 30 сут (метод — ВЫВОДЫ.md, записан до расчёта) к
наблюдениям s223 (сетка 4 ч, 37 признаков, исходы с хеджем). Только данные до T; меньше 48 точек в окне — пусто.
- займ (часовая панель s21, часы в канале): zbor, zrep — ln(значение / медиана), znet — (набор − среднее) / ст. откл.;
- ставка займа (s11/rates, почасовой ряд как в s216): zrate — ln(ставка / медиана);
- цена и оборот (15-мин свечи): zr4, zr24 — ln-ход за 4 / 24 ч к ст. откл. таких ходов (точки каждый час);
  zqv — ln(оборот за 24 ч / медиана 30 суточных оборотов до T);
- позиции (s22/metrics_full, строка не позже T − 1 ч, как в s216): zoi4, zoi24 — ln-изменение OI к ст. откл. таких изменений;
  zlsr, zlsrt — (доля счетов / топ-позиций в лонге − среднее) / ст. откл.;
- фандинг: zf — (последнее начисление на 8 ч − среднее) / ст. откл. начислений за 30 сут.
Итог — s225_feat.pkl. Запуск из /home/user/mc_data: python3 <repo>/research/s225/features.py
Окружение (s224b, отрезок D): IN и OUT — файлы входа и итога (по умолчанию s223_feat.pkl и s225_feat.pkl)."""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s216", "s187"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
import features as F216  # noqa: E402  (s216: coin_of)
import fastbt as FB  # noqa: E402

H, DAY, W = 3600, 86400, 30 * 86400
MINP = 48
NEW = ("zbor", "zrep", "znet", "zrate", "zr4", "zr24", "zqv", "zoi4", "zoi24", "zlsr", "zlsrt", "zf")


def win(t, T, lo_off=W, hi_off=0):
    """Индексы точек t (отсортированы) в окне [T − lo_off − hi_off, T − hi_off)."""
    return int(np.searchsorted(t, T - hi_off - lo_off, "left")), int(np.searchsorted(t, T - hi_off, "left"))


def zstd(x):
    x = x[np.isfinite(x)]
    return float(np.std(x)) if len(x) >= MINP else np.nan


def hourly_close(s):
    a = FB.K[s]; t = a["t"].astype(np.int64) + 900; c = a["c"].astype(float); qv = a["qv"].astype(float)
    m = t % H == 0
    cs = np.r_[0.0, np.cumsum(qv)]
    q24 = np.where(np.arange(len(t)) >= 95, cs[np.arange(len(t)) + 1] - cs[np.maximum(np.arange(len(t)) - 95, 0)], np.nan)
    return t[m], c[m], t, q24


def main():
    G = pd.read_pickle(os.environ.get("IN", "s223_feat.pkl")).sort_values(["T", "s"]).reset_index(drop=True)
    P = pd.read_pickle("s21/panel.pkl")
    out = {k: np.full(len(G), np.nan) for k in NEW}
    for s, idx in G.groupby("s").groups.items():
        pos = np.asarray(idx); TT = G.loc[idx, "T"].to_numpy(np.int64)
        # займ: часы в канале
        p = P[P.s == s].sort_values("T"); tp = p["T"].to_numpy(np.int64)
        bor, rep = p.bor.to_numpy(float), p.rep.to_numpy(float); net = bor - rep
        for j, T in zip(pos, TT):
            a, b = win(tp, T)
            if b - a >= MINP:
                mb, mr = np.median(bor[a:b]), np.median(rep[a:b])
                x = G.at[j, "bor"]; y = G.at[j, "rep"]
                out["zbor"][j] = np.log(x / mb) if x > 0 and mb > 0 else np.nan
                out["zrep"][j] = np.log(y / mr) if y > 0 and mr > 0 else np.nan
                sd = np.std(net[a:b])
                out["znet"][j] = (x - y - np.mean(net[a:b])) / sd if sd > 0 else np.nan
        # ставка займа: почасовой ряд, последний полный час до T (как s216.rate_features)
        rp = f"s11/rates/{F216.coin_of(s)}.csv"
        if os.path.exists(rp):
            r = np.loadtxt(rp, delimiter=",", ndmin=2)
            if len(r):
                hrs = np.arange(int(r[0, 0]) // H * H, int(r[-1, 0]) // H * H + H, H)
                v = r[np.maximum(np.searchsorted(r[:, 0], hrs, "right") - 1, 0), 1]
                for j, T in zip(pos, TT):
                    k = int(np.searchsorted(hrs, T - H, "right")) - 1
                    if k >= MINP:
                        med = np.median(v[max(k - 720, 0):k])
                        out["zrate"][j] = np.log(v[k] / med) if v[k] > 0 and med > 0 else np.nan
        # цена и оборот
        if s in FB.K:
            th, ch, t15, q24 = hourly_close(s)
            l4 = np.full(len(th), np.nan); l4[4:] = np.log(ch[4:] / ch[:-4])
            l24 = np.full(len(th), np.nan); l24[24:] = np.log(ch[24:] / ch[:-24])
            for j, T in zip(pos, TT):
                a, b = win(th, T)
                s4, s24 = zstd(l4[a:b]), zstd(l24[a:b])
                r4, r24 = G.at[j, "r4"], G.at[j, "r24"]
                out["zr4"][j] = np.log1p(r4) / s4 if s4 and s4 > 0 and np.isfinite(r4) else np.nan
                out["zr24"][j] = np.log1p(r24) / s24 if s24 and s24 > 0 and np.isfinite(r24) else np.nan
                d = [T - k * DAY for k in range(1, 31)]
                ii = np.searchsorted(t15, d, "right") - 1
                okd = (ii >= 0) & (t15[np.maximum(ii, 0)] == d)
                qs = q24[ii[okd]]
                qs = qs[np.isfinite(qs) & (qs > 0)]
                qn = G.at[j, "qv24"]
                out["zqv"][j] = np.log(qn / np.median(qs)) if len(qs) >= 20 and qn > 0 else np.nan
        # позиции
        fl = sorted(glob.glob(f"s22/metrics_full/{s}/*.npy"))
        if fl:
            M = np.vstack([x for x in (np.load(f) for f in fl) if len(x)])
            M = M[np.argsort(M[:, 0])]
            tm = M[:, 0].astype(np.int64); oi = M[:, 1]
            o4 = np.full(len(tm), np.nan); o24 = np.full(len(tm), np.nan)
            okp = (tm[4:] - tm[:-4] == 4 * H) & (oi[:-4] > 0) & (oi[4:] > 0)
            o4[4:][okp] = np.log(oi[4:][okp] / oi[:-4][okp])
            okq = (tm[24:] - tm[:-24] == DAY) & (oi[:-24] > 0) & (oi[24:] > 0)
            o24[24:][okq] = np.log(oi[24:][okq] / oi[:-24][okq])
            for j, T in zip(pos, TT):
                a, b = win(tm, T - H)
                if b - a < MINP:
                    continue
                s4, s24 = zstd(o4[a:b]), zstd(o24[a:b])
                d4, d24 = G.at[j, "doi4"], G.at[j, "doi24"]
                out["zoi4"][j] = np.log1p(d4) / s4 if s4 and s4 > 0 and np.isfinite(d4) and d4 > -1 else np.nan
                out["zoi24"][j] = np.log1p(d24) / s24 if s24 and s24 > 0 and np.isfinite(d24) and d24 > -1 else np.nan
                for col, name, cur in ((5, "zlsr", "lsr_acc"), (4, "zlsrt", "lsr_top")):
                    x = M[a:b, col]; x = x[np.isfinite(x)]
                    c = G.at[j, cur]
                    if len(x) >= MINP and np.std(x) > 0 and np.isfinite(c):
                        out[name][j] = (c - x.mean()) / x.std()
        # фандинг
        fr = FB.funding(s)
        if len(fr) > 1:
            ft = fr[:, 0].astype(np.int64); gap = np.r_[np.nan, np.diff(ft) / H]
            f8 = np.where(gap > 0, fr[:, 1] * 8 / gap, np.nan)
            for j, T in zip(pos, TT):
                a, b = int(np.searchsorted(ft, T - W, "right")), int(np.searchsorted(ft, T, "right"))
                x = f8[a:b]; x = x[np.isfinite(x)]
                c = G.at[j, "f8"]
                if len(x) >= MINP and np.std(x) > 0 and np.isfinite(c):
                    out["zf"][j] = (c - x.mean()) / x.std()
    for k in NEW:
        G[k] = out[k]
    G.to_pickle(os.environ.get("OUT", "s225_feat.pkl"))
    print("готово:", G.shape, "заполнено:", {k: round(float(np.isfinite(G[k]).mean()), 2) for k in NEW}, flush=True)


if __name__ == "__main__":
    main()
