"""Google Flights client via the fast-flights scraper (no API key required)."""

import re
import time
from datetime import datetime, timedelta
from urllib.parse import quote_plus

from fast_flights import FlightData, Passengers, get_flights


def search_flights(fly_from, fly_to, depart_date, return_date, adults):
    """Search one round-trip date pair via Google Flights.

    Returns a list of parsed flight dicts. The scraper exposes outbound-leg
    detail and a total round-trip price; return-leg details are not available.
    """
    try:
        result = get_flights(
            flight_data=[
                FlightData(date=depart_date, from_airport=fly_from, to_airport=fly_to),
                FlightData(date=return_date, from_airport=fly_to, to_airport=fly_from),
            ],
            trip="round-trip",
            seat="economy",
            passengers=Passengers(adults=adults),
            fetch_mode="fallback",
        )
    except Exception as e:
        print(f"  Error {fly_from} → {fly_to} on {depart_date}/{return_date}: {e}")
        return []

    out = []
    for flight in (getattr(result, "flights", None) or []):
        parsed = _parse_flight(flight, fly_from, fly_to, depart_date, return_date)
        if parsed:
            out.append(parsed)
    return out


def _parse_flight(flight, origin, destination, depart_date, return_date):
    """Convert a fast-flights Flight object into the agent's schema."""
    try:
        price = _extract_price(getattr(flight, "price", None))
        if price is None:
            return None

        out_duration_h = _duration_to_hours(getattr(flight, "duration", ""))
        airline = getattr(flight, "name", None) or "?"
        raw_stops = getattr(flight, "stops", 0)
        stops = int(raw_stops) if raw_stops is not None else 0

        return {
            "price": price,
            "currency": "GBP",
            "origin": origin,
            "destination": destination,
            "departure_date": depart_date,
            "return_date": return_date,
            "outbound_duration_h": round(out_duration_h, 1),
            "return_duration_h": 0.0,       # Google Flights scrape does not expose return-leg detail
            "total_duration_h": round(out_duration_h, 1),
            "outbound_stops": [],            # intermediate stop-airport codes not exposed
            "return_stops": [],
            "outbound_airlines": [airline],
            "return_airlines": [],
            "num_stops_outbound": stops,
            "num_stops_return": 0,
            "booking_link": _build_booking_link(origin, destination, depart_date, return_date),
        }
    except (AttributeError, ValueError, TypeError):
        return None


_PRICE_RE = re.compile(r"[\d,]+(?:\.\d+)?")


def _extract_price(s):
    """Parse '£350' / '$1,234' / '350.00' into an int."""
    if not s:
        return None
    m = _PRICE_RE.search(str(s))
    if not m:
        return None
    return int(round(float(m.group(0).replace(",", ""))))


_DUR_RE = re.compile(r"(?:(\d+)\s*hr)?\s*(?:(\d+)\s*min)?", re.IGNORECASE)


def _duration_to_hours(s):
    """Parse '12 hr 30 min' / '8 hr' / '45 min' into hours (float)."""
    if not s:
        return 0.0
    m = _DUR_RE.search(str(s))
    if not m:
        return 0.0
    h = int(m.group(1)) if m.group(1) else 0
    mi = int(m.group(2)) if m.group(2) else 0
    return h + mi / 60


def _build_booking_link(origin, destination, depart, ret):
    q = f"Flights from {origin} to {destination} on {depart} returning {ret}"
    return f"https://www.google.com/travel/flights?q={quote_plus(q)}"


def _generate_date_pairs(date_from, date_to, step_days, night_options):
    """Generate (depart, return) date pairs sampled across the departure window."""
    start = datetime.strptime(date_from, "%Y-%m-%d")
    end = datetime.strptime(date_to, "%Y-%m-%d")

    pairs = []
    cur = start
    while cur <= end:
        for nights in night_options:
            r = cur + timedelta(days=nights)
            pairs.append((cur.strftime("%Y-%m-%d"), r.strftime("%Y-%m-%d")))
        cur += timedelta(days=step_days)
    return pairs


def search_all_airports(airports, fly_to, date_from, date_to,
                        step_days, night_options, adults,
                        max_stopovers, delay=2.0):
    """Search flights from multiple airports across a grid of date pairs."""
    date_pairs = _generate_date_pairs(date_from, date_to, step_days, night_options)
    total = len(date_pairs) * len(airports)
    print(f"Scraping {len(date_pairs)} date pairs × {len(airports)} airports "
          f"= {total} Google Flights queries (delay {delay}s between calls)\n")

    all_flights = []
    for airport in airports:
        print(f"Searching {airport} → {fly_to}...")
        airport_count = 0
        for depart, ret in date_pairs:
            results = search_flights(airport, fly_to, depart, ret, adults)
            # Filter by max stopovers (outbound leg only — return-leg stops unknown).
            results = [r for r in results if r["num_stops_outbound"] <= max_stopovers]
            all_flights.extend(results)
            airport_count += len(results)
            time.sleep(delay)
        print(f"  Found {airport_count} flights from {airport}")

    all_flights.sort(key=lambda f: (f["price"], f["total_duration_h"]))
    return all_flights
