"""Г1, уточнение: почему у отдачи на ходе цены (💸) сделки +3,4%, а у того же хода без отдачи +1,0%, хотя доход к рынку
различается лишь на ~1 п. п. Сделки 7 суток со стопом 50% раскладываются на цену, фандинг и комиссию; плюс фандинг
монеты за сутки до входа. Нужен s22/h1_panel.pkl (h1_forced.py). Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import ct, fwd, funding, thin
from borrow_trades import sims

if __name__ == "__main__":
    D = pd.read_pickle("s22/h1_panel.pkl")
    acc_b = (D.bor >= 1.5 * D.bor4) & (D.bor >= 50e3); acc_r = (D.rep >= 1.5 * D.rep4) & (D.rep >= 20e3)
    for nm, m in (("отдача на ходе цены ±5% (💸)", acc_r & ~acc_b & D.px), ("тот же ход без отдачи и займа", ~acc_r & ~acc_b & D.px)):
        d = thin(D[m]); R = sims(d, sl=0.5, hold_h=168)
        f_pre = []
        for s, T in zip(R.s, R["T"]):
            fr = funding(s); w = fr[(fr[:, 0] > T - 86400) & (fr[:, 0] <= T)] if len(fr) else fr
            f_pre.append(w[:, 1].sum() if len(w) else np.nan)
        R["f_pre"] = f_pre
        up, dn = R.merge(d[["s", "T", "r4"]], on=["s", "T"]).r4 > 0, None
        print(f"{nm}: n={len(R)}, сделка {R.net.mean() * 100:+.2f}% = цена {R.price.mean() * 100:+.2f}% + фандинг шорту "
              f"{R.fund.mean() * 100:+.2f}% − комиссия; стопов {(R.why == 'стоп').mean():.0%}; фандинг за сутки до входа "
              f"{np.nanmean(R.f_pre) * 100:+.3f}% (медиана {np.nanmedian(R.f_pre) * 100:+.3f}%)")
        print(f"   после роста: сделка {R.net[up.values].mean() * 100:+.2f}% (n={up.sum()}), после падения "
              f"{R.net[~up.values].mean() * 100:+.2f}% (n={(~up).sum()})")
