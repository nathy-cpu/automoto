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


def get_continent_from_country(country_name):
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


def parse_location_components(location_text):
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
