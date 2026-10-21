"""Маржинальный канал (займы на марже Binance, посты раз в минуту с 20.02.2025): разбор всех постов и признаки на момент
каждого пампа — есть ли монета в канале, сколько часов подряд, сколько занято (BOR), B/R, место в посте, доля постов за сутки."""
import json, re, datetime, pickle
import numpy as np, pandas as pd
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
def num(x):
    x = x.strip().replace(",", ".")
    m = {"K": 1e3, "M": 1e6, "B": 1e9}.get(x[-1:].upper(), 1)
    try: return float(x[:-1] if m != 1 else x) * m
    except ValueError: return np.nan
posts = {}
for f in ("posts_old.jsonl", "posts.jsonl", "posts_new.jsonl", "posts_oct.jsonl", "posts_oct2.jsonl"):
    for ln in open(f):
        x = json.loads(ln)
        if len(x) > 2 and isinstance(x[2], str) and ("B/R" in x[2][:60]): posts[x[0]] = (x[1], x[2])
rows = []; PT = []
for pid, (ts, txt) in sorted(posts.items()):
    t = datetime.datetime.fromisoformat(ts).timestamp(); PT.append(t); rank = 0
    for ln in txt.split("\n")[2:]:
        p = ln.split()
        if len(p) < 4 or ln.startswith("MarginData"): continue
        sym = re.sub(r"[^\w]", "", p[0])
        if not sym: continue
        rank += 1; rows.append((sym, t, num(p[1]), num(p[2]), num(p[3]) if p[3] != "inf" else np.inf, rank))
M = pd.DataFrame(rows, columns=["sym", "t", "bor", "rep", "br", "rank"]); PT = np.array(sorted(PT))
print("постов", len(PT), "строк", len(M), "монет", M.sym.nunique(), datetime.datetime.utcfromtimestamp(PT[0]), "→", datetime.datetime.utcfromtimestamp(PT[-1]))
G = {s: g[["t", "bor", "rep", "br", "rank"]].to_numpy() for s, g in M.groupby("sym")}
pickle.dump({"G": G, "PT": PT}, open("s7/margin.pkl", "wb"))
D = pd.read_pickle("s6/feat.pkl")[["s", "t"]]; GAP = 30 * 60
out = []
for s, T in zip(D.s, D.t):
    r = dict(s=s, t=T); k = np.searchsorted(PT, T) - 1
    if k < 0 or T - PT[k] > GAP: out.append(r); continue            # канал молчал — нет данных
    a = G.get(strip(s)); r["mc_alive"] = 1
    if a is None: r.update(mc_in=0, mc_run=0.0, mc_share24=0.0); out.append(r); continue
    m = a[:, 0] < T; a = a[m]
    if not len(a): r.update(mc_in=0, mc_run=0.0, mc_share24=0.0); out.append(r); continue
    last = a[-1]; inn = T - last[0] <= GAP
    st = last[0]
    if inn:
        tt = a[:, 0][::-1]; gaps = np.flatnonzero(-np.diff(tt) > GAP)
        st = tt[gaps[0]] if len(gaps) else tt[-1]
    a24 = a[a[:, 0] >= T - 86400]; n24 = ((PT >= T - 86400) & (PT < T)).sum()
    r.update(mc_in=int(inn), mc_run=(T - st) / 3600 if inn else 0.0, mc_bor=last[1] if inn else 0.0, mc_br=min(last[3], 1e4) if inn else np.nan,
             mc_rank=last[4] if inn else np.nan, mc_bor24=a24[:, 1].max() if len(a24) else 0.0, mc_share24=len(a24) / max(n24, 1),
             mc_seen7=int((a[:, 0] >= T - 7 * 86400).any()))
    out.append(r)
R = pd.DataFrame(out); R.to_pickle("s7/ev_margin.pkl")
print(R.notna().mean().round(2).to_dict()); print("в канале в момент пампа:", R.mc_in.mean().round(3), "из пампов с живым каналом")
