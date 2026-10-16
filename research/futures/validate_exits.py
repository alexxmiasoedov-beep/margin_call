"""Проверка выходов: входы ровно как у бота (время и цена из выгрузки), исходы считаем по архиву и сравниваем с ботом."""
import re, datetime, pickle
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
def sim(sym, t0, e, tp, sl):
    days = sorted({day(t) for t in range(t0, min(t0 + 49 * 3600, END), 3600)} | {day(t0)})
    a = bv.klines(sym, "klines", "1m", (), days); m = bv.klines(sym, "markPriceKlines", "1m", (), days)
    mm = dict(zip(m[:, 0].astype(int), m[:, 2]))
    slp, tpp = e * (1 + sl / 100), (e * (1 - tp / 100) if tp else None)
    A = a[(a[:, 0] >= (t0 // 60 + 1) * 60) & (a[:, 0] < t0 + 48 * 3600)]
    for t, o, h, l, c in A:
        if mm.get(int(t), h) >= slp: kind, px, xt = "стоп", slp, t + 60; break
        if tpp and l < tpp: kind, px, xt = "тейк", tpp, t + 60; break
    else:
        if t0 + 48 * 3600 <= END: kind, px, xt = "время", A[-1, 4], t0 + 48 * 3600
        else: return None
    fund = sum(r for t, r in fund_list(sym) if t0 < t <= xt) * 10
    return dict(kind=kind, closed=xt, pnl=(1 - px / e) * 100 * 10 / 100 + fund - 0.01, fund=fund)
rows = []
for ln in open("bot_export.txt"):
    parts = [x.strip() for x in ln.split("|")]
    m = re.match(r"(\d\d\.\d\d \d\d:\d\d:\d\d) (\S+) (\S+) вход (\S+)", parts[0])
    t0, sym, rule, e = P(m.group(1)), m.group(2), m.group(3), float(m.group(4))
    for jp in parts[1:]:
        icon = jp[0]; q = re.match(r".\s+(\S+)/(\d+) (время|стоп|тейк) (\d\d\.\d\d \d\d:\d\d) ([+-][\d.]+) ф([+-][\d.]+)", jp)
        if not q: continue
        tp = None if q.group(1) == "—" else float(q.group(1)); sl = float(q.group(2))
        bot = dict(kind=q.group(3), closed=P(q.group(4)), pnl=float(q.group(5)), fund=float(q.group(6)))
        rows.append((icon, sym, t0, e, tp, sl, bot, sim(sym, t0, e, tp, sl)))
ok = [(r, s) for *r, s in rows if s is not None]
print(f"сделок бота с исходом до конца архива: {len(ok)} из {len(rows)}")
same = sum(r[6]["kind"] == s["kind"] for r, s in ok)
print(f"исход совпал: {same} из {len(ok)}")
dmin = [abs(s["closed"] - r[6]["closed"]) / 60 for r, s in ok if r[6]["kind"] == s["kind"] and s["kind"] != "время"]
print(f"время стопа/тейка: медиана расхождения {np.median(dmin):.1f} мин, макс {max(dmin):.0f} мин")
dp = [s["pnl"] - r[6]["pnl"] for r, s in ok]; df_ = [s["fund"] - r[6]["fund"] for r, s in ok]
print(f"итог сделки: средняя разница {np.mean(dp):+.3f}, медиана |разницы| {np.median(np.abs(dp)):.3f}, макс {max(np.abs(dp)):.2f}")
print(f"фандинг: сумма у бота {sum(r[6]['fund'] for r, s in ok):+.2f}, в пересчёте {sum(s['fund'] for r, s in ok):+.2f}")
for icon in "📓📗📘📙":
    sel = [(r, s) for r, s in ok if r[0] == icon]
    print(f"  {icon}: бот {sum(r[6]['pnl'] for r, s in sel):+.2f}, пересчёт {sum(s['pnl'] for r, s in sel):+.2f} ({len(sel)} сделок)")
for r, s in ok:
    if r[6]["kind"] != s["kind"] or abs(s["pnl"] - r[6]["pnl"]) > 0.15:
        print(f"  ≠ {r[0]} {r[1]} {datetime.datetime.fromtimestamp(r[2], UTC):%d.%m %H:%M} {r[4] or '—'}/{r[5]:g}: бот {r[6]['kind']} {r[6]['pnl']:+.2f} ф{r[6]['fund']:+.2f} | пересчёт {s['kind']} {s['pnl']:+.2f} ф{s['fund']:+.2f}")
print("сдвиг времени закрытия > 5 мин:")
for r, s in ok:
    if r[6]["kind"] == s["kind"] and s["kind"] != "время" and abs(s["closed"] - r[6]["closed"]) > 300:
        f = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%d.%m %H:%M")
        print(f"  {r[0]} {r[1]} {r[6]['kind']}: по архиву {f(s['closed'])}, бот записал {f(r[6]['closed'])}")
