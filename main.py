"""Flight Booking Agent — searches for the cheapest flights and uses Gemini to recommend the best options."""

import os
import sys

from dotenv import load_dotenv

import config
from kiwi_client import search_all_airports
from flight_agent import analyze_flights
from utils import print_summary_table


def main():
    load_dotenv()

    kiwi_key = os.getenv("KIWI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not kiwi_key or kiwi_key == "your_kiwi_api_key_here":
        print("Error: Set your KIWI_API_KEY in the .env file.")
        print("Sign up at https://tequila.kiwi.com to get a free API key.")
        sys.exit(1)

    if not gemini_key or gemini_key == "your_gemini_api_key_here":
        print("Error: Set your GEMINI_API_KEY in the .env file.")
        print("Get a free key at https://aistudio.google.com")
        sys.exit(1)

    # Step 1: Search flights from all origin airports
    print(f"\nSearching flights to {config.DESTINATION} for {config.ADULTS} adults...")
    print(f"Departure window: {config.DEPARTURE_DATE_FROM} – {config.DEPARTURE_DATE_TO}")
    print(f"Trip length: {config.NIGHTS_IN_DST_FROM}–{config.NIGHTS_IN_DST_TO} days\n")

    flights = search_all_airports(
        api_key=kiwi_key,
        airports=config.ORIGIN_AIRPORTS,
        fly_to=config.DESTINATION,
        date_from=config.DEPARTURE_DATE_FROM,
        date_to=config.DEPARTURE_DATE_TO,
        nights_from=config.NIGHTS_IN_DST_FROM,
        nights_to=config.NIGHTS_IN_DST_TO,
        adults=config.ADULTS,
        max_stopovers=config.MAX_STOPOVERS,
        currency=config.CURRENCY,
        limit=config.RESULTS_PER_AIRPORT,
    )

    if not flights:
        print("No flights found. Try adjusting dates or increasing max stopovers in config.py.")
        sys.exit(0)

    print(f"\nTotal flights found: {len(flights)}")

    # Step 2: Show a quick summary table
    print_summary_table(flights)

    # Step 3: Send to Gemini for analysis
    print("Sending results to Gemini for analysis...\n")
    recommendations = analyze_flights(gemini_key, flights)

    print("=" * 90)
    print("FLIGHT RECOMMENDATIONS")
    print("=" * 90)
    print(recommendations)


if __name__ == "__main__":
    main()
