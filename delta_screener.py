import streamlit as st
import pandas as pd
import requests
import time
from ta.trend import SMAIndicator

# --- Config ---
st.set_page_config(page_title="SMA Categorizer", layout="centered")
st.title("📈 SMA 20 vs SMA 200 Categorizer")
st.caption("Shows assets under Bullish/Bearish by SMA structure")

API_BASE = "https://api.india.delta.exchange"
TIMEFRAMES = ["5m", "15m"]
LIMIT = 200

# --- Fetch tradable symbols ---
def get_symbols():
    url = f"{API_BASE}/v2/products"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json().get("result", [])
        symbols = sorted(list({p["symbol"] for p in data if p.get("contract_type") == "perpetual_futures"}))
        return symbols
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
        "resolution": interval.replace("m", ""),
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
        df["timestamp"] = pd.to_datetime(df["time"], unit="s") + pd.Timedelta(hours=5, minutes=30)
        df.set_index("timestamp", inplace=True)
        df = df.rename(columns={
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume"
        })
        return df[["open", "high", "low", "close", "volume"]].astype(float)
    except Exception as e:
        st.warning(f"Data error for {symbol} [{interval}]: {e}")
        return None

# --- SMA check ---
def calculate_sma_structure(df):
    df["sma_20"] = SMAIndicator(df["close"], window=20).sma_indicator()
    df["sma_200"] = SMAIndicator(df["close"], window=200).sma_indicator()
    last = df.iloc[-1]
    if pd.isna(last["sma_20"]) or pd.isna(last["sma_200"]):
        return "No Data"
    elif last["sma_20"] > last["sma_200"]:
        return "Bullish"
    elif last["sma_20"] < last["sma_200"]:
        return "Bearish"
    else:
        return "Neutral"

# --- UI ---
all_symbols = get_symbols()
selected_assets = st.multiselect("Select up to 10 assets", options=all_symbols, max_selections=10)

if not selected_assets:
    st.warning("⚠️ Please select assets to scan.")
    st.stop()

st.info("🔍 Scanning selected assets across timeframes...")
results = []

for symbol in selected_assets:
    result = {"Symbol": symbol}
    for tf in TIMEFRAMES:
        df = fetch_ohlcv(symbol, tf)
        if df is not None and not df.empty:
            result[f"SMA Structure {tf}"] = calculate_sma_structure(df)
        else:
            result[f"SMA Structure {tf}"] = "No Data"
    results.append(result)

result_df = pd.DataFrame(results)

st.success(f"✅ Scan complete. Total assets scanned: {len(result_df)}")

# --- Display results per time frame ---
for tf in TIMEFRAMES:
    st.subheader(f"📊 {tf.upper()} Time Frame")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### ✅ Bullish")
        bullish = result_df[result_df[f"SMA Structure {tf}"] == "Bullish"]
        st.write(bullish[["Symbol"]])
        st.caption(f"Count: {len(bullish)}")

    with col2:
        st.markdown("### ❌ Bearish")
        bearish = result_df[result_df[f"SMA Structure {tf}"] == "Bearish"]
        st.write(bearish[["Symbol"]])
        st.caption(f"Count: {len(bearish)}")

# --- Download Button ---
st.download_button(
    label="📅 Download Results (CSV)",
    data=result_df.to_csv(index=False).encode('utf-8'),
    file_name="sma_structure_scan.csv",
    mime="text/csv"
)
