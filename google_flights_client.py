"""Google Flights client via the fast-flights scraper (no API key required).

Uses fast-flights' `local` fetch mode, which drives a headless Playwright
browser. This is required for UK/EU users because Google serves a GDPR
cookie consent interstitial before showing flight results, which a plain
HTTP client can't dismiss. Playwright clicks through the consent page and
waits for JS-rendered flight cards before fast-flights parses the HTML.
"""

import json
import os
import re
import time
from datetime import datetime, timedelta
from urllib.parse import quote_plus

from fast_flights import FlightData, Passengers, get_flights


def search_flights(fly_from, fly_to, depart_date, return_date, adults, max_stops=None):
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
            fetch_mode="local",
            max_stops=max_stops,
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


def _load_cache(cache_path):
    """Load a JSONL cache file into (completed_keys, flights_by_airport).

    Each line is a dict: {"airport", "depart", "return", "flights"}.
    Malformed lines are skipped (e.g. from an interrupted write).
    """
    completed = set()
    by_airport = {}
    if not cache_path or not os.path.exists(cache_path):
        return completed, by_airport
    with open(cache_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                key = (entry["airport"], entry["depart"], entry["return"])
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
            if key in completed:
                continue
            completed.add(key)
            by_airport.setdefault(entry["airport"], []).extend(entry.get("flights", []))
    return completed, by_airport


def search_all_airports(airports, fly_to, date_from, date_to,
                        step_days, night_options, adults,
                        max_stopovers, delay=0.5, cache_path=None):
    """Search flights from multiple airports across a grid of date pairs.

    If cache_path is given, every completed query is appended as a JSON line
    immediately, so a mid-run failure loses at most the in-flight query. On
    restart with the same cache file, already-done queries are skipped.
    Delete the cache file if you change date/airport/destination config.
    """
    date_pairs = _generate_date_pairs(date_from, date_to, step_days, night_options)
    total = len(date_pairs) * len(airports)

    completed_keys, flights_by_airport = _load_cache(cache_path)
    for a in airports:
        flights_by_airport.setdefault(a, [])

    remaining = total - len(completed_keys)
    if completed_keys:
        print(f"Cache: resuming from {cache_path} — {len(completed_keys)} queries "
              f"already done, skipping those.")
    print(f"Scraping {len(date_pairs)} date pairs × {len(airports)} airports "
          f"= {total} queries total ({remaining} new, delay {delay}s)\n")

    # If we see this many consecutive empty results, we assume Google has
    # blocked us and halt — retrying in a loop is pointless and only deepens
    # the block. Empties are not cached (so they'll be retried next run).
    MAX_CONSECUTIVE_EMPTY = 10
    consecutive_empty = 0
    blocked = False

    cache_f = open(cache_path, "a") if cache_path else None
    try:
        for airport in airports:
            if blocked:
                break
            cached_flights_for_airport = len(flights_by_airport[airport])
            new_queries = 0
            new_flights = 0
            print(f"Searching {airport} → {fly_to}...")
            for depart, ret in date_pairs:
                key = (airport, depart, ret)
                if key in completed_keys:
                    continue
                results = search_flights(
                    airport, fly_to, depart, ret, adults, max_stops=max_stopovers,
                )
                new_queries += 1

                if results:
                    consecutive_empty = 0
                    flights_by_airport[airport].extend(results)
                    new_flights += len(results)
                    if cache_f:
                        cache_f.write(json.dumps({
                            "airport": airport,
                            "depart": depart,
                            "return": ret,
                            "flights": results,
                        }) + "\n")
                        cache_f.flush()
                else:
                    consecutive_empty += 1
                    if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                        print(f"\n*** {consecutive_empty} consecutive empty results — "
                              f"Google likely rate-limiting/blocking. Halting. ***")
                        print(f"    Cached results so far are saved. Re-run later to resume.")
                        blocked = True
                        break

                time.sleep(delay)
            total_for_airport = len(flights_by_airport[airport])
            if new_queries > 0:
                print(f"  Found {total_for_airport} flights from {airport} "
                      f"({new_flights} new, {cached_flights_for_airport} from cache)")
            else:
                print(f"  {total_for_airport} flights from {airport} (all from cache)")
    finally:
        if cache_f:
            cache_f.close()

    all_flights = [f for lst in flights_by_airport.values() for f in lst]
    all_flights.sort(key=lambda f: (f["price"], f["total_duration_h"]))
    return all_flights
