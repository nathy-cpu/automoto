import logging
import re

import pycountry_convert as pc

logger = logging.getLogger(__name__)

US_STATE_CODES = {
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
}
COUNTRY_SPECIAL_CASES = {
    "USA": "US",
    "UK": "GB",
    "United Kingdom": "GB",
    "UAE": "AE",
    "United States": "US",
}
LOCATION_SPLIT_RE = re.compile(r"\s*,\s*")


WEEKDAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]


def parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def describe_cron(cron_expression: str) -> str:
    parts = cron_expression.strip().split()
    if len(parts) != 5:
        return cron_expression

    minute, hour, dom, month, dow = parts

    if minute == "0" and hour == "0" and dom == "*" and month == "*" and dow == "*":
        return "Once per day at midnight"
    if minute == "0" and hour.startswith("*/"):
        interval = hour[2:]
        return f"Every {interval} hours"
    if minute == "0" and "," in hour and dom == "*" and month == "*" and (dow == "*" or dow == "?"):
        times = ", ".join(_format_hour(h) for h in hour.split(","))
        return f"Daily at {times}"
    if minute == "0" and "," in hour and dom == "*" and month == "*" and dow != "*" and dow != "?":
        day_names = _expand_dow(dow)
        times = ", ".join(_format_hour(h) for h in hour.split(","))
        return f"Every {day_names} at {times}"
    if minute == "0" and hour != "*" and hour != "?" and dom == "*" and month == "*" and (dow == "*" or dow == "?"):
        return f"Daily at {_format_hour(hour)}"
    if minute == "0" and hour != "*" and hour != "?" and dom == "*" and month == "*" and dow != "*" and dow != "?":
        day_names = _expand_dow(dow)
        return f"Every {day_names} at {_format_hour(hour)}"
    if minute.startswith("*/"):
        interval = minute[2:]
        return f"Every {interval} minutes"
    if dom != "*" and dom != "?" and dom.isdigit():
        day = _ordinal(int(dom))
        return f"{_month_name(month)} {day} at {_format_hour(hour)}" if month != "*" else f"On the {day} of each month at {_format_hour(hour)}"

    return cron_expression


def _format_hour(hour: str) -> str:
    h = int(hour)
    period = "am" if h < 12 else "pm"
    display = h if h <= 12 else h - 12
    return f"{display}:00{period}"


def _expand_dow(dow: str) -> str:
    if "*" in dow or "?" in dow:
        return "day"
    if "," in dow:
        return ", ".join(WEEKDAYS[int(d)] for d in dow.split(",") if d.isdigit())
    if "-" in dow:
        parts_list = dow.split("-")
        start, end = int(parts_list[0]), int(parts_list[1])
        return ", ".join(WEEKDAYS[i] for i in range(start, end + 1) if i < 7)
    if dow.isdigit():
        return WEEKDAYS[int(dow)]
    return dow


def _month_name(month: str) -> str:
    months = ["", "january", "february", "march", "april", "may", "june",
              "july", "august", "september", "october", "november", "december"]
    if month.isdigit():
        m = int(month)
        return months[m] if 1 <= m <= 12 else month
    return month


def _ordinal(n: int) -> str:
    if 11 <= n <= 13:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def resolve_scrape_location(countries: str = "", continents: str = "", fallback_location: str = "us") -> str:
    country_filters = parse_csv_list(countries)
    if country_filters:
        return country_filters[0]

    continent_filters = parse_csv_list(continents)
    if continent_filters:
        return continent_filters[0]

    return (fallback_location or "us").strip() or "us"


def get_continent_from_country(country_name: str) -> str:
    """
    Returns the continent name for a given country name.
    """
    if not country_name:
        return "Unknown"

    try:
        # Try to get the country code from the country name
        # Many sources might provide full names, some might provide codes.
        # This is a bit naive but covers common cases.
        country_name = country_name.strip()

        if country_name.upper() in US_STATE_CODES:
            return "North America"

        # Handle some common mismatches or simplified inputs
        country_code = COUNTRY_SPECIAL_CASES.get(country_name, None)

        if not country_code:
            # Try to lookup ISO code by name
            # pycountry can be used here for more robustness if needed
            # but pycountry-convert expect alpha2 codes.
            try:
                import pycountry

                country = pycountry.countries.search_fuzzy(country_name)[0]
                country_code = country.alpha_2
            except Exception:
                # Fallback: if it's already a 2-letter code, use it
                if len(country_name) == 2:
                    country_code = country_name.upper()
                else:
                    return "Unknown"

        continent_code = pc.country_alpha2_to_continent_code(country_code)
        continent_name = pc.convert_continent_code_to_continent_name(continent_code)
        return continent_name
    except Exception:
        logger.exception("continent_lookup_failed country=%s", country_name)
        return "Unknown"


def parse_location_components(location_text: str) -> dict[str, str]:
    """Normalize location text into city/country/continent."""
    loc_text = (location_text or "").strip()
    if not loc_text:
        return {"city": "", "country": "", "continent": "Unknown"}

    city = ""
    country = ""
    continent = ""
    loc_upper = loc_text.upper()

    if "EUROPE" in loc_upper:
        return {"city": "", "country": "", "continent": "Europe"}
    if "EMEA" in loc_upper:
        return {"city": "", "country": "", "continent": "Europe"}
    if "USA" in loc_upper or "UNITED STATES" in loc_upper:
        return {"city": "", "country": "United States", "continent": "North America"}

    parts = [part.strip() for part in LOCATION_SPLIT_RE.split(loc_text) if part.strip()]
    if len(parts) >= 2:
        city = parts[0]
        last_part = parts[-1].upper()
        if last_part in US_STATE_CODES or last_part in {"USA", "US", "UNITED STATES"}:
            return {
                "city": city,
                "country": "United States",
                "continent": "North America",
            }
        country = parts[-1]
    else:
        only_part = parts[0]
        if only_part.upper() in US_STATE_CODES:
            return {
                "city": "",
                "country": "United States",
                "continent": "North America",
            }
        country = only_part

    continent = get_continent_from_country(country) if country else "Unknown"
    return {"city": city, "country": country, "continent": continent}
