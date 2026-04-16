"""Google Flights client via the fast-flights scraper (no API key required).

Uses one-way searches for each leg and pairs them manually to find the
cheapest round-trip combinations. This is necessary for niche routes like
UK↔SXR where Google Flights' round-trip search returns no packaged fares
(the trip is actually booked as two separate tickets), even though flights
exist on both legs.

Strategy:
  - Scrape outbound one-way prices for each (airport, depart_date)
  - Scrape return one-way prices for each (airport, return_date)
  - For each (depart_date, return_date) pair, combine the cheapest outbound
    and cheapest return into a synthetic round-trip record

Uses fast-flights' `local` fetch mode (Playwright) to get past Google's
GDPR consent wall on EU IPs and to wait for JS-rendered flight cards.
"""

import json
import os
import re
import time
from datetime import datetime, timedelta
from urllib.parse import quote_plus

import fast_flights.local_playwright as _ff_local
from fast_flights import FlightData, Passengers, get_flights
from playwright.async_api import async_playwright as _async_playwright


# ---------------------------------------------------------------------------
# Override fast-flights' Playwright fetcher with a 10-second locator timeout
# (the library's default is 30s, which turns every empty-results page into
# a 30-second stall — adds up badly over hundreds of queries).
# ---------------------------------------------------------------------------
_LOCATOR_TIMEOUT_MS = 10_000


async def _fetch_with_playwright_fast(url: str) -> str:
    async with _async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(url)
            if page.url.startswith("https://consent.google.com"):
                await page.click('text="Accept all"')
            locator = page.locator(".eQ35Ce")
            await locator.wait_for(timeout=_LOCATOR_TIMEOUT_MS)
            body = await page.evaluate(
                "() => document.querySelector('[role=\"main\"]').innerHTML"
            )
        finally:
            await browser.close()
    return body


_ff_local.fetch_with_playwright = _fetch_with_playwright_fast


# ---------------------------------------------------------------------------
# Core scraping
# ---------------------------------------------------------------------------
def search_oneway(fly_from, fly_to, date, adults, max_stops=None):
    """Search a single one-way date via Google Flights. Returns list of dicts."""
    try:
        result = get_flights(
            flight_data=[
                FlightData(date=date, from_airport=fly_from, to_airport=fly_to),
            ],
            trip="one-way",
            seat="economy",
            passengers=Passengers(adults=adults),
            fetch_mode="local",
            max_stops=max_stops,
        )
    except Exception as e:
        # Collapse multi-line error (Playwright call log) into one line
        msg = str(e).splitlines()[0]
        print(f"  Error {fly_from} → {fly_to} on {date}: {msg}")
        return []

    out = []
    for flight in (getattr(result, "flights", None) or []):
        try:
            price = _extract_price(getattr(flight, "price", None))
            if price is None:
                continue
            duration_h = _duration_to_hours(getattr(flight, "duration", ""))
            airline = getattr(flight, "name", None) or "?"
            raw_stops = getattr(flight, "stops", 0)
            stops = int(raw_stops) if raw_stops is not None else 0
            out.append({
                "price": price,
                "duration_h": round(duration_h, 1),
                "airline": airline,
                "stops": stops,
            })
        except (AttributeError, ValueError, TypeError):
            continue
    return out


# ---------------------------------------------------------------------------
# Pairing + result schema
# ---------------------------------------------------------------------------
def _pair_as_flight(origin, destination, depart_date, return_date, outbound, ret_leg):
    """Combine an outbound and return one-way option into a round-trip record."""
    total_h = round(outbound["duration_h"] + ret_leg["duration_h"], 1)
    return {
        "price": outbound["price"] + ret_leg["price"],
        "currency": "GBP",
        "origin": origin,
        "destination": destination,
        "departure_date": depart_date,
        "return_date": return_date,
        "outbound_duration_h": outbound["duration_h"],
        "return_duration_h": ret_leg["duration_h"],
        "total_duration_h": total_h,
        "outbound_stops": [],
        "return_stops": [],
        "outbound_airlines": [outbound["airline"]],
        "return_airlines": [ret_leg["airline"]],
        "num_stops_outbound": outbound["stops"],
        "num_stops_return": ret_leg["stops"],
        "booking_link": _build_booking_link(origin, destination, depart_date, return_date),
    }


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


# ---------------------------------------------------------------------------
# Cache (JSONL, append-only)
# Each line: {"origin", "dest", "date", "direction": "outbound"|"return", "options"}
# ---------------------------------------------------------------------------
def _load_cache(cache_path):
    """Return a dict keyed by (origin, dest, date, direction) → list of option dicts."""
    cache = {}
    if not cache_path or not os.path.exists(cache_path):
        return cache
    with open(cache_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                key = (e["origin"], e["dest"], e["date"], e["direction"])
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
            cache[key] = e.get("options", [])
    return cache


def _append_cache(cache_f, origin, dest, date, direction, options):
    if not cache_f:
        return
    cache_f.write(json.dumps({
        "origin": origin,
        "dest": dest,
        "date": date,
        "direction": direction,
        "options": options,
    }) + "\n")
    cache_f.flush()


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------
def search_all_airports(airports, fly_to, date_from, date_to,
                        step_days, night_options, adults,
                        max_stopovers, delay=0.5, cache_path=None):
    """One-way + pairing search: scrape each leg separately, then pair up.

    If cache_path is given, every leg query is appended as a JSON line
    immediately. On restart, already-scraped (origin, dest, date, direction)
    entries are skipped. Delete the cache file if you change config in a way
    that affects results (destination, adults, max_stopovers).
    """
    date_pairs = _generate_date_pairs(date_from, date_to, step_days, night_options)
    outbound_dates = sorted({p[0] for p in date_pairs})
    return_dates = sorted({p[1] for p in date_pairs})

    total_queries = len(airports) * (len(outbound_dates) + len(return_dates))
    print(f"One-way pairing mode:")
    print(f"  {len(outbound_dates)} outbound dates × {len(airports)} airports = "
          f"{len(outbound_dates) * len(airports)} outbound queries")
    print(f"  {len(return_dates)} return dates × {len(airports)} airports = "
          f"{len(return_dates) * len(airports)} return queries")
    print(f"  Total: {total_queries} queries (will pair into {len(date_pairs) * len(airports)} "
          f"round-trip combinations)")

    cache = _load_cache(cache_path)
    if cache:
        print(f"  Cache: {len(cache)} leg queries already done, skipping those.\n")
    else:
        print()

    cache_f = open(cache_path, "a") if cache_path else None
    try:
        for airport in airports:
            # --- outbound leg: airport → fly_to on each outbound_date ---
            print(f"=== Outbound: {airport} → {fly_to} ({len(outbound_dates)} dates) ===")
            for date in outbound_dates:
                key = (airport, fly_to, date, "outbound")
                if key in cache:
                    continue
                options = search_oneway(airport, fly_to, date, adults, max_stops=max_stopovers)
                cache[key] = options
                _append_cache(cache_f, airport, fly_to, date, "outbound", options)
                if options:
                    cheapest = min(options, key=lambda o: o["price"])
                    print(f"  OK  {airport}→{fly_to} {date}: {len(options)} opts, "
                          f"cheapest GBP {cheapest['price']} ({cheapest['airline']}, "
                          f"{cheapest['stops']} stops)")
                else:
                    print(f"  --  {airport}→{fly_to} {date}: no options")
                time.sleep(delay)

            # --- return leg: fly_to → airport on each return_date ---
            print(f"=== Return: {fly_to} → {airport} ({len(return_dates)} dates) ===")
            for date in return_dates:
                key = (fly_to, airport, date, "return")
                if key in cache:
                    continue
                options = search_oneway(fly_to, airport, date, adults, max_stops=max_stopovers)
                cache[key] = options
                _append_cache(cache_f, fly_to, airport, date, "return", options)
                if options:
                    cheapest = min(options, key=lambda o: o["price"])
                    print(f"  OK  {fly_to}→{airport} {date}: {len(options)} opts, "
                          f"cheapest GBP {cheapest['price']} ({cheapest['airline']}, "
                          f"{cheapest['stops']} stops)")
                else:
                    print(f"  --  {fly_to}→{airport} {date}: no options")
                time.sleep(delay)
    finally:
        if cache_f:
            cache_f.close()

    # --- pair outbound × return for each date combo ---
    print()
    print("Pairing outbound + return legs...")
    all_flights = []
    paired = 0
    skipped = 0
    for airport in airports:
        for depart, ret in date_pairs:
            outbounds = cache.get((airport, fly_to, depart, "outbound"), [])
            returns = cache.get((fly_to, airport, ret, "return"), [])
            if not outbounds or not returns:
                skipped += 1
                continue
            ob = min(outbounds, key=lambda o: o["price"])
            rb = min(returns, key=lambda o: o["price"])
            all_flights.append(_pair_as_flight(airport, fly_to, depart, ret, ob, rb))
            paired += 1

    print(f"Paired {paired} round-trip combinations; skipped {skipped} "
          f"(missing outbound or return availability)")

    all_flights.sort(key=lambda f: (f["price"], f["total_duration_h"]))
    return all_flights
