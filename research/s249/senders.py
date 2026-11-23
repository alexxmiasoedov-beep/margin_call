"""s249 — кто отправители событий ≥ 0,5% обращения на адреса сметания Binance в BNB Chain: адреса пополнения (несколько
переводов) или внутренние кошельки (много крупных переводов, приходы от Binance). Для отчёта, на правило не влияет.
Запуск из /home/user/mc_data: python3 <repo>/research/s249/senders.py"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run  # noqa: E402

R = run.raw()
E = run.events(R)
print("событий:", len(E))
c = E.groupby("frm").agg(n=("perp", "size"), coins=("perp", "nunique"), frac=("frac", "median")).sort_values("n", ascending=False)
print("отправителей:", len(c), "; с одним событием:", int((c.n == 1).sum()), "; с ≥ 5 событиями:", int((c.n >= 5).sum()))
print(c.head(15).to_string())
allr = R.groupby("frm").size()
print("\nвсего переводов у топ-отправителей событий:", {a: int(allr.get(a, 0)) for a in c.head(10).index})
