"""Поиск рисунка KAIA 09.10 на 15-мин свечах всех фьючерсов Binance (USDT) за месяц."""
import pickle, datetime, numpy as np
UTC = datetime.timezone.utc; MSK = datetime.timezone(datetime.timedelta(hours=3))
K = pickle.load(open("kaia/k15_all.pkl", "rb"))
T0 = datetime.datetime(2026, 9, 19, tzinfo=MSK).timestamp(); TEND = datetime.datetime(2026, 10, 19, tzinfo=UTC).timestamp()
REV = 0.12                                        # разворот зигзага: откат/отскок от 12%
def find(sym, k, imp_min=0.12):
    t, o, h, l, c, qv = k[:, 0], k[:, 1], k[:, 2], k[:, 3], k[:, 4], k[:, 6]
    out = []; skip_until = 0
    for i in range(288, len(k) - 4):
        if t[i] < T0 or t[i] < skip_until: continue
        body = c[i] / o[i] - 1
        if body < imp_min or (h[i] - c[i]) > 0.25 * (h[i] - l[i]): continue
        base = slice(i - 32, i)
        if h[base].max() / l[base].min() > BASE: continue                         # 8 ч до импульса — спокойная база
        med = np.median(qv[i - 96:i])
        if med <= 0 or qv[i] < 10 * med: continue                               # объём импульса ≥ 10× обычного
        if l[i + 1:i + 1 + PAUSE].min() < c[i] - 0.35 * (c[i] - o[i]): continue           # пауза держит ≥ 65% импульса
        if h[i + 1:i + 1 + PAUSE].max() > c[i] * 1.08: continue                           # и не продолжает рост сразу (флаг)
        # первая вершина: максимум до первого отката на 12% (откат считаем со свечи после максимума), не позже 12 ч
        run, j1, j = h[i], i, i + 1
        while j < len(k) and t[j] <= t[i] + 12 * 3600:
            if h[j] > run: run, j1 = h[j], j
            elif l[j] <= run * (1 - REV): break
            j += 1
        else:
            continue
        H1, t1 = run, t[j1]
        if H1 < c[i] * 1.10 or t1 - t[i] < 3600: continue                         # рост после паузы ещё ≥ 10%, вершина не раньше 1 ч
        # дно отката: минимум до отскока на 12% (зигзаг) — не дольше 24 ч от вершины
        mn, jl = l[j], j
        while j < len(k) and t[j] <= t1 + 24 * 3600:
            if l[j] < mn: mn, jl = l[j], j
            elif h[j] >= mn * (1 + REV): break
            j += 1
        L, tl = mn, t[jl]
        R = (H1 - L) / (H1 - o[i])                                                 # глубина отката от всего роста
        # вторая волна: максимум за 24 ч после дна
        w = (t > tl) & (t <= tl + 24 * 3600)
        if not w.any(): continue
        j2 = np.flatnonzero(w)[np.argmax(h[w])]; H2, t2 = h[j2], t[j2]
        complete = tl + 24 * 3600 <= TEND
        out.append(dict(sym=sym, ti=t[i], o=o[i], c=c[i], imp=body * 100, volx=qv[i] / med, H1=H1, t1=t1, up1=(H1 / o[i] - 1) * 100,
                        L=L, tl=tl, drop=(1 - L / H1) * 100, R=R * 100, H2=H2, t2=t2, h2vs1=(H2 / H1 - 1) * 100, h2fromL=(H2 / L - 1) * 100,
                        climax=qv[j1] >= qv[i:jl + 1].max() * 0.999, complete=complete, i=i))
        skip_until = tl
    return out
import sys
IMP = float(sys.argv[1]) if len(sys.argv) > 1 else 0.12
BASE = float(sys.argv[2]) if len(sys.argv) > 2 else 1.10
PAUSE = int(sys.argv[3]) if len(sys.argv) > 3 else 2
OUT = sys.argv[4] if len(sys.argv) > 4 else 'kaia/patterns.pkl'
res = [r for s, k in K.items() for r in find(s, k, IMP)]
pickle.dump(res, open(OUT, "wb"))
f = lambda x: datetime.datetime.fromtimestamp(x, MSK).strftime("%d.%m %H:%M")
print(f"найдено {len(res)} рисунков (импульс ≥ +{IMP*100:.0f}% от спокойной базы, пауза, рост ещё ≥ 10%, откат ≥ 12%)")
for r in sorted(res, key=lambda r: r["ti"]):
    print(f"{r['sym']:10s} импульс {f(r['ti'])} {r['imp']:+5.1f}% (объём ×{r['volx']:4.0f}) | вершина 1 {f(r['t1'])} +{r['up1']:4.0f}% | "
          f"откат {f(r['tl'])} −{r['drop']:4.1f}% (глубина {r['R']:3.0f}% роста) | волна 2 {f(r['t2'])} {r['h2vs1']:+6.1f}% к вершине 1"
          + ("" if r["complete"] else " (не досмотрено)"))
