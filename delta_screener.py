import streamlit as st
import pandas as pd
import requests
import time
from ta.trend import SMAIndicator

st.set_page_config(page_title="SMA Categorizer", layout="centered")
st.title("📈 SMA 20 vs SMA 200 Categorizer")
st.caption("Shows assets under Bullish/Bearish/Slight structure by SMA structure")

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
        response = r.json()

        # If it's a dict with a key "result", extract it
        data = response.get("result", response)

        # Ensure data is a list
        if not isinstance(data, list):
            st.error("Unexpected API response format.")
            return []

        st.expander("🔍 Raw products sample:").write(data[:3])

        symbols = []
        for p in data:
            symbol = p.get("symbol")
            state = p.get("state")
            status = p.get("trading_status")
            notional_type = p.get("notional_type")
            quoting_asset = p.get("quoting_asset") or {}
            quoting_asset_symbol = quoting_asset.get("symbol", "").upper()

            if (
                notional_type == "vanilla"
                and state == "live"
                and status == "operational"
                and quoting_asset_symbol in ["USDT", "USD"]
            ):
                symbols.append(symbol)

        if not symbols:
            st.warning("⚠️ No matching assets found.")
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

    url = f"{API_BASE}/chart/history"
    params = {
        "symbol": symbol,
        "resolution": interval.replace("m", ""),
        "from": start,
        "to": end
    }
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        if not data.get("c"):
            return None

        df = pd.DataFrame({
            "close": data.get("c"),
            "open": data.get("o"),
            "high": data.get("h"),
            "low": data.get("l"),
            "volume": data.get("v"),
            "timestamp": pd.to_datetime(data.get("t"), unit="s") + pd.Timedelta(hours=5, minutes=30)
        })
        df.set_index("timestamp", inplace=True)
        return df
    except Exception as e:
        st.warning(f"❌ Data error for {symbol} @ {interval}: {e}")
        return None

# --- Calculate SMA structure ---
def calculate_sma_structure(df):
    df["sma_20"] = SMAIndicator(df["close"], window=20).sma_indicator()
    df["sma_200"] = SMAIndicator(df["close"], window=200).sma_indicator()
    last = df.iloc[-1]
    if pd.isna(last["sma_20"]) or pd.isna(last["sma_200"]):
        return "Not enough data"
    if last["close"] > last["sma_20"] and last["sma_20"] < last["sma_200"]:
        return "Slight Bullish"
    if last["close"] < last["sma_20"] and last["sma_20"] > last["sma_200"]:
        return "Slight Bearish"
    if last["sma_20"] > last["sma_200"]:
        return "Bullish"
    elif last["sma_20"] < last["sma_200"]:
        return "Bearish"
    else:
        return "Neutral"

# --- UI: Asset selection ---
st.markdown("---")
all_symbols = get_symbols()

if not all_symbols:
    st.error("❌ No symbols fetched. Please check API or try again later.")
    st.stop()

selected_assets = st.multiselect("Select up to 10 assets", options=all_symbols, max_selections=10)

if not selected_assets:
    st.warning("⚠️ Please select assets to scan.")
    st.stop()

# --- Scanning ---
st.info("🔍 Scanning selected assets across timeframes...")
data_rows = []

for symbol in selected_assets:
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
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### ✅ Bullish")
        st.write(result_df[result_df[f"SMA Structure {tf}"] == "Bullish"]["Symbol"])
    with col2:
        st.markdown("### ⚠️ Slight")
        slight_df = result_df[result_df[f"SMA Structure {tf}"].str.contains("Slight")]
        st.write(slight_df[["Symbol", f"SMA Structure {tf}"]])
    with col3:
        st.markdown("### ❌ Bearish")
        st.write(result_df[result_df[f"SMA Structure {tf}"] == "Bearish"]["Symbol"])

# --- Download option ---
st.download_button(
    label="🗕️ Download Results (CSV)",
    data=result_df.to_csv(index=False).encode('utf-8'),
    file_name='sma_structure_results.csv',
    mime='text/csv'
)
