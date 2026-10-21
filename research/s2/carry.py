"""Лонг «на перенос»: после выплаты фандинга, если сумма ставок за 72 ч ≤ порога (шорты переплачивают), — лонг в закрытии
15-мин свечи после выплаты; держим H ч (или до стопа/тейка), получаем отрицательный фандинг. Одна позиция на монету.
Комиссия 0,1%; фандинг — фактические выплаты из архива за время удержания."""
import pickle, datetime, sys
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
UTC = datetime.timezone.utc
T0 = datetime.datetime(2024, 10, 19, tzinfo=UTC).timestamp(); T1 = datetime.datetime(2026, 10, 15, tzinfo=UTC).timestamp()
def run(thr, H, sl, tp=None, vmin=2e6):
    out = []
    for s, fr in F.items():
        a = K.get(s)
        if a is None or len(fr) < 10: continue
        t = a["t"]; c = a["c"].astype(np.float64); l = a["l"].astype(np.float64); h = a["h"].astype(np.float64); qv = a["qv"]
        n = len(t); cs = np.concatenate([[0.0], np.cumsum(fr[:, 2])]); busy = 0
        for k in range(len(fr)):
            tk = fr[k, 0]
            if not (T0 <= tk <= T1) or tk < busy: continue
            k0 = np.searchsorted(fr[:, 0], tk - 72 * 3600, "right"); cum = cs[k + 1] - cs[k0]
            if cum > thr: continue
            j = np.searchsorted(t, (int(tk) // 900) * 900)               # свеча, начавшаяся в момент выплаты: вход в её закрытие (+15 мин)
            if j <= 96 or j + 4 >= n or t[j] != (int(tk) // 900) * 900: continue
            if qv[j - 95:j + 1].sum() < vmin: continue
            e = c[j]; end = min(j + H * 4, n - 1)
            lo, hi = l[j + 1:end + 1], h[j + 1:end + 1]
            ks = np.flatnonzero(lo <= e * (1 - sl)); kt = np.flatnonzero(hi >= e * (1 + tp)) if tp else np.array([], int)
            q1 = ks[0] if len(ks) else 10**9; q2 = kt[0] if len(kt) else 10**9
            if q1 <= q2 and q1 < 10**9: q = j + 1 + q1; px = -sl; how = "стоп"
            elif q2 < 10**9: q = j + 1 + q2; px = tp; how = "тейк"
            else: q = end; px = c[end] / e - 1; how = "время"
            t_in, t_out = t[j] + 900, t[q] + 900
            m = (fr[:, 0] > t_in) & (fr[:, 0] <= t_out); fund = -fr[m, 2].sum()     # лонг получает −ставку
            out.append((s, t_in, cum, px, fund, px + fund - 0.001, how, (t_out - t_in) / 3600)); busy = t_out
    D = pd.DataFrame(out, columns=["s", "t", "cum72", "price", "fund", "pnl", "how", "hours"])
    D["q"] = pd.to_datetime(D.t, unit="s").dt.to_period("Q").astype(str); return D
if __name__ == "__main__":
    res = []
    for thr in (-0.03, -0.05, -0.1):
        for H, sl in ((24, 0.15), (48, 0.2), (72, 0.25), (72, 0.99)):
            D = run(thr, H, sl); qm = D.groupby("q").pnl.mean()
            res.append((f"≤ {thr:.0%}", f"{H} ч, стоп {sl:.0%}" if sl < 0.9 else f"{H} ч, без стопа", len(D), D.s.nunique(), round(D.price.mean() * 100, 2),
                        round(D.fund.mean() * 100, 2), round(D.pnl.mean() * 100, 2), round((D.pnl > 0).mean() * 100), f"{(qm > 0).sum()}/{len(qm)}",
                        " ".join(f"{k[2:]}:{v * 100:+.1f}" for k, v in qm.items())))
            if thr == -0.05 and H == 48: D.to_pickle("s2/carry_05_48.pkl")
    pd.set_option("display.width", 300)
    print(pd.DataFrame(res, columns=["фандинг 72 ч", "удержание", "сделок", "монет", "цена %", "фандинг %", "итог %", "в плюсе %", "кварт. в плюсе", "по кварталам"]).to_string(index=False))
