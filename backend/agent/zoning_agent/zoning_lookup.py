"""Zoning parameters lookup table.
Maps San Diego zoning codes to max height, FAR, lot size, etc.

Source: San Diego Municipal Code Title 13 (Land Use Code)
https://docs.sandiego.gov/municode/MuniCodeChapter13/Ch13Art02Division04.pdf

NOTE: This is a starter set — only 6 codes are defined. Add more from zoning documents.
"""
import logging as _logging


def get_zoning_params(code: str) -> dict | None:
    """Look up zoning parameters by code, logging a warning on miss."""
    params = ZONING_PARAMS.get(code)
    if params is None:
        _logging.getLogger(__name__).warning(
            "Zoning code %r not found in lookup table; returning None", code
        )
    return params

ZONING_PARAMS = {
    # Residential Single Family
    "RS-1-7": {
        "MAX_HEIGHT": 30,  # feet
        "MAX_FAR": 0.5,
        "MIN_LOT_SIZE": 7000,  # sq ft
        "ALLOWED_USES": ["single-family", "accessory dwelling unit"],
    },
    "RS-1-14": {
        "MAX_HEIGHT": 30,
        "MAX_FAR": 0.45,
        "MIN_LOT_SIZE": 14000,
        "ALLOWED_USES": ["single-family"],
    },

    # Residential Multi-Family
    "RM-1-1": {
        "MAX_HEIGHT": 30,
        "MAX_FAR": 0.75,
        "MIN_LOT_SIZE": 5000,
        "ALLOWED_USES": ["single-family", "duplex"],
    },
    "RM-3-7": {
        "MAX_HEIGHT": 45,
        "MAX_FAR": 1.5,
        "MIN_LOT_SIZE": 5000,
        "ALLOWED_USES": ["multi-family", "townhomes"],
    },

    # Commercial
    "CN-1-2": {
        "MAX_HEIGHT": 30,
        "MAX_FAR": 1.0,
        "MIN_LOT_SIZE": 5000,
        "ALLOWED_USES": ["neighborhood commercial", "mixed-use"],
    },
    "CC-3-6": {
        "MAX_HEIGHT": 65,
        "MAX_FAR": 3.0,
        "MIN_LOT_SIZE": None,
        "ALLOWED_USES": ["commercial", "office", "residential"],
    },

    # Add more codes here from your zoning documents
    # ...
}
