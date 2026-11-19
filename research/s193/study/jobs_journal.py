"""s193 — задания «сутки входа журнала» (фьючерсы): до 150 случайных входов на журнал и период (seed 193), сутки входа
UTC; вход в первые 2 ч суток — ещё и предыдущие сутки (окно до входа). Для частот «алгоритм идёт в момент входа»
(доходы не считаются). Итог — /home/user/mc_data/s193/jobs_journal.pkl (+ entries_journal.pkl: монета, время входа)."""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/margin_call/research/s183/study")
import common183 as C  # noqa: E402

D = "/home/user/mc_data/s193"
DAY = 86400


def main():
    rng = np.random.default_rng(193)
    J0 = pd.read_pickle(f"{D}/jobs.pkl")
    have = set(zip(J0.mkt, J0.s, J0.d))
    perps = {}
    for per in C.PERS:
        perps[per] = set(pd.read_pickle(f"{C.D}/s183/daily_{per}.pkl").s.unique())
    jobs, ents = {}, []
    for per in C.PERS:
        Jr = C.journals(per)
        t0, t1 = C.ts(C.PER[per]["t0"]), C.ts(C.PER[per]["t1"])
        Jr = Jr[(Jr.t >= t0) & (Jr.t < t1)]
        for j, g in Jr.groupby("j"):
            g = g.iloc[np.sort(rng.choice(len(g), min(150, len(g)), replace=False))]
            for s, t in zip(g.s, g.t):
                p = s if s in perps[per] else ("1000" + s if "1000" + s in perps[per] else None)
                if p is None:
                    continue
                d = (int(t) // DAY) * DAY
                ents.append(dict(per=per, j=j, s=p, t=int(t), d=d))
                for dd in ([d - DAY, d] if t - d < 7200 else [d]):
                    k = ("um", p, dd)
                    if k in have:
                        continue
                    jobs.setdefault(k, dict(mkt="um", s=p, d=dd, per=per, tags=set(), inj=0))["tags"].add("journal")
    J = pd.DataFrame(jobs.values())
    J["tags"] = J.tags.map(lambda z: ",".join(sorted(z)))
    J.to_pickle(f"{D}/jobs_journal.pkl")
    E = pd.DataFrame(ents)
    E.to_pickle(f"{D}/entries_journal.pkl")
    print("входов:", len(E), E.groupby(["per", "j"]).size().to_dict())
    print("новых заданий:", len(J), J.groupby("per").size().to_dict())


if __name__ == "__main__":
    main()
