def normalize_year(y: str) -> str:
    """
    Standardize year strings into '1st Year', '2nd Year', etc.
    Handles: numeric prefixes, roman numerals (with or without 'Year' appended).
    """
    if not y:
        return ""
    y_stripped = y.strip()
    y_upper = y_stripped.upper()

    # Remove trailing "YEAR" or " YEAR" to isolate the prefix
    for suffix in (" YEAR", "YEAR"):
        if y_upper.endswith(suffix):
            prefix = y_upper[: -len(suffix)].strip()
            break
    else:
        prefix = y_upper

    # Match roman numerals or numeric prefixes
    if prefix in {"I", "1", "1ST"}:
        return "1st Year"
    if prefix in {"II", "2", "2ND"}:
        return "2nd Year"
    if prefix in {"III", "3", "3RD"}:
        return "3rd Year"
    if prefix in {"IV", "4", "4TH"}:
        return "4th Year"
    if prefix.startswith("1"):
        return "1st Year"
    if prefix.startswith("2"):
        return "2nd Year"
    if prefix.startswith("3"):
        return "3rd Year"
    if prefix.startswith("4"):
        return "4th Year"

    # Fallback: re-assemble with capitalize
    if y_upper.endswith("YEAR") or y_upper.endswith(" YEAR"):
        return f"{prefix.capitalize()} Year"
    return f"{y_stripped.capitalize()} Year"

