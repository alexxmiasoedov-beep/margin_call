"""s252 — частоты по Ethereum без нового сбора: заводы ≥ 0,5% монет в обращении (s160_events.pkl — переводы ERC-20 на адреса
бирж, CMC, 10.2020–11.2026) у перпов, которых нет на споте Binance (снимок 23.11.2026, s252/nospot.json).
Только число событий; доходы и цену после событий не считаем.
Классы: (а) биржа в составе индекса перпа; (б) прочие биржи; (г) Binance. Отправитель — не биржа (from_exch = False).
Событие — после запуска перпа; «первое у монеты за 48 ч» — среди всех классов и внутри класса.
Для сравнения с правилом 🐋 — доля событий в «спокойном рынке» (ход перпа за 24 ч до свечи входа ±5%, свечи s2/k2y.pkl до
18.10.2026) — это условие входа, а не исход. Пересечение с разлоками: окно [T − 7 сут, T + 1 сут] разлоков ≥ 1% (s142).
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/eth_nospot.py"""
import json
import pickle

import numpy as np
import pandas as pd

CONS2EX = {"gateio": "Gate.io", "mexc": "MEXC", "bitget": "Bitget", "bybit": "Bybit", "okex": "OKX", "kucoin": "KuCoin",
           "coinbase": "Coinbase", "bitfinex": "Bitfinex"}


def first48(df, key):
    keep, last = [], {}
    for r in df.itertuples():
        k = key(r)
        keep.append(not (k in last and r.t - last[k] < 48 * 3600))
        if keep[-1]:
            last[k] = r.t
    return keep


def calm(K, fs, t):
    """Ход перпа за 24 ч до закрытия первой 15-мин свечи не раньше чем через 15 мин после события (как 🐋); None — нет свечей."""
    a = K.get(fs)
    if a is None:
        return None
    te = (int(t) + 900) // 900 * 900 + 900          # закрытие первой свечи, начавшейся не раньше t + 15 мин
    i = np.searchsorted(a["t"], te - 900)
    j = np.searchsorted(a["t"], te - 900 - 86400)
    if i >= len(a["t"]) or a["t"][i] != te - 900 or j >= len(a["t"]) or a["qv"][i] <= 0:
        return None
    if a["t"][0] > te - 900 - 86400:                # перп моложе суток
        return None
    return abs(a["c"][i] / a["c"][j] - 1) <= 0.05


def main():
    E = pd.read_pickle("s160_events.pkl")
    NS = json.load(open("s252/nospot.json"))
    syms = {s[:-4]: s for s in NS}
    X = E[E.perp.isin(syms)].copy()
    X = X[~X.from_exch.fillna(False).astype(bool)]
    X["onb"] = X.perp.map(lambda p: NS[syms[p]]["onboard"] / 1000)
    X = X[X.t >= X.onb].sort_values("t")
    X["cls"] = [("г" if r.exch == "Binance" else
                 "а" if r.exch in {CONS2EX.get(c["exchange"], c["exchange"]) for c in NS[syms[r.perp]]["cons"]} else "б")
                for r in X.itertuples()]
    X["f48"] = first48(X, lambda r: r.perp)
    X["f48c"] = first48(X, lambda r: (r.perp, r.cls))
    X["m"] = pd.to_datetime(X.t, unit="s").dt.strftime("%Y-%m")
    K = pickle.load(open("s2/k2y.pkl", "rb"))
    X["calm"] = [calm(K, r.perp, r.t) for r in X.itertuples()]
    U = pd.read_pickle("s142_2024–2026.pkl")[["s", "T"]]
    X["unl"] = [bool(((U.s == r.perp) & (U["T"] - 7 * 86400 <= r.t) & (r.t <= U["T"] + 86400)).any()) for r in X.itertuples()]
    X.to_pickle("s252/eth_nospot.pkl")
    print("переводов ≥ 0,5% от не-бирж после запуска перпа:", len(X), "| перпов:", X.perp.nunique())
    Y = X[X.f48c]
    print("первые за 48 ч в своём классе:", len(Y), Y.cls.value_counts().to_dict())
    for lab, a, b in (("10.2024–06.2025", "2024-10", "2025-06"), ("07–12.2025", "2025-07", "2025-12"),
                      ("01–10.2026", "2026-01", "2026-10")):
        Z = Y[(Y.m >= a) & (Y.m <= b)]
        n = len(pd.period_range(a, b, freq="M"))
        zc = Z[Z.calm.eq(True)]
        print(f"  {lab}: в месяц (а) {len(Z[Z.cls == 'а']) / n:.1f}, (б) {len(Z[Z.cls == 'б']) / n:.1f}, (г) {len(Z[Z.cls == 'г']) / n:.1f}"
              f" | (а) в спокойном рынке {len(zc[zc.cls == 'а']) / n:.1f} | перпов без спота с событиями {Z.perp.nunique()}")
    print("биржи (а):", Y[Y.cls == "а"].exch.value_counts().to_dict())
    print("биржи (б):", Y[Y.cls == "б"].exch.value_counts().to_dict())
    print("доля у разлоков ≥ 1% (s142, T − 7 … T + 1 сут):", f"{Y.unl.mean():.1%}", "| перпов с разлоками s142:",
          Y[Y.unl].perp.nunique())
    print("доля 'спокойного рынка' среди событий со свечами:", f"{Y.calm.dropna().astype(bool).mean():.0%}",
          "(со свечами:", int(Y.calm.notna().sum()), ")")
    print("по перпам (а):", Y[Y.cls == "а"].perp.value_counts().head(15).to_dict())


if __name__ == "__main__":
    main()
