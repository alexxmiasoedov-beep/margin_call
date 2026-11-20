"""s224b — сборка свежего отрезка D из собранного d_fetch.py (метод — ВЫВОДЫ.md, коммит a47b59b). Этапы:
- gmerge — разбор канала: прежний s7/margin.pkl (по 21.10.2026 05:51) + посты позже него из s41/posts.jsonl и
  s224/posts_new.jsonl тем же разбором, что s7/margin_ev.py → s224/work/s7/margin.pkl; сверка разбора на постах 01–21.10.2026;
- kmerge — свечи и фандинг: s2/k2y.pkl + хвосты s224/kl (заглушки без объёма с прежней ценой там, где свечи нет) →
  s224/k_d.pkl; s2/fund2y.pkl + месяцы s15/fund (как s15/common.funding) + хвосты s224/fund → s224/fund_d.pkl;
- panel — research/s21/borrow_study.py в s224/work на новых свечах (MC_K, MC_F) → s224/work/s21/panel.pkl; сверка с прежней;
- features — research/s216/features.py (GRID=1, T0=2026-10-01) и research/s223/features.py → s224/feat_D.pkl;
- check — сверка feat_D с s216_feat.pkl на общих (монета, T) сетки 4 ч.
Перед features нужны d_fetch.py rates, metrics, cmc. Запуск из /home/user/mc_data:
python3 <repo>/research/s224/d_build.py <этап> […]"""
import datetime
import json
import os
import pickle
import re
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..")
UTC = datetime.timezone.utc
KEND = 1792367100
TAIL0 = KEND + 900
END = int(datetime.datetime(2026, 11, 20, tzinfo=UTC).timestamp())
OUT = "s224"
WORK = f"{OUT}/work"
ENV = dict(os.environ, MC_K=os.path.abspath(f"{OUT}/k_d.pkl"), MC_F=os.path.abspath(f"{OUT}/fund_d.pkl"))


def num(x):
    x = x.strip().replace(",", ".")
    m = {"K": 1e3, "M": 1e6, "B": 1e9}.get(x[-1:].upper(), 1)
    try:
        return float(x[:-1] if m != 1 else x) * m
    except ValueError:
        return np.nan


def parse(posts):
    """Тот же разбор, что s7/margin_ev.py: строки (монета, время, займ, отдача, B/R, место в посте) и времена постов."""
    rows, PT = [], []
    for pid, (ts, txt) in sorted(posts.items()):
        t = datetime.datetime.fromisoformat(ts).timestamp(); PT.append(t); rank = 0
        for ln in txt.split("\n")[2:]:
            p = ln.split()
            if len(p) < 4 or ln.startswith("MarginData"):
                continue
            sym = re.sub(r"[^\w]", "", p[0])
            if not sym:
                continue
            rank += 1; rows.append((sym, t, num(p[1]), num(p[2]), num(p[3]) if p[3] != "inf" else np.inf, rank))
    return rows, PT


def read_posts(paths, t_from=None, t_to=None):
    posts = {}
    for f in paths:
        for ln in open(f):
            x = json.loads(ln)
            if len(x) > 2 and isinstance(x[2], str) and ("B/R" in x[2][:60]) and x[0] not in posts:
                t = datetime.datetime.fromisoformat(x[1]).timestamp()
                if (t_from is None or t > t_from) and (t_to is None or t <= t_to):
                    posts[x[0]] = (x[1], x[2])
    return posts


def gmerge():
    M = pickle.load(open("s7/margin.pkl", "rb")); G, PT = M["G"], M["PT"]
    tl = float(PT[-1])
    # сверка разбора: посты s41 за 01.10.2026 … конец прежнего разбора против прежних строк
    t0 = datetime.datetime(2026, 10, 1, tzinfo=UTC).timestamp()
    rows, pt = parse(read_posts(["s41/posts.jsonl"], t0 - 1e-9, tl))
    new = {(r[0], r[1]): r[2:] for r in rows}
    old = {}
    for c, g in G.items():
        for r in g[(g[:, 0] >= t0) & (g[:, 0] <= tl)]:
            old[(c, float(r[0]))] = tuple(r[1:])
    same = sum(1 for k, v in old.items() if k in new and all((a == b) or (np.isnan(a) and np.isnan(b)) for a, b in zip(v, new[k])))
    print(f"сверка разбора за 01.10–21.10: постов прежних {int(((PT >= t0) & (PT <= tl)).sum())}, новых {len(pt)}; строк "
          f"прежних {len(old)}, новых {len(new)}, совпали {same} ({same / max(len(old), 1):.2%})", flush=True)
    rows, pt = parse(read_posts(["s41/posts.jsonl", f"{OUT}/posts_new.jsonl"], tl))
    Mn = pd.DataFrame(rows, columns=["sym", "t", "bor", "rep", "br", "rank"])
    G2 = dict(G)
    for s, g in Mn.groupby("sym"):
        a = g[["t", "bor", "rep", "br", "rank"]].to_numpy(dtype=float)
        G2[s] = np.vstack([G[s].astype(float), a]) if s in G else a
    PT2 = np.array(sorted(list(PT) + pt))
    os.makedirs(f"{WORK}/s7", exist_ok=True)
    pickle.dump({"G": G2, "PT": PT2}, open(f"{WORK}/s7/margin.pkl", "wb"))
    print(f"разбор канала: новых постов {len(pt)}, строк {len(Mn)}, монет {Mn.sym.nunique()}; посты по "
          f"{datetime.datetime.fromtimestamp(PT2[-1], UTC):%Y-%m-%d %H:%M}", flush=True)


def kmerge():
    K = pickle.load(open("s2/k2y.pkl", "rb"))
    grid = np.arange(TAIL0, END, 900, dtype=np.int64)
    fields = ("o", "h", "l", "c", "qv", "tb", "n")
    ext = stub = 0
    for s in list(K):
        a = K[s]
        if int(a["t"][-1]) != KEND:
            continue
        p = f"{OUT}/kl/{s}.npy"
        x = np.load(p) if os.path.exists(p) else np.zeros((0, 8))
        T = {f: np.full(len(grid), np.nan) for f in fields}
        if len(x):
            i = ((x[:, 0] - TAIL0) // 900).astype(int); ok = (i >= 0) & (i < len(grid))
            for j, f in enumerate(fields):
                T[f][i[ok]] = x[ok, j + 1]
        last = float(a["c"][-1]); empty = 0
        for k in range(len(grid)):                       # заглушки: без объёма, цена — последнее закрытие
            if np.isnan(T["c"][k]):
                T["o"][k] = T["h"][k] = T["l"][k] = T["c"][k] = last
                T["qv"][k] = T["tb"][k] = T["n"][k] = 0.0; empty += 1
            last = T["c"][k]
        K[s] = {"t": np.concatenate([a["t"], grid])} | {f: np.concatenate([a[f], T[f].astype(np.float32)]) for f in fields}
        ext += 1; stub += empty == len(grid)
    new = 0
    for p in sorted(os.listdir(f"{OUT}/kl")):
        s = p[:-4]
        if s in K:
            continue
        x = np.load(f"{OUT}/kl/{p}")
        if not len(x):
            continue
        g = np.arange(int(x[0, 0]), END, 900, dtype=np.int64)
        T = {f: np.full(len(g), np.nan) for f in fields}
        i = ((x[:, 0] - g[0]) // 900).astype(int)
        for j, f in enumerate(fields):
            T[f][i] = x[:, j + 1]
        last = float(x[0, 4])
        for k in range(len(g)):
            if np.isnan(T["c"][k]):
                T["o"][k] = T["h"][k] = T["l"][k] = T["c"][k] = last
                T["qv"][k] = T["tb"][k] = T["n"][k] = 0.0
            last = T["c"][k]
        K[s] = {"t": g} | {f: T[f].astype(np.float32) for f in fields}
        new += 1
    pickle.dump(K, open(f"{OUT}/k_d.pkl", "wb"), protocol=4)
    print(f"свечи: продлено {ext} (из них только заглушки {stub}), новых {new}; конец "
          f"{datetime.datetime.fromtimestamp(int(K['BTC']['t'][-1]), UTC):%Y-%m-%d %H:%M}", flush=True)
    FU = pickle.load(open("s2/fund2y.pkl", "rb"))
    out = {}
    for s in K:
        f = FU.get(s)
        rows = [(float(r[0]), float(r[1]), float(r[2])) for r in f] if f is not None else []
        last = max((r[0] for r in rows), default=0)
        for m in ("2026-09", "2026-10"):                 # как s15/common.funding без MC_F
            path = f"s15/fund/{s}-{m}.csv"
            if os.path.exists(path):
                for ln in open(path).read().splitlines():
                    p = ln.split(",")
                    if p and p[0].isdigit() and int(p[0]) // 1000 > last:
                        rows.append((float(int(p[0]) // 1000), float(p[1]), float(p[2])))
        last = max((r[0] for r in rows), default=0)
        path = f"{OUT}/fund/{s}.csv"
        if os.path.exists(path):
            for ln in open(path).read().splitlines():
                t, v = ln.split(",")
                if int(t) // 1000 > last:
                    rows.append((float(int(t) // 1000), np.nan, float(v)))
        if rows:
            out[s] = np.array(sorted(rows), dtype=np.float64)
    pickle.dump(out, open(f"{OUT}/fund_d.pkl", "wb"), protocol=4)
    print(f"фандинг: символов {len(out)}; BTC последнее начисление "
          f"{datetime.datetime.fromtimestamp(int(out['BTC'][-1, 0]), UTC):%Y-%m-%d %H:%M}", flush=True)


def panel():
    os.makedirs(f"{WORK}/s21", exist_ok=True)
    p = subprocess.run([sys.executable, os.path.join(RES, "s21", "borrow_study.py")], cwd=WORK, env=ENV,
                       capture_output=True, text=True)
    print(p.stdout[-600:], p.stderr[-1500:], flush=True)
    A = pd.read_pickle("s21/panel.pkl"); B = pd.read_pickle(f"{WORK}/s21/panel.pkl")
    tl = A["T"].max()
    cols = ["s", "T", "bor", "rep", "bor4", "rep4", "in4"]
    m = A[cols].merge(B[B["T"] <= tl][cols], on=["s", "T"], how="outer", suffixes=("", "_n"), indicator=True)
    both = m[m._merge == "both"]
    eq = np.all([np.isclose(both[c].astype(float), both[c + "_n"].astype(float), rtol=1e-9, equal_nan=True)
                 for c in cols[2:]], axis=0)
    print(f"панель: строк {len(B)}, по {datetime.datetime.fromtimestamp(int(B['T'].max()), UTC):%Y-%m-%d %H:%M}; сверка с "
          f"прежней до {datetime.datetime.fromtimestamp(int(tl), UTC):%Y-%m-%d %H:%M}: общих {len(both)}, только в прежней "
          f"{(m._merge == 'left_only').sum()}, только в новой {(m._merge == 'right_only').sum()}, совпали все поля "
          f"{eq.mean():.4%}", flush=True)


def features():
    env = dict(ENV, GRID="1", T0="2026-10-01", OUT="feat_raw_D.pkl")
    for f in ("s167",):
        if not os.path.lexists(f"{WORK}/{f}"):
            os.symlink(os.path.abspath(f), f"{WORK}/{f}")
    p = subprocess.run([sys.executable, os.path.join(RES, "s216", "features.py")], cwd=WORK, env=env, capture_output=True,
                       text=True)
    print(p.stdout[-1500:], p.stderr[-1500:], flush=True)
    env = dict(ENV, IN="feat_raw_D.pkl", OUT=os.path.abspath(f"{OUT}/feat_D.pkl"))
    p = subprocess.run([sys.executable, os.path.join(RES, "s223", "features.py")], cwd=WORK, env=env, capture_output=True,
                       text=True)
    print(p.stdout[-1500:], p.stderr[-800:], flush=True)


def check():
    A = pd.read_pickle("s216_feat.pkl"); D = pd.read_pickle(f"{OUT}/feat_D.pkl")
    t0 = datetime.datetime(2026, 10, 1, tzinfo=UTC).timestamp(); tl = A["T"].max()
    A = A[A["T"] >= t0]
    B = D[(D["T"] % (4 * 3600) == 0) & (D["T"] <= tl)]
    m = A.merge(B, on=["s", "T"], how="outer", suffixes=("", "_n"), indicator=True)
    both = m[m._merge == "both"]
    print(f"сверка с s216_feat.pkl за 01.10 … {datetime.datetime.fromtimestamp(int(tl), UTC):%Y-%m-%d %H:%M} (сетка 4 ч): "
          f"общих {len(both)}, только в s216 {(m._merge == 'left_only').sum()}, только в D {(m._merge == 'right_only').sum()}")
    feats = [c for c in A.columns if c not in ("s", "T") and not re.fullmatch(r"[sl]\d+", c)]
    res = []
    for c in feats + [c for c in A.columns if re.fullmatch(r"[sl]\d+", c)]:
        x, y = both[c].to_numpy(float), both[c + "_n"].to_numpy(float)
        same = (np.isnan(x) & np.isnan(y)) | (np.abs(x - y) <= 1e-6 * np.maximum(np.abs(x), np.abs(y)) + 1e-12)
        both_ok = np.isfinite(x) & np.isfinite(y)
        res.append((c, same.mean(), (np.isnan(x) & ~np.isnan(y)).mean(), (~np.isnan(x) & np.isnan(y)).mean(),
                    (both_ok & ~same).mean()))
    R = pd.DataFrame(res, columns=["признак", "совпало", "NaN только в s216", "NaN только в D", "разные числа"])
    print(R.to_string(index=False, float_format=lambda v: f"{v:.2%}"))
    bad = R[(R["признак"].isin(feats)) & (R["совпало"] < 0.95)]
    print("порог ≥ 95% по каждому признаку:", "пройден" if bad.empty else "НЕ пройден: " + ", ".join(bad["признак"]))
    days = pd.to_datetime(D["T"], unit="s").dt.strftime("%Y-%m-%d").value_counts().sort_index()
    print("наблюдений feat_D по дням:", ", ".join(f"{d[5:]} {n}" for d, n in days.items()))
    R.to_csv(f"{OUT}/check.csv", index=False)


if __name__ == "__main__":
    for st in sys.argv[1:]:
        {"gmerge": gmerge, "kmerge": kmerge, "panel": panel, "features": features, "check": check}[st]()
