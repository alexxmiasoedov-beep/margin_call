"""s171 — события «займ ускорился» (З↑) и признаки сочетаний К1, К2, К4, К5, К6 (гипотезы — ВЫВОДЫ.md, записаны до
расчёта). События — `s21/panel.pkl`: монета в канале сейчас и 4 ч назад, займ за 24 ч ≥ ×1,5 к значению 4 ч назад и
≥ 50 тыс. $, одно событие на монету за сутки (common22.thin). Признаки:
- К1 — доля агрессивных покупок на споте Binance за 4 ч до T (`s23/spot1h.pkl`: [начало часа, оборот, покупки тейкеров,
  сделок, цена]);
- К2 — открытый интерес фьючерса в T к T − 4 ч (`common22.oi_at`, 5-мин метрики data.binance.vision, кэш s20/metrics)
  и фандинг за 24 ч (f24 таблицы);
- К4 — разлок ≥ 1% монет в обращении (события 🔑⁺, `s142_<период>.pkl`) в (T, T + 14 сут];
- К5 — ликвидации шортов монеты на Binance за (T − 4 ч, T] (канал ликвидаций, `s72/liq.jsonl`);
- К6 — завод токена на Binance ≥ 0,5% монет в обращении за (T − 24 ч, T] (`s160_events.pkl`), только токены Ethereum.
Исходы — `s21/borrow_trades.sims`: 7 сут со стопом +50% и 48 ч со стопом +25%. Итог — s171_events.pkl в папке данных.
Запуск из /home/user/mc_data: python3 <repo>/research/s171/build.py"""
import json
import os
import pickle
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s21", "s22"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common22 import DAY, H, oi_at, thin  # noqa: E402
from borrow_trades import sims  # noqa: E402


def spot_key(s, S):
    if s in S:
        return s
    m = re.match(r"^(1000000|1000)(.+)$", s)
    return m.group(2) if m and m.group(2) in S else None


def liq_table():
    """{фьючерс: массив [время, $ ликвидированных шортов]}."""
    rows = {}
    for ln in open("s72/liq.jsonl"):
        r = json.loads(ln)
        m = re.search(r"#(\S+) Liquidated Short: \$([\d.]+)([KMB]?)", r[2])
        if not m:
            continue
        v = float(m.group(2)) * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(3)]
        rows.setdefault(m.group(1), []).append((pd.Timestamp(r[1]).timestamp(), v))
    return {s: np.array(sorted(v)) for s, v in rows.items()}


def main():
    D = pd.read_pickle("s21/panel.pkl")
    E = D[D.in4 & (D.bor >= 1.5 * D.bor4) & (D.bor >= 50e3)].sort_values("T")
    E = thin(E).reset_index(drop=True)
    print("событий З↑", len(E), "монет", E.s.nunique(), flush=True)
    # К1 — поток спота
    S = pickle.load(open("s23/spot1h.pkl", "rb"))
    k1 = []
    for r in E.itertuples():
        k = spot_key(r.s, S)
        if not k:
            k1.append(np.nan); continue
        a = S[k]; m = (a[:, 0] >= r.T - 4 * H) & (a[:, 0] < r.T)
        qv = a[m, 1].sum()
        k1.append(a[m, 2].sum() / qv if m.sum() == 4 and qv > 0 else np.nan)
    E["buy4"] = k1
    # К2 — открытый интерес за 4 ч
    with ThreadPoolExecutor(8) as ex:
        o1 = list(ex.map(lambda x: oi_at(*x), zip(E.s, E["T"])))
        o0 = list(ex.map(lambda x: oi_at(*x), zip(E.s, E["T"] - 4 * H)))
    E["doi4"] = np.array(o1) / np.array(o0) - 1
    # К4 — разлок впереди
    U = pd.concat([pd.read_pickle(f"s142_{p}.pkl") for p in ("2022–2024", "2024–2026")])
    UT = {s: np.sort(g["T"].values.astype(np.int64)) for s, g in U.groupby("s")}
    E["unl14"] = [bool(np.any((UT.get(s, np.array([], np.int64)) > T) & (UT.get(s, np.array([], np.int64)) <= T + 14 * DAY)))
                  for s, T in zip(E.s, E["T"])]
    # К5 — ликвидации шортов за 4 ч
    L = liq_table()
    E["sqz4"] = [float(L[s][(L[s][:, 0] > T - 4 * H) & (L[s][:, 0] <= T), 1].sum()) if s in L else 0.0
                 for s, T in zip(E.s, E["T"])]
    # К6 — заводы на Binance за 24 ч (токены Ethereum)
    C = pd.read_pickle("s160_events.pkl"); erc = set(C.perp)
    C = C[C.exch == "Binance"]
    CT = {s: np.sort(g.t.values.astype(np.int64)) for s, g in C.groupby("perp")}
    E["erc"] = E.s.isin(erc)
    E["dep24"] = [bool(np.any((CT.get(s, np.array([], np.int64)) > T - DAY) & (CT.get(s, np.array([], np.int64)) <= T)))
                  for s, T in zip(E.s, E["T"])]
    # исходы
    for sl, hold, nm in ((0.5, 168, "n7"), (0.25, 48, "n2")):
        R = sims(E[["s", "T"]], sl=sl, hold_h=hold)
        E = E.merge(R[["s", "T", "net", "hedged"]].rename(columns={"net": nm, "hedged": nm + "h"}), on=["s", "T"], how="left")
    E.to_pickle("s171_events.pkl")
    print("готово:", len(E), "с исходом 7 сут", int(E.n7.notna().sum()), "| К1 есть", int(E.buy4.notna().sum()),
          "| К2 есть", int(E.doi4.notna().sum()), "| К4", int(E.unl14.sum()), "| К5 ≥ 100 тыс. $", int((E.sqz4 >= 1e5).sum()),
          "| К6", int(E.dep24.sum()), "из токенов Ethereum", int(E.erc.sum()), flush=True)


if __name__ == "__main__":
    main()
