import re


def normalize_year(y: str) -> str:
    """
    Standardize year strings into '1st Year', '2nd Year', etc.
    Supports labels like:
    - '2', '2nd', 'second', 'II', 'II-I', 'B.Tech II', 'Year 2'
    - similarly for 1/3/4
    """
    if not y:
        return ""

    source = str(y).strip()
    if not source:
        return ""

    # Normalize separators so token boundaries are easier to detect.
    tokenized = re.sub(r"[^A-Z0-9]+", " ", source.upper()).strip()
    if not tokenized:
        return ""

    # Check higher years first to avoid overlap (e.g., 'III' containing 'II').
    checks = [
        (4, [r"\bIV\b", r"\b4\b", r"\b4TH\b", r"\bFOURTH\b"]),
        (3, [r"\bIII\b", r"\b3\b", r"\b3RD\b", r"\bTHIRD\b"]),
        (2, [r"\bII\b", r"\b2\b", r"\b2ND\b", r"\bSECOND\b"]),
        (1, [r"\bI\b", r"\b1\b", r"\b1ST\b", r"\bFIRST\b"]),
    ]

    for year_number, patterns in checks:
        if any(re.search(pattern, tokenized) for pattern in patterns):
            suffix = {1: "st", 2: "nd", 3: "rd", 4: "th"}[year_number]
            return f"{year_number}{suffix} Year"

    # If we cannot classify reliably, keep behavior predictable.
    return source

