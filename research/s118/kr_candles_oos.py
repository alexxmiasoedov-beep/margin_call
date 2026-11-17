"""s118 — часовые свечи рынков к воне Upbit и Bithumb за 01.10.2022–01.10.2024 для проверки корейских журналов вне выборки:
код s15/kr_candles.py с другими границами и архивом фьючерсов s117/k_oos.pkl (MC_K). Кэш — s15/kc/<биржа>/ в рабочей папке,
итог — s15/kr_candles_<биржа>.pkl там же (~/mc_oos). Рынки — текущий список бирж: снятые с корейских бирж до 2024 г.
монеты не попадают. Запуск из ~/mc_oos: MC_K=… python3 <repo>/research/s118/kr_candles_oos.py upbit|bithumb"""
import datetime
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15"))
import kr_candles as kc  # noqa: E402

kc.T0 = datetime.datetime(2022, 10, 1, tzinfo=datetime.timezone.utc)
kc.T1 = datetime.datetime(2024, 10, 1, tzinfo=datetime.timezone.utc)
kc.K = pickle.load(open(os.environ["MC_K"], "rb"))

if __name__ == "__main__":
    kc.exchange(sys.argv[1])
