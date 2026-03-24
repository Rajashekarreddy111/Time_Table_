def normalize_year(y: str) -> str:
    """
    Standardize year strings into '1st Year', '2nd Year', etc.
    Handles: numeric prefixes, roman numerals (with or without 'Year' appended).
    """
    if not y:
        return ""
    y_stripped = y.strip()
    y_upper = y_stripped.upper()

    # Remove leading/trailing "YEAR" or " YEAR" to isolate the prefix
    prefix = y_upper.replace("YEAR", "").strip()
    if not prefix: # If the original was just "YEAR", try to use the input
        prefix = y_upper

    # Match roman numerals, numeric prefixes, or verbal names
    if prefix in {"I", "1", "1ST", "FIRST"}:
        return "1st Year"
    if prefix in {"II", "2", "2ND", "SECOND"}:
        return "2nd Year"
    if prefix in {"III", "3", "3RD", "THIRD"}:
        return "3rd Year"
    if prefix in {"IV", "4", "4TH", "FOURTH"}:
        return "4th Year"
    
    # Handle "B.TECH II", "YEAR 2", etc.
    if "II" in prefix or "2ND" in prefix or "SECOND" in prefix or "2" in prefix:
        return "2nd Year"
    if "III" in prefix or "3RD" in prefix or "THIRD" in prefix or "3" in prefix:
        return "3rd Year"
    if "IV" in prefix or "4TH" in prefix or "FOURTH" in prefix or "4" in prefix:
        return "4th Year"
    if "I" in prefix or "1ST" in prefix or "FIRST" in prefix or "1" in prefix:
        return "1st Year"

    # Fallback: re-assemble with capitalize
    res = prefix.capitalize()
    if "Year" not in res:
        return f"{res} Year"
    return res

