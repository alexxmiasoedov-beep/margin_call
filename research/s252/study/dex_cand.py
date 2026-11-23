"""s252 — класс (в) «крупная продажа на DEX», шаг 1: часы-кандидаты по обороту пулов (GeckoTerminal, последние 180 сут).
Продажа одной транзакцией на X $ даёт оборот часа ≥ X $, поэтому час с оборотом главных пулов < порога (доля капитализации
в обращении CMC за день до часа: 0,25% и 0,5%) продажи такого размера не содержит. Число часов-кандидатов — верхняя
граница числа событий; шаг 2 (dex_swaps.py) проверяет часы по сделкам.
Вход — s252/gt/<пул>.json, s252/dex_pairs.json, s252/bsc_tokens.json. Итог — s252/dex_cand.pkl и печать.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/dex_cand.py"""
import bisect
import json
import os

import pandas as pd


def main():
    TK = json.load(open("s252/tokens.json"))
    TB = json.load(open("s252/bsc_tokens.json"))
    DP = json.load(open("s252/dex_pairs.json"))
    NS = json.load(open("s252/nospot.json"))
    rows = []
    cover = {}
    for s, pools in DP.items():
        v = TB.get(s)
        if not v or not v.get("cmc") or TK[s].get("alpha_chain") != "bsc" or not TK[s]["bsc_native"]:
            continue
        vol = {}
        used = []
        for p in pools:
            f = f"s252/gt/{p['pair'].lower()}.json"
            if not os.path.exists(f):
                continue
            used.append(p["pair"])
            for r in json.load(open(f)):
                vol[int(r[0])] = vol.get(int(r[0]), 0.0) + float(r[5] or 0)
        if not vol:
            continue
        D = [d[0] for d in v["days"]]
        mc = [d[1] * d[2] for d in v["days"]]
        cover[s] = (min(vol), max(vol), len(vol), used)
        on = NS[s]["onboard"] / 1000
        for t, q in vol.items():
            if t < on:
                continue
            i = bisect.bisect_right(D, pd.Timestamp(t - 86400, unit="s").strftime("%Y-%m-%d")) - 1
            if i < 0:
                continue
            rows.append((s, t, q, mc[i], q / mc[i] if mc[i] else None))
    X = pd.DataFrame(rows, columns=["perp", "t", "vol", "mcap", "vm"])
    X.to_pickle("s252/dex_hours.pkl")
    hrs = X.groupby("perp").size()
    print("токенов с оборотом GT:", X.perp.nunique(), "часов:", len(X), "в среднем часов на токен:", round(hrs.mean()))
    months = len(X) / X.perp.nunique() / (30.44 * 24)
    for thr in (0.0025, 0.005, 0.01):
        c = X[X.vm >= thr]
        # отдельные эпизоды: соседние часы одного токена — один эпизод
        c = c.sort_values(["perp", "t"])
        ep = (c.groupby("perp").t.diff().fillna(1e9) > 3600).sum()
        print(f"оборот часа ≥ {thr:.2%} капитализации: часов {len(c)} у {c.perp.nunique()} токенов, эпизодов {ep}; "
              f"на токен в месяц: {len(c) / X.perp.nunique() / months:.2f} часов, {ep / X.perp.nunique() / months:.2f} эпизодов")
    top = X[X.vm >= 0.005].perp.value_counts().head(15)
    print("больше всего часов ≥ 0,5%:", top.to_dict())
    print("медиана оборота часа к капитализации:", f"{X.vm.median():.4%}")


if __name__ == "__main__":
    main()
