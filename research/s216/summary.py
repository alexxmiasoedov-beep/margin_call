"""s216 — сводка перебора по восьми исходам и перемешанному контролю (пороги находки 1–2 из ВЫВОДЫ.md).
Запуск из /home/user/mc_data после bombe.py по всем исходам: python3 <repo>/research/s216/summary.py"""
import os

import numpy as np
import pandas as pd

OUTS = ("s4", "s24", "s48", "s168", "l4", "l24", "l48", "l168")
NAME = {"s4": "шорт 4 ч", "s24": "шорт 24 ч", "s48": "шорт 48 ч", "s168": "шорт 7 сут",
        "l4": "лонг 4 ч", "l24": "лонг 24 ч", "l48": "лонг 48 ч", "l168": "лонг 7 сут"}


def main():
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 120)
    rows, bests = [], []
    for o in OUTS:
        p = f"s216_bombe_{o}.pkl"
        if not os.path.exists(p):
            continue
        R = pd.read_pickle(p); base = R.attrs["base"]; P = R[R.passB]
        sh = []
        for k in range(3):
            q = f"s216_bombe_{o}_shuf{k}.pkl"
            if os.path.exists(q):
                S = pd.read_pickle(q); SP = S[S.passB]
                sh.append((len(SP), SP.m_C.mean() if len(SP) else np.nan))
        shm = np.nanmean([x[1] for x in sh]) if sh else np.nan
        best = P.sort_values("z_B", ascending=False).iloc[0] if len(P) else None
        ok1 = len(P) > 0 and P.m_C.mean() > base[2] and P.m_C.mean() > shm
        ok2 = best is not None and best.m_C > 0 and best.z_C >= 2.5
        rows.append({"исход": NAME[o], "все A/B/C": f"{base[0]:+.2%} / {base[1]:+.2%} / {base[2]:+.2%}",
                     "прошли B": len(P), "их C": f"{P.m_C.mean():+.2%}" if len(P) else "—",
                     "контроль: прошли B / их C": " · ".join(f"{n} / {m:+.2%}" for n, m in sh),
                     "лучшее по B на C": f"{best.m_C:+.2%} (t {best.z_C:+.1f}, n {best.n_C:.0f})" if best is not None else "—",
                     "порог 1": "да" if ok1 else "нет", "порог 2": "да" if ok2 else "нет"})
        if best is not None:
            bests.append((NAME[o], best["правило"], best))
    print(pd.DataFrame(rows).to_string(index=False))
    print("\nЛучшие по B правила (выбраны до просмотра C):")
    for nm, rule, b in bests:
        print(f"  {nm}: {rule}\n    A {b.m_A:+.2%} (n {b.n_A:.0f}, t {b.z_A:+.1f}) | B {b.m_B:+.2%} (n {b.n_B:.0f}, t {b.z_B:+.1f}) | "
              f"C {b.m_C:+.2%} (n {b.n_C:.0f}, t {b.z_C:+.1f})")


if __name__ == "__main__":
    main()
