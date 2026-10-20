"""Листинги Upbit (начало торгов новой монеты) и фьючерсы Binance: лонг от реакции на объявление до открытия торгов, шорт после открытия."""
import pickle, datetime
import numpy as np
UTC = datetime.timezone.utc; MSK = datetime.timezone(datetime.timedelta(hours=3))
f = lambda t: datetime.datetime.fromtimestamp(t, MSK).strftime("%d.%m %H:%M")
L = pickle.load(open("mm/upbit_listings.pkl", "rb")); K = pickle.load(open("kaia/k15_6m.pkl", "rb"))
ev = {}
for x in sorted(L, key=lambda x: x["t"]):
    b = x["base"]
    if b in ev and abs(x["t"] - ev[b][-1]["t"]) < 6 * 3600: ev[b][-1]["markets"].append(x["quote"]); continue
    ev.setdefault(b, []).append(dict(base=b, t=x["t"], markets=[x["quote"]]))
E = [e for v in ev.values() for e in v if e["base"] in K]
rows = []
for e in E:
    k = K[e["base"]]; t, o, h, l, c, qv = k[:, 0], k[:, 1], k[:, 2], k[:, 3], k[:, 4], k[:, 6]
    it = int(np.searchsorted(t, e["t"], side="right")) - 1                      # свеча, в которой открылись торги
    if it < 200 or it + 200 >= len(k): continue
    win = range(it - 16, it + 1)                                                # 4 ч до открытия
    ia = max(win, key=lambda j: c[j] / o[j] - 1); imp = c[ia] / o[ia] - 1
    base_p = c[it - 24] if it >= 24 else c[0]
    pre = c[it] / o[it - 16] - 1
    long_ret = c[it] / (c[ia] * 1.003) - 1 - 0.001 if ia < it else np.nan      # лонг: закрытие свечи-реакции → открытие торгов Upbit
    def short(d0, hold=None, tp=None, sl=None):
        i0 = it + d0; p = c[i0] * 0.999
        n = hold or 96
        for d in range(1, n + 1):
            if sl and h[i0 + d] >= p * (1 + sl): return -sl - 0.001
            if tp and l[i0 + d] <= p * (1 - tp): return tp - 0.001
        return 1 - c[i0 + n] / p - 0.001
    top_after = h[it:it + 97].max() / c[it] - 1; low_after = l[it:it + 97].min() / c[it] - 1
    j_top = it - 16 + int(np.argmax(h[it - 16:it + 97]))
    rows.append(dict(base=e["base"], t=e["t"], markets="/".join(e["markets"]), imp=imp, imp_t=t[ia], pre=pre, long=long_ret,
                     s0_24=short(0, 96), s1_24=short(2, 96), s0_48=short(0, 192), s_tp=short(0, 96, 0.15, 0.10), s_bot=short(0, 192, 0.15, 0.25),
                     top_after=top_after, low_after=low_after, top_vs_open=(t[j_top] - e["t"]) / 3600))
pickle.dump(rows, open("mm/upbit_rows.pkl", "wb"))
print(f"листингов Upbit с фьючерсом Binance в периоде данных: {len(rows)}")
print("монета  открытие торгов Upbit (МСК)  рынки        реакция до открытия  лонг до открытия  шорт 24 ч  вершина относительно открытия")
for r in sorted(rows, key=lambda r: r["t"]):
    print(f"{r['base']:7s} {f(r['t'])}   {r['markets']:12s} свеча {r['imp']*100:+5.1f}% ({f(r['imp_t'])})  {r['long']*100 if np.isfinite(r['long']) else float('nan'):+6.1f}%   "
          f"{r['s0_24']*100:+6.1f}%   {r['top_vs_open']:+5.1f} ч")
A = lambda key, sel=None: np.array([r[key] for r in rows if (sel is None or sel(r)) and np.isfinite(r[key])])
for lab, sel in (("все", None), ("реакция до открытия ≥ +5%", lambda r: r["imp"] >= 0.05)):
    print(f"\n{lab}: событий {len(A('s0_24', sel))}")
    for key, name in (("long", "лонг: от свечи-реакции до открытия торгов"), ("s0_24", "шорт с открытия, 24 ч"), ("s1_24", "шорт через 30 мин после открытия, 24 ч"),
                      ("s0_48", "шорт с открытия, 48 ч"), ("s_tp", "шорт с открытия, −15% / +10% / 24 ч"), ("s_bot", "шорт с открытия, 15/25 / 48 ч")):
        x = A(key, sel)
        if len(x): print(f"  {name:45s} {x.mean()*100:+6.2f}% на сделку (медиана {np.median(x)*100:+5.1f}%), в плюсе {np.mean(x > 0)*100:.0f}%, n={len(x)}")
