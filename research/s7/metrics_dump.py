"""Метрики фьючерса (OI, LSR, тейкеры) вокруг каждого дампа — как s6/metrics_ev.py для пампов."""
import sys
src = open("s6/metrics_ev.py").read()
src = src.replace('P = pd.read_pickle("s2/pump_TRY.pkl")', 'P = pd.DataFrame([(e["s"], e["t_in"]) for e in pickle.load(open("s7/dumps.pkl", "rb"))], columns=["s", "t"])')
src = src.replace('D.to_pickle("s6/ev_metrics.pkl")', 'D.to_pickle("s7/ev_metrics_dump.pkl")')
exec(src)
