"""s201: проба getTrendingWords (почасовой список трендовых слов Santiment) — доступен ли без ключа и в каком виде."""
import hashlib
import os

import san

q = '''{
  getTrendingWords(from: "2026-10-01T00:00:00Z", to: "2026-10-02T00:00:00Z", size: 10, interval: "1h") {
    datetime
    topWords { word score }
  }
}'''
print("в кэше:", os.path.exists(f"{san.CACHE}/{hashlib.sha1(q.encode()).hexdigest()}.json"))
js = san.gql(q, "probe_trending", {"metric": "getTrendingWords", "interval": "1h", "from": "2026-10-01", "to": "2026-10-02"})
print(js.get("errors"))
d = (js.get("data") or {}).get("getTrendingWords") or []
print(len(d))
for x in d[:3]:
    print(x["datetime"], [(w["word"], round(w["score"], 1)) for w in x["topWords"]])
