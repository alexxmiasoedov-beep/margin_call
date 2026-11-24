"""s278 — таблицы для отчёта (markdown) из res_<период>.json и hyp_<период>.json (/home/user/mc_data/s278/).
Запуск: python3 -I report_tables.py > /dev/shm/s278/tables.md"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel278 import NAME, OUT  # noqa: E402

RESET = {"upbit": 0, "bithumb": 15, "okx": 16, "bitget": 16, "htx": 16, "gate": 16, "kucoin": 16, "binance_spot": 0,
         "indodax": 17, "bitkub": 17, "coindcx": 18, "btcturk": 21, "binance_try": 21, "coinbase": 4, "bitvavo": 23,
         "bitbank": 15, "gmo": 21}
HOURS = [0, 1, 15, 16, 17, 18, 21, 4]


def pct(x, d=1):
    return "—" if x is None or x != x else f"{x * 100:.{d}f}".replace(".", ",")


def num(x, d=1):
    return "—" if x is None or x != x else f"{x:.{d}f}".replace(".", ",")


def load(name):
    f = f"{OUT}/{name}.json"
    return json.load(open(f)) if os.path.exists(f) else None


def venues_table(r, title):
    print(f"\n**{title}: доля площадки V / (V + перп), медиана по монетам, %; «горб» — к соседним часам**\n")
    print("| Площадка | Монет | Оборот к перпу | 00 | 01 | 15 | 16 | 17 | 18 | 21 | 04 | Час сброса: горб | Наибольший горб |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for v, d in r["venues"].items():
        med = d["med_share"]
        hump = d["hump"]
        rh = RESET.get(v)
        hmax = max(range(24), key=lambda h: hump[h] if hump[h] == hump[h] else -1)
        days = d.get("hours", 0) / 24
        print(f"| {NAME[v]} | {d['coins']} | {pct(d['total_ratio'])}% | " + " | ".join(pct(med[h]) for h in HOURS)
              + f" | {rh:02d} UTC: {num(hump[rh], 2)} | {hmax:02d} UTC: {num(hump[hmax], 2)}"
              + (f" ({days:.0f} сут)" if days < 700 else "") + " |")


def rhythm_table(r, title):
    print(f"\n**{title}: доля суточного оборота по часам UTC, % (три самых активных часа)**\n")
    print("| Площадка | 00 | 03 | 06 | 09 | 12 | 13 | 14 | 15 | 16 | 18 | 20 | 22 | Пик (UTC) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    hs = [0, 3, 6, 9, 12, 13, 14, 15, 16, 18, 20, 22]
    pf = r["perp_frac"]
    top = sorted(range(24), key=lambda h: -pf[h])[:3]
    print("| перпы Binance | " + " | ".join(pct(pf[h]) for h in hs) + " | " + ", ".join(f"{h:02d}" for h in sorted(top)) + " |")
    for v, d in r["venues"].items():
        fr = d["frac"]
        top = sorted(range(24), key=lambda h: -fr[h])[:3]
        print(f"| {NAME[v]} | " + " | ".join(pct(fr[h]) for h in hs) + " | " + ", ".join(f"{h:02d}" for h in sorted(top)) + " |")


def events_table(r, title, groups):
    print(f"\n**{title}: скачки перпа ≥ 5% за час в месяц при доле группы в том же часе ≥ 10% / ≥ 20%**\n")
    print("| Группа | Месяцев | " + " | ".join(f"{h:02d} UTC" for h in HOURS) + " | Среднее по часам |")
    print("|---|---|" + "---|" * (len(HOURS) + 1))
    print("| все скачки | — | " + " | ".join(num(r["jumps"]["all"][h]) for h in HOURS)
          + f" | {num(sum(r['jumps']['all']) / 24)} |")
    for g, gname in groups:
        if g not in r["groups"]:
            continue
        rows = r["groups"][g]["rows"]
        a, b = rows["0.1"]["pm"], rows["0.2"]["pm"]
        print(f"| {gname} | {num(r['groups'][g]['months'])} | " + " | ".join(f"{num(a[h])} / {num(b[h])}" for h in HOURS)
              + f" | {num(sum(a) / 24)} / {num(sum(b) / 24)} |")


def signature_table(r, title, groups):
    print(f"\n**{title}: подпись часа — частота скачков у монет верхней трети доли группы (за прошлые 7 сут) "
          "к их средней по часам; в скобках — то же у нижней трети**\n")
    print("| Группа | Верхняя треть: доля ≥ | " + " | ".join(f"{h:02d} UTC" for h in HOURS) + " |")
    print("|---|---|" + "---|" * len(HOURS))
    for g, gname in groups:
        s = r["signature"].get(g)
        if not s or s["cut"][1] < 0.005:
            continue
        t, b = s["top"]["norm"], s["bot"]["norm"]
        print(f"| {gname} | {pct(s['cut'][1])}% | " + " | ".join(f"{num(t[h], 2)} ({num(b[h], 2)})" for h in HOURS) + " |")


def excess_table(r, title, groups):
    """Подпись часа одним числом: отношение «верх / низ» в часе к медиане этого отношения по всем часам."""
    import statistics
    print(f"\n**{title}: избыток скачков у монет «своей» розницы — (верх / низ в часе) / медиана (верх / низ) по часам; "
          "три часа с наибольшим избытком**\n")
    print("| Группа | 00 UTC | 15 UTC | 16 UTC | 17 UTC | Наибольший избыток |")
    print("|---|---|---|---|---|---|")
    for g, gname in groups:
        s = r["signature"].get(g)
        if not s or s["cut"][1] < 0.005:                         # доля площадки ничтожна — подпись не считается
            continue
        rat = s["ratio"]
        med = statistics.median(rat)
        ex = [x / med if med > 0 else float("nan") for x in rat]
        top = sorted(range(24), key=lambda h: -ex[h])[:3]
        print(f"| {gname} | " + " | ".join(num(ex[h], 2) for h in (0, 15, 16, 17)) + " | "
              + ", ".join(f"{h:02d} UTC: {num(ex[h], 2)}" for h in top) + " |")


def hyp_table(h1, h0):
    print("\n**Частоты гипотез (событий в месяц; доходы не считались)**\n")
    print("| Код | Правило | 2024–2026: в месяц | половины | монет | час R к другим: событий / доля среди скачков | с ⏰ | пампы | ≥ 10% | 2022–2024: в месяц |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for code, x in h1.items():
        y = (h0 or {}).get(code)
        hs = f"{num(x['pm1'])} / {num(x['pm2'])}" if x["pm1"] is not None and x["pm2"] is not None else "—"
        old = num(y["pm"]) + (f" ({num(y['months'])} мес.)" if y["months"] < 23 else "") if y else "—"
        print(f"| {code} | {x['title']} | {num(x['pm'])} ({num(x['months'])} мес.) | {hs} | {x['coins']} | "
              f"{num(x['hour_vs_other'], 2)} / {num(x.get('frac_vs_other'), 2)} | {x['o9']} | {x['pump']} | {x['big']} | {old} |")


def main():
    r1, r0 = load("res_P1"), load("res_P0")
    groups = [("KR", "Корея"), ("UP", "Upbit"), ("BT", "Bithumb"), ("CN3", "OKX + Bitget + KuCoin"),
              ("CN4", "+ Gate"), ("CN5", "+ Gate + HTX"), ("OK", "OKX"), ("BG", "Bitget"), ("KC", "KuCoin"),
              ("GT", "Gate"), ("HX", "HTX"), ("BS", "спот Binance"), ("TR", "Турция"), ("US", "Coinbase"),
              ("EU", "Bitvavo"), ("SEA", "Indodax + Bitkub"), ("IN", "CoinDCX"), ("JP", "bitbank + GMO")]
    if r1:
        venues_table(r1, "2024–2026")
        rhythm_table(r1, "2024–2026")
        events_table(r1, "2024–2026", groups)
        signature_table(r1, "2024–2026", groups)
        excess_table(r1, "2024–2026", groups)
    if r0:
        venues_table(r0, "2022–2024")
        events_table(r0, "2022–2024", groups)
        signature_table(r0, "2022–2024", groups)
        excess_table(r0, "2022–2024", groups)
    h1, h0 = load("hyp_P1"), load("hyp_P0")
    if h1:
        hyp_table(h1, h0)


if __name__ == "__main__":
    main()
