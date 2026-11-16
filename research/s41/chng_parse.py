"""s41 — разбор постов канала (s41/posts.jsonl, chng_scrape.py) в строки «монета, время, займ, отдача, B/R, CHNG» и проверка,
что считает CHNG: сравнение с изменением займа, отдачи и B/R той же монеты от прошлого поста. Итог — s41/rows.pkl.
Запуск из папки с данными."""
import datetime
import json
import re
import numpy as np, pandas as pd

ROW = re.compile(r"^([A-Z0-9]+)\s+([\d.]+[KMB]?)\s+([\d.]+[KMB]?)\s+(\S+)\s+([+-]?[\d.]+)\s*$")


def num(x):
    m = {"K": 1e3, "M": 1e6, "B": 1e9}.get(x[-1:], 1)
    try:
        return float(x[:-1] if m != 1 else x) * m
    except ValueError:
        return np.nan


def parse():
    rows, heads = [], {}
    for ln in open("s41/posts.jsonl"):
        pid, ts, text = json.loads(ln)
        if "CHNG" not in text:
            continue
        t = datetime.datetime.fromisoformat(ts).timestamp()
        lines = text.split("\n")
        heads[lines[0][:60]] = heads.get(lines[0][:60], 0) + 1
        for l in lines:
            r = ROW.match(l.strip())
            if not r:
                continue
            br = np.inf if r.group(4) == "inf" else num(r.group(4))
            rows.append((r.group(1), t, pid, num(r.group(2)), num(r.group(3)), br, float(r.group(5))))
    R = pd.DataFrame(rows, columns=["c", "t", "pid", "bor", "rep", "br", "chng"]).sort_values(["c", "t"]).reset_index(drop=True)
    return R, heads


if __name__ == "__main__":
    R, heads = parse()
    R.to_pickle("s41/rows.pkl")
    print("строк:", len(R), "| монет:", R.c.nunique(), "| постов:", R.pid.nunique(),
          "| период:", pd.to_datetime(R.t.min(), unit="s"), "→", pd.to_datetime(R.t.max(), unit="s"))
    print("частые заголовки:", sorted(heads.items(), key=lambda kv: -kv[1])[:3])
    print("CHNG перцентили 1/5/25/50/75/95/99:", np.round(np.percentile(R.chng, [1, 5, 25, 50, 75, 95, 99]), 3))
    print(f"доля CHNG > 0: {(R.chng > 0).mean():.1%}, = 0: {(R.chng == 0).mean():.1%}, < 0: {(R.chng < 0).mean():.1%}, > 1: {(R.chng > 1).mean():.2%}")
    # что считает CHNG: изменения от прошлого поста той же монеты (≤ 2 ч назад)
    g = R.groupby("c")
    R["dt"] = g.t.diff(); R["dbor"] = g.bor.diff(); R["drep"] = g.rep.diff(); R["dbr"] = g.br.diff()
    R["bor_prev"] = g.bor.shift(); R["br_prev"] = g.br.shift()
    X = R[(R.dt > 0) & (R.dt <= 7200) & np.isfinite(R.br) & np.isfinite(R.br_prev)].copy()
    X["dbor_rel"] = X.dbor / X.bor_prev
    X["net_m"] = (X.dbor - X.drep) / 1e6
    for c in ("dbr", "dbor_rel", "net_m", "br"):
        ok = np.isfinite(X[c]) & np.isfinite(X.chng)
        print(f"  корреляция CHNG с {c:9s}: Пирсон {np.corrcoef(X.chng[ok], X[c][ok])[0, 1]:+.3f}, ранги {X.chng[ok].rank().corr(X[c][ok].rank()):+.3f}")
    print("примеры (монета, займ, отдача, B/R, CHNG, прошлый B/R):")
    print(X.sample(12, random_state=1)[["c", "bor", "rep", "br", "chng", "br_prev", "bor_prev"]].to_string(index=False))
