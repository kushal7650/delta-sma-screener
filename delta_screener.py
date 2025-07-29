def get_symbols():
    url = f"{API_BASE}/v2/products"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        products = data.get("result", [])
        st.write("🔍 Raw products sample:", products[:5])  # DEBUG

        # 🔍 Log contract types
        all_types = set(p.get("contract_type", "Unknown") for p in products)
        st.write("🧩 Unique contract types found:", all_types)

        # ✅ Updated filter (adjust as needed based on what the log shows)
        symbols = [
            p["symbol"] for p in products
            if p.get("contract_type") == "perpetual_futures"
            and p.get("settling_asset", {}).get("symbol") == "USDT"
        ]

        st.write("✅ Symbols fetched:", symbols)
        return sorted(symbols)
    except Exception as e:
        st.error(f"Error fetching symbols: {e}")
        return []
