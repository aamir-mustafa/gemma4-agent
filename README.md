# Flight Booking Agent

A Python-based AI agent that finds the cheapest return flights from airports near St Neots, Cambridgeshire (UK) to Srinagar (SXR), India. It searches multiple airports, collects results via the Kiwi Tequila API, and uses Google's Gemma 4 model to analyze and recommend the best-value options.

## Features

- Searches 5 UK airports nearest to St Neots (STN, LTN, LHR, LGW, BHX)
- Finds return flights for 2 passengers across a flexible date range
- Supports configurable trip length (default: 2-4 weeks)
- Ranks flights by price and duration
- Uses Gemma 4 (31B) to reason over results and recommend the top 5 options
- Provides direct Kiwi.com booking links

## Prerequisites

- Python 3.10+
- A [Kiwi Tequila API key](https://tequila.kiwi.com) (free)
- A [Google AI API key](https://aistudio.google.com) (free tier)

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Add your API keys** to the `.env` file:
   ```
   KIWI_API_KEY=your_kiwi_api_key
   GEMINI_API_KEY=your_google_ai_api_key
   ```

3. **Run the agent:**
   ```bash
   python main.py
   ```

## Configuration

Edit `config.py` to change search parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ORIGIN_AIRPORTS` | STN, LTN, LHR, LGW, BHX | Departure airports |
| `DESTINATION` | SXR | Arrival airport |
| `DEPARTURE_DATE_FROM` | 20/04/2026 | Earliest departure date |
| `DEPARTURE_DATE_TO` | 31/05/2026 | Latest departure date |
| `NIGHTS_IN_DST_FROM` | 14 | Minimum trip length (days) |
| `NIGHTS_IN_DST_TO` | 28 | Maximum trip length (days) |
| `ADULTS` | 2 | Number of passengers |
| `CURRENCY` | GBP | Price currency |
| `MAX_STOPOVERS` | 2 | Maximum layovers per direction |

## Project Structure

```
agents/
├── main.py            # Entry point
├── config.py          # Search parameters
├── kiwi_client.py     # Kiwi Tequila API wrapper
├── flight_agent.py    # Gemma 4 reasoning agent
├── utils.py           # Formatting helpers
├── requirements.txt   # Python dependencies
├── .env               # API keys (not committed)
└── .gitignore
```

## How It Works

1. Queries the Kiwi Tequila API for return flights from each origin airport
2. Collects and sorts all results by price, then duration
3. Sends the top 30 candidates to Gemma 4 (hosted on Google AI, free tier)
4. Gemma 4 analyzes the options and returns 5 recommendations with booking links

## Notes

- There are no direct flights from the UK to Srinagar. All routes connect via Delhi, Mumbai, or Gulf hubs (Dubai, Doha).
- May is peak tourist season for Kashmir -- book early for better prices.
- The Gemma 4 model runs in the cloud via Google's API (no local GPU required).
