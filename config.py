"""Search parameters for the flight booking agent."""

# Airports near St Neots, Cambridgeshire (sorted by proximity)
ORIGIN_AIRPORTS = [
    "STN",  # London Stansted (~30 miles)
    "LTN",  # London Luton (~30 miles)
    "LHR",  # London Heathrow (~65 miles)
    "LGW",  # London Gatwick (~75 miles)
    "BHX",  # Birmingham (~80 miles)
]

DESTINATION = "SXR"  # Srinagar, India

# Travel dates (dd/mm/YYYY format for Kiwi API)
DEPARTURE_DATE_FROM = "20/04/2026"
DEPARTURE_DATE_TO = "31/05/2026"

# Return window: 14-28 days after departure
NIGHTS_IN_DST_FROM = 14
NIGHTS_IN_DST_TO = 28

# Passengers
ADULTS = 2

# Search preferences
CURRENCY = "GBP"
MAX_STOPOVERS = 2
RESULTS_PER_AIRPORT = 20  # Top results per origin airport
