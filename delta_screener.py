import streamlit as st
import pandas as pd
import requests
import time
import matplotlib.pyplot as plt
from ta.trend import SMAIndicator

st.set_page_config(page_title="SMA Categorizer", layout="centered")
st.title("📈 SMA 20 vs SMA 200 Categorizer")
st.caption("Shows assets under Bullish/Bearish by SMA structure")

# --- Config ---
API_BASE = "https://api.india.delta.exchange"
TIMEFRAMES = {"5m": 5, "15m": 15}
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
def fetch_ohlcv(symbol: str, resolution: int, limit: int = LIMIT):
    end = int(time.time())
    start = end - limit * 60 * resolution

    url = f"{API_BASE}/v2/history/candles"
    params = {
        "symbol": symbol,
        "resolution": resolution,
        "start": start,
        "end": end
    }
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        candles = r.json().get("result", [])
        if not candles or len(candles) < 200:
            return None
        df = pd.DataFrame(candles)
        df["timestamp"] = pd.to_datetime(df["time"], unit='s') + pd.Timedelta(hours=5, minutes=30)
        df.set_index("timestamp", inplace=True)
        df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
        return df
    except Exception as e:
        st.warning(f"❌ Data error for {symbol} @ {resolution}m: {e}")
        return None

# --- Calculate SMA structure ---
def calculate_sma_structure(df, timeframe_label):
    df["sma_20"] = SMAIndicator(df["close"], window=20).sma_indicator()
    df["sma_200"] = SMAIndicator(df["close"], window=200).sma_indicator()
    last = df.iloc[-1]
    price = last["close"]
    sma20 = last["sma_20"]
    sma200 = last["sma_200"]

    if pd.isna(sma20) or pd.isna(sma200):
        return "Not enough data"

    if price > sma20 and sma20 > sma200:
        return "Bullish"
    elif price < sma20 and sma20 < sma200:
        return "Bearish"
    elif timeframe_label == "5m" and price > sma20 and sma20 < sma200:
        return "Slight Bullish"
    elif timeframe_label == "5m" and price < sma20 and sma20 > sma200:
        return "Slight Bearish"
    else:
        return "Neutral"

# --- UI: Asset selection ---
st.markdown("---")
all_symbols = get_symbols()
selected_assets = st.multiselect("Select up to 10 assets", options=all_symbols, max_selections=10)

if not selected_assets:
    st.warning("⚠️ Please select assets to scan.")
    st.stop()

# --- Scanning ---
st.info("🔍 Scanning selected assets across timeframes...")
data_rows = []
dataframes = {}  # Store for charting

for symbol in selected_assets:
    row = {"Symbol": symbol}
    for label, resolution in TIMEFRAMES.items():
        df = fetch_ohlcv(symbol, resolution, limit=LIMIT)
        if df is None or df.empty:
            row[f"SMA Structure {label}"] = "No Data"
        else:
            df["sma_20"] = SMAIndicator(df["close"], window=20).sma_indicator()
            df["sma_200"] = SMAIndicator(df["close"], window=200).sma_indicator()
            dataframes[(symbol, label)] = df  # Store for later
            structure = calculate_sma_structure(df, label)
            row[f"SMA Structure {label}"] = structure
    data_rows.append(row)

result_df = pd.DataFrame(data_rows)
st.success(f"✅ Scan complete. Total assets scanned: {len(result_df)}")

# --- Display Tables ---
for tf_label in TIMEFRAMES:
    st.subheader(f"🕒 {tf_label.upper()} Time Frame")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("### ✅ Bullish")
        bullish_df = result_df[result_df[f"SMA Structure {tf_label}"] == "Bullish"]
        st.write(bullish_df[["Symbol"]])
    with col2:
        st.markdown("### ⚠️ Slight Bullish")
        slight_df = result_df[result_df[f"SMA Structure {tf_label}"] == "Slight Bullish"]
        st.write(slight_df[["Symbol"]])
    with col3:
        st.markdown("### ❌ Bearish")
        bearish_df = result_df[result_df[f"SMA Structure {tf_label}"] == "Bearish"]
        st.write(bearish_df[["Symbol"]])
    with col4:
        st.markdown("### 🔻 Slight Bearish")
        slight_bear_df = result_df[result_df[f"SMA Structure {tf_label}"] == "Slight Bearish"]
        st.write(slight_bear_df[["Symbol"]])

# --- Download option ---
st.download_button(
    label="📅 Download Results (CSV)",
    data=result_df.to_csv(index=False).encode('utf-8'),
    file_name='sma_structure_results.csv',
    mime='text/csv'
)

# --- Chart Preview ---
st.markdown("---")
st.header("📊 Chart Previews")
sel_symbol = st.selectbox("Select asset to view chart", selected_assets)
sel_tf = st.radio("Choose timeframe", list(TIMEFRAMES.keys()), horizontal=True)

if (sel_symbol, sel_tf) in dataframes:
    df = dataframes[(sel_symbol, sel_tf)]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df.index, df["close"], label="Close", linewidth=1)
    ax.plot(df.index, df["sma_20"], label="SMA 20", linestyle="--")
    ax.plot(df.index, df["sma_200"], label="SMA 200", linestyle=":")
    ax.set_title(f"{sel_symbol} - {sel_tf} Chart")
    ax.legend()
    ax.grid(True)
    st.pyplot(fig)
else:
    st.info("Chart not available for selected asset/timeframe.")
