# utils.py

import requests
import json

def get_market_data():
    """
    Get market data for the daily category
    """
    response = requests.get(
        "https://api.limitless.exchange/markets/active/30",
        params={
          "page": "1",
          "limit": "10",
          "sortBy": "newest"
        }
    )

    return response.json()

market_data = get_market_data()

# Find a market with tokens
# Some markets do not have tokens, so we need to check for that
for item in market_data.get("data"):
  if item.get("tokens"):
    print(item.get("slug"))
    print(json.dumps(item.get("tokens"), indent=2))
    print(item.get("prices"))
    break
