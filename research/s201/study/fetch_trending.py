"""s201: почасовой список «трендовых слов» Santiment (getTrendingWords, топ-20 слов в час со счётом) за окно без ключа.
Santiment считает список раз в час: слова с наибольшим всплеском упоминаний за 24 ч к своему среднему за 2 недели
(хайп-счёт по объёму и числу авторов). Итог — /home/user/mc_data/s201/trending_hourly.pkl (datetime, rank, word, score)."""
import pandas as pd

import san

D = san.D
edges = pd.date_range("2025-11-20", "2026-10-20", freq="60D", tz="UTC").tolist() + [pd.Timestamp("2026-10-20", tz="UTC")]
rows = []
for a, b in zip(edges[:-1], edges[1:]):
    if a >= b:
        continue
    fa, fb = a.strftime("%Y-%m-%dT%H:%M:%SZ"), b.strftime("%Y-%m-%dT%H:%M:%SZ")
    q = (f'{{\n  getTrendingWords(from: "{fa}", to: "{fb}", size: 20, interval: "1h") {{\n    datetime\n'
         f'    topWords {{ word score }}\n  }}\n}}')
    js = san.gql(q, "trending", {"metric": "getTrendingWords", "interval": "1h", "from": fa, "to": fb})
    if js.get("errors"):
        print("ошибка:", js["errors"][0].get("message"))
        continue
    for x in js["data"]["getTrendingWords"]:
        for i, w in enumerate(sorted(x["topWords"], key=lambda w: -w["score"])):
            rows.append((x["datetime"], i + 1, w["word"], w["score"]))
T = pd.DataFrame(rows, columns=["datetime", "rank", "word", "score"])
T["datetime"] = pd.to_datetime(T.datetime, utc=True)
T = T.drop_duplicates(["datetime", "word"])
T.to_pickle(f"{D}/trending_hourly.pkl")
print("часов:", T.datetime.nunique(), "строк:", len(T), "разных слов:", T.word.nunique(),
      "с", T.datetime.min(), "по", T.datetime.max())
