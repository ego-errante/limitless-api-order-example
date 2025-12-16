import json
import requests

API_BASE_URL = "https://api.limitless.exchange"


def get_daily_markets(page: int = 1, limit: int = 100):
    """
    Fetch all active markets and filter for Daily markets with tokens.
    """
    response = requests.get(
        f"{API_BASE_URL}/markets/active",
        params={"sortBy": "newest"},
    )
    response.raise_for_status()
    data = response.json()

    # Filter for markets that are Daily and have tokens
    daily_markets = [
        market
        for market in data.get("data", [])
        if "Daily" in market.get("categories", []) and market.get("tokens")
    ]

    return daily_markets


# Example usage
daily_markets = get_daily_markets()

if daily_markets:
    market = daily_markets[0]
    print(market.get("slug"))
    print(json.dumps(market.get("tokens"), indent=2))
    print(market.get("prices"))
else:
    print("No Daily markets with tokens found.")
