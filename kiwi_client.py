"""Kiwi Tequila API client for searching flights."""

import time
import requests


TEQUILA_BASE_URL = "https://tequila-api.kiwi.com"


def search_flights(api_key, fly_from, fly_to, date_from, date_to,
                   nights_from, nights_to, adults, max_stopovers, currency,
                   limit):
    """Search for return flights via the Kiwi Tequila API.

    Returns a list of parsed flight dictionaries, or an empty list on error.
    """
    headers = {"apikey": api_key}
    params = {
        "fly_from": fly_from,
        "fly_to": fly_to,
        "dateFrom": date_from,
        "dateTo": date_to,
        "nights_in_dst_from": nights_from,
        "nights_in_dst_to": nights_to,
        "flight_type": "round",
        "adults": adults,
        "curr": currency,
        "max_stopovers": max_stopovers,
        "sort": "price",
        "limit": limit,
    }

    try:
        resp = requests.get(
            f"{TEQUILA_BASE_URL}/v2/search",
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"  Error searching {fly_from} → {fly_to}: {e}")
        return []

    flights = []
    for item in data.get("data", []):
        flights.append(_parse_flight(item, currency))
    return flights


def _parse_flight(item, currency):
    """Extract relevant fields from a Kiwi flight result."""
    routes = item.get("route", [])

    # Split route into outbound and return legs
    outbound_legs = [r for r in routes if r.get("return") == 0]
    return_legs = [r for r in routes if r.get("return") == 1]

    outbound_airlines = sorted({r.get("airline", "?") for r in outbound_legs})
    return_airlines = sorted({r.get("airline", "?") for r in return_legs})

    outbound_stops = [r.get("flyTo") for r in outbound_legs[:-1]] if len(outbound_legs) > 1 else []
    return_stops = [r.get("flyTo") for r in return_legs[:-1]] if len(return_legs) > 1 else []

    return {
        "price": item.get("price"),
        "currency": currency,
        "origin": item.get("flyFrom"),
        "destination": item.get("flyTo"),
        "departure_date": item.get("local_departure", "")[:10],
        "return_date": item.get("local_arrival", "")[:10],
        "outbound_duration_h": round(item.get("duration", {}).get("departure", 0) / 3600, 1),
        "return_duration_h": round(item.get("duration", {}).get("return", 0) / 3600, 1),
        "total_duration_h": round(
            (item.get("duration", {}).get("departure", 0) +
             item.get("duration", {}).get("return", 0)) / 3600, 1
        ),
        "outbound_stops": outbound_stops,
        "return_stops": return_stops,
        "outbound_airlines": outbound_airlines,
        "return_airlines": return_airlines,
        "num_stops_outbound": len(outbound_stops),
        "num_stops_return": len(return_stops),
        "booking_link": item.get("deep_link", ""),
    }


def search_all_airports(api_key, airports, fly_to, date_from, date_to,
                        nights_from, nights_to, adults, max_stopovers,
                        currency, limit, delay=1.5):
    """Search flights from multiple origin airports with rate-limit delays."""
    all_flights = []
    for airport in airports:
        print(f"Searching {airport} → {fly_to}...")
        results = search_flights(
            api_key, airport, fly_to, date_from, date_to,
            nights_from, nights_to, adults, max_stopovers, currency, limit,
        )
        print(f"  Found {len(results)} flights from {airport}")
        all_flights.extend(results)
        time.sleep(delay)

    # Sort by price, then total duration
    all_flights.sort(key=lambda f: (f["price"], f["total_duration_h"]))
    return all_flights
