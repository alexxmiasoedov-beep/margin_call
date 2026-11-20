"""s238 — ядро 🗳 в момент корейского внимания (метод — ВЫВОДЫ.md, записан до расчёта).
Отметки 4 ч вне канала из s228/feat.pkl; момент M — всплеск доли Кореи в часе до T (s15/kr_panel.pkl); ядро — строгое
ядро 🗳; исход — шорт 4 ч с хеджем альтов (y). Запуск из /home/user/mc_data: python3 <repo>/research/s238/run.py"""
import numpy as np
import pandas as pd

WEEK = 7 * 86400
HALF = pd.Timestamp("2025-10-01", tz="UTC").timestamp()
END = pd.Timestamp("2026-10-19", tz="UTC").timestamp()
MONTHS = (END - pd.Timestamp("2024-10-02", tz="UTC").timestamp()) / (30.44 * 86400)


def ct(x, t):
    x = np.asarray(x, float); w = (np.asarray(t, float) // WEEK).astype(np.int64); ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return (x.mean() if len(x) else np.nan), np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def honest(D, sel):
    idx = np.flatnonzero(sel & np.isfinite(D.y.to_numpy()) & np.isfinite(D.u_e.to_numpy()))
    busy, take = {}, []
    for i in idx:
        s = D.s.iat[i]; T = D["T"].iat[i]
        if T >= busy.get(s, -1):
            take.append(i); busy[s] = D.u_e.iat[i]
    return np.array(take, int)


def main():
    F = pd.read_pickle("s228/feat.pkl")
    F = F[(~F.inch.astype(bool)) & (F["T"] < END)].sort_values(["T", "s"]).reset_index(drop=True)
    P = pd.read_pickle("s15/kr_panel.pkl")
    rows = []
    for s, d in P.items():
        d = d[["T", "kr", "share", "norm"]].copy()
        d["T"] = d["T"].astype(np.int64) + 3600                 # строка часа [T0, T0 + 1 ч) — известна в T0 + 1 ч
        d["s"] = s
        rows.append(d)
    K = pd.concat(rows, ignore_index=True)
    F = F.merge(K, on=["s", "T"], how="left")
    kor = F.share.notna()
    M = kor & (F.share >= np.maximum(2 * F.norm, 0.10)) & (F.kr >= 3e5)
    core = (F.dlsr24 >= 0.130122) & (F.zoi4 >= 0.630958)
    print(f"отметок вне канала у монет с рынком к воне: {int(kor.sum())}; моментов M: {int(M.sum())}; ядро: {int((kor & core).sum())}; "
          f"M и ядро: {int((M & core).sum())}")
    rng = np.random.default_rng(7)
    F["mon"] = pd.to_datetime(F["T"], unit="s").dt.to_period("M").astype(str)
    pools = {k: g.y.to_numpy() for k, g in F[kor & F.y.notna()].groupby(["s", "mon"])}
    for lab, sel in (("M и ядро (основная)", M & core), ("M без ядра", M & ~core), ("ядро без M", kor & core & ~M),
                     ("все отметки корейских монет", kor)):
        tk = honest(F, sel.to_numpy())
        y = F.y.to_numpy()[tk]; T = F["T"].to_numpy()[tk]
        m, t, n = ct(y, T)
        h1, h2 = y[T < HALF].mean() if (T < HALF).any() else np.nan, y[T >= HALF].mean() if (T >= HALF).any() else np.nan
        pl = np.array([np.mean(rng.choice(pools[(F.s.iat[i], F.mon.iat[i])], 20)) if (F.s.iat[i], F.mon.iat[i]) in pools
                       else np.nan for i in tk])
        mp, tp, _ = ct(y - pl, T)
        print(f"{lab}: {n} сделок ({n / MONTHS:.1f} в мес.), {m:+.2%} (t {t:+.1f}); половины {h1:+.2%} / {h2:+.2%}; "
              f"сверх плацебо {mp:+.2%} (t {tp:+.1f})")
        if lab.startswith("M и ядро"):
            ok = m > 0 and t >= 3 and h1 > 0 and h2 > 0 and mp > 0 and n / MONTHS >= 20
            print("  порог: " + ("ПРОЙДЕН" if ok else "не пройден"))


if __name__ == "__main__":
    main()
