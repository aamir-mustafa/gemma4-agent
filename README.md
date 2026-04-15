# Flight Booking Agent

A Python-based AI agent that finds the cheapest return flights from airports near St Neots, Cambridgeshire (UK) to Srinagar (SXR), India. It searches multiple airports, collects results by scraping Google Flights via the [`fast-flights`](https://pypi.org/project/fast-flights/) library, and uses Google's Gemma 4 model to analyze and recommend the best-value options.

## Features

- Searches 5 UK airports nearest to St Neots (STN, LTN, LHR, LGW, BHX)
- Finds return flights for 2 passengers across a flexible date range
- Samples multiple departure dates × multiple trip lengths (default: 14/21/28 nights)
- Ranks flights by price and duration
- Uses Gemma 4 (31B) to reason over results and recommend the top 5 options
- **No API key or signup required** — uses the `fast-flights` Google Flights scraper

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed locally to run Gemma

## Setup

1. **Install Ollama and pull a Gemma model:**
   ```bash
   brew install ollama
   ollama serve                 # leave running in a separate terminal
   ollama pull gemma4:31b       # or gemma4:26b (MoE) / gemma4:e4b / gemma4:e2b for smaller models
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **(Optional) `.env` file for Ollama overrides:**
   ```
   # Optional — defaults shown
   OLLAMA_HOST=http://localhost:11434
   OLLAMA_MODEL=gemma4:31b
   ```
   No flight-search credentials are required — Google Flights is scraped directly.

4. **Run the agent:**
   ```bash
   python main.py
   ```

## Configuration

Edit `config.py` to change search parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ORIGIN_AIRPORTS` | STN, LTN, LHR, LGW, BHX | Departure airports |
| `DESTINATION` | SXR | Arrival airport |
| `DEPARTURE_DATE_FROM` | 2026-04-20 | Earliest departure date (YYYY-MM-DD) |
| `DEPARTURE_DATE_TO` | 2026-05-31 | Latest departure date (YYYY-MM-DD) |
| `DEPARTURE_STEP_DAYS` | 7 | Sample a departure every N days across the window |
| `RETURN_NIGHT_OPTIONS` | [14, 21, 28] | Trip lengths to try (in nights) |
| `ADULTS` | 2 | Number of passengers |
| `MAX_STOPOVERS` | 2 | Maximum outbound-leg layovers (return-leg stops not exposed by the scraper) |

> **Scrape volume:** total queries per run = `ceil(window ÷ step) × len(night_options) × len(airports)`. Defaults: 7 × 3 × 5 = **105 queries** at a 2s delay each ≈ 3.5 minutes per run. Keep the delay generous — Google will IP-block aggressive scrapers.

## Project Structure

```
agents/
├── main.py                    # Entry point
├── config.py                  # Search parameters
├── google_flights_client.py   # Google Flights scraper wrapper (fast-flights)
├── flight_agent.py            # Gemma 4 reasoning agent
├── utils.py                   # Formatting helpers
├── requirements.txt           # Python dependencies
├── .env                       # Optional Ollama overrides (not committed)
└── .gitignore
```

## How It Works

1. Generates a grid of (departure date, return date) pairs from the configured window
2. For each (airport × date-pair), calls `fast_flights.get_flights(...)` which scrapes Google Flights
3. Parses each result into a common schema (price, outbound duration, stops, airline)
4. Filters by `MAX_STOPOVERS` and sorts all results by price, then duration
5. Sends the top 30 candidates to a local Gemma model served by Ollama
6. Gemma analyzes the options and returns 5 recommendations with Google Flights search links

## Notes

- There are no direct flights from the UK to Srinagar. All routes connect via Delhi, Mumbai, or Gulf hubs (Dubai, Doha).
- May is peak tourist season for Kashmir -- book early for better prices.
- **Scraper caveats:** Google Flights has no official public API; `fast-flights` reverse-engineers their internal URL format. It can break without warning if Google changes their site, and hitting it too aggressively may get your IP rate-limited. The default 2s inter-call delay is conservative; don't reduce it. For personal use only — Google's ToS doesn't allow commercial scraping.
- **Data limitation:** Google Flights' round-trip response exposes only outbound-leg details (duration, stops, airline). Return-leg details aren't available, so the agent's prompt is scoped to outbound-only detail with a total round-trip price.
- Each recommendation includes a Google Flights search URL — click through to book on an airline or OTA.
- The Gemma model runs locally via Ollama. The `gemma4:31b` dense variant needs ~20GB RAM; use `gemma4:26b` (MoE, ~18GB), `gemma4:e4b` (~9.6GB), or `gemma4:e2b` (~7.2GB) on smaller machines.
