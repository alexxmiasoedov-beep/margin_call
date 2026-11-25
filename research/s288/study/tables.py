"""s288 — сводные таблицы для ВЫВОДЫ.md из итогов скриптов (cat_counts.csv, scale_summary.csv): только счёт и кратности.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s288/study/tables.py → s288/tables.md"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common288 as C  # noqa: E402

P3 = ("2020–2022", "2022–2024", "2024–2026")


def f(x, d=1):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def main():
    out = []
    CT = pd.read_csv(f"{C.OUT}/cat_counts.csv").set_index("категория")
    out.append("| Категория | 2020–2022 | 2022–2024 | 2024–2026 | свежий |\n|---|---:|---:|---:|---:|")
    for c, r in CT.sort_values("2024–2026", ascending=False).iterrows():
        if max(r[list(C.PER)]) < 1:
            continue
        out.append(f"| {c} | " + " | ".join(f(r[p]) for p in C.PER) + " |")
    S = pd.read_csv(f"{C.OUT}/scale_summary.csv")
    out.append("\n| Семья | В месяц | \\|ход\\| BTC 15 мин | \\|ход\\| BTC 60 мин | \\|ход\\| корзины альтов 60 мин | \\|ход\\| монеты 60 мин | "
               "оборот 60 мин (BTC; монеты) | \\|ход\\| BTC за 60 мин ДО |\n|---|---|---|---|---|---|---|---|")
    for fam in S["семья"].unique():
        x = S[S["семья"] == fam].set_index("период")

        def tri(c, d=1):
            return " / ".join(f(x.loc[p, c], d) if p in x.index else "—" for p in P3)
        coin = tri("coin_a60_x", 2) if x["coin_a60_x"].notna().any() else "—"
        q = tri("coin_q60_x", 2) if x["coin_q60_x"].notna().any() else tri("btc_q60_x", 2)
        out.append(f"| {fam} | {tri('в месяц')} | {tri('btc_a15_x', 2)} | {tri('btc_a60_x', 2)} | {tri('idx_a60_x', 2)} | "
                   f"{coin} | {q} | {tri('btc_pre60_x', 2)} |")
    open(f"{C.OUT}/tables.md", "w").write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
