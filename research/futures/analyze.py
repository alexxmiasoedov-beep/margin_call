from sim import *
print(f"сигналов {len(SIG)} (правило 1 {sum(s['rule']=='1' for s in SIG)}, правило 2 {sum(s['rule']=='2' for s in SIG)}), "
      f"период {datetime.datetime.utcfromtimestamp(SIG[0]['ep']):%d.%m}–{datetime.datetime.utcfromtimestamp(SIG[-1]['ep']):%d.%m.%Y}; "
      f"монет без фьючерса Binance: {len(D['nof'])}")
print("\n== 1. ТЕКУЩАЯ СТРАТЕГИЯ: тейк 6 / стоп 20, 48 ч, пауза 48 ч ==")
x = run(6, 20); print(summ(x, "оба правила"))
for r in "12": print(summ(x[x.rule == r], f"правило {r}"))
print(summ(run(6, 20, with_fund=False), "без фандинга"))
print(summ(run(6, 20, mark=False), "стоп по цене, не марк"))
print(summ(run(6, 20, strict=False), "тейк по касанию"))
print(summ(run(6, 20, slip=False), "стоп без проскальз."))
x["m"] = pd.to_datetime(x.ep, unit="s").dt.strftime("%Y-%m")
print(x.groupby("m").agg(n=("pnl", "size"), итого=("pnl", "sum"), тейк=("kind", lambda k: (k == "тейк").mean() * 100),
                         стоп=("kind", lambda k: (k == "стоп").mean() * 100), фандинг=("fund", "sum")).round(1).to_string())
print("ход против шорта до выхода (стопы не в счёт): медиана {:.1f}%, 90-й перцентиль {:.1f}%".format(
      x[x.kind != "стоп"].maxup.median(), x[x.kind != "стоп"].maxup.quantile(0.9)))

print("\n== 2. СЕТКА ТЕЙК × СТОП (48 ч, пауза 48) — итого USDT / стопов % ==")
tab = {}; stp = {}
for tp in (4, 6, 8, 10, 15, None):
    for sl in (10, 15, 20, 25, 30, 40):
        y = run(tp, sl); tab[(tp or "нет", sl)] = round(y.pnl.sum(), 1); stp[(tp or "нет", sl)] = round((y.kind == "стоп").mean() * 100)
t = pd.Series(tab).unstack(); s_ = pd.Series(stp).unstack()
print(t.to_string()); print("стопов, %:"); print(s_.to_string())

print("\n== 3. ВРЕМЯ УДЕРЖАНИЯ и ПАУЗА (6/20) ==")
for h in (12, 24, 36, 48, 72): print(summ(run(6, 20, hold_h=h), f"выход {h} ч"))
for p in (0, 24, 48, 96): print(summ(run(6, 20, pause_h=p), f"пауза {p} ч"))

print("\n== 4. ЖУРНАЛЫ И ФАНДИНГ ==")
print(summ(run(None, 25), "📓 без тейка / 25"))
G = lambda fh: (15, 25) if fh is not None and fh * 100 < -0.03 else (6, 20)
print(summ(run(params=G), "📗 по фандингу"))
for fx in (0.1, 0.2, 0.4, 0.8): print(summ(run(6, 20, fexit=fx), f"6/20 + fexit {fx}"))
print(summ(run(None, 25, fexit=0.4), "📓 + fexit 0.4"))
x = run(6, 20); x["fh"] = [fh_entry(s) for s in SIG if (s["ep"], s["sym"]) in set(zip(x.ep, x.sym))][:len(x)] if False else None
fhm = {(s["ep"], s["sym"]): fh_entry(s) for s in SIG}; x["fh"] = [fhm[(a, b)] for a, b in zip(x.ep, x.sym)]
x["fb"] = pd.cut(x.fh * 100, [-9, -0.1, -0.03, -0.01, 0.0, 9], labels=["<−0,1", "−0,1..−0,03", "−0,03..−0,01", "−0,01..0", "≥0"])
print(x.groupby("fb", observed=True).agg(n=("pnl", "size"), на_сделку=("pnl", "mean"), тейк=("kind", lambda k: (k == "тейк").mean() * 100),
      стоп=("kind", lambda k: (k == "стоп").mean() * 100), фандинг=("fund", "sum")).round(2).to_string())

print("\n== 5. ПАТТЕРНЫ (6/20) ==")
pm = {(s["ep"], s["sym"]): s for s in SIG}
def s_of(r): return pm[(r.ep, r.sym)]
x["ok"] = None
p1 = x[x.rule == "1"].copy()
def struct_ok(s):
    st = s["s_pump"]; return None if not st else bool(st["move_prior"] >= 3 and -15 <= st["pull"] <= -4 and st["vs_prior"] >= -3)
p1["ok"] = [struct_ok(s_of(r)) for r in p1.itertuples()]
for v, lab in ((True, "структура ✅"), (False, "структура ⚠️")): print(summ(p1[p1.ok == v], "пр.1 " + lab))
p1["fp"] = [s_of(r)["from_peak"] for r in p1.itertuples()]
print(summ(p1[(p1.fp <= -0.5) & (p1.fp >= -3)], "пр.1 от пика −0,5..−3%")); print(summ(p1[~((p1.fp <= -0.5) & (p1.fp >= -3))], "пр.1 прочие"))
p2 = x[x.rule == "2"].copy(); p2["rb"] = [s_of(r)["rise_before"] for r in p2.itertuples()]
for lo, hi, lab in ((30, 1e9, ">30%"), (15, 30, "15–30%"), (5, 15, "5–15%"), (-1e9, 5, "<5%")):
    print(summ(p2[(p2.rb >= lo) & (p2.rb < hi)], f"пр.2 рост до {lab}"))
