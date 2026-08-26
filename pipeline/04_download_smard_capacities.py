"""Download SMARD's own monthly installed-capacity series (national, DE).

Pure data acquisition -- no charts. An independent, national-level
cross-check against the MaStR-derived capacity panels this project
otherwise relies on for regional weighting: if SMARD's own national
capacity figure and MaStR's summed-up regional figure disagree materially,
that's worth knowing before trusting MaStR-weighted PECD potential as the
"true" capacity basis.

Same incremental-download approach as pipeline/03; region is "DE" (not
"DE-LU") for these SMARD series -- confirmed against
~/research/delu-headline-forecast/docs/data_sources.md.
"""

from datetime import timedelta

import pandas as pd

from pkg.paths import ProjPaths
from pkg.smard import DEFAULT_START_DATE, Variable, download_series

paths = ProjPaths()
paths.ensure_directories()

SERIES = {
    "solar": Variable.CAPACITY_SOLAR,
    "wind_onshore": Variable.CAPACITY_WIND_ONSHORE,
    "wind_offshore": Variable.CAPACITY_WIND_OFFSHORE,
}


def download_and_update(name: str, variable: Variable) -> None:
    output_file = paths.smard_capacity_file(name)
    existing = pd.read_parquet(output_file) if output_file.exists() else None

    if existing is not None and not existing.empty:
        start_time = existing.index.max().to_pydatetime() + timedelta(hours=1)
        print(f"capacity_{name}: incremental download from {start_time}")
    else:
        start_time = DEFAULT_START_DATE
        print(f"capacity_{name}: full download from {start_time}")

    new_data = download_series(variable, region="DE", start_time=start_time)
    print(f"  fetched {len(new_data):,} new rows")

    if existing is not None and not existing.empty:
        combined = pd.concat([existing, new_data])
        combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    else:
        combined = new_data

    combined.to_parquet(output_file)
    print(f"  {len(combined):,} total rows ({combined.index.min()} .. {combined.index.max()}) -> {output_file}")


for series_name, series_variable in SERIES.items():
    download_and_update(series_name, series_variable)
