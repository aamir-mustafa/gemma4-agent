"""Search parameters for the flight booking agent."""

# Airports near St Neots that actually have SXR connections.
# STN, LTN, BHX are low-cost-carrier airports with almost no SXR availability —
# every UK→SXR route connects via DEL/BOM/DXB/DOH, and only LHR/LGW run the
# necessary long-haul feeders.
ORIGIN_AIRPORTS = [
    "LHR",  # London Heathrow (~65 miles)
    "LGW",  # London Gatwick (~75 miles)
]

DESTINATION = "SXR"  # Srinagar, India

# Travel dates (YYYY-MM-DD)
DEPARTURE_DATE_FROM = "2026-04-25"
DEPARTURE_DATE_TO = "2026-05-20"

# Google Flights is queried once per (departure, return) date pair, so we sample:
#   - every DEPARTURE_STEP_DAYS across the departure window
#   - trying each of RETURN_NIGHT_OPTIONS as the trip length
# Total queries per run = ceil(window/step) * len(night_options) * len(airports)
DEPARTURE_STEP_DAYS = 1
RETURN_NIGHT_OPTIONS = list(range(14, 29))  # 14, 15, ..., 28 nights

# Passengers
ADULTS = 2

# Search preferences
# (Currency follows Google Flights' IP-based locale — GBP for UK users.)
MAX_STOPOVERS = 2  # applied to outbound leg only (return-leg stops not exposed)
