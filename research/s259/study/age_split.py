"""s259, вопрос 1 (проверка на возраст) — эпизоды премии у перпов без спота и со спотом по возрасту перпа (1–30, 30–90, 90–365,
старше 365 сут): не эффект ли молодости перпов без спота. Доходы не считаются.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s259/study/age_split.py"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common259 import OUT  # noqa: E402
from premium import describe, panel  # noqa: E402


def main():
    P = panel()
    U = json.load(open(f"{OUT}/universe.json"))
    for s, d in P.items():
        d["age"] = (d["t"] - U[s]["live0"]) / 86400
    for lo, hi in ((1, 30), (30, 90), (90, 365), (365, 1e9)):
        nm = f"{lo}–{hi if hi < 1e8 else '∞'} сут"
        describe(P, lambda s, d: d["ns"], f"без спота, возраст перпа {nm}", sub=lambda s, d, lo=lo, hi=hi: (d["age"] >= lo) & (d["age"] < hi))
        describe(P, lambda s, d: ~d["ns"], f"со спотом, возраст перпа {nm}", sub=lambda s, d, lo=lo, hi=hi: (d["age"] >= lo) & (d["age"] < hi))


if __name__ == "__main__":
    main()
