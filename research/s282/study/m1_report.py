"""s282 — сводка скорости до минимума (максимума) по m1_speed.csv (только путь до экстремума).

Вывод — /home/user/mc_data/s282/m1_speed.txt.
Запуск: python3 -I <repo>/research/s282/study/m1_report.py"""
import numpy as np
import pandas as pd

OUT = "/home/user/mc_data/s282"
LINES = []


def out(s=""):
    print(s)
    LINES.append(s)


def pc(x):
    return f"{100 * np.mean(x):3.0f}%"


def block(D, lab):
    D = D[D.status == "ок"]
    if len(D) < 20:
        return
    mt, ml, mh = D.m_touch.values, D.m_low.values, D.m_half.values
    desc = mt - mh
    out(f"  {lab:<34} n={len(D):4d} | касание в мин. 0: {pc(mt == 0)}, 1–4: {pc((mt >= 1) & (mt <= 4))}, "
        f"5–9: {pc((mt >= 5) & (mt <= 9))}, 10–14: {pc(mt >= 10)} | одной минутой ≥ X: {pc(D.one.values.astype(bool))} | "
        f"до мин. касания пройдено < 25% пути: {pc(D.pre.values < 0.25)}, ≥ 75%: {pc(D.pre.values >= 0.75)} | "
        f"от половины пути до касания 0 мин.: {pc(desc == 0)}, ≥ 1: {pc(desc >= 1)}, ≥ 3: {pc(desc >= 3)} | "
        f"экстремум в минуте касания: {pc(ml == mt)}, через 1–2 мин.: {pc((ml - mt >= 1) & (ml - mt <= 2))}, ≥ 3: {pc(ml - mt >= 3)} | "
        f"экстремум в последние 3 мин. свечи: {pc(ml >= 12)}")


def main():
    D = pd.read_csv(f"{OUT}/m1_speed.csv")
    out("s282 — как быстро достигается минимум (максимум) в 15-мин свече-событии; выборка 250 событий на период, сторону и порог")
    out("Событие: минимум свечи ≤ c0·(1 − X) (вниз) или максимум ≥ c0·(1 + X) (вверх), c0 — закрытие прошлой 15-мин свечи;"
        " перп ≥ 7 сут, первое у монеты за 24 ч. Минута 0 — первая минута свечи. Только путь до экстремума.")
    for per in D.per.unique():
        out()
        out(f"=== {per}")
        for side, sl in ((-1, "вниз"), (1, "вверх")):
            for x in (0.05, 0.10):
                S = D[(D.per == per) & (D.side == side) & (D.x == x)]
                block(S, f"{sl} {100 * x:.0f}%")
    out()
    out("=== Разрезы (все периоды вместе, вниз 5% и 10%): класс по числу перпов с тем же событием в свече; оборот за 24 ч")
    S = D[D.side == -1]
    for c, lab in ((0, "одиночный"), (1, "2–4 перпа"), (2, "≥ 5, < 10% рынка"), (3, "≥ 10% рынка")):
        block(S[S.cls == c], f"вниз, {lab}")
    for lo, hi, lab in ((0, 5e6, "оборот < 5 млн $"), (5e6, 50e6, "5–50 млн $"), (50e6, np.inf, "≥ 50 млн $")):
        block(S[(S.turn >= lo) & (S.turn < hi)], f"вниз, {lab}")
    S = D[D.side == 1]
    for c, lab in ((0, "одиночный"), (3, "≥ 10% рынка")):
        block(S[S.cls == c], f"вверх, {lab}")
    open(f"{OUT}/m1_speed.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
