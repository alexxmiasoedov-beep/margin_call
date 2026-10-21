"""Маржинальный канал на момент каждого дампа — как s7/margin_ev.py (разбор постов берём готовый из s7/margin.pkl)."""
import pickle, re
import numpy as np, pandas as pd
src = open("s7/margin_ev.py").read()
body = src.split('D = pd.read_pickle("s6/feat.pkl")[["s", "t"]]; GAP = 30 * 60')[1]
X = pickle.load(open("s7/margin.pkl", "rb")); G, PT = X["G"], X["PT"]
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
D = pd.DataFrame([(e["s"], e["t_in"]) for e in pickle.load(open("s7/dumps.pkl", "rb"))], columns=["s", "t"]); GAP = 30 * 60
exec(body.replace('R.to_pickle("s7/ev_margin.pkl")', 'R.to_pickle("s7/ev_margin_dump.pkl")'))
