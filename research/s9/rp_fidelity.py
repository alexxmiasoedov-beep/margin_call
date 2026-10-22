"""Сверка нового scanner.repay_rule (с условием «резкий всплеск») с бэктестом research/s9 (цепочка как в repay.py) на архивных
постах MarginData в формате с CHNG (с 02.09.2025). Окно постов — ровно LOOKBACK_RP_H (худший случай: fetch_posts отдаёт не меньше)
и на 1,5 ч глубже (обычный случай: последняя страница канала захватывает лишние посты)."""
import sys, json, pickle, bisect, datetime, os
import numpy as np, pandas as pd
sys.path.insert(0, os.environ.get("BOT_DIR", "bot"))   # папка bot репозитория: BOT_DIR=…/margin_call/bot
os.environ.setdefault("STATE_FILE", "/tmp/rp_fid_state.json")
import scanner, trader
K = pickle.load(open("s2/k2y.pkl", "rb"))
posts = {}
for f in ("posts_old.jsonl", "posts.jsonl", "posts_new.jsonl", "posts_oct.jsonl", "posts_oct2.jsonl"):
    for ln in open(f):
        x = json.loads(ln)
        if len(x) < 3 or not isinstance(x[2], str): continue
        ts = datetime.datetime.fromisoformat(x[1]).timestamp()
        rows, rows_all = {}, {}
        for l in x[2].splitlines():
            r = scanner.ROW.match(l.strip())
            if r: rows[r.group(1)] = (r.group(2), r.group(3), r.group(4))
            r = scanner.ROW_ALL.match(l.strip())
            if r: rows_all[r.group(1)] = (r.group(2), r.group(3), r.group(4), r.group(5))
        if rows_all: posts[x[0]] = {"id": x[0], "ts": ts, "rows": rows, "rows_all": rows_all}
P = sorted(posts.values(), key=lambda p: p["ts"]); PTS = [p["ts"] for p in P]
NOW = [0.0]
scanner.time.time = lambda: NOW[0]
trader._contracts.clear(); trader._contracts.update({f"{s}USDT": {} for s in K})
trader.contract = lambda sym: trader._contracts.get(f"{sym}USDT")
def closed_15m(sym, T, n=99):
    a = K.get(sym)
    if a is None: return None
    j = int(np.searchsorted(a["t"], T - 900))
    if j >= len(a["t"]) or a["t"][j] != T - 900: return None
    return [[int(a["t"][i]) * 1000, 0, 0, 0, float(a["c"][i])] for i in range(max(0, j - n + 1), j + 1)]
scanner._closed_15m = closed_15m
scanner.log = lambda *a: None
T0 = int(P[0]["ts"] // 900 * 900) + 12 * 3600; T1 = int(datetime.datetime(2026, 9, 22, tzinfo=datetime.timezone.utc).timestamp())
C = pd.read_pickle("s9/repay_clean.pkl")
BASE = (C.x >= 2) & (C.run >= 6) & (C.dr >= 20e3) & (C.mv.abs() >= 0.10) & C.chain
R = C[BASE & (C["T"] >= T0) & (C["T"] < T1)].drop_duplicates(["s", "j"]).sort_values("t"); keep = []; last = {}
for i, s, T in zip(R.index, R.s, R["T"]):
    if T - last.get(s, -1e18) >= 86400: keep.append(i); last[s] = T
R = R.loc[keep]; kr = set(zip(R.s, R["T"].round()))
for extra in (0.0, 1.5):
    opened = []; last = {}
    def virt_open(state, key, sym, rule, note, price=None):
        if NOW[0] - last.get(sym, -1e18) < 24 * 3600: return None
        last[sym] = NOW[0]; opened.append((sym, NOW[0] - 60, note)); return f"↩️ {sym}"
    trader.virt_open = virt_open
    state = {}
    for T in range(T0, T1, 900):
        NOW[0] = T + 60
        lo = bisect.bisect_left(PTS, NOW[0] - (scanner.LOOKBACK_RP_H + extra) * 3600); hi = bisect.bisect_left(PTS, NOW[0])
        win = P[lo:hi][::-1]
        if win: scanner.repay_rule(state, win)
    O = pd.DataFrame(opened, columns=["s", "T", "note"]); ko = set(zip(O.s, O["T"].round()))
    print(f"окно {scanner.LOOKBACK_RP_H + extra:g} ч: бот открыл {len(O)}, бэктест {len(R)}; совпало {len(ko & kr)}, только у бота {len(ko - kr)}, только в бэктесте {len(kr - ko)}")
    for s, t in sorted(ko - kr)[:6]: print("   только у бота:", s, datetime.datetime.utcfromtimestamp(t))
    for s, t in sorted(kr - ko)[:6]: print("   только в бэктесте:", s, datetime.datetime.utcfromtimestamp(t))
    U = C.drop_duplicates(["s", "T"]).set_index(["s", "T"])
    pn = [U.p10_25.get((s, float(t))) for s, t in zip(O.s, O["T"])]
    pn = [x for x in pn if x is not None and not np.isnan(x)]
    print(f"   исходы сделок бота (по 15-мин свечам, 10/25): {len(pn)} шт., {np.mean(pn)*100:+.2f}% на сделку, WR {np.mean(np.array(pn) > 0):.0%}; "
          f"бэктест за тот же период {R.p10_25.mean()*100:+.2f}% WR {(R.p10_25 > 0).mean():.0%}")
    if extra == 0.0: print("   пример заметки:", O.note.iloc[0] if len(O) else "—")
