"""s192 — четвёртый период «2019–2020» (01.10.2019–01.10.2020, середина 01.04.2020) для общего кода без правки
чужих файлов.

Данные периода (/home/user/mc_data/s192): k_2019.pkl, fund_2019.pkl (как s117/k_2020.pkl, fund_2020.pkl), spotcache/ и
spot1h_2019.pkl (спот Binance 1h), kc/<биржа>/KRW-*.pkl и map.pkl (как s88/oos2020). Запись периода строится из записи
«2020–2022» заменой дат и путей (SUBST); модули с собственным PER (s180, s185, s187/bars, s135 PERIODS …) и общие
(common182, common183) получают «2019–2020» первой строкой — их файлы не меняются.

Запуск:
  python3 -I period.py s183
      дневная панель и недельные признаки s183 → /home/user/mc_data/s183/daily_2019–2020.pkl, feat_2019–2020.pkl,
      feat2_2019–2020.pkl (OI архива для периода нет — колонки OI пустые);
  cd /home/user/mc_data && MC_K=/home/user/mc_data/s192/k_2019.pkl MC_F=/home/user/mc_data/s192/fund_2019.pkl \\
      MC_CUT=2020-04-01 python3 <repo>/research/s192/period.py run <скрипт.py> <функция> [аргументы …]
      модуль скрипта загружается без блока __main__, в PER его и загруженных общих модулей добавляется «2019–2020»,
      затем вызывается функция (например: … run research/s185/oos.py run 2019–2020);
  python3 period.py show <скрипт.py>  — какую запись PER получит скрипт (без расчёта)."""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
D = "/home/user/mc_data"
NEW, TPL = "2019–2020", "2020–2022"
# порядок важен: длинные подстроки раньше коротких
SUBST = [
    ("s117/k_2020.pkl", "s192/k_2019.pkl"),
    ("s117/fund_2020.pkl", "s192/fund_2019.pkl"),
    ("/home/user/mc_2020/s23/spotcache", f"{D}/s192/spotcache"),
    ("s88/oos2020/kc", "s192/kc"),
    ("s88/oos2020/map.pkl", "s192/map.pkl"),
    ("s88/oos2020", "s192"),
    ("/home/user/mc_2020", f"{D}/s192/work"),
    ("2020-10-01", "2019-10-01"),                                 # начало периода
    ("2022-10-01", "2020-10-01"),                                 # конец периода
    ("2021-10-01", "2020-04-01"),                                 # середина (MC_CUT)
]
T0, T1, CUT = "2019-10-01", "2020-10-01", "2020-04-01"


def derive(v):
    """Запись периода из записи «2020–2022»: строки — заменой SUBST, кортежи/списки/словари — поэлементно."""
    if isinstance(v, str):
        for a, b in SUBST:
            if a in v:
                v = v.replace(a, b)
        return v
    if isinstance(v, tuple):
        return tuple(derive(x) for x in v)
    if isinstance(v, list):
        return [derive(x) for x in v]
    if isinstance(v, dict):
        return {k: derive(x) for k, x in v.items()}
    return v


def patch_module(m, verbose=True):
    """Добавить «2019–2020» в словари периодов (PER, PERIODS) и списки (PERS) модуля; вернуть, что добавлено."""
    done = []
    for name in ("PER", "PERIODS"):
        P = getattr(m, name, None)
        if isinstance(P, dict) and TPL in P and NEW not in P:
            e = derive(P[TPL])
            new = {NEW: e, **P}
            P.clear()
            P.update(new)                                          # тот же объект: ссылки других модулей видят период
            done.append((name, e))
    L = getattr(m, "PERS", None)
    if isinstance(L, list) and TPL in L and NEW not in L:
        L.insert(0, NEW)
        done.append(("PERS", list(L)))
    if verbose:
        for name, e in done:
            print(f"[s192] {getattr(m, '__name__', m)}.{name}[{NEW}] = {e}", flush=True)
    return done


PRELOAD = [("s182", "common182"), (os.path.join("s183", "study"), "common183")]


def preload():
    """Общие модули с PER, которые скрипты импортируют внутри функций (s190/g2.report → common182): загрузить заранее,
    чтобы поздний import взял уже дополненный модуль из sys.modules."""
    for d, name in PRELOAD:
        p = os.path.join(REPO, "research", d)
        if p not in sys.path:
            sys.path.append(p)                                     # в конец: не заслонять модули самого скрипта
        if name not in sys.modules:
            importlib.import_module(name)


def patch_loaded(verbose=True):
    preload()
    for m in list(sys.modules.values()):
        f = getattr(m, "__file__", None) or ""
        if f.startswith(os.path.join(REPO, "research")):
            patch_module(m, verbose)


def load_script(path, name="s192_target"):
    path = os.path.abspath(path if os.path.exists(path) else os.path.join(REPO, path))
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)                                   # __name__ != "__main__": блок запуска не выполняется
    return mod


def run_s183():
    sys.path.insert(0, os.path.join(REPO, "research", "s183", "study"))
    import common183 as C                                          # noqa: E402
    patch_module(C)
    import panel                                                   # noqa: E402
    import features                                                # noqa: E402
    import feat_oi                                                 # noqa: E402
    panel.main(NEW)
    features.main(NEW)
    feat_oi.main(NEW)


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "s183":
        run_s183()
    elif what in ("run", "show"):
        mod = load_script(sys.argv[2])
        patch_loaded()
        if what == "run":
            res = getattr(mod, sys.argv[3])(*sys.argv[4:])
            if res is not None and not hasattr(res, "to_pickle"):
                print(res)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
