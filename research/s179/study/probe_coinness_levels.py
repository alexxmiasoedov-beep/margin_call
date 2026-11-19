"""s179 — как часто корейская лента Coinness (s78/coinness.jsonl, t.me/s/coinnesskr) пишет в заголовке о пересечении
ценового уровня («N원 돌파», «N달러 회복» и т. п.). Проверка механизма «внимание к круглой цене через новости».
Только счёт заголовков, без цен.

Запуск: python3 -I probe_coinness_levels.py <папка данных>
"""
import json
import os
import re
import sys
from collections import Counter

import pandas as pd

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
KRW = re.compile(r"(\d[\d,\.]*\s*(?:만|억)?\s*원)\s*(?:선\s*)?(돌파|회복|붕괴|탈환|하회|상회|아래|위)")
USD = re.compile(r"(\d[\d,\.]*\s*(?:만|억)?\s*(?:달러|\$))\s*(?:선\s*)?(돌파|회복|붕괴|탈환|하회|상회)")
NOT_PRICE = re.compile(r"환율|시총|거래량|거래액|예치|공급|대출|손실|수익|주가|순유입|유입|보유|매출|자산|규모|청산")
BTC_ETH = re.compile(r"BTC|비트코인|ETH|이더리움")


def main():
    rows = [json.loads(ln) for ln in open(os.path.join(D, "s78/coinness.jsonl"))]
    df = pd.DataFrame(rows, columns=["id", "t", "text"])
    df["t"] = pd.to_datetime(df.t, utc=True)
    df["title"] = df.text.str.split("\n").str[0]
    months = (df.t.max() - df.t.min()).days / 30.44
    print(f"постов {len(df)}, {df.t.min().date()} – {df.t.max().date()} ({months:.1f} мес.)")
    k = df.title.str.contains(KRW)
    u = df.title.str.contains(USD)
    lvl = df[k | u]
    price = lvl[~lvl.title.str.contains(NOT_PRICE)]
    alt = price[~price.title.str.contains(BTC_ETH)]
    print(f"заголовков о пересечении уровня: вона {int(k.sum())}, доллар {int(u.sum())}; из них о цене монеты "
          f"{len(price)} ({len(price) / months:.1f} в мес.), о цене альткоина {len(alt)} ({len(alt) / months:.1f} в мес.)")
    verbs = Counter((KRW.search(x) or USD.search(x)).group(2) for x in lvl.title)
    print(f"глаголы: {verbs.most_common()}")
    print("заголовки о цене альткоина:")
    for _, r in alt.iterrows():
        print(f"  {r.t.date()} {r.title[:110]}")


if __name__ == "__main__":
    main()
