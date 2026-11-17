"""s95 — каким t может достичь лучший результат чистого шума при N проверках (максимум N независимых нормальных величин).
Запуск: python3 research/s95/noise_max.py"""
import numpy as np

rng = np.random.default_rng(1)
for N in (100, 200, 300, 500, 1000):
    m = rng.standard_normal((20000, N)).max(axis=1)
    print(f"N={N:5d}: медиана {np.median(m):.2f}, 90% {np.quantile(m, .9):.2f}, 99% {np.quantile(m, .99):.2f};"
          f" P(max ≥ 3) = {(m >= 3).mean():.0%}, P(max ≥ 3,5) = {(m >= 3.5).mean():.0%}, P(max ≥ 4) = {(m >= 4).mean():.1%}")
