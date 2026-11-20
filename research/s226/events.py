"""s226 — таблица событий «был займ» (метод — ВЫВОДЫ.md, записан до расчёта доходов) с признаками s216 и доходами шорта.

События по часовой панели канала s21/panel.pkl:
- новый займ (ev = 1) — монета появилась в канале, а за прошлые 24 ч её там не было;
- займ вырос (ev = 2) — займ за 24 ч ≥ 1,5 × займа 4 ч назад и ≥ 50 тыс. $, первый час такого роста.
Признаки — строки s224h_feat.pkl (37 признаков s216 на часовой сетке; там же шорт с хеджем y_hs* и выходы u_e_hs*).
Доход шорта без хеджа — s187/fastbt.trades, вход на закрытии часа события: s4 (стоп 10%), s24 (25%), s48 (25%),
s168 (50%), выходы — u_x_<срок>. Итог — s226_ev.pkl. Запуск из /home/user/mc_data: python3 <repo>/research/s226/events.py
Окружение (свежий отрезок D, s224b): PANEL, FEAT, OUT — панель, признаки и итог (по умолчанию s21/panel.pkl, s224h_feat.pkl,
s226_ev.pkl); свечи и фандинг — MC_K и MC_F."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
import fastbt as FB  # noqa: E402

H, DAY = 3600, 86400
OUTS = {"s4": (0.10, 4), "s24": (0.25, 24), "s48": (0.25, 48), "s168": (0.50, 168)}


def events():
    P = pd.read_pickle(os.environ.get("PANEL", "s21/panel.pkl")).sort_values(["s", "T"]).reset_index(drop=True)
    gap = P.groupby("s")["T"].diff()
    new = gap.isna() | (gap > 24 * H)
    acc = P.in4 & (P.bor >= 1.5 * P.bor4) & (P.bor >= 50e3)
    prev_acc = acc.groupby(P.s).shift(1).fillna(False).astype(bool) & (gap == H)
    grew = acc & ~prev_acc
    E = P.loc[new | grew, ["s", "T"]].copy()
    E["ev"] = np.where(new[new | grew], 1, 2)
    return E


def main():
    E = events()
    F = pd.read_pickle(os.environ.get("FEAT", "s224h_feat.pkl"))
    X = E.merge(F, on=["s", "T"], how="left").sort_values(["T", "s"]).reset_index(drop=True)
    for k in OUTS:
        X[k] = np.nan; X["u_x_" + k] = np.nan
    for s, idx in X.groupby("s").groups.items():
        if s not in FB.K:
            continue
        t = FB.K[s]["t"].astype(np.int64)
        pos = np.asarray(idx)
        st = X.loc[idx, "T"].to_numpy(np.int64) - 900
        I = np.searchsorted(t, st)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == st)
        lo, _ = FB.live(s)
        ok &= t[np.minimum(I, len(t) - 1)] >= lo + DAY
        if not ok.any():
            continue
        for k, (sl, hold) in OUTS.items():
            okt, net, _, _, tend = FB.trades(s, I[ok], sl, hold, -1)
            X.loc[pos[ok], k] = np.where(okt, net, np.nan)
            X.loc[pos[ok], "u_x_" + k] = np.where(okt, tend, np.nan)
    X.to_pickle(os.environ.get("OUT", "s226_ev.pkl"))
    print("событий", len(X), "| новый займ", int((X.ev == 1).sum()), "| займ вырос", int((X.ev == 2).sum()))
    print("доход посчитан:", {k: int(X[k].notna().sum()) for k in OUTS})


if __name__ == "__main__":
    main()
