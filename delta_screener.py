import requests, time

end = int(time.time())
start = end - (5 * 60 * 200)  # last 200 candles of 5m data

r = requests.get(
  "https://api.india.delta.exchange/v2/history/candles",
  params={"symbol":"BTCUSD","resolution":"5m","start":start,"end":end}
)

print(r.status_code, r.json().keys(), len(r.json().get("result", [])))
