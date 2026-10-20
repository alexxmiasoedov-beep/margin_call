import numpy as np
N = 96                                           # окно 24 ч из 15-мин свечей
def zrow(x):
    x = x - x.mean(); s = np.sqrt((x * x).sum())
    return x / s if s > 0 else None
def windows(k, step=4, min_range=0.25, t_from=None, t_to=None):
    """Все окна 24 ч с шагом step свечей: форма цены (лог close от начала, z-норм.), форма объёма, размах, конец окна."""
    t, h, l, c, qv = k[:, 0], k[:, 2], k[:, 3], k[:, 4], k[:, 6]
    out = []
    for e in range(N, len(k) + 1, step):
        te = t[e - 1] + 900
        if (t_from and te < t_from) or (t_to and te > t_to): continue
        hh, ll = h[e - N:e].max(), l[e - N:e].min()
        rng = hh / ll - 1
        if rng < min_range: continue
        if np.any(np.diff(t[e - N:e]) != 900): continue              # без дыр в данных
        p = zrow(np.log(c[e - N:e])); v = zrow(np.log1p(qv[e - N:e]))
        if p is None or v is None: continue
        out.append((te, e, rng, np.log(hh / ll), p, v))
    return out
