@st.cache_data(show_spinner=False)
def fetch_ohlcv(symbol: str, interval: str, limit: int = LIMIT):
    url = f"{API_BASE}/charts/v2/market_data"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()

        candles = data.get("candles", [])
        if not candles:
            return None

        df = pd.DataFrame(candles)
        df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s") + pd.Timedelta(hours=5, minutes=30)
        df.set_index("timestamp", inplace=True)
        return df
    except Exception as e:
        st.warning(f"❌ Data error for {symbol} @ {interval}: {e}")
        return None
