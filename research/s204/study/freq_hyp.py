#!/usr/bin/env python3
"""s204: частоты событий для гипотез (без доходов). Окно подсчёта Upbit — дневная свеча d-1 (00–24 UTC)."""
import csv, json, collections
from datetime import date, timedelta, datetime
OUT = "/home/user/mc_data/s204"
def cand(c):
    try: return json.load(open(f"{OUT}/upbit_days/{c}.json"))
    except Exception: return {}
D = [x for x in csv.DictReader(open(f"{OUT}/upbit_days_D.csv")) if x["new_episode"] == "1" and x["binance_perp_1d"] == "1"]
V = {(x["coin"], x["day"]) for x in csv.DictReader(open(f"{OUT}/upbit_days_V.csv"))}
months = 241 / 30.44
cnt = collections.Counter()
for x in D:
    C = cand(x["coin"]); d = date.fromisoformat(x["day"])
    c0 = C.get((d - timedelta(days=1)).isoformat())
    if not c0 or not c0[0]:
        cnt["нет свечи"] += 1; continue
    r = c0[3] / c0[0] - 1
    calm = abs(r) <= 0.05
    cnt["все"] += 1
    cnt["спокойные ±5%"] += calm
    cnt["спокойные ±5%, L3"] += calm and x["level"] == "3"
    cnt["без V"] += (x["coin"], x["day"]) not in V
    cnt["спокойные и без V"] += calm and (x["coin"], x["day"]) not in V
print("Upbit D (новые, с перпом), 24.03–19.11.2026, в месяц:")
for k, v in cnt.items(): print(f"  {k}: {v} ({v / months:.0f} в месяц)")
# Г2: Bithumb D раньше Upbit D (та же монета, Bithumb за 0–12 ч до 01:00 UTC)
B = collections.defaultdict(list)
for x in csv.DictReader(open(f"{OUT}/bithumb_events_D.csv")):
    B[x["coin"]].append((datetime.strptime(x["start_utc"], "%Y-%m-%d %H:%M"), x["new_episode"], x["binance_perp_1d"], x["step"]))
Uall = collections.defaultdict(set)
for x in csv.DictReader(open(f"{OUT}/upbit_days_D.csv")):
    Uall[x["coin"]].add(datetime.fromisoformat(x["day"]) + timedelta(hours=1))
g2 = collections.Counter()
for c, L in B.items():
    for t, new, perp, st in L:
        if new != "1" or perp != "1" or not (datetime(2026, 3, 24) <= t < datetime(2026, 11, 19)):
            continue
        g2["Bithumb D новые с перпом"] += 1
        nxt = [u for u in Uall.get(c, ()) if timedelta(0) < u - t <= timedelta(hours=12)]
        g2["... и Upbit D в следующие 12 ч"] += bool(nxt)
        g2["... шаг 위험 (30)"] += st == "30"
print("\nBithumb D, 24.03–19.11.2026 (8 мес.), в месяц:")
for k, v in g2.items(): print(f"  {k}: {v} ({v / months:.0f} в месяц)")
# Bithumb D по периодам (новые с перпом): 07.2023–09.2024 и 10.2024–10.2026
per = collections.Counter()
for c, L in B.items():
    for t, new, perp, st in L:
        if new == "1" and perp == "1":
            if t < datetime(2024, 10, 1): per["07.2023–09.2024"] += 1
            elif t < datetime(2026, 11, 1): per["10.2024–10.2026"] += 1
print("\nBithumb D новые с перпом по периодам:", {k: (v, round(v / (15 if k.startswith('07') else 25), 0)) for k, v in per.items()}, "(всего, в месяц)")
# Г3: Bithumb C с перпом
Cn = collections.Counter()
for x in csv.DictReader(open(f"{OUT}/bithumb_events_C.csv")):
    if x["new_episode"] == "1" and x["binance_perp_1d"] == "1":
        t = datetime.strptime(x["start_utc"], "%Y-%m-%d %H:%M")
        Cn["до 05.08.2026" if t < datetime(2026, 8, 5) else "с 05.08.2026"] += 1
print("\nBithumb C новые с перпом:", dict(Cn), "| в месяц: до", round(Cn["до 05.08.2026"] / 37, 1), "после", round(Cn["с 05.08.2026"] / 3.5, 0))
