"""Г1, Г2, Г4 — поиск на первой половине (до 01.12.2025): регрессии Фамы — Макбета дохода к рынку через 1/3/7 суток на
ранги признаков окна 24 ч. Г1: поток Φ при равном доходе R; Г2: размер сделки TS и его взаимодействие с R; Г4: изменение
премии dPM и взаимодействие с R. Контроль — относительный оборот A и волатильность VOL. С ключом --confirm — вторая
половина. Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from feat23 import CUT, build, days, fm, fwd_ex, report

CONF = "--confirm" in sys.argv
W = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--W=")), 24))
F = build(W)
D = days(F)
D = D[D >= CUT] if CONF else D[D < CUT]
print(f"окно {W} ч, {'ВТОРАЯ половина (подтверждение)' if CONF else 'первая половина (поиск)'}: срезов {len(D)}")
for h in (24, 72, 168):
    Y = fwd_ex(F["C"], h)
    print(report(fm(F, Y, ["R", "PHI"], D), h, "Г1: доход R и поток Φ"))
    print(report(fm(F, Y, ["R", "PHI", "A", "VOL"], D), h, "Г1 с контролем оборота и волатильности"))
    print(report(fm(F, Y, ["R", "D"], D), h, "Г1′: R и «доход сверх положенного по потоку» D = R − λΦ"))
    print(report(fm(F, Y, ["R", "TS"], D, extra=lambda X: {"R×TS": X["R"] * X["TS"] * 4}), h, "Г2: размер сделки"))
    print(report(fm(F, Y, ["R", "dPM"], D, extra=lambda X: {"R×dPM": X["R"] * X["dPM"] * 4}), h, "Г4: премия"))
    print(flush=True)
