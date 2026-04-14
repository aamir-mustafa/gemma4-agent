"""Gemma 4-powered flight analysis agent (hosted via Google AI API)."""

from google import genai


SYSTEM_PROMPT = """\
You are an expert travel advisor helping a family of 2 find the best-value \
return flights from the UK to Srinagar (SXR), India.

Analyze the flight options provided and recommend the **top 5 best-value** options.

For each recommendation, consider:
- Total price for 2 passengers
- Total travel time (outbound + return)
- Number of stops and layover quality
- Airline reputation and comfort
- Convenience of departure airport (Stansted/Luton are closest to the traveller)

Present each recommendation in this format:

### Option N: [Brief description]
- **Price**: total for 2 pax
- **Route (Outbound)**: Airport → Stops → SXR
- **Route (Return)**: SXR → Stops → Airport
- **Departure**: date | **Return**: date
- **Airlines**: list
- **Outbound duration**: Xh | **Return duration**: Xh
- **Stops**: outbound X, return X
- **Why this option**: 1-2 sentence explanation
- **Book here**: [booking link]

After the 5 options, add a brief **Summary** comparing them and a final recommendation.\
"""


def analyze_flights(api_key, flights, top_n=30):
    """Send top flight results to Gemini for analysis and recommendations."""
    if not flights:
        return "No flights found to analyze."

    # Take top N cheapest flights for analysis
    candidates = flights[:top_n]

    # Build flight data text
    flight_text = _format_flights_for_prompt(candidates)

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemma-4-31b-it",
        contents=f"Here are {len(candidates)} flight options. Analyze and recommend the top 5:\n\n{flight_text}",
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=4096,
            temperature=0.3,
        ),
    )
    return response.text


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
