"""Листинги Upbit старше 200 дней: ищем первую свечу, листая дневные свечи назад (до марта 2025)."""
import json, subprocess, time, datetime, pickle
UTC = datetime.timezone.utc
def get(u):
    for i in range(5):
        try:
            x = json.loads(subprocess.run(["curl", "-s", "-m", "20", u], capture_output=True, text=True).stdout or "null")
            if isinstance(x, list): return x
        except Exception: pass
        time.sleep(1 + i)
    return None
new = {x["market"] for x in pickle.load(open("mm/upbit_listings.pkl", "rb"))}
mk = [m for m in get("https://api.upbit.com/v1/market/all") if m["market"] not in new and m["market"].startswith("KRW-")]
LIMIT = datetime.datetime(2025, 3, 1, tzinfo=UTC)
out = []
for m in mk:
    to = (datetime.datetime.now(UTC) - datetime.timedelta(days=199)).strftime("%Y-%m-%dT%H:%M:%SZ"); first_day = None
    for _ in range(3):
        d = get(f"https://api.upbit.com/v1/candles/days?market={m['market']}&count=200&to={to}"); time.sleep(0.12)
        if not d: break
        fd = min(x["candle_date_time_utc"] for x in d)
        if len(d) < 200: first_day = fd; break
        if datetime.datetime.fromisoformat(fd).replace(tzinfo=UTC) < LIMIT: break
        to = fd + "Z"
    if not first_day or datetime.datetime.fromisoformat(first_day).replace(tzinfo=UTC) < LIMIT: continue
    to = (datetime.datetime.fromisoformat(first_day) + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"); first = None
    for _ in range(10):
        c = get(f"https://api.upbit.com/v1/candles/minutes/1?market={m['market']}&count=200&to={to}"); time.sleep(0.12)
        if not c: break
        first = min(x["candle_date_time_utc"] for x in c)
        if len(c) < 200: break
        to = first + "Z"
    if first:
        out.append(dict(market=m["market"], base=m["market"].split("-")[1], quote="KRW",
                        t=datetime.datetime.fromisoformat(first).replace(tzinfo=UTC).timestamp(), name=m.get("english_name")))
pickle.dump(out, open("mm/upbit_listings_old.pkl", "wb"))
print("листингов к воне с 01.03.2025 по ~04.2026:", len(out))
