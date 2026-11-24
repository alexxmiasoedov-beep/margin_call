"""s267 — сводка проб: читает /home/user/mc_data/s267/probe_*.json и печатает таблицу «сеть, окно, переводов на Binance,
событий ≥ 0,5% / 0,25% / 0,1% в месяц, по монетам, крупнейший перевод».
Запуск из /home/user/mc_data: python3 -I <repo>/research/s267/study/summary.py"""
import glob
import json
import os


def main():
    for p in sorted(glob.glob("s267/probe_*.json")):
        d = json.load(open(p))
        s = d.get("summary") or {}
        if not s:
            continue
        name = os.path.basename(p)[6:-5]
        top = d.get("top") or []
        mx = max((r.get("share", 0) for r in top), default=0)
        n = d.get("n_rows", d.get("to_binance", len(d.get("rows") or [])))
        print(f"{name:28s} {d.get('days', 0):5.0f} сут | на Binance {n:6} | ≥0,5% {s['0.005']['events']:3} "
              f"({s['0.005']['per_month']:4} в мес.) | ≥0,25% {s['0.0025']['per_month']:4} | ≥0,1% {s['0.001']['per_month']:5} | "
              f"макс. {100 * mx:.2f}% | {s['0.005'].get('by_perp', '')}")


if __name__ == "__main__":
    main()
