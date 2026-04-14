"""Formatting helpers for flight results."""


def print_summary_table(flights, max_rows=10):
    """Print a quick summary table of the cheapest flights."""
    if not flights:
        print("No flights found.")
        return

    print(f"\n{'='*90}")
    print(f"{'#':>3}  {'From':>4}  {'Price':>8}  {'Depart':>10}  {'Return':>10}  "
          f"{'Duration':>9}  {'Stops':>5}")
    print(f"{'-'*90}")

    for i, f in enumerate(flights[:max_rows], 1):
        print(
            f"{i:>3}  {f['origin']:>4}  "
            f"{f['currency']} {f['price']:>5}  "
            f"{f['departure_date']:>10}  {f['return_date']:>10}  "
            f"{f['total_duration_h']:>7.1f}h  "
            f"{f['num_stops_outbound']}+{f['num_stops_return']}"
        )

    print(f"{'='*90}\n")
