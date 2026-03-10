def normalize_year(y: str) -> str:
    """
    Standardize year strings into '1st Year', '2nd Year', etc.
    """
    if not y:
        return ""
    y = y.strip().upper()
    if y == "I" or y.startswith("1"):
        return "1st Year"
    if y == "II" or y.startswith("2"):
        return "2nd Year"
    if y == "III" or y.startswith("3"):
        return "3rd Year"
    if y == "IV" or y.startswith("4"):
        return "4th Year"
    if y.endswith(" YEAR"):
        return y.capitalize()
    if "YEAR" not in y:
        return f"{y.capitalize()} Year"
    return y.capitalize()
