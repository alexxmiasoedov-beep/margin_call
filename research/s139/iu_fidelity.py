"""s139 — сверка правила бота 🔑 с бэктестом U2: функция scanner._iu_candidates на сохранённых файлах DefiLlama
(s139/ll/e_<slug>.json, ll_fetch.py) против unlock_test.events() (инсайдеры, доля ≥ 1%). Горизонт правила на время сверки
растянут на весь период, поэтому одного вызова на проект хватает. Запуск из /home/user/mc_data:
python3 <repo>/research/s139/iu_fidelity.py"""
import glob
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "bot"))
os.environ.setdefault("STATE_FILE", "/tmp/claude-iu-fidelity/state.json")
import scanner  # noqa: E402
import unlock_test as U  # noqa: E402

T0, T1 = U.ts("2020-10-01"), U.ts("2026-10-19")


def main():
    scanner.IU_HORIZON_D = (T1 - T0) / 86400 + 1
    M = pd.read_pickle(f"{U.OUT}/s139/map.pkl").set_index("slug")
    bot = set()
    for f in sorted(glob.glob(f"{U.LL}/e_*.json")):
        slug = os.path.basename(f)[2:-5]
        if slug not in M.index or not isinstance(M.at[slug, "fut"], str):
            continue
        try:
            E = json.load(open(f))
        except Exception:
            continue
        for c in scanner._iu_candidates(E, T0 - 1):
            if c["T"] < T1:
                bot.add((slug, int(c["T"]), round(c["share"], 2)))
    E = U.events()
    E = E[(E.grp == "инсайдеры") & (E.share >= 0.01) & (E["T"] >= T0) & (E["T"] < T1)]
    bt = {(r.slug, int(r.T), round(r.share * 100, 2)) for r in E.itertuples()}
    kb, kt = {x[:2] for x in bot}, {x[:2] for x in bt}
    print(f"бот: {len(kb)} разлоков, бэктест: {len(kt)}, совпали {len(kb & kt)}, только у бота {len(kb - kt)}, "
          f"только в бэктесте {len(kt - kb)}")
    db = {x[:2]: x[2] for x in bot}
    off = [(k, db[k], v) for k, v in ((x[:2], x[2]) for x in bt) if k in db and abs(db[k] - v) > 0.01]
    print(f"доля разошлась больше чем на 0,01 п. п.: {len(off)}", off[:5])
    for k in sorted(kb - kt)[:5] + sorted(kt - kb)[:5]:
        print("  расхождение:", k)
    for y in (2021, 2023, 2025):
        s = U.ts(f"{y}-01-01"); e = U.ts(f"{y + 1}-01-01")
        print(f"  {y}: бот {sum(1 for x in kb if s <= x[1] < e)}, бэктест {sum(1 for x in kt if s <= x[1] < e)}")


if __name__ == "__main__":
    main()
