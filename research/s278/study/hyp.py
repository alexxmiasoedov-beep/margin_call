"""s278 — частоты событий гипотез (гипотезы записаны до расчёта доходов; доходы здесь не считаются).

Событие: перп за час [R, R+1) UTC вырос на ≥ 5% (закрытие к закрытию), перп торгуется ≥ суток; доля группы площадок
в том же часе V / (V + перп) ≥ порога (и, если задано, ≥ k × её доли у монеты за прошлые 7 сут); условие по Корее:
«none» — у монеты нет рынка к воне, «max10» — доля Upbit + Bithumb в часе < 10%. Вход для будущей проверки — шорт
на закрытии часа R + 1. Здесь — частота в месяц (весь период и половины), число монет, та же частота в другие часы
(«подпись часа»: час R к среднему остальных), пересечения: с ⏰ в те же сутки, с пампом 🇰🇷/🛒 (рост за 2 ч ≥ 15%),
скачки ≥ 10%. Месяцы — только часы, где у всех площадок группы есть данные.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s278/study/hyp.py [P1|P0]"""
import json
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hours import GROUPS, group_volume  # noqa: E402
from panel278 import DAY, H, MONTH, OUT, PER, TMP, panel  # noqa: E402

RULES = [
    ("Г1", "16 UTC (полночь UTC+8), OKX+Bitget+KuCoin+Gate ≥ 10%, Корея < 10%", dict(hour=16, group="CN4", thr=0.10, kr="max10")),
    ("Г1а", "то же без Gate (история 2 года)", dict(hour=16, group="CN3", thr=0.10, kr="max10")),
    ("Г1б", "то же, доля Азии-CEX ≥ 5% и ≥ 2× нормы за 7 сут", dict(hour=16, group="CN4", thr=0.05, rel=2.0, kr="max10")),
    ("Г1в", "16 UTC, весь спот без Кореи (Binance + OKX + Bitget + KuCoin) ≥ 35%, Корея < 10%", dict(hour=16, group="SP4", thr=0.35, kr="max10")),
    ("Г2", "00 UTC без рынка к воне, OKX+Bitget+KuCoin+Gate ≥ 10%", dict(hour=0, group="CN4", thr=0.10, kr="none")),
    ("Г2а", "то же без Gate", dict(hour=0, group="CN3", thr=0.10, kr="none")),
    ("Г2в", "00 UTC без рынка к воне, весь спот без Кореи ≥ 35%", dict(hour=0, group="SP4", thr=0.35, kr="none")),
    ("Г3", "00 UTC без рынка к воне, спот Binance ≥ 26%", dict(hour=0, group="BS", thr=0.26, kr="none")),
    ("Г4", "15 UTC (полночь Кореи и Японии), Upbit ≥ 20%", dict(hour=15, group="UP", thr=0.20, kr="any")),
    ("Г5", "17 UTC (полночь UTC+7), Indodax + Bitkub ≥ 5%", dict(hour=17, group="SEA", thr=0.05, kr="any")),
    ("Г6", "18 UTC (полночь Индии — 18:30), CoinDCX ≥ 1%", dict(hour=18, group="IN", thr=0.01, kr="any")),
    ("Г7", "21 UTC (полночь Турции; сутки GMO), BTCTurk + Binance TRY ≥ 20%", dict(hour=21, group="TR", thr=0.20, kr="any")),
    ("Г8", "04 UTC (полночь США), Coinbase ≥ 20%", dict(hour=4, group="US", thr=0.20, kr="any")),
    ("Г9", "21 UTC (сутки GMO), bitbank + GMO ≥ 2%", dict(hour=21, group="JP", thr=0.02, kr="any")),
    ("⏰", "контроль: 00 UTC, Upbit + Bithumb ≥ 20%", dict(hour=0, group="KR", thr=0.20, kr="any")),
]


def main():
    per = next((a for a in sys.argv[1:] if a in PER), "P1")
    cfg = PER[per]
    P, C, Q, F, VV, INFO = panel(per)
    VV = {v: x for v, x in VV.items() if INFO[v]["matched"] > 0}
    t0, n = cfg["t0"], C.shape[1]
    T = t0 + np.arange(n) * H
    hod = (T // H) % 24
    Qd = Q.astype(np.float64)
    R = np.full_like(C, np.nan)
    R[:, 1:] = C[:, 1:] / C[:, :-1] - 1
    R2 = np.full_like(C, np.nan)
    R2[:, 2:] = C[:, 2:] / C[:, :-2] - 1
    live = (Q > 0) & np.roll(Q > 0, 1, axis=1) & ((T[None, :] - F[:, None]) >= DAY)
    live[:, 0] = False
    jmp = live & np.isfinite(R) & (R >= 0.05)
    KR, _ = group_volume(VV, GROUPS["KR"])
    SK = KR / np.maximum(KR + Qd, 1.0) if KR is not None else None
    o9 = jmp & (hod[None, :] == 0) & (np.nan_to_num(SK) >= 0.2) if SK is not None else None
    o9_days = set()
    if o9 is not None:
        oi, ok_ = np.nonzero(o9)
        o9_days = set(zip(oi.tolist(), (T[ok_] // DAY).tolist()))
    cQ = np.concatenate([np.zeros((len(P), 1)), np.cumsum(Qd, axis=1)], axis=1)
    k_all = np.arange(n)
    a7 = np.maximum(k_all - 168, 0)
    half = T < cfg["mid"]
    hpm = MONTH / H
    out = {}
    print(f"Период {cfg['name']}")
    print(f"{'':<5} {'мес.':>5} {'в мес.':>7} {'половины':>11} {'монет':>6} {'час R / др.':>12} {'доля R / др.':>12} {'⏰':>5} {'памп':>5} {'≥10%':>5}")
    for code, title, r in RULES:
        G, act = group_volume(VV, GROUPS[r["group"]])
        if G is None or act.sum() < 24 * 20:
            print(f"{code:<5} нет данных — {title}")
            continue
        S = G / np.maximum(G + Qd, 1.0)
        cond = jmp & act[None, :] & np.isfinite(G) & (S >= r["thr"])
        if r.get("rel"):
            cG = np.concatenate([np.zeros((len(P), 1)), np.cumsum(np.nan_to_num(G), axis=1)], axis=1)
            v7 = cG[:, k_all] - cG[:, a7]
            q7 = cQ[:, k_all] - cQ[:, a7]
            s7 = v7 / np.maximum(v7 + q7, 1.0)
            cond &= (S >= r["rel"] * s7) & (k_all[None, :] >= 168)
        if SK is not None and r["kr"] == "none":
            cond &= ~np.isfinite(KR)
        elif SK is not None and r["kr"] == "max10":
            cond &= ~(np.nan_to_num(SK) >= 0.10)
        months = act.sum() / hpm
        by_h = np.array([cond[:, hod == h].sum() for h in range(24)]) / months
        # доля событий среди всех скачков монет, торгующихся на площадках группы (без условия доли): убирает разную
        # «скачковость» часов (сессия США, начисления фандинга)
        base_j = jmp & act[None, :] & np.isfinite(G)
        if SK is not None and r["kr"] == "none":
            base_j &= ~np.isfinite(KR)
        elif SK is not None and r["kr"] == "max10":
            base_j &= ~(np.nan_to_num(SK) >= 0.10)
        fr_h = np.array([cond[:, hod == h].sum() / max(base_j[:, hod == h].sum(), 1) for h in range(24)])
        ev = cond & (hod[None, :] == r["hour"])
        m1 = (act & half).sum() / hpm
        m2 = (act & ~half).sum() / hpm
        ii, kk = np.nonzero(ev)
        cnt = len(ii)
        h1 = int(ev[:, half].sum())
        ov9 = sum((i, d) in o9_days for i, d in zip(ii.tolist(), (T[kk] // DAY).tolist()))
        other = np.delete(by_h, r["hour"]).mean()
        res = dict(title=title, rule=r, months=months, n=cnt, pm=cnt / months,
                   pm1=h1 / m1 if m1 > 0.5 else None, pm2=(cnt - h1) / m2 if m2 > 0.5 else None,
                   coins=len(set(ii.tolist())), by_hour=by_h.tolist(), hour_vs_other=float(by_h[r["hour"]] / max(other, 1e-9)),
                   frac_by_hour=fr_h.tolist(), frac_vs_other=float(fr_h[r["hour"]] / max(np.delete(fr_h, r["hour"]).mean(), 1e-9)),
                   o9=ov9, pump=int((ev & (R2 >= 0.15)).sum()), big=int((ev & (R >= 0.10)).sum()))
        out[code] = res
        hs = f"{res['pm1']:.1f} / {res['pm2']:.1f}" if res["pm1"] is not None and res["pm2"] is not None else "—"
        print(f"{code:<5} {months:5.1f} {res['pm']:7.1f} {hs:>11} {res['coins']:6d} {res['hour_vs_other']:12.2f}"
              f" {res['frac_vs_other']:12.2f} {ov9:5d} {res['pump']:5d} {res['big']:5d}   {title}")
    print("\nЧастота тех же условий по часам суток, в месяц:")
    print("      " + " ".join(f"{h:5d}" for h in range(24)))
    for code, res in out.items():
        print(f"{code:<5} " + " ".join(f"{x:5.1f}" for x in res["by_hour"]))
    print("\nДоля событий среди скачков монет группы по часам суток, %:")
    print("      " + " ".join(f"{h:5d}" for h in range(24)))
    for code, res in out.items():
        print(f"{code:<5} " + " ".join(f"{x * 100:5.1f}" for x in res["frac_by_hour"]))
    f = f"{TMP}/hyp_{per}.json"
    json.dump(out, open(f, "w"), ensure_ascii=False)
    shutil.copy(f, f"{OUT}/hyp_{per}.json")


if __name__ == "__main__":
    main()
