"""s252 — сколько было перпов без спота Binance в прошлом и сколько заводов ≥ 0,5% на другие биржи у них видно в Ethereum
(s160_events.pkl). Перпы — все USDT-M PERPETUAL из exchangeInfo (TRADING и SETTLING — снятые; дата запуска onboardDate,
для снятых конец — последняя свеча k2y или дата снятия неизвестна → до конца k2y). Спот — первая дневная свеча пар монеты
(s252/spot_dates.json). «Без спота» — от запуска перпа до открытия спота (или до сегодня). Только частоты.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/prespot.py"""
import json
import pickle
import re

import pandas as pd


def base(fs):
    m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", fs)
    if m and not m.group(2)[0].isdigit():
        return m.group(2)
    return fs


def main():
    FX = json.load(open("s252/exinfo.json"))["symbols"]
    SD = json.load(open("s252/spot_dates.json"))
    K = pickle.load(open("s2/k2y.pkl", "rb"))
    now = 1795449600
    per = {}
    for s in FX:
        if s["contractType"] != "PERPETUAL" or s["quoteAsset"] != "USDT" or s["status"] not in ("TRADING", "SETTLING"):
            continue
        if (s.get("underlyingType") or "") in ("INDEX", "PREMARKET") or "Index" in (s.get("underlyingSubType") or []):
            continue
        fs = s["symbol"][:-4]
        coin = base(s["baseAsset"])
        on = s["onboardDate"] / 1000
        end = now
        if s["status"] == "SETTLING":
            k = K.get(fs)
            end = float(k["t"][k["qv"] > 0][-1]) if k is not None and (k["qv"] > 0).any() else None
            if end is None:
                continue                                   # снят до 10.2024 — конца не знаем, пропускаем
        sp = SD.get(coin, SD.get(s["baseAsset"]))
        a, b = on, min(end, sp) if sp else end
        if b - a < 86400:
            continue
        per[fs] = (a, b, s["status"])
    rows = []
    for fs, (a, b, st) in per.items():
        for m in pd.period_range(pd.Timestamp(a, unit="s").strftime("%Y-%m"), pd.Timestamp(b, unit="s").strftime("%Y-%m"), freq="M"):
            rows.append((fs, str(m), st))
    U = pd.DataFrame(rows, columns=["perp", "m", "st"])
    U["y"] = U.m.str[:4]
    print("перпов, бывших без спота ≥ 1 сут:", len(per), "| из них сняты с торгов:", sum(1 for v in per.values() if v[2] == "SETTLING"))
    print("перпо-месяцев без спота по годам:", U.groupby("y").size().to_dict())
    print("перпов без спота в среднем на месяц:", (U.groupby("m").size().groupby(lambda m: m[:4]).mean().round(0)).to_dict())
    E = pd.read_pickle("s160_events.pkl")
    E = E[(E.exch != "Binance") & (E.from_exch != True)]                     # noqa: E712  (без перекладки)
    inwin = [fs in per and per[fs][0] <= t < per[fs][1] for fs, t in zip(E.perp, E.t)]
    X = E[inwin].sort_values("t")
    keep, last = [], {}
    for r in X.itertuples():
        keep.append(not (r.perp in last and r.t - last[r.perp] < 48 * 3600))
        if keep[-1]:
            last[r.perp] = r.t
    X = X[keep]
    X["y"] = pd.to_datetime(X.t, unit="s").dt.strftime("%Y")
    print("заводы ≥ 0,5% на биржи кроме Binance (Ethereum, без перекладки, первые за 48 ч) в периоды без спота, по годам:",
          X.groupby("y").size().to_dict())
    print("из них у перпов, которые потом получили спот или сняты:",
          X[X.perp.map(lambda p: per[p][2] == "SETTLING" or per[p][1] < now - 86400)].groupby("y").size().to_dict())
    pd.to_pickle({"per": per, "U": U, "X": X}, "s252/prespot.pkl")


if __name__ == "__main__":
    main()
