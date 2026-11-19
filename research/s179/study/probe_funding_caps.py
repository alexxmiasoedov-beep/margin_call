"""s179 — упор фандинга Binance в потолок и пол: частота по трём периодам, без доходов и цен после событий.

Запуск: python3 -I probe_funding_caps.py <папка данных>   (по умолчанию /home/user/mc_data)

Данные: s117/fund_2020.pkl (10.2020–09.2022), s117/fund_oos.pkl (10.2022–09.2024), s2/fund2y.pkl (10.2024–09.2026):
словарь «монета → массив [время, интервал в часах, ставка]». Премия к индексу — s12/prem.pkl (15-мин закрытия,
только 10.2024–10.2026); премия ранних периодов — probe_unpaid_old.py; снимок правил — snapshot_rules.py.

Что считаем:
1) начисления точно на известной границе Binance (|ставка| ∈ KNOWN, допуск 5e-9) — «упор»; отдельно пол и потолок;
2) эпизоды упора: подряд идущие упоры одной монеты с разрывом < 24 ч; длительность эпизода;
3) глубокие ставки в 8-часовом эквиваленте (ставка · 8 / интервал) ≤ −0,5% и ≤ −1% — для сравнения с упором;
4) смена интервала на 1 ч после упора (правило с 02.05.2025);
5) 2024–2026: «неоплаченная премия» — средняя премия интервала (линейные веса, как у Binance) против пола:
   F* = [P̄ + clamp(0,01% − P̄, ±0,05%)] / (8/N); недоплата = F* − пол (в п. п. за интервал).
Правило Binance до 11.05.2021 — подвижная граница (прошлая ставка ± 0,75·MMR), упор по точному значению там не виден.
"""
import os
import pickle
import sys
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
NONCRYPTO = {"XAU", "XAG", "XPT", "XPD", "COPPER", "NATGAS", "CL", "BZ", "AAPL", "MSFT", "AMD", "QQQ", "SPY", "TSM",
             "BABA", "AMC", "CVX", "DIA", "AVGO", "QCOM", "ANET", "PAXG", "USDC", "FDUSD", "TUSD", "USDP", "BTCDOM",
             "DEFI", "BLUEBIRD", "HUT", "APLD", "GPRO", "SKHY", "OPENAI", "ANTHROPIC", "SPCX", "POPMART", "UNITREE",
             "MARSCOIN", "USAR", "SLX", "ESP"}
MAJORS = {"BTC", "ETH"}
KNOWN = np.array([0.003, 0.00375, 0.0045, 0.004875, 0.005, 0.0075, 0.009, 0.01, 0.015, 0.01875, 0.02, 0.025, 0.03,
                  0.04, 0.05])
PERIODS = [("2020–2022", "s117/fund_2020.pkl", "2020-10-01", "2022-10-01"),
           ("2022–2024", "s117/fund_oos.pkl", "2022-10-01", "2024-10-01"),
           ("2024–2026", "s2/fund2y.pkl", "2024-10-01", "2026-10-01")]
kind = pd.read_pickle(os.path.join(D, "s12/perp_kind.pkl"))
BAD = (set(kind.get("tradfi", set())) | NONCRYPTO) - MAJORS


def ts(s):
    return pd.Timestamp(s, tz="UTC").timestamp()


def at_known(r):
    a = np.abs(r)
    return (np.min(np.abs(a[:, None] - KNOWN[None, :]), axis=1) < 5e-9) & (a >= 0.003)


def per_month(times, t0, t1):
    """Среднее, медиана, мин и макс числа событий по календарным месяцам периода (пустые месяцы — нули)."""
    months = pd.period_range(pd.Timestamp(t0, unit="s"), pd.Timestamp(t1 - 1, unit="s"), freq="M")
    c = pd.Series(pd.to_datetime(np.asarray(times, float), unit="s").to_period("M")).value_counts() if len(times) else pd.Series(dtype=int)
    v = np.array([int(c.get(m, 0)) for m in months])
    return v.mean(), np.median(v), v.min(), v.max(), len(months)


def fmt(name, times, t0, t1):
    m, med, lo, hi, n = per_month(times, t0, t1)
    return f"  {name}: всего {len(times)}, в месяц среднее {m:.1f}, медиана {med:.0f}, мин {lo}, макс {hi}"


def main():
    prem = None
    out_unpaid = []
    for name, path, a, b in PERIODS:
        t0, t1 = ts(a), ts(b)
        F = pickle.load(open(os.path.join(D, path), "rb"))
        syms = [s for s in F if s not in BAD and not s.endswith("USDC") and len(F[s])]
        floor_ev, cap_ev, deep05, deep1 = [], [], [], []
        floor_coin_days, cap_coin_days = set(), set()
        episodes, ep_len_h, ep_n = [], [], []
        cap_episodes = []
        coins_floor = defaultdict(set)
        switch_after_floor, floor_after_rule = 0, 0
        unknown_rep = Counter()
        vals_floor = Counter()
        sett_total = 0
        for s in syms:
            x = F[s]
            x = x[(x[:, 0] >= t0) & (x[:, 0] < t1)]
            if not len(x):
                continue
            sett_total += len(x)
            t, n, r = x[:, 0], x[:, 1], x[:, 2]
            k = at_known(r)
            fl = k & (r < 0)
            cp = k & (r > 0)
            # повторяющиеся крайние значения вне списка (на случай неизвестных границ)
            rr = np.round(r, 7)
            cnt = Counter(rr[np.abs(rr) >= 0.003].tolist())
            for v, c in cnt.items():
                if c >= 3 and not (np.min(np.abs(abs(v) - KNOWN)) < 5e-9):
                    unknown_rep[(s, v)] = c
            e8 = r * 8.0 / np.where(n > 0, n, 8.0)
            deep05 += list(t[e8 <= -0.005])
            deep1 += list(t[e8 <= -0.01])
            for i in np.flatnonzero(fl):
                vals_floor[round(float(r[i]), 6)] += 1
                floor_ev.append(t[i])
                floor_coin_days.add((s, int(t[i] // 86400)))
                coins_floor[pd.Timestamp(t[i], unit="s").to_period("M")].add(s)
                if t[i] >= ts("2025-05-02 08:00") and i + 1 < len(t):
                    floor_after_rule += 1
                    if n[i + 1] == 1 and n[i] > 1:
                        switch_after_floor += 1
            for i in np.flatnonzero(cp):
                cap_ev.append(t[i])
                cap_coin_days.add((s, int(t[i] // 86400)))
            # эпизоды пола
            idx = np.flatnonzero(fl)
            if len(idx):
                start = idx[0]; last = idx[0]; cnt_ep = 1
                for j in idx[1:]:
                    if t[j] - t[last] < 86400:
                        last = j; cnt_ep += 1
                    else:
                        episodes.append((s, t[start])); ep_len_h.append((t[last] - t[start]) / 3600 + n[start]); ep_n.append(cnt_ep)
                        start = j; last = j; cnt_ep = 1
                episodes.append((s, t[start])); ep_len_h.append((t[last] - t[start]) / 3600 + n[start]); ep_n.append(cnt_ep)
            idc = np.flatnonzero(cp)
            if len(idc):
                last = -1e18
                for j in idc:
                    if t[j] - last >= 86400:
                        cap_episodes.append((s, t[j]))
                    last = t[j]
            # неоплаченная премия (только где есть премия)
            if name == "2024–2026":
                if prem is None:
                    prem = pickle.load(open(os.path.join(D, "s12/prem.pkl"), "rb"))
                if s in prem:
                    pt, pv = prem[s]
                    for i in np.flatnonzero(fl | cp):
                        N = n[i]
                        lo_t = t[i] - N * 3600
                        sel = (pt >= lo_t) & (pt <= t[i] - 900)
                        if sel.sum() < max(2, int(N * 4 * 0.75)):
                            continue
                        p = pv[sel].astype(float)
                        if N > 1:
                            w = np.arange(1, len(p) + 1, dtype=float)
                            pbar = float((w * p).sum() / w.sum())
                        else:
                            pbar = float(p.mean())
                        fstar = (pbar + np.clip(0.0001 - pbar, -0.0005, 0.0005)) / (8.0 / N)
                        out_unpaid.append((s, t[i], N, r[i], fstar, float(p[-1])))
        print(f"== {name}: монет {len(syms)}, начислений {sett_total}")
        print(fmt("упор в пол (начисления)", floor_ev, t0, t1))
        print(fmt("упор в пол (монето-сутки)", [d * 86400 for _, d in floor_coin_days], t0, t1))
        print(fmt("эпизоды упора в пол (разрыв ≥ 24 ч)", [e[1] for e in episodes], t0, t1))
        if ep_len_h:
            print(f"    длина эпизода, ч: медиана {np.median(ep_len_h):.0f}, 75% {np.percentile(ep_len_h, 75):.0f}, "
                  f"90% {np.percentile(ep_len_h, 90):.0f}; начислений в эпизоде: медиана {np.median(ep_n):.0f}, "
                  f"доля эпизодов из одного начисления {np.mean(np.array(ep_n) == 1):.0%}")
        nc = [len(v) for v in coins_floor.values()]
        print(f"    разных монет на полу за месяц: медиана {np.median(nc) if nc else 0:.0f}, макс {max(nc) if nc else 0}")
        print(f"    значения пола: {vals_floor.most_common(8)}")
        print(fmt("упор в потолок (начисления)", cap_ev, t0, t1))
        print(fmt("эпизоды упора в потолок", [e[1] for e in cap_episodes], t0, t1))
        print(fmt("ставка в 8-ч эквиваленте ≤ −0,5% (начисления)", deep05, t0, t1))
        print(fmt("ставка в 8-ч эквиваленте ≤ −1% (начисления)", deep1, t0, t1))
        if floor_after_rule:
            print(f"    после 02.05.2025: упоров в пол {floor_after_rule}, за ними перевод на 1 ч {switch_after_floor} "
                  f"({switch_after_floor / floor_after_rule:.0%})")
        if unknown_rep:
            print(f"    повторяющиеся крайние значения вне списка границ (≥ 3 раз у монеты): {len(unknown_rep)}; "
                  f"примеры {list(unknown_rep.items())[:6]}")
        # по годам — для смены режима
        yrs = Counter(pd.to_datetime(np.array(floor_ev, float), unit="s").year) if floor_ev else {}
        print(f"    упоров в пол по годам: {dict(sorted(yrs.items()))}")
        del F
    if out_unpaid:
        u = pd.DataFrame(out_unpaid, columns=["s", "t", "N", "r", "fstar", "p_last"])
        fl = u[u.r < 0].copy()
        fl["short"] = fl.fstar - fl.r            # < 0 — премия глубже, чем пол разрешает
        print("== 2024–2026, неоплаченная премия на начислениях с упором в пол (премия есть у "
              f"{len(fl)} из начислений)")
        for N in sorted(fl.N.unique()):
            g = fl[fl.N == N]
            print(f"  интервал {N:.0f} ч: начислений {len(g)}; F*/пол медиана {np.median(g.fstar / g.r):.2f}; "
                  f"недоплата за интервал медиана {np.median(g.short) * 100:.2f} п. п., 25% {np.percentile(g.short, 25) * 100:.2f}; "
                  f"доля F* ≤ 1,5·пол {np.mean(g.fstar <= 1.5 * g.r):.0%}, ≤ 2·пол {np.mean(g.fstar <= 2 * g.r):.0%}; "
                  f"премия на последней 15-мин свече медиана {np.median(g.p_last) * 100:.2f}%")
        cp = u[u.r > 0]
        if len(cp):
            print(f"  потолок: начислений с премией {len(cp)}; F*/потолок медиана {np.median(cp.fstar / cp.r):.2f}")
        u.to_pickle(os.path.join(D, "s179/unpaid_2024_2026.pkl"))
    # снимок действующих правил (потолки, интервалы, коридоры) — snapshot_rules.py


if __name__ == "__main__":
    main()
