import logging

import pycountry_convert as pc

logger = logging.getLogger(__name__)


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

        # Handle some common mismatches or simplified inputs
        special_cases = {
            "USA": "US",
            "UK": "GB",
            "United Kingdom": "GB",
            "UAE": "AE",
        }

        country_code = special_cases.get(country_name, None)

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
