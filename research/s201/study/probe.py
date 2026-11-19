"""s201: пробы формата — (1) почасовой social_volume_total с computedAt; (2) labelled_historical_balance с меткой
владельца Binance для нескольких монет одним вызовом. Только проверка, что отвечает API."""
import json
import san

js, q = san.per_slug("social_volume_total", ["chainlink", "pepe", "solana"], "2026-10-10T00:00:00Z",
                     "2026-10-12T00:00:00Z", "1h", tag="probe_hourly", computed_at=True)
df = san.per_slug_frame(js)
print("почасовой social_volume_total:", len(df), "строк; ошибки:", js.get("errors"))
print(df.head(6).to_string())
if len(df):
    df["lag_h"] = (__import__("pandas").to_datetime(df.computedAt, utc=True) - df.datetime).dt.total_seconds() / 3600
    print("задержка computedAt − datetime, ч: медиана", df.lag_h.median(), "мин", df.lag_h.min(), "макс", df.lag_h.max())

js, q = san.per_slug("labelled_historical_balance", ["chainlink", "uniswap", "pepe"], "2026-10-01T00:00:00Z",
                     "2026-10-06T00:00:00Z", "1d", tag="probe_label",
                     extra_selector='labelFqn: "santiment/owner->binance:v1"')
df = san.per_slug_frame(js)
print("\nбаланс Binance (метка santiment/owner->binance:v1):", len(df), "строк; ошибки:", js.get("errors"))
print(df.to_string())
