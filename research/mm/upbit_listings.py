"""Время начала торгов новых рынков Upbit (по первой свече) за последние ~200 дней."""
import json, subprocess, time, datetime, pickle
UTC = datetime.timezone.utc
def get(u):
    for i in range(5):
        try:
            x = json.loads(subprocess.run(["curl", "-s", "-m", "20", u], capture_output=True, text=True).stdout or "null")
            if isinstance(x, list): return x
            if isinstance(x, dict) and x.get("error"): time.sleep(1 + i)
        except Exception: time.sleep(1 + i)
    return None
mk = get("https://api.upbit.com/v1/market/all")
out = []
for m in mk:
    d = get(f"https://api.upbit.com/v1/candles/days?market={m['market']}&count=200"); time.sleep(0.12)
    if not d or len(d) >= 200: continue                                    # старше 200 дней — не новый
    first_day = min(x["candle_date_time_utc"] for x in d)
    # точная первая минута: листаем минутные свечи назад от конца первого дня
    to = (datetime.datetime.fromisoformat(first_day) + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"); first = None
    for _ in range(10):
        c = get(f"https://api.upbit.com/v1/candles/minutes/1?market={m['market']}&count=200&to={to}"); time.sleep(0.12)
        if not c: break
        first = min(x["candle_date_time_utc"] for x in c)
        if len(c) < 200: break
        to = first + "Z"
    if first:
        out.append(dict(market=m["market"], base=m["market"].split("-")[1], quote=m["market"].split("-")[0],
                        t=datetime.datetime.fromisoformat(first).replace(tzinfo=UTC).timestamp(), name=m.get("english_name")))
pickle.dump(out, open("mm/upbit_listings.pkl", "wb"))
print("новых рынков за ~200 дней:", len(out))
for x in sorted(out, key=lambda x: x["t"])[-15:]:
    print(" ", x["market"], datetime.datetime.fromtimestamp(x["t"], UTC).strftime("%d.%m.%Y %H:%M UTC"))
