import zipfile, io, datetime
import numpy as np
import bv
def book(sym, day):
    """Снимки стакана: t, {уровень%: notional $}. Уровни: −5..−0,2 — покупки, 0,2..5 — продажи (накопительно от середины)."""
    d = bv.fetch(f"daily/bookDepth/{sym}USDT/{sym}USDT-bookDepth-{day}.zip")
    if not d: return None
    z = zipfile.ZipFile(io.BytesIO(d)); rows = {}
    for ln in z.read(z.namelist()[0]).decode().splitlines()[1:]:
        ts, pc, dep, no = ln.split(",")
        t = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp()
        rows.setdefault(t, {})[float(pc)] = float(no)
    T = np.array(sorted(rows)); L = [-5, -4, -3, -2, -1, -0.2, 0.2, 1, 2, 3, 4, 5]
    M = np.array([[rows[t].get(float(x), np.nan) for x in L] for t in T])
    return T, L, M
