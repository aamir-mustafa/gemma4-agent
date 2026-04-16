"""Gemma-powered flight analysis agent (local via Ollama)."""

from ollama import Client


SYSTEM_PROMPT = """\
You are an expert travel advisor helping a family of 2 find the best-value \
return flights from the UK to Srinagar (SXR), India.

Analyze the flight options provided and recommend the **top 5 best-value** options.

For each recommendation, consider:
- Total price for 2 passengers (outbound + return combined)
- Total travel time (outbound + return)
- Number of stops on each leg
- Airline reputation and comfort
- Convenience of the London airport (LHR has more daily long-haul options than LGW)

Important context on the data:
- Each option's price is the sum of the cheapest one-way outbound + cheapest \
one-way return for the given date pair. Users will book these as two separate \
tickets since single-ticket round-trip fares rarely exist for UK↔SXR.
- All routes connect via a hub (most commonly Delhi — DEL), so "1 stop" means \
the connecting layover.

Present each recommendation in this format:

### Option N: [Brief description]
- **Price**: total (outbound + return) for 2 pax
- **Departure**: date from {origin airport} | **Return**: date
- **Outbound**: airline, Xh, X stops
- **Return**: airline, Xh, X stops
- **Why this option**: 1-2 sentence explanation
- **Search on Google Flights**: [booking link]

After the 5 options, add a brief **Summary** comparing them and a final recommendation.\
"""


def analyze_flights(flights, top_n=30, model="gemma4:31b", host="http://localhost:11434"):
    """Send top flight results to a local Gemma model via Ollama for analysis."""
    if not flights:
        return "No flights found to analyze."

    # Take top N cheapest flights for analysis
    candidates = flights[:top_n]

    # Build flight data text
    flight_text = _format_flights_for_prompt(candidates)

    client = Client(host=host)
    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Here are {len(candidates)} flight options. "
                    f"Analyze and recommend the top 5:\n\n{flight_text}"
                ),
            },
        ],
        options={"temperature": 0.3, "num_predict": 4096},
    )
    return response["message"]["content"]


def _format_flights_for_prompt(flights):
    """Format flight list into readable text for the LLM prompt."""
    lines = []
    for i, f in enumerate(flights, 1):
        out_route = f" → {' → '.join(f['outbound_stops'])} → " if f["outbound_stops"] else " → "
        ret_route = f" → {' → '.join(f['return_stops'])} → " if f["return_stops"] else " → "

        lines.append(
            f"Flight {i}:\n"
            f"  Price: {f['currency']} {f['price']} (for 2 pax)\n"
            f"  Outbound: {f['origin']}{out_route}{f['destination']} on {f['departure_date']} "
            f"({f['outbound_duration_h']}h, {f['num_stops_outbound']} stops, "
            f"airlines: {', '.join(f['outbound_airlines'])})\n"
            f"  Return: {f['destination']}{ret_route}{f['origin']} on {f['return_date']} "
            f"({f['return_duration_h']}h, {f['num_stops_return']} stops, "
            f"airlines: {', '.join(f['return_airlines'])})\n"
            f"  Total duration: {f['total_duration_h']}h\n"
            f"  Booking link: {f['booking_link']}\n"
        )
    return "\n".join(lines)
