"""s220 — сбор крупных сметаний на Binance 1 по всем токенам Solana с фьючерсом (sol_circ.json) за 01.10.2024–30.10.2026.
Порог сбора — 0,25% наименьшего числа монет в обращении за период (в анализе s221 — 0,5% обращения дня до завода).
Шаг выборки остатка — не реже 1500 точек на токен (у монет с большим потоком операций шаг больше 100).
Готовые токены пропускаются (events/<фьючерс>_all.json). Запуск из /home/user/mc_data/s220:
  python3 <repo>/research/s220/collect_all.py"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
D0, D1 = "2024-10-01", "2026-10-30"


def main():
    C = json.load(open("sol_circ.json"))
    for fs, r in sorted(C.items()):
        out = f"events/{fs}_all.json"
        if os.path.exists(out):
            continue
        circ = [c for d, c, _ in r["days"] if D0 <= d <= D1 and c]
        if not circ:
            print(fs, "нет обращения CMC за период", flush=True); continue
        thr = 0.0025 * min(circ)
        p = subprocess.run([sys.executable, os.path.join(HERE, "collect.py"), fs, r["mint"], D0, D1, f"{thr:.6f}", "all"],
                           capture_output=True, text=True, timeout=6 * 3600)
        print(p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr.strip()[-300:], flush=True)


if __name__ == "__main__":
    main()
