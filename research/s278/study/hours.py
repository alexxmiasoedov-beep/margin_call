"""s278 — кто торгует по часам суток UTC и сколько скачков перпа «как ⏰» приходится на каждый час. Доходов нет.

Для периода (P1 — 2024–2026, P0 — 2022–2024):
A. Ритм площадок: доля суточного оборота площадки по часам, оборот площадки к обороту перпов тех же монет,
   доля площадки V / (V + перп) — суммарная и медиана по монетам; «горб» часа — медиана доли в часе к среднему
   соседних часов.
B. Скачки перпа: рост за час ≥ 5% (закрытие к закрытию, как ⏰), перп торгуется ≥ суток; по часу суток — все скачки
   и скачки при доле группы площадок в том же часе ≥ 10 / 20 / 30%, в месяц (месяцы — только часы, где у всех площадок
   группы есть данные), по половинам; доля «пампов» (рост за 2 ч ≥ 15%, как у 🇰🇷 и 🛒).
C. Отклик внимания: после скачка (час k) доля площадки в часы k+1…k+2 к её обычной доле в те же часы суток за 7 прошлых
   дней (медиана по скачкам), по часу скачка; то же для доли в самом часе скачка.
D. Подпись обнуления без самоотбора: доля группы у монеты за прошлые 7 сут (до часа) → верхняя и нижняя трети;
   частота скачков по часу суток в каждой трети (к средней по часам) и отношение верх / низ. Если площадка обнуляет
   «изменение за день» в час R и её розница двигает перп, у «её» монет скачков в час R больше, чем у прочих.
Результат — печать и /dev/shm/s278/res_<период>.json (копия — /home/user/mc_data/s278/).
Запуск из /home/user/mc_data: python3 -I <repo>/research/s278/study/hours.py P1 [rebuild | rebuild=okx,bitget]"""
import json
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel278 import DAY, H, MONTH, NAME, OUT, PER, TMP, panel  # noqa: E402

JUMP = 0.05
THR = (0.1, 0.2, 0.3)
# группы площадок: страна / язык розницы; отдельные площадки — для подписи обнуления
GROUPS = {
    "KR": ["upbit", "bithumb"], "UP": ["upbit"], "BT": ["bithumb"],
    "CN3": ["okx", "bitget", "kucoin"], "CN4": ["okx", "bitget", "kucoin", "gate"], "CN5": ["okx", "bitget", "kucoin", "gate", "htx"],
    "OK": ["okx"], "BG": ["bitget"], "KC": ["kucoin"], "GT": ["gate"], "HX": ["htx"],
    "SEA": ["indodax", "bitkub"], "IN": ["coindcx"], "TR": ["btcturk", "binance_try"], "US": ["coinbase"],
    "EU": ["bitvavo"], "BS": ["binance_spot"], "JP": ["bitbank", "gmo"],
    "SP4": ["binance_spot", "okx", "bitget", "kucoin"],
    "MX": ["mexc"], "CN6": ["okx", "bitget", "kucoin", "gate", "htx", "mexc"],
}
GNAME = {"KR": "Корея (Upbit + Bithumb)", "UP": "Upbit", "BT": "Bithumb", "CN3": "OKX + Bitget + KuCoin",
         "CN4": "OKX + Bitget + KuCoin + Gate", "CN5": "OKX + Bitget + KuCoin + Gate + HTX", "OK": "OKX", "BG": "Bitget",
         "KC": "KuCoin", "GT": "Gate", "HX": "HTX", "SEA": "Indodax + Bitkub", "IN": "CoinDCX",
         "TR": "BTCTurk + Binance TRY", "US": "Coinbase", "EU": "Bitvavo", "BS": "спот Binance", "JP": "bitbank + GMO",
         "SP4": "спот Binance + OKX + Bitget + KuCoin", "MX": "MEXC", "CN6": "OKX + Bitget + KuCoin + Gate + HTX + MEXC"}


OPTIONAL = {"bitget"}                                          # Bitget за 2022–2024 мог не собраться — группа без него


def group_volume(VV, names):
    """Сумма оборотов площадок группы (NaN — монеты нет ни на одной) и маска часов, где данные есть у всех площадок.
    Если нет данных хотя бы одной площадки группы (кроме Bitget) — None: группа в этом периоде не считается."""
    if any(v not in VV for v in names if v not in OPTIONAL):
        return None, None
    names = [v for v in names if v in VV]
    if not names:
        return None, None
    G = np.zeros(VV[names[0]].shape, dtype=np.float64)
    listed = np.zeros(G.shape, bool)
    act = np.ones(G.shape[1], bool)
    for v in names:
        x = VV[v]
        ok = np.isfinite(x)
        G[ok] += x[ok]
        listed |= ok
        act &= ok.sum(axis=0) >= 5                              # у площадки есть данные хотя бы по 5 монетам в этот час
    G[~listed] = np.nan
    return G, act


def hour_rows(mask, hod):
    return np.array([mask[:, hod == h].sum() for h in range(24)])


def main():
    per = next((a for a in sys.argv[1:] if a in PER), "P1")
    cfg = PER[per]
    P, C, Q, F, VV, INFO = panel(per)
    VV = {v: x for v, x in VV.items() if INFO[v]["matched"] > 0}
    t0, n = cfg["t0"], C.shape[1]
    T = t0 + np.arange(n) * H                                  # начало часа k
    hod = (T // H) % 24
    Qd = Q.astype(np.float64)
    res = dict(period=cfg["name"], venues={}, groups={}, jumps={}, response={}, signature={})
    print(f"Период {cfg['name']}: перпов {len(P)}, часов {n}")
    for v, inf in INFO.items():
        print(f"  {NAME[v]:<14} монет с перпом {inf['matched']:4d}, отброшено по цене {len(inf['price_bad'])}, без цены {inf['no_price']}")

    # ---- A. ритм площадок
    pf = np.array([Qd[:, hod == h].sum() for h in range(24)])
    res["perp_frac"] = (pf / pf.sum()).tolist()
    print("\nA. Доля суточного оборота по часам UTC, %:")
    print("   час:         " + " ".join(f"{h:4d}" for h in range(24)))
    print("   перпы        " + " ".join(f"{x * 100:4.1f}" for x in res["perp_frac"]))
    for v, V in VV.items():
        ok = np.isfinite(V) & (Qd > 0)
        Vs = np.where(ok, V, 0.0)
        Qs = np.where(ok, Qd, 0.0)
        vh = np.array([Vs[:, hod == h].sum() for h in range(24)])
        qh = np.array([Qs[:, hod == h].sum() for h in range(24)])
        if vh.sum() <= 0:
            continue
        med = []
        for h in range(24):
            m = hod == h
            num = Vs[:, m].sum(axis=1)
            den = num + Qs[:, m].sum(axis=1)
            good = ok[:, m].sum(axis=1) >= 10
            med.append(float(np.median(num[good] / den[good])) if good.any() else float("nan"))
        hump = [med[h] / ((med[(h - 1) % 24] + med[(h + 1) % 24]) / 2) for h in range(24)]
        act_h = int((ok.sum(axis=0) >= 5).sum())
        res["venues"][v] = dict(frac=(vh / vh.sum()).tolist(), ratio=(vh / np.maximum(qh, 1)).tolist(),
                                share=(vh / np.maximum(vh + qh, 1)).tolist(), med_share=med, hump=hump,
                                total_ratio=float(vh.sum() / max(qh.sum(), 1)), coins=int((ok.sum(axis=1) > 0).sum()),
                                hours=act_h)
        print(f"   {NAME[v][:12]:<12} " + " ".join(f"{x * 100:4.1f}" for x in res["venues"][v]["frac"])
              + f" | к перпу {res['venues'][v]['total_ratio'] * 100:.1f}%, монет {res['venues'][v]['coins']}, сут {act_h / 24:.0f}")
    print("\n   Доля площадки V / (V + перп), медиана по монетам, %:")
    for v in res["venues"]:
        print(f"   {NAME[v][:12]:<12} " + " ".join(f"{x * 100:4.1f}" for x in res["venues"][v]["med_share"]))
    print("\n   «Горб» доли: медиана в часе к среднему соседних часов:")
    for v in res["venues"]:
        print(f"   {NAME[v][:12]:<12} " + " ".join(f"{x:4.2f}" for x in res["venues"][v]["hump"]))

    # ---- B. скачки
    R = np.full_like(C, np.nan)
    R[:, 1:] = C[:, 1:] / C[:, :-1] - 1
    age_ok = (T[None, :] - F[:, None]) >= DAY
    live = (Q > 0) & np.roll(Q > 0, 1, axis=1) & age_ok
    live[:, 0] = False
    R2 = np.full_like(C, np.nan)
    R2[:, 2:] = C[:, 2:] / C[:, :-2] - 1
    jmp = live & np.isfinite(R) & (R >= JUMP)
    half = T < cfg["mid"]
    hpm = MONTH / H                                             # часов в месяце
    J = hour_rows(jmp, hod)
    res["jumps"]["all"] = (J / (n / hpm)).tolist()
    print(f"\nB. Скачки перпа ≥ {JUMP:.0%} за час в месяц по часу UTC (начало часа); в скобках — месяцев данных группы")
    print("   час:          " + " ".join(f"{h:5d}" for h in range(24)))
    print("   все           " + " ".join(f"{x:5.1f}" for x in res["jumps"]["all"]))
    GV = {}
    for g, names in GROUPS.items():
        G, act = group_volume(VV, names)
        if G is None or act.sum() < 24 * 20:
            continue
        GV[g] = (G, act)
        S = G / np.maximum(G + Qd, 1.0)
        months = act.sum() / hpm
        rows = {}
        for th in THR:
            e = jmp & np.isfinite(G) & (S >= th) & act[None, :]
            cnt = hour_rows(e, hod)
            h1 = np.array([e[:, (hod == h) & half].sum() for h in range(24)])
            m1 = (act & half).sum() / hpm
            m2 = (act & ~half).sum() / hpm
            pump = hour_rows(e & (R2 >= 0.15), hod)
            rows[str(th)] = dict(pm=(cnt / months).tolist(), n=cnt.tolist(),
                                 pm1=(h1 / m1).tolist() if m1 > 0.5 else None,
                                 pm2=((cnt - h1) / m2).tolist() if m2 > 0.5 else None,
                                 pump_share=(pump / np.maximum(cnt, 1)).tolist())
        res["groups"][g] = dict(rows=rows, months=months, coins=int(np.isfinite(G).any(axis=1).sum()))
        for th in THR:
            print(f"   {g:<4}≥{th:.0%} ({months:4.1f}) " + " ".join(f"{x:5.1f}" for x in rows[str(th)]["pm"]))

    # ---- C. отклик внимания
    print("\nC. Отклик внимания: доля площадки в 2 ч после скачка к её обычной доле в те же часы (медиана), по часу скачка")
    print("   час:         " + " ".join(f"{h:5d}" for h in range(24)))
    ii, kk = np.nonzero(jmp)
    keep = (kk >= 24 * 7 + 1) & (kk + 3 < n)
    ii, kk = ii[keep], kk[keep]
    for g, (G, act) in GV.items():
        G0 = np.nan_to_num(G)
        cG = np.concatenate([np.zeros((G.shape[0], 1)), np.cumsum(G0, axis=1)], axis=1)
        cQ = np.concatenate([np.zeros((G.shape[0], 1)), np.cumsum(Qd, axis=1)], axis=1)

        def share(i, a, b):
            v = cG[i, b] - cG[i, a]
            q = cQ[i, b] - cQ[i, a]
            return v / np.maximum(v + q, 1.0)

        lst = np.isfinite(G[ii, kk]) & act[kk] & act[kk - 24 * 7]
        i1, k1 = ii[lst], kk[lst]
        if not len(i1):
            continue
        post = share(i1, k1 + 1, k1 + 3)
        base = np.nanmedian(np.stack([share(i1, k1 + 1 - 24 * d, k1 + 3 - 24 * d) for d in range(1, 8)]), axis=0)
        sj = share(i1, k1, k1 + 1)
        bj = np.nanmedian(np.stack([share(i1, k1 - 24 * d, k1 + 1 - 24 * d) for d in range(1, 8)]), axis=0)
        okb = base >= 0.01
        rp = post[okb] / base[okb]
        rj = sj[okb] / np.maximum(bj[okb], 1e-4)
        hh = hod[k1[okb]]
        med_p = [float(np.median(rp[hh == h])) if (hh == h).sum() >= 20 else float("nan") for h in range(24)]
        med_j = [float(np.median(rj[hh == h])) if (hh == h).sum() >= 20 else float("nan") for h in range(24)]
        cnt = [int((hh == h).sum()) for h in range(24)]
        res["response"][g] = dict(post=med_p, jump=med_j, n=cnt)
        print(f"   {g:<4} после  " + " ".join(f"{x:5.2f}" for x in med_p) + f"  (скачков {sum(cnt)})")
        print(f"   {g:<4} в час  " + " ".join(f"{x:5.2f}" for x in med_j))

    # ---- D. подпись обнуления: монеты «своей» розницы по доле за прошлые 7 сут
    print("\nD. Частота скачков по часу суток у монет верхней и нижней трети доли группы за прошлые 7 сут")
    print("   (частота в часе к средней по часам своей трети; последняя строка — отношение верх / низ)")
    print("   час:          " + " ".join(f"{h:5d}" for h in range(24)))
    for g, (G, act) in GV.items():
        G0 = np.nan_to_num(G)
        cG = np.concatenate([np.zeros((G.shape[0], 1)), np.cumsum(G0, axis=1)], axis=1)
        cQ = np.concatenate([np.zeros((G.shape[0], 1)), np.cumsum(Qd, axis=1)], axis=1)
        k = np.arange(n)
        a = np.maximum(k - 168, 0)
        v7 = cG[:, k] - cG[:, a]
        q7 = cQ[:, k] - cQ[:, a]
        s7 = v7 / np.maximum(v7 + q7, 1.0)
        valid = live & np.isfinite(G) & act[None, :] & (k[None, :] >= 168) & np.isfinite(R)
        if valid.sum() < 1000:
            continue
        lo, hi = np.quantile(s7[valid], [1 / 3, 2 / 3])
        out = {}
        for lab, m in (("top", valid & (s7 >= hi)), ("bot", valid & (s7 <= lo))):
            num = hour_rows(m & jmp, hod).astype(float)
            den = hour_rows(m, hod).astype(float)
            rate = num / np.maximum(den, 1)
            out[lab] = dict(rate=rate.tolist(), norm=(rate / rate.mean()).tolist(), jumps=num.tolist())
        out["ratio"] = (np.array(out["top"]["rate"]) / np.maximum(np.array(out["bot"]["rate"]), 1e-9)).tolist()
        out["cut"] = [float(lo), float(hi)]
        res["signature"][g] = out
        print(f"   {g:<4} верх     " + " ".join(f"{x:5.2f}" for x in out["top"]["norm"]) + f"  (доля ≥ {hi:.1%})")
        print(f"   {g:<4} низ      " + " ".join(f"{x:5.2f}" for x in out["bot"]["norm"]) + f"  (доля ≤ {lo:.1%})")
        print(f"   {g:<4} верх/низ " + " ".join(f"{x:5.2f}" for x in out["ratio"]))

    f = f"{TMP}/res_{per}.json"
    json.dump(res, open(f, "w"), ensure_ascii=False)
    shutil.copy(f, f"{OUT}/res_{per}.json")
    print(f"\nзаписано: {f}")


if __name__ == "__main__":
    main()
