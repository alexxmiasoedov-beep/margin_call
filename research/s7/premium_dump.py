"""Премия фьючерса к индексу вокруг каждого дампа — как s7/premium_ev.py для пампов."""
src = open("s7/premium_ev.py").read()
src = src.replace('D = pd.read_pickle("s6/feat.pkl")[["s", "t", "dur"]]',
                  'EVD = pickle.load(open("s7/dumps.pkl", "rb")); D = pd.DataFrame([(e["s"], e["t_in"], (e["jK"] - e["iK"]) * 15) for e in EVD], columns=["s", "t", "dur"])')
src = src.replace('R.to_pickle("s7/ev_premium.pkl")', 'R.to_pickle("s7/ev_premium_dump.pkl")')
exec(src)
