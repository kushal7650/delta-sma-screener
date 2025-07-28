import streamlit as st
import pandas as pd
import requests
from ta.trend import SMAIndicator
import time

st.set_page_config(page_title="SMA Categorizer", layout="centered")
st.title("📈 SMA 20 vs SMA 200 Categorizer")
st.caption("Shows assets under Bullish/Bearish by SMA structure")

# --- Config ---
API_BASE = "https://api.delta.exchange"
TIMEFRAMES = {"5m": 300, "15m": 900}  # timeframe: resolution in seconds
LIMIT = 300  # Number of candles

def get_symbols():
    url = f"{API_BASE}/v2/products"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        products = data.get("result", [])
        symbols = [p["symbol"] for p in products if p.get("contract_type") == "perpetual_futures"]
        return sorted(symbols)
    except Exception as e:
        st.error(f"Error fetching symbols: {e}")
        return []

@st.cache_data(show_spinner=False)
def fetch_ohlcv(symbol: str, resolution_sec: int, limit: int = LIMIT):
    end_time = int(time.time())
    start_time = end_time - (limit * resolution_sec)

    url = f"{API_BASE}/chart/history"
    params = {
        "symbol": symbol,
        "resolution": resolution_sec // 60,
        "from": start_time,
        "to": end_time
    }

    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        if not data.get("c"):
            return None

        df = pd.DataFrame({
            "timestamp": pd.to_datetime(data["t"], unit='s'),
            "open": data["o"],
            "high": data["h"],
            "low": data["l"],
            "close": data["c"],
            "volume": data["v"]
        })
        df.set_index("timestamp", inplace=True)
        return df
    except Exception as e:
        st.warning(f"Data error for {symbol}: {e}")
        return None

def calculate_sma_structure(df):
    df["sma_20"] = SMAIndicator(df["close"], window=20).sma_indicator()
    df["sma_200"] = SMAIndicator(df["close"], window=200).sma_indicator()
    last = df.iloc[-1]
    if pd.isna(last["sma_20"]) or pd.isna(last["sma_200"]):
        return "Not enough data"
    if last["sma_20"] > last["sma_200"]:
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

# --- Scanning ---
st.info("🔍 Scanning selected assets across timeframes...")
data_rows = []

for symbol in selected_assets:
    row = {"Symbol": symbol}
    for tf_label, resolution_sec in TIMEFRAMES.items():
        df = fetch_ohlcv(symbol, resolution_sec, limit=LIMIT)
        if df is None or df.empty:
            row[f"SMA Structure {tf_label}"] = "No Data"
        else:
            row[f"SMA Structure {tf_label}"] = calculate_sma_structure(df)
    data_rows.append(row)

result_df = pd.DataFrame(data_rows)
st.success(f"✅ Scan complete. Total assets scanned: {len(result_df)}")

# --- Display Tables ---
for tf_label in TIMEFRAMES:
    st.subheader(f"🕒 {tf_label.upper()} Time Frame")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### ✅ Bullish")
        bullish_df = result_df[result_df[f"SMA Structure {tf_label}"] == "Bullish"]
        st.write(bullish_df[["Symbol"]])

    with col2:
        st.markdown("### ❌ Bearish")
        bearish_df = result_df[result_df[f"SMA Structure {tf_label}"] == "Bearish"]
        st.write(bearish_df[["Symbol"]])

# --- Download option ---
st.download_button(
    label="📥 Download Results (CSV)",
    data=result_df.to_csv(index=False).encode('utf-8'),
    file_name='sma_structure_results.csv',
    mime='text/csv'
)
