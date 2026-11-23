"""s252 — сводка частот BNB Chain по окнам пилота для отчёта: «монето-окна» с событием (не больше одного на монету и класс
в 12-часовом окне) в пересчёте на месяц, по периодам, классам и группам токенов, пороги 0,5% / 0,25%, с поправкой на пачки
по Ethereum (calib.py: отношение настоящих «первых за 48 ч» к оценке по тем же окнам). Вход — s252/cex_transfers.pkl
(events.py) и s252/windows.json. Только частоты. Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/bsc_rates.py"""
import json
import os

import pandas as pd


def main():
    E = pd.read_pickle("s252/cex_transfers.pkl")
    W = [w for w in json.load(open("s252/windows.json")) if os.path.exists(f"s252/rawwin/done_{w['id']}")]
    E["wid"] = None
    for w in W:
        E.loc[(E.t >= w["t0"]) & (E.t < w["t1"]), "wid"] = w["id"]
    E = E[E.wid.notna()]
    per = (("04–06.2025", "2025-04", "2025-06"), ("07–12.2025", "2025-07", "2025-12"), ("01–11.2026", "2026-01", "2026-11"))
    print("окон:", len(W), "часов:", sum((w["t1"] - w["t0"]) / 3600 for w in W))
    for thr in (0.005, 0.0025):
        X = E[E.frac >= thr]
        print(f"\n== порог {thr:.2%}")
        for lab, a, b in per:
            ws = [w for w in W if a <= pd.Timestamp(w["t0"], unit="s").strftime("%Y-%m") <= b]
            if not ws:
                continue
            hw = sum((w["t1"] - w["t0"]) / 3600 for w in ws)
            Z = X[X.wid.isin([w["id"] for w in ws])]
            cw = Z.drop_duplicates(["wid", "perp", "cls"])
            k = 730.5 / hw
            line = []
            for cls in ("а", "б", "г"):
                for grp in ("H", "M"):
                    n = int(((cw.cls == cls) & (cw.grp == grp)).sum())
                    line.append(f"{cls}{grp} {n * k:.0f}")
            print(f"  {lab}: окон {len(ws)} ({hw:.0f} ч), монето-окон в месяц — " + ", ".join(line) +
                  f"; переводов {len(Z)}, монет {Z.perp.nunique()}")
        Z = X[X.cls == "а"].drop_duplicates(["wid", "perp"])
        print("  биржи (а), монето-окна:", Z.ex.value_counts().to_dict())
        Z = X[X.cls == "б"].drop_duplicates(["wid", "perp"])
        print("  биржи (б), монето-окна:", Z.ex.value_counts().to_dict())


if __name__ == "__main__":
    main()
