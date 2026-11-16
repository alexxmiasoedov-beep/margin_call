"""s43 — разбор постов oi_detector (s43/posts.jsonl) в таблицу s43/rows.pkl. Три формата постов:
2024 («Score: 10/10», «OI changed in 15 mins», столбцы «├ 🟩+0.93% (5m)» по разделам), с 03.2025 (таблица
«OI | цена» в строку) и с 2026 г. (то же через «•», плюс «Indicators»). Запуск из папки с данными."""
import datetime
import json
import re
import sys

import numpy as np
import pandas as pd

TFS = ("5m", "15m", "1h", "24h")
NUM = r"([+\-−]?\d+(?:\.\d+)?)"


def fnum(s):
    return float(s.replace("−", "-"))


def parse(n, ts, x):
    m = re.search(r"(🟢|🔴|🪙)\s*#(\S+)", x)
    if not m:
        return None
    d = dict(n=n, t=datetime.datetime.fromisoformat(ts).timestamp(), dir={"🟢": 1, "🔴": -1}.get(m.group(1), 0),
             coin=m.group(2))                              # 🪙 (с 10.2026, смысл не ясен) — dir 0, в проверку не идёт
    m = re.search(r"#\S+\s+\$" + NUM, x) or re.search(r"Price \$" + NUM, x)
    d["price"] = fnum(m.group(1)) if m else np.nan
    m = re.search(r"(\d+)/10", x)
    d["score"] = int(m.group(1)) if m else np.nan
    m = re.search(r"OI \[(\d+)(m|h)\]", x)
    if m:
        d["win"] = int(m.group(1)) * (60 if m.group(2) == "h" else 1)
    else:
        m = re.search(r"OI (?:increased|decreased|changed) in (\d+) min", x)
        d["win"] = int(m.group(1)) if m else np.nan
    m = re.search(r"🔈\s*(?:Signals during the day:\s*)?(\d+)", x)
    d["sig"] = int(m.group(1)) if m else np.nan
    d["fire"] = "🔥" in x
    m = re.search(r"([A-Za-z0-9]+)USDT\.P", x)
    d["tick"] = m.group(1) if m else None
    sec, table = None, False
    for ln in x.split("\n"):
        if any(w in ln for w in ("Volume", "Funding", "RSI", "Long/Short", "Indicators")):
            continue
        if "Open Interest" in ln or "🌐OI" in ln:
            table = "Price change" in ln
            sec = "oi"
            continue
        if "Price change" in ln:
            sec = "p"
            continue
        tf = re.search(r"\((5m|15m|1h|24h)\)", ln)
        pc = re.findall(NUM + "%", ln)
        if not tf or not pc:
            continue
        k = tf.group(1)
        if table and len(pc) >= 2:
            d["oi" + k], d["p" + k] = fnum(pc[0]), fnum(pc[1])
        elif sec in ("oi", "p"):
            d[sec + k] = fnum(pc[0])
    m = re.search(r"Volume(?: change)?\s*" + NUM + "%", x)
    d["vol24"] = fnum(m.group(1)) if m else np.nan
    m = re.search(r"Funding(?: rate)?\s*" + NUM + "%", x)
    d["fund"] = fnum(m.group(1)) if m else np.nan
    m = re.search(r"Long/Short\s*" + NUM + r"\s*\(5m\)\D*?" + NUM + r"\s*\(15m\)\D*?" + NUM + r"\s*\(1h\)", x, re.S)
    if m:
        d["ls5"], d["ls15"], d["ls1h"] = (fnum(g) for g in m.groups())
    m = re.search(r"RSI\s*" + NUM + r"\s*\(15m\)\D*?" + NUM + r"\s*\(1h\)", x, re.S)
    if m:
        d["rsi15"], d["rsi1h"] = (fnum(g) for g in m.groups())
    return d


def main(path="s43/posts.jsonl", out="s43/rows.pkl"):
    rows, bad = [], []
    for line in open(path):
        n, ts, x = json.loads(line)
        d = parse(n, ts, x)
        (rows if d else bad).append(d or (n, ts, x[:160]))
    R = pd.DataFrame(rows).sort_values("n").reset_index(drop=True)
    for k in TFS:
        for p in ("oi", "p"):
            if p + k not in R:
                R[p + k] = np.nan
    R.to_pickle(out)
    print(f"постов {len(R) + len(bad)}, разобрано {len(R)}, не оповещения {len(bad)}")
    for b in bad[:8]:
        print("   не разобран:", b[0], b[1], b[2].replace("\n", " | "))
    print("доля пустых полей:\n" + R[["price", "score", "win", "sig", "oi15m", "oi1h", "p1h", "p24h", "fund", "vol24"]].isna()
          .mean().round(3).to_string())
    return R


if __name__ == "__main__":
    main(*sys.argv[1:])
