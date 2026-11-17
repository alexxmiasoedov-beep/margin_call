"""s132 — откат пампов и возраст фьючерса (гипотеза — ВЫВОДЫ.md, записана до расчёта). Пампы трёх периодов — файлы s119
(s119_y2020.pkl в ~/mc_2020, s119_old.pkl в ~/mc_oos, s119_new.pkl в ~/mc_data): шорт 10/25/48 (net). Возраст фьючерса —
от первого месяца месячных свечей в архиве data.binance.vision (листинг S3, кэш s132_first.json). Запуск из ~/mc_data:
python3 <repo>/research/s132/age_test.py"""
import json
import os
import re
import sys
import time
import urllib.request

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s43"))
from oi_test import ct  # noqa: E402

DAY = 86400
LIST = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/monthly/klines/{}/1h/"
FILES = {"10.2020–09.2022": ("/home/user/mc_2020/s119_y2020.pkl", "2021-10-01"),
         "10.2022–09.2024": ("/home/user/mc_oos/s119_old.pkl", "2023-10-01"),
         "10.2024–10.2026": ("/home/user/mc_data/s119_new.pkl", "2025-12-01")}
CACHE = "s132_first.json"


def first_month(sym):
    for i in range(4):
        try:
            req = urllib.request.Request(LIST.format(sym), headers={"User-Agent": "research-script/1.0"})
            x = urllib.request.urlopen(req, timeout=30).read().decode()
            m = re.findall(rf"{sym}-1h-(\d{{4}}-\d{{2}})\.zip</Key>", x)
            return min(m) if m else None
        except Exception:
            time.sleep(2 + 2 * i)
    return "ERR"


def main():
    X = []
    for per, (f, cut) in FILES.items():
        x = pd.read_pickle(f)[["s", "t", "net"]].copy()
        x["per"] = per; x["cut"] = pd.Timestamp(cut, tz="UTC").timestamp()
        X.append(x)
    X = pd.concat(X, ignore_index=True)
    X = X[X.net.notna()]
    first = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    for s in sorted(set(X.s)):
        if s not in first or first[s] == "ERR":
            first[s] = first_month(s + "USDT"); time.sleep(0.15)
    json.dump(first, open(CACHE, "w"))
    fm = {s: pd.Timestamp(m + "-01", tz="UTC").timestamp() for s, m in first.items() if m and m != "ERR"}
    X["age"] = (X.t - X.s.map(fm)) / DAY
    print(f"пампов {len(X)}; возраст известен у {X.age.notna().mean():.0%}; ошибок листинга "
          f"{sum(v == 'ERR' for v in first.values())}")
    X["g"] = pd.cut(X.age, [-60, 180, 365, 1e5], labels=["< 180 сут", "180–365 сут", "≥ 365 сут"])
    for per, x in X.groupby("per", sort=False):
        months = (x.t.max() - x.t.min()) / (30.4 * DAY)
        print(f"\n{per}: пампов {len(x)} ({len(x) / months:.0f} в месяц), все {x.net.mean():+.2%}")
        res = {}
        for lab, y in list(x.groupby("g", observed=True)) + [("молодые < 365", x[x.age < 365])]:
            if len(y) < 8:
                print(f"  {lab:14s} n={len(y)}"); continue
            m, t, n = ct(y.net, y.t)
            h1, h2 = y[y.t < y.cut].net.mean(), y[y.t >= y.cut].net.mean()
            print(f"  {lab:14s} n={n:5d} ({n / months:5.1f}/мес) {m:+.2%} (t {t:+.1f}) в плюсе {(y.net > 0).mean():.0%} |"
                  f" половины {h1:+.2%} / {h2:+.2%}")
            res[lab] = y.net
        if "молодые < 365" in res and "≥ 365 сут" in res:
            a, b = res["молодые < 365"], res["≥ 365 сут"]
            d = a.mean() - b.mean(); se = np.sqrt(a.var() / len(a) + b.var() / len(b))
            print(f"  молодые − старые: {d:+.2%} (t ≈ {d / se:+.1f})")
    X.to_pickle("s132_pumps.pkl")


if __name__ == "__main__":
    main()
