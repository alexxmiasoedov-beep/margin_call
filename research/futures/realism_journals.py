"""Сделки журналов бота (bot_export.txt): как бот (вход по марк-цене, выход ровно по уровню, комиссии 0,05% × 2)
и как реальный счёт (вход рыночным по цене сделок, тейк/стоп от цены исполнения, стоп с проскальзыванием 0,2%, тейк — мейкер 0,02%)."""
import re, datetime
import numpy as np
import bv
from fund_est import estimate
UTC = datetime.timezone.utc
END = int(datetime.datetime(2026, 10, 16, tzinfo=UTC).timestamp())
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
P = lambda s: int(datetime.datetime.strptime(f"2026.{s}", "%Y.%d.%m %H:%M:%S" if s.count(":") == 2 else "%Y.%d.%m %H:%M").replace(tzinfo=UTC).timestamp())
_F = {}
def fund_list(sym):
    if sym in _F: return _F[sym]
    rows = []
    for m in ("2026-08", "2026-09"):
        for p in bv.rows(bv.fetch(f"monthly/fundingRate/{sym}USDT/{sym}USDT-fundingRate-{m}.zip")):
            try: rows.append((int(p[0]) // 1000, int(float(p[1])), float(p[2])))
            except (ValueError, IndexError): pass
    rows.sort(); out = [(t, r) for t, iv, r in rows]
    if rows:
        orig = next((iv for t, iv, r in reversed(rows) if iv in (4, 8)), 8)
        out += estimate(sym, rows[-1][0], rows[-1][1], END, orig)
    _F[sym] = out; return out
def sim(sym, t0, e_mark, tp, sl, real):
    days = sorted({day(t) for t in range(t0, min(t0 + 49 * 3600, END), 3600)} | {day(t0)})
    a = bv.klines(sym, "klines", "1m", (), days); m = bv.klines(sym, "markPriceKlines", "1m", (), days)
    mm = dict(zip(m[:, 0].astype(int), m[:, 2])); mo = dict(zip(m[:, 0].astype(int), m[:, 1])); lo_ = dict(zip(a[:, 0].astype(int), a[:, 1]))
    if real:                                   # цена сделок в секунду входа: доля «цена/марк» между открытиями минут, по секундам
        M0 = t0 // 60 * 60; w = (t0 - M0) / 60
        prem = (1 - w) * (lo_[M0] / mo[M0]) + w * (lo_.get(M0 + 60, lo_[M0]) / mo.get(M0 + 60, mo[M0]))
        e = e_mark * prem
    else:
        e = e_mark
    slp, tpp = e * (1 + sl / 100), (e * (1 - tp / 100) if tp else None)
    A = a[(a[:, 0] >= (t0 // 60 + 1) * 60) & (a[:, 0] < t0 + 48 * 3600)]
    for t, o, h, l, c in A:
        if mm.get(int(t), h) >= slp: kind, px, xt = "стоп", slp * (1.002 if real else 1), t + 60; break
        if tpp and l < tpp: kind, px, xt = "тейк", tpp, t + 60; break
    else:
        if t0 + 48 * 3600 > END: return None
        kind, px, xt = "время", A[-1, 4], t0 + 48 * 3600
    fund = sum(r for t, r in fund_list(sym) if t0 < t <= xt) * 10
    fee = 10 * (0.0005 + (0.0002 if real and kind == "тейк" else 0.0005))
    return dict(kind=kind, pnl=(1 - px / e) * 10 + fund - fee, prem=(e / e_mark - 1) * 100)
res = {}
for ln in open("bot_export.txt"):
    parts = [x.strip() for x in ln.split("|")]
    m = re.match(r"(\d\d\.\d\d \d\d:\d\d:\d\d) (\S+) (\S+) вход (\S+)", parts[0])
    t0, sym, e = P(m.group(1)), m.group(2), float(m.group(4))
    for jp in parts[1:]:
        q = re.match(r".\s+(\S+)/(\d+) (время|стоп|тейк) (\d\d\.\d\d \d\d:\d\d) ([+-][\d.]+)", jp)
        if not q: continue
        tp = None if q.group(1) == "—" else float(q.group(1)); sl = float(q.group(2))
        v, r = sim(sym, t0, e, tp, sl, False), sim(sym, t0, e, tp, sl, True)
        res.setdefault(jp[0], []).append((sym, t0, float(q.group(5)), v, r))
for icon in "📓📗📘📙":
    rows = [x for x in res[icon] if x[3] and x[4]]
    bot = sum(x[2] for x in rows); v = sum(x[3]["pnl"] for x in rows); r = sum(x[4]["pnl"] for x in rows)
    diff = sum(x[3]["kind"] != x[4]["kind"] for x in rows)
    print(f"{icon}: {len(rows)} сделок до конца архива | бот {bot:+.2f} | пересчёт как бот {v:+.2f} | как реальный счёт {r:+.2f} | исход поменялся в {diff}")
prem = [x[4]["prem"] for x in res["📘"] if x[4]]
print(f"📘: цена сделок к марк-цене в момент входа — медиана {np.median(prem):+.2f}%, от {min(prem):+.2f}% до {max(prem):+.2f}%")
for x in res["📘"]:
    if x[3] and x[4] and (x[3]["kind"] != x[4]["kind"] or abs(x[4]["pnl"] - x[3]["pnl"]) > 0.15):
        print(f"  {x[0]} {datetime.datetime.fromtimestamp(x[1], UTC):%d.%m %H:%M}: как бот {x[3]['kind']} {x[3]['pnl']:+.2f} → реально {x[4]['kind']} {x[4]['pnl']:+.2f} (цена/марк {x[4]['prem']:+.2f}%)")
