"""Re-analyze already-scraped flight data with different Gemma prompts.

Usage:
    python ask_gemma.py                  # interactive menu
    python ask_gemma.py budget           # run a specific analysis
    python ask_gemma.py all              # run all analyses
    python ask_gemma.py custom "Your question here"
"""

import json
import os
import sys
from datetime import timedelta

from dotenv import load_dotenv
from ollama import Client

from google_flights_client import _pair_as_flight, _generate_date_pairs
from flight_agent import _format_flights_for_prompt
import config


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
PROMPTS = {
    "budget": {
        "name": "Budget Analysis",
        "system": """\
You are a budget travel expert helping a family of 2 fly from the UK to \
Srinagar (SXR), India.

From the flight data provided, find the absolute cheapest options. \
For each option explain exactly how much is saved compared to the average \
price across all options. Highlight any date patterns that lead to lower prices.

Present the top 5 cheapest options with:
- Price breakdown (outbound + return)
- Dates and airports
- Airlines and stops
- How much cheaper it is vs. the dataset average
- A Google Flights search link

End with a summary of which days of the week or date ranges are cheapest.\
""",
        "instruction": "Find the 5 absolute cheapest options and explain the savings:",
    },

    "comfort": {
        "name": "Comfort & Convenience",
        "system": """\
You are a premium travel consultant helping a family of 2 fly from the UK to \
Srinagar (SXR), India.

Recommend flights that minimize total travel time and number of stops, \
even if they cost more. Prioritize:
- Fewest stops (1 stop preferred over 2)
- Shortest total duration
- LHR over LGW (better facilities, more connections)
- Reputable full-service airlines

Present the top 5 most comfortable options with:
- Price for 2 pax
- Total travel time and stops per leg
- Airlines
- Why this is a comfortable choice
- A Google Flights search link

End with a comparison table of comfort vs. cost trade-offs.\
""",
        "instruction": "Recommend the 5 most comfortable flight options:",
    },

    "date_trends": {
        "name": "Date & Price Trends",
        "system": """\
You are a travel data analyst. Analyze the flight pricing data for UK to \
Srinagar (SXR) routes.

Provide a detailed analysis of:
1. Which departure days of the week are cheapest on average
2. Which return days of the week are cheapest on average
3. The optimal trip duration (in nights) for the best prices
4. Price trends across the departure window (early vs mid vs late)
5. Whether LHR or LGW is consistently cheaper
6. Any sweet-spot date combinations

Use specific numbers from the data. Present findings with averages and \
ranges where possible. End with a clear actionable recommendation for \
when to book.\
""",
        "instruction": "Analyze all price trends across dates, airports, and trip durations:",
        "top_n": 100,
    },

    "airlines": {
        "name": "Airline Comparison",
        "system": """\
You are an airline industry analyst helping a family of 2 choose flights \
from the UK to Srinagar (SXR), India.

Compare all airlines appearing in the data. For each airline or airline \
combination, analyze:
- Average and range of prices
- Average and range of travel times
- Number of stops typically required
- Routes (which hubs they connect through)
- General reputation for long-haul and India domestic legs

Rank the airlines from best to worst value. Highlight any cases where \
paying more for a specific airline is worth it for comfort or reliability.

End with a clear recommendation of which airline to prioritize.\
""",
        "instruction": "Compare all airlines in these flight options:",
        "top_n": 80,
    },

    "weekend": {
        "name": "Weekend Departures",
        "system": """\
You are a travel advisor helping a family of 2 who can only fly on \
Fridays, Saturdays, or Sundays, from the UK to Srinagar (SXR), India.

Filter the data to only consider options where:
- The outbound departure falls on a Friday, Saturday, or Sunday
- The return departure falls on a Friday, Saturday, or Sunday

From those filtered results, recommend the top 5 best-value options. \
If very few weekend options exist, note that and suggest the closest \
alternatives.

Present each option with price, dates, airlines, stops, duration, and \
a Google Flights search link.\
""",
        "instruction": "Find the best weekend-departure flight options:",
        "top_n": 80,
    },

    "stopover": {
        "name": "Stopover & Layover Analysis",
        "system": """\
You are a travel logistics expert helping a family of 2 fly from the UK \
to Srinagar (SXR), India.

All flights connect through hubs (Delhi, Dubai, Doha, Bahrain, etc.). \
Analyze the data to advise on:

1. Which connecting hubs appear most often and their impact on price/time
2. Whether 1-stop or 2-stop routes are better value
3. The trade-off between fewer stops (faster) and more stops (sometimes cheaper)
4. Any routes that are significantly faster despite having 2 stops

Present the top 5 options that offer the best balance of connections \
and value. For each, explain the routing.

End with a recommendation on which hub/routing to target.\
""",
        "instruction": "Analyze stopover patterns and recommend the best-connected routes:",
        "top_n": 60,
    },
}


# ---------------------------------------------------------------------------
# Load flights from cache (no re-scraping)
# ---------------------------------------------------------------------------
def load_flights_from_cache(cache_path=".flight_cache.jsonl"):
    """Rebuild paired flights from the JSONL cache file."""
    if not os.path.exists(cache_path):
        print(f"Cache file not found: {cache_path}")
        print("Run main.py first to scrape flight data.")
        sys.exit(1)

    cache = {}
    with open(cache_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                key = (e["origin"], e["dest"], e["date"], e["direction"])
                cache[key] = e.get("options", [])
            except (json.JSONDecodeError, KeyError):
                continue

    # Re-pair using the same config
    date_pairs = _generate_date_pairs(
        config.DEPARTURE_DATE_FROM,
        config.DEPARTURE_DATE_TO,
        config.DEPARTURE_STEP_DAYS,
        config.RETURN_NIGHT_OPTIONS,
    )

    all_flights = []
    for airport in config.ORIGIN_AIRPORTS:
        for depart, ret in date_pairs:
            outbounds = cache.get((airport, config.DESTINATION, depart, "outbound"), [])
            returns = cache.get((config.DESTINATION, airport, ret, "return"), [])
            if not outbounds or not returns:
                continue
            ob = min(outbounds, key=lambda o: o["price"])
            rb = min(returns, key=lambda o: o["price"])
            all_flights.append(
                _pair_as_flight(airport, config.DESTINATION, depart, ret, ob, rb)
            )

    all_flights.sort(key=lambda f: (f["price"], f["total_duration_h"]))
    return all_flights


# ---------------------------------------------------------------------------
# Query Gemma
# ---------------------------------------------------------------------------
def query_gemma(flights, prompt_key, model, host):
    """Send flights to Gemma with a specific prompt."""
    prompt = PROMPTS[prompt_key]
    top_n = prompt.get("top_n", 30)
    candidates = flights[:top_n]
    flight_text = _format_flights_for_prompt(candidates)

    print(f"\nSending {len(candidates)} flights to {model} for: {prompt['name']}...\n")

    client = Client(host=host)
    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": f"{prompt['instruction']}\n\n{flight_text}"},
        ],
        options={"temperature": 0.3, "num_predict": 4096},
    )
    return response["message"]["content"]


def query_gemma_custom(flights, question, model, host, top_n=50):
    """Send flights to Gemma with a free-form question."""
    candidates = flights[:top_n]
    flight_text = _format_flights_for_prompt(candidates)

    print(f"\nSending {len(candidates)} flights to {model} for custom question...\n")

    client = Client(host=host)
    response = client.chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert travel data analyst. You have been given "
                    "flight data for UK to Srinagar (SXR) routes for a family of 2. "
                    "Answer the user's question based on the data provided. "
                    "Be specific, use numbers from the data, and provide actionable advice."
                ),
            },
            {
                "role": "user",
                "content": f"{question}\n\nHere is the flight data:\n\n{flight_text}",
            },
        ],
        options={"temperature": 0.3, "num_predict": 4096},
    )
    return response["message"]["content"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def print_menu():
    print("\n" + "=" * 60)
    print("FLIGHT DATA ANALYZER — Ask Gemma Different Questions")
    print("=" * 60)
    for i, (key, prompt) in enumerate(PROMPTS.items(), 1):
        print(f"  {i}. {prompt['name']:30s} [{key}]")
    print(f"  {len(PROMPTS) + 1}. Custom question")
    print(f"  {len(PROMPTS) + 2}. Run all analyses")
    print(f"  0. Exit")
    print("=" * 60)


def main():
    load_dotenv()
    model = os.getenv("OLLAMA_MODEL", "gemma4:31b")
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    # Handle CLI arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        flights = load_flights_from_cache()
        print(f"Loaded {len(flights)} flights from cache.\n")

        if arg == "custom" and len(sys.argv) > 2:
            question = " ".join(sys.argv[2:])
            result = query_gemma_custom(flights, question, model, host)
            print(result)
            return

        if arg == "all":
            for key in PROMPTS:
                result = query_gemma(flights, key, model, host)
                print("=" * 90)
                print(f"  {PROMPTS[key]['name'].upper()}")
                print("=" * 90)
                print(result)
                print()
            return

        if arg in PROMPTS:
            result = query_gemma(flights, arg, model, host)
            print(result)
            return

        print(f"Unknown analysis: {arg}")
        print(f"Available: {', '.join(PROMPTS.keys())}, all, custom")
        sys.exit(1)

    # Interactive menu
    flights = load_flights_from_cache()
    print(f"Loaded {len(flights)} flights from cache.")

    prompt_keys = list(PROMPTS.keys())

    while True:
        print_menu()
        choice = input("\nChoose an analysis (number or name): ").strip()

        if choice == "0":
            break

        if choice.isdigit():
            idx = int(choice)
            if idx == 0:
                break
            elif 1 <= idx <= len(prompt_keys):
                key = prompt_keys[idx - 1]
                result = query_gemma(flights, key, model, host)
                print("\n" + "=" * 90)
                print(f"  {PROMPTS[key]['name'].upper()}")
                print("=" * 90)
                print(result)
            elif idx == len(PROMPTS) + 1:
                question = input("Enter your question: ").strip()
                if question:
                    result = query_gemma_custom(flights, question, model, host)
                    print("\n" + "=" * 90)
                    print("  CUSTOM ANALYSIS")
                    print("=" * 90)
                    print(result)
            elif idx == len(PROMPTS) + 2:
                for key in prompt_keys:
                    result = query_gemma(flights, key, model, host)
                    print("\n" + "=" * 90)
                    print(f"  {PROMPTS[key]['name'].upper()}")
                    print("=" * 90)
                    print(result)
                    print()
            else:
                print("Invalid choice.")
        elif choice.lower() in PROMPTS:
            key = choice.lower()
            result = query_gemma(flights, key, model, host)
            print("\n" + "=" * 90)
            print(f"  {PROMPTS[key]['name'].upper()}")
            print("=" * 90)
            print(result)
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
