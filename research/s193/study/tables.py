"""s193 — сбор частей `parts/*.pkl.gz` в таблицы: days (монето-сутки), runs (прогоны D1/D1n), d2 (часы с ритмом),
lev (потолки и полы D3), inj (синтетические вставки). Итог — /home/user/mc_data/s193/tables.pkl.
Доходы и цены после начала эпизода не считаются."""
import glob
import gzip
import pickle

import numpy as np
import pandas as pd

D = "/home/user/mc_data/s193"
BENF = np.log10(1 + 1 / np.arange(1, 10))


def main():
    J = pd.read_pickle(f"{D}/jobs.pkl")
    import os
    for extra in ("jobs_journal.pkl", "jobs_spot.pkl"):
        if os.path.exists(f"{D}/{extra}"):
            J = pd.concat([J, pd.read_pickle(f"{D}/{extra}")], ignore_index=True)
    tag = {(m, s, int(d)): (p, t) for m, s, d, p, t in zip(J.mkt, J.s, J.d, J.per, J.tags)}
    days, runs, d2, lev, inj, bad = [], [], [], [], [], []
    for f in sorted(glob.glob(f"{D}/parts/*.pkl.gz")):
        try:
            with gzip.open(f, "rb") as g:
                R = pickle.load(g)
        except (EOFError, OSError, pickle.UnpicklingError):
            print("часть не прочитана (пишется?):", f)
            continue
        for r in R:
            key = r["key"]
            per, tags = tag.get(key, (None, ""))
            if not r.get("ok"):
                bad.append(dict(mkt=key[0], s=key[1], d=key[2], per=per, tags=tags, code=str(r.get("code"))[:60]))
                continue
            mkt, s, d = key
            bq = r["benf_q"] / max(r["benf_q"].sum(), 1)
            bv = r["benf_v"] / max(r["benf_v"].sum(), 1)
            sh = r["sec_hist"].astype(float)
            sh /= max(sh.sum(), 1)
            mh = r["ms_hist"].astype(float)
            mh /= max(mh.sum(), 1)
            hv, hb = r["h_vol"].astype(float), r["h_volb"].astype(float)
            imb = np.where(hv > 0, (2 * hb - hv) / np.maximum(hv, 1e-9), np.nan)
            row = dict(mkt=mkt, s=s, d=d, per=per, tags=tags, n_agg=r["n_agg"], n_ord=r["n_ord"], vol=r["vol"],
                       volb=r["volb"], gamma=r["gamma"], p_stay=r["p_stay"], rl_max=r["rl_max"],
                       mad_q=float(np.abs(bq - BENF).mean()), mad_v=float(np.abs(bv - BENF).mean()),
                       round_q=r["round_q"], round_v=r["round_v"], pair_n=r["pair_n"], pair_v=r["pair_v"],
                       sec_max=float(sh.max()), sec0=float(sh[0]), sec_kl=float(np.sum(sh[sh > 0] * np.log(sh[sh > 0] * 60))),
                       ms0=float(mh[0]), ms_kl=float(np.sum(mh[mh > 0] * np.log(mh[mh > 0] * 20))),
                       vq50=float(r["vq"][0]), vq90=float(r["vq"][1]), vq99=float(r["vq"][2]), lev_mean=r["lev_mean"],
                       ngroups10=r.get("ngroups10", 0), nspike=r.get("nspike", 0), n_runs=r.get("n_runs", 0),
                       tick=r.get("tick", np.nan), p_open=r["p_open"], t_cpu=r.get("t_cpu", np.nan), mb=r.get("mb", np.nan),
                       imb_absmax=float(np.nanmax(np.abs(imb))) if np.isfinite(imb).any() else np.nan)
            for i, l in enumerate((1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)):
                row[f"acf{l}"] = float(r["acf"][i])
            for i in range(8):
                row[f"rlh{i}"] = int(r["rlh"][i])
            days.append(row)
            for z in r["runs"]:
                runs.append(dict(mkt=mkt, s=s, d=d, per=per, tags=tags, **z))
            x = r["d2"]
            for h in range(24):
                for si in (0, 1):
                    if np.isfinite(x[h, si, 1]) and x[h, si, 1] >= 20:
                        d2.append(dict(mkt=mkt, s=s, d=d, per=per, tags=tags, h=h, side=1 if si == 0 else -1,
                                       period=float(x[h, si, 0]), snr=float(x[h, si, 1]), snr_h2=float(x[h, si, 2]),
                                       snr_oth=float(x[h, si, 3]), nbig=float(x[h, si, 4])))
            for z in r["lev_runs"]:
                lev.append(dict(mkt=mkt, s=s, d=d, per=per, tags=tags, **z))
            for z in r.get("inj", []):
                inj.append(dict(mkt=mkt, s=s, d=d, per=per, **z))
    T = dict(days=pd.DataFrame(days), runs=pd.DataFrame(runs), d2=pd.DataFrame(d2), lev=pd.DataFrame(lev),
             inj=pd.DataFrame(inj), bad=pd.DataFrame(bad))
    pd.to_pickle(T, f"{D}/tables.pkl")
    for k, v in T.items():
        print(k, v.shape)


if __name__ == "__main__":
    main()
