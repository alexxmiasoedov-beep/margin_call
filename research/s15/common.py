"""Общее для s15: 15-мин свечи и фандинг фьючерсов Binance, сделка с тейком, стопом и сроком.
Запуск скриптов — из папки с данными (s2/k2y.pkl, s2/fund2y.pkl)."""
import io
import os
import pickle
import urllib.request
import zipfile
import numpy as np

BAR, FEE = 900, 0.001
K = pickle.load(open("s2/k2y.pkl", "rb"))
FU = pickle.load(open("s2/fund2y.pkl", "rb"))


_live = {}


def live(s):
    """Время первой и последней 15-мин свечи фьючерса с объёмом. В архиве (s2/k2y.pkl) у всех символов полная сетка
    01.10.2024–18.10.2026: свечи до начала торгов и после делистинга — заглушки без объёма с неизменной ценой."""
    if s not in _live:
        nz = np.flatnonzero(K[s]["qv"] > 0)
        _live[s] = (float(K[s]["t"][nz[0]]), float(K[s]["t"][nz[-1]])) if len(nz) else (np.inf, -np.inf)
    return _live[s]


def fut_of(base):
    """Фьючерс Binance для монеты и множитель цены (1000PEPE = 1000 PEPE); (None, 1) — фьючерса нет."""
    for p in ("", "1000", "1000000"):
        if p + base in K:
            return p + base, float(p or 1)
    return None, 1.0


_fund = {}


def funding(sym):
    """Фандинг [время, ставка]: из ветки data (по 30.09.2026), дальше — месяцы из архива Binance (кэш в s15/fund/)."""
    if sym in _fund:
        return _fund[sym]
    f = FU.get(sym)
    rows = [(int(r[0]), float(r[2])) for r in f] if f is not None else []
    last = max((r[0] for r in rows), default=0)
    os.makedirs("s15/fund", exist_ok=True)
    for m in ("2026-09", "2026-10"):
        path = f"s15/fund/{sym}-{m}.csv"
        if not os.path.exists(path):
            url = f"https://data.binance.vision/data/futures/um/monthly/fundingRate/{sym}USDT/{sym}USDT-fundingRate-{m}.zip"
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    z = zipfile.ZipFile(io.BytesIO(r.read()))
                open(path, "w").write(z.read(z.namelist()[0]).decode())
            except Exception:
                open(path, "w").write("")
        for ln in open(path).read().splitlines():
            p = ln.split(",")
            if p and p[0].isdigit() and int(p[0]) // 1000 > last:
                rows.append((int(p[0]) // 1000, float(p[2])))
    _fund[sym] = np.array(sorted(rows)) if rows else np.zeros((0, 2))
    return _fund[sym]


def trade(s, i, tp=None, sl=0.25, hold_h=48, side=-1):
    """Сделка на фьючерсе s: вход в закрытии 15-мин свечи i; side −1 — шорт, +1 — лонг. Тейк tp и стоп sl — доли цены входа
    (None — нет); если оба в одной свече — считается стоп; стоп исполняется по худшей из цены стопа и открытия свечи, плюс
    проскальзывание 0,2%. Иначе выход в закрытии свечи i + 4·hold_h. Комиссия 0,1% за круг, фактический фандинг.
    Возвращает dict(net, price, fund, why, bars) или None, если свечей на весь срок нет или окно выходит за время торгов
    фьючерсом (свечи-заглушки до начала торгов и после делистинга)."""
    a = K[s]; t = a["t"]; n = int(hold_h * 4)
    if i < 0 or i + n >= len(t) or t[i + n] != t[i] + n * BAR:
        return None
    lo_t, hi_t = live(s)
    if not lo_t <= t[i] or t[i + n] > hi_t:                  # вход до начала торгов или выход после делистинга — заглушки
        return None
    p0 = float(a["c"][i])
    hi, lo, op = (a[x][i + 1:i + n + 1].astype(float) for x in ("h", "l", "o"))
    adv, fav = (hi, lo) if side < 0 else (lo, hi)
    ks = np.flatnonzero(side * (adv - p0 * (1 - side * sl)) <= 0) if sl else np.array([], int)
    kt = np.flatnonzero(side * (fav - p0 * (1 + side * tp)) >= 0) if tp else np.array([], int)
    k_s = int(ks[0]) if len(ks) else n
    k_t = int(kt[0]) if len(kt) else n
    if k_s < n and k_s <= k_t:
        stop = p0 * (1 - side * sl)
        px = (max(stop, op[k_s]) * 1.002) if side < 0 else (min(stop, op[k_s]) * 0.998)
        xi, why = i + 1 + k_s, "стоп"
    elif k_t < n:
        px, xi, why = p0 * (1 + side * tp), i + 1 + k_t, "тейк"
    else:
        px, xi, why = float(a["c"][i + n]), i + n, "время"
    t0, t1 = float(t[i]) + BAR, float(t[xi]) + BAR
    fr = funding(s)
    f = float(fr[(fr[:, 0] > t0) & (fr[:, 0] <= t1), 1].sum()) if len(fr) else 0.0
    price = side * (px / p0 - 1)
    return dict(net=price - side * f - FEE, price=price, fund=-side * f, why=why, bars=xi - i)
