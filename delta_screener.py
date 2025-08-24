import streamlit as st
import pandas as pd
import requests
import time
from ta.trend import SMAIndicator

st.set_page_config(page_title="SMA Categorizer", layout="centered")
st.title("📈 SMA 20 vs SMA 200 Categorizer")
st.caption("Shows assets under Bullish/Bearish by SMA structure across all available assets")

# --- Config ---
API_BASE = "https://api.india.delta.exchange"
TIMEFRAMES = ["5m", "15m"]
LIMIT = 200  # Number of candles

# --- Get available trading symbols ---
def get_symbols():
    url = f"{API_BASE}/v2/products"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        products = data.get("result") or data.get("products") or []
        symbols = [p['symbol'] for p in products if 'symbol' in p]
        return sorted(symbols)
    except Exception as e:
        st.error(f"Error fetching symbols: {e}")
        return []

# --- Fetch OHLCV data ---
@st.cache_data(show_spinner=False)
def fetch_ohlcv(symbol: str, interval: str, limit: int = LIMIT):
    end = int(time.time())
    multiplier = {"5m": 60 * 5, "15m": 60 * 15}.get(interval, 60 * 5)
    start = end - limit * multiplier

    url = f"{API_BASE}/v2/history/candles"
    params = {
        "symbol": symbol,
        "resolution": interval,
        "start": start,
        "end": end
    }
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        candles = r.json().get("result", [])
        if not candles:
            return None
        df = pd.DataFrame(candles)
        df["timestamp"] = pd.to_datetime(df["time"], unit='s') + pd.Timedelta(hours=5, minutes=30)
        df.set_index("timestamp", inplace=True)
        df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
        return df
    except Exception as e:
        st.warning(f"Data error for {symbol} [{interval}]: {e}")
        return None

# --- Calculate SMA structure ---
def calculate_sma_structure(df):
    df["sma_20"] = SMAIndicator(df["close"], window=20).sma_indicator()
    df["sma_200"] = SMAIndicator(df["close"], window=200).sma_indicator()
    last = df.iloc[-1]
    if pd.isna(last["sma_20"]) or pd.isna(last["sma_200"]):
        return "Not enough data"

    price = last["close"]
    sma_20 = last["sma_20"]
    sma_200 = last["sma_200"]

    if (price > sma_20 and sma_20 > sma_200) or (price > sma_20 and price > sma_200):
        return "Bullish"
    elif price < sma_20 and sma_20 < sma_200:
        return "Bearish"
    else:
        return "Neutral"

# --- Get all symbols ---
all_symbols = get_symbols()
if not all_symbols:
    st.stop()

st.markdown("---")
st.info(f"🔍 Scanning ALL {len(all_symbols)} available assets across timeframes...")

# --- Scanning ---
data_rows = []

for symbol in all_symbols:
    row = {"Symbol": symbol}
    for tf in TIMEFRAMES:
        df = fetch_ohlcv(symbol, tf, limit=LIMIT)
        if df is None or df.empty:
            row[f"SMA Structure {tf}"] = "No Data"
        else:
            structure = calculate_sma_structure(df)
            row[f"SMA Structure {tf}"] = structure
    data_rows.append(row)

result_df = pd.DataFrame(data_rows)
st.success(f"✅ Scan complete. Total assets scanned: {len(result_df)}")

# --- Display Tables ---
for tf in TIMEFRAMES:
    st.subheader(f"🕒 {tf.upper()} Time Frame")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### ✅ Bullish")
        bullish_df = result_df[result_df[f"SMA Structure {tf}"] == "Bullish"]
        st.write(bullish_df[["Symbol"]])
    with col2:
        st.markdown("### ❌ Bearish")
        bearish_df = result_df[result_df[f"SMA Structure {tf}"] == "Bearish"]
        st.write(bearish_df[["Symbol"]])

# --- Download option ---
st.download_button(
    label="📅 Download Results (CSV)",
    data=result_df.to_csv(index=False).encode('utf-8'),
    file_name='sma_structure_results.csv',
    mime='text/csv'
)
