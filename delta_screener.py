url = "https://api.delta.exchange/chart/history"
params = {
    "symbol": symbol,
    "resolution": interval.replace("m", ""),  # strip 'm'
    "from": start,
    "to": end
}
