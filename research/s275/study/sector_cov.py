"""s275 — покрытие таблицы секторов (sectors.csv) по периодам: доля перпов и доля монето-суток вселенной топ-100 с сектором,
подсектором и сетью; средний состав топ-100 по секторам в каждом периоде. Доходы не считаются.
Запуск: из /home/user/mc_data — python3 -I <repo>/research/s275/study/sector_cov.py → OUT/sector_cov.txt"""
import collections
import os
import pickle
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common275 import OUT, PER, TMP, load_k, perps, sectors, universe  # noqa: E402

LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def main():
    SEC = sectors()
    say(f"s275 — покрытие таблицы секторов: строк {len(SEC)}")
    for per in PER:
        K = load_k(per)
        P = perps(K)
        LR = universe(K, P, per)
        del K
        has = lambda p, k: bool(SEC.get(p, {}).get(k))  # noqa: E731
        say(f"\n== {per}: перпов {len(P)}; с сектором {np.mean([has(p, 'sector') for p in P]):.0%}, "
            f"с подсектором {np.mean([has(p, 'subsector') for p in P]):.0%}, с сетью {np.mean([has(p, 'eco') for p in P]):.0%}")
        days = [d for d in LR if PER[per]["t0"] <= d < PER[per]["t1"]]
        cs = collections.Counter(); ce = collections.Counter(); n = 0; ok_s = ok_e = 0
        for d in days:
            for p in LR[d]:
                n += 1
                s = SEC.get(p, {})
                if s.get("sector"):
                    ok_s += 1; cs[s["sector"]] += 1
                if s.get("eco"):
                    ok_e += 1; ce[s["eco"]] += 1
        say(f"  монето-суток топ-100: {n}; с сектором {ok_s / n:.1%}, с сетью {ok_e / n:.1%}")
        say("  средний состав топ-100 по секторам: " + ", ".join(f"{k} {v / len(days):.1f}" for k, v in cs.most_common()))
        say("  по сетям: " + ", ".join(f"{k} {v / len(days):.1f}" for k, v in ce.most_common(12)))
    open(f"{OUT}/sector_cov.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
