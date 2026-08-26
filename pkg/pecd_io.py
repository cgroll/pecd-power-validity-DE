"""Parsing helper for PECD v4.2 CDS region-aggregated-timeseries downloads.

Adapted from ~/research/pecd-replication/pecdr/pecd_io.py, trimmed to just
`load_region_timeseries_zip` -- this project only consumes PECD's ready-made
region-level capacity factor series, never the gridded NetCDF products (no
grid masks, no per-cell weather), so the xarray-based helpers for those
aren't needed here.
"""

import io
import zipfile
from pathlib import Path

import pandas as pd


def load_region_timeseries_zip(zip_path: Path, region_prefix: str = "DE") -> pd.DataFrame:
    """Read a PECD region-aggregated-timeseries ZIP (one CSV per year inside) into a wide, hourly-indexed DataFrame.

    Each member CSV has a few metadata header rows before the real
    `Date,...` header, and one column per European region (e.g. `DE01`..
    `DE07` for PEON zones). `region_prefix` filters columns down to one
    country's zones instead of loading all of Europe's.
    """
    parts = []
    with zipfile.ZipFile(zip_path) as z:
        for csv_name in z.namelist():
            with z.open(csv_name) as f:
                text = io.TextIOWrapper(f, encoding="utf-8")
                header_idx = next(i for i, line in enumerate(text) if line.startswith("Date,"))
            with z.open(csv_name) as f:
                df = pd.read_csv(
                    f,
                    skiprows=header_idx,
                    parse_dates=["Date"],
                    index_col="Date",
                    usecols=lambda c: c == "Date" or c.startswith(region_prefix),
                )
            parts.append(df)
    combined = pd.concat(parts).sort_index()
    combined.index.name = "timestamp"
    if combined.index.duplicated().any():
        combined = combined[~combined.index.duplicated(keep="first")]
    return combined
