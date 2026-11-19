"""s188 — разбор выгрузки Reddit (reddit_list.py): темы по словам в заголовке, лучшие посты по рейтингу, отбор тредов
для чтения комментариев. Без сетевых запросов. Итог — печать в лог и /home/user/mc_data/s188/reddit/top.json."""
import glob
import warnings
import json
import re
import time

import pandas as pd

warnings.filterwarnings("ignore")

R = "/home/user/mc_data/s188/reddit"
rows = []
for fn in glob.glob(f"{R}/list_*.jsonl"):
    for ln in open(fn):
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass
P = pd.DataFrame(rows).drop_duplicates("id")
P["when"] = pd.to_datetime(P.created_utc, unit="s")
P["title"] = P.title.fillna("")
print("постов:", len(P), {s: int(n) for s, n in P.subreddit.value_counts().items()})
print("охват:", {s: f"{x.when.min():%Y-%m} … {x.when.max():%Y-%m}" for s, x in P.groupby("subreddit")})
T = {
    "займы": r"\bborrow|\blend(ing)?\b|\bmargin\b|interest rate|short interest|cost to borrow|utili[sz]ation|loan",
    "фандинг и базис": r"funding|\bbasis\b|\bcarry\b|cash.and.carry|delta.neutral|perp",
    "сквизы, ликвидации, OI": r"squeeze|liquidat|open interest|\bOI\b",
    "листинги и Корея": r"listing|listed|delist|upbit|bithumb|korea|kimchi",
    "пампы и манипуляции": r"\bpump|\bdump|p&d|manipulat|wash trad",
    "разлоки": r"unlock|vesting|token release",
    "ошибки бэктеста": r"overfit|look.?ahead|survivor|curve.?fit|out.of.sample|walk.?forward|data snoop|p.?hack"
                       r"|too good to be true|backtest.*(wrong|lie|bias|mistake|bug|pitfall)",
    "киты и ончейн": r"whale|on.?chain|exchange (inflow|outflow)|smart money",
    "настроение": r"sentiment|reddit|twitter|google trends|fear.and.greed",
}
CRY = r"crypto|bitcoin|\bbtc\b|\beth\b|binance|altcoin|\balts?\b|perp|bybit|okx|hyperliquid|coin"
top = {}
for k, rx in T.items():
    m = P.title.str.contains(rx, case=False, regex=True)
    if k in ("ошибки бэктеста",):
        x = P[m]
    else:
        x = P[m & ((P.subreddit != "algotrading") & (P.subreddit != "quant")
                   | P.title.str.contains(CRY, case=False, regex=True))]
    x = x.sort_values("score", ascending=False)
    print(f"\n== {k}: постов {len(x)} (" + ", ".join(f"{s} {n}" for s, n in x.subreddit.value_counts().items()) + ")")
    for _, p in x.head(18).iterrows():
        print(f"  {p.score:>5} ↑ {p.num_comments:>4} комм.  {p.when:%Y-%m-%d}  r/{p.subreddit}: {p.title[:120]}")
    top[k] = x.head(18)[["id", "subreddit", "created_utc", "score", "num_comments", "title"]].to_dict("records")
json.dump(top, open(f"{R}/top.json", "w"), ensure_ascii=False, indent=0)
