"""Г1. Вынужденная отдача против добровольной (Blocher, Dong, Ringgenberg & Savor «Short Covering»).
Событие отдачи — как у 💸 без условия на цену: монета в канале сейчас и 4 ч назад, REP за 24 ч вырос к значению 4 ч назад
в 1,5+ раза и не меньше 20 тыс. $, BOR при этом не вырос в 1,5 раза до 50+ тыс. $ (таблица монето-часов s21/panel.pkl).
Триггер в тот же час (заданы заранее по отчёту s22):
  а) цена фьючерса за 4 ч ±5% и больше (нынешний 💸);
  б) дневная ставка займа монеты ≥ ×1,5 к медиане почасовых значений за 7 суток (s11/rates);
  в) реализованная волатильность за 4 ч (СКО 16 15-мин доходностей) в верхнем дециле значений монеты за 30 суток;
  г) без триггера.
Контроль — тот же триггер без ускорения отдачи (и без ускорения займа). Исход — шорт к рынку на 1/3/7/14/30 суток,
вход с задержкой 0/24/48 ч, сделки 7 суток со стопом 50% (с фандингом и комиссией) и с хеджем BTC. Одно наблюдение на
монету за сутки в каждой ячейке; t — с кластеризацией по дню входа. Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import BAR, COIN_OF, DAY, GR, H, HSET, K, ct, fwd, rate_jump, summ, thin
from borrow_trades import sims


def vol_flag(D):
    """Флаг (в): СКО 15-мин лог-доходностей за 4 ч в верхнем дециле значений монеты за прошлые 30 суток (по часам)."""
    out = np.zeros(len(D), bool)
    for s, idx in D.groupby("s").groups.items():
        a = K[s]; t = a["t"].astype(np.int64) + BAR
        lr = pd.Series(np.log(a["c"].astype(float)), index=t).diff()
        rv = lr.rolling(16, min_periods=16).std()
        rvh = rv[rv.index % H == 0]
        p90 = rvh.shift(1).rolling(720, min_periods=360).quantile(0.9)
        Ts = D.loc[idx, "T"].values
        cur, thr = rvh.reindex(Ts).values, p90.reindex(Ts).values
        out[D.index.get_indexer(idx)] = np.isfinite(cur) & np.isfinite(thr) & (cur >= thr)
    return out


def report(name, d, base=None):
    d = thin(d)
    print(f"\n  {name}: {len(d)} событий")
    xs = {h: np.array([fwd(s, T, h) for s, T in zip(d.s, d["T"])]) for h in HSET}
    print("    к рынку: " + " | ".join(f"{h // 24} сут {np.nanmean(xs[h]) * 100:+.2f}% (t {ct(xs[h], d['T'])[1]:+.1f})"
                                    for h in HSET))
    if base is not None:
        print("    к рынку минус база: " + " | ".join(f"{h // 24} сут {(np.nanmean(xs[h]) - base[h]) * 100:+.2f}" for h in HSET))
    for dl in (24, 48):
        x = np.array([fwd(s, T, 168, delay=dl) for s, T in zip(d.s, d["T"])])
        print(f"    вход через {dl} ч, 7 сут к рынку: {summ(x, d['T'].values)}")
    R = sims(d.rename(columns={}), sl=0.5, hold_h=168)
    if len(R):
        print(f"    сделки 7 сут, стоп 50% (цена+фандинг): {summ(R.net.values, R['T'].values)}; с хеджем BTC "
              f"{np.nanmean(R.hedged) * 100:+.2f}% (t {ct(R.hedged.values, R['T'].values)[1]:+.1f})")
    return xs


if __name__ == "__main__":
    D = pd.read_pickle("s21/panel.pkl").reset_index(drop=True)
    D = D[D.in4].reset_index(drop=True)
    acc_b = (D.bor >= 1.5 * D.bor4) & (D.bor >= 50e3)
    acc_r = (D.rep >= 1.5 * D.rep4) & (D.rep >= 20e3)
    E = acc_r & ~acc_b
    print(f"монето-часов (в канале сейчас и 4 ч назад): {len(D):,}; событий отдачи (до прореживания): {E.sum():,}")
    D["px"] = D.r4.abs() >= 0.05
    D["rj"] = [rate_jump(COIN_OF.get(s, s), T) for s, T in zip(D.s, D["T"])]
    D["rate"] = D.rj >= 1.5
    D["vol"] = vol_flag(D)
    print(f"есть ставка займа у {np.isfinite(D.rj).mean():.0%} монето-часов; доля триггеров среди всех: цена "
          f"{D.px.mean():.1%}, ставка {D.rate.mean():.1%}, волатильность {D.vol.mean():.1%}")
    D.to_pickle("s22/h1_panel.pkl")

    B = thin(D)
    base = {h: np.nanmean([fwd(s, T, h) for s, T in zip(B.s, B["T"])]) for h in HSET}
    print("\nБаза (все монето-часы канала, одно на монету за сутки): " + " | ".join(f"{h // 24} сут {base[h] * 100:+.2f}%"
                                                                                   for h in HSET))
    print("\nСобытия отдачи по триггеру:")
    cells = (("а) цена ±5% (💸)", E & D.px), ("б) ставка ×1,5, без хода цены", E & D.rate & ~D.px),
             ("в) волатильность, без хода цены", E & D.vol & ~D.px),
             ("б или в, без хода цены", E & (D.rate | D.vol) & ~D.px),
             ("г) без триггера", E & ~D.px & ~D.rate & ~D.vol))
    for nm, m in cells:
        report(nm, D[m], base)
    print("\nКонтроль: тот же триггер без ускорения отдачи и займа:")
    no = ~acc_r & ~acc_b
    for nm, m in (("а) цена ±5%", no & D.px), ("б) ставка ×1,5, без хода цены", no & D.rate & ~D.px),
                  ("в) волатильность, без хода цены", no & D.vol & ~D.px)):
        report(nm, D[m], base)
