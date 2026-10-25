"""Small, explicit data-preparation helpers for UrbanHeat Analytics."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import numpy as np
import pandas as pd
from pandas.errors import EmptyDataError, ParserError


def parse_csv_bytes(payload: bytes) -> pd.DataFrame:
    """Read a CSV without changing its source values or dropping its rows."""
    if not payload or not payload.strip():
        raise ValueError("The uploaded file is empty.")

    try:
        frame = pd.read_csv(BytesIO(payload))
    except EmptyDataError as exc:
        raise ValueError("The uploaded file does not contain a CSV header or data.") from exc
    except (ParserError, UnicodeDecodeError) as exc:
        raise ValueError(
            "This file could not be read as a valid UTF-8 CSV. Check its delimiter, quoting, and encoding."
        ) from exc

    if len(frame.columns) == 0:
        raise ValueError("The CSV does not contain any columns.")
    return frame


def _numeric_values(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    numeric = pd.Series(numeric, index=values.index, dtype="float64")
    finite = np.isfinite(numeric.to_numpy(dtype="float64", na_value=np.nan))
    return numeric.mask(~finite)


def _derived_name(frame: pd.DataFrame, base: str) -> str:
    name = base
    suffix = 2
    while name in frame.columns:
        name = f"{base}_{suffix}"
        suffix += 1
    return name


def prepare_analysis_data(
    raw: pd.DataFrame, mappings: dict[str, Any]
) -> tuple[pd.DataFrame, dict[str, str], dict[str, int]]:
    """Build a separate analytical view and quality counts; keep every raw row."""
    frame = raw.copy(deep=True)
    derived: dict[str, str] = {}
    quality: dict[str, int] = {}

    def selected_column(field: str) -> str | None:
        column = mappings.get(field)
        if column is None or column == "":
            return None
        if column not in raw.columns:
            raise ValueError(f"The selected {field} column is not present in the uploaded CSV.")
        return str(column)

    temperature_column = selected_column("temperature")
    if temperature_column is not None:
        temperature = _numeric_values(raw[temperature_column])
        name = _derived_name(frame, "analysis_temperature")
        frame[name] = temperature
        derived["temperature"] = name
        quality["temperature_missing"] = int(raw[temperature_column].isna().sum())
        quality["temperature_invalid"] = int(
            (raw[temperature_column].notna() & temperature.isna()).sum()
        )
        quality["temperature_usable"] = int(temperature.notna().sum())

    date_column = selected_column("date")
    if date_column is not None:
        dates = pd.to_datetime(
            raw[date_column],
            errors="coerce",
            utc=True,
            format="mixed",
            dayfirst=bool(mappings.get("date_dayfirst", False)),
        )
        dates = dates.dt.tz_convert(None)
        name = _derived_name(frame, "analysis_date")
        frame[name] = dates
        derived["date"] = name
        quality["date_missing"] = int(raw[date_column].isna().sum())
        quality["date_invalid"] = int((raw[date_column].notna() & dates.isna()).sum())
        quality["date_usable"] = int(dates.notna().sum())

    latitude_column = selected_column("latitude")
    longitude_column = selected_column("longitude")
    if (latitude_column is None) != (longitude_column is None):
        quality["coordinates_configured"] = 0
        quality["coordinates_invalid"] = 0
    elif latitude_column is not None and longitude_column is not None:
        latitude = _numeric_values(raw[latitude_column])
        longitude = _numeric_values(raw[longitude_column])
        valid_coordinates = (
            latitude.between(-90, 90)
            & longitude.between(-180, 180)
        ).fillna(False)

        latitude_name = _derived_name(frame, "analysis_latitude")
        longitude_name = _derived_name(frame, "analysis_longitude")
        frame[latitude_name] = latitude.where(valid_coordinates)
        frame[longitude_name] = longitude.where(valid_coordinates)
        derived["latitude"] = latitude_name
        derived["longitude"] = longitude_name
        derived["coordinates_valid"] = _derived_name(frame, "analysis_coordinates_valid")
        frame[derived["coordinates_valid"]] = valid_coordinates
        quality["coordinates_configured"] = 1
        quality["coordinates_invalid"] = int((~valid_coordinates).sum())
        quality["coordinates_usable"] = int(valid_coordinates.sum())
    else:
        quality["coordinates_configured"] = 0
        quality["coordinates_invalid"] = 0

    vegetation_column = selected_column("vegetation")
    if vegetation_column is not None:
        vegetation = _numeric_values(raw[vegetation_column])
        if mappings.get("vegetation_type") == "NDVI":
            vegetation = vegetation.where(vegetation.between(-1, 1))
        name = _derived_name(frame, "analysis_vegetation")
        frame[name] = vegetation
        derived["vegetation"] = name
        quality["vegetation_missing"] = int(raw[vegetation_column].isna().sum())
        quality["vegetation_invalid"] = int(
            (raw[vegetation_column].notna() & vegetation.isna()).sum()
        )
        quality["vegetation_usable"] = int(vegetation.notna().sum())

    return frame, derived, quality


def summarize_numeric(values: pd.Series) -> dict[str, float | int | None]:
    """Calculate descriptive statistics from finite numeric observations only."""
    numeric = _numeric_values(values)
    clean = numeric.dropna()
    if clean.empty:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "std": None,
            "min": None,
            "q25": None,
            "q75": None,
            "max": None,
        }
    return {
        "count": int(clean.size),
        "mean": float(clean.mean()),
        "median": float(clean.median()),
        "std": float(clean.std(ddof=1)) if clean.size > 1 else None,
        "min": float(clean.min()),
        "q25": float(clean.quantile(0.25)),
        "q75": float(clean.quantile(0.75)),
        "max": float(clean.max()),
    }


def association_summary(
    x: pd.Series, y: pd.Series, method: str = "pearson"
) -> dict[str, float | int | None]:
    """Return a pairwise correlation only when the sample supports calculation."""
    paired = pd.DataFrame(
        {"x": _numeric_values(x), "y": _numeric_values(y)}
    ).dropna()
    n = int(len(paired))
    correlation: float | None = None
    if n >= 3 and paired["x"].nunique() > 1 and paired["y"].nunique() > 1:
        value = paired["x"].corr(paired["y"], method=method)
        if pd.notna(value) and np.isfinite(value):
            correlation = float(value)
    return {
        "n": n,
        "missing_pairs": int(len(x) - n),
        "correlation": correlation,
    }
