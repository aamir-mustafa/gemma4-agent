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

# Travel dates (YYYY-MM-DD)
DEPARTURE_DATE_FROM = "2026-04-20"
DEPARTURE_DATE_TO = "2026-05-31"

# Google Flights is queried once per (departure, return) date pair, so we sample:
#   - every DEPARTURE_STEP_DAYS across the departure window
#   - trying each of RETURN_NIGHT_OPTIONS as the trip length
# Total queries per run = ceil(window/step) * len(night_options) * len(airports)
DEPARTURE_STEP_DAYS = 7
RETURN_NIGHT_OPTIONS = [14, 21, 28]

# Passengers
ADULTS = 2

# Search preferences
# (Currency follows Google Flights' IP-based locale — GBP for UK users.)
MAX_STOPOVERS = 2  # applied to outbound leg only (return-leg stops not exposed)
