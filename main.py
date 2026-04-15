"""Flight Booking Agent — searches for the cheapest flights and uses a local Gemma model (via Ollama) to recommend the best options."""

import os
import sys

from dotenv import load_dotenv

import config
from google_flights_client import search_all_airports
from flight_agent import analyze_flights
from utils import print_summary_table


def main():
    load_dotenv()

    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "gemma4:31b")

    # Step 1: Search flights from all origin airports
    print(f"\nSearching flights to {config.DESTINATION} for {config.ADULTS} adults...")
    print(f"Departure window: {config.DEPARTURE_DATE_FROM} – {config.DEPARTURE_DATE_TO}")
    print(f"Trip lengths: {config.RETURN_NIGHT_OPTIONS} nights\n")

    flights = search_all_airports(
        airports=config.ORIGIN_AIRPORTS,
        fly_to=config.DESTINATION,
        date_from=config.DEPARTURE_DATE_FROM,
        date_to=config.DEPARTURE_DATE_TO,
        step_days=config.DEPARTURE_STEP_DAYS,
        night_options=config.RETURN_NIGHT_OPTIONS,
        adults=config.ADULTS,
        max_stopovers=config.MAX_STOPOVERS,
    )

    if not flights:
        print("No flights found. Try adjusting dates or increasing max stopovers in config.py.")
        sys.exit(0)

    print(f"\nTotal flights found: {len(flights)}")

    # Step 2: Show a quick summary table
    print_summary_table(flights)

    # Step 3: Send to local Gemma model (via Ollama) for analysis
    print(f"Sending results to local Gemma model ({ollama_model}) via Ollama for analysis...\n")
    recommendations = analyze_flights(flights, model=ollama_model, host=ollama_host)

    print("=" * 90)
    print("FLIGHT RECOMMENDATIONS")
    print("=" * 90)
    print(recommendations)


if __name__ == "__main__":
    main()
