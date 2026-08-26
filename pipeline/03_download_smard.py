"""Download hourly SMARD generation, load, and price series for the DE-LU
market area.

Pure data acquisition -- no charts. Downloads five series at hourly
resolution for the DE-LU market area:

  - pv            SMARD "Photovoltaik" (Variable.SOLAR)
  - wind_onshore  SMARD "Wind Onshore"
  - wind_offshore SMARD "Wind Offshore"
  - load          SMARD "Gesamt (Netzlast)" (Variable.TOTAL_LOAD)
  - price_de_lu   SMARD day-ahead auction price, DE/LU (Variable.PRICE_DE_LU)
    -- needed to identify negative-price hours (voluntary curtailment).

Each series is saved to its own parquet file in data/downloads/smard/.
Incremental: if a file already exists, only fetches data newer than its
last timestamp.

Pattern adapted from pecd-replication/pipeline/13_download_smard.py.
"""

from datetime import timedelta

import pandas as pd

from pkg.paths import ProjPaths
from pkg.smard import DEFAULT_START_DATE, Variable, download_series

paths = ProjPaths()
paths.ensure_directories()

SERIES = {
    "pv": Variable.SOLAR,
    "wind_onshore": Variable.WIND_ONSHORE,
    "wind_offshore": Variable.WIND_OFFSHORE,
    "load": Variable.TOTAL_LOAD,
    "price_de_lu": Variable.PRICE_DE_LU,
}


def download_and_update(name: str, variable: Variable) -> None:
    output_file = paths.smard_raw_file(name)
    existing = pd.read_parquet(output_file) if output_file.exists() else None

    if existing is not None and not existing.empty:
        start_time = existing.index.max().to_pydatetime() + timedelta(hours=1)
        print(f"{name}: incremental download from {start_time}")
    else:
        start_time = DEFAULT_START_DATE
        print(f"{name}: full download from {start_time}")

    new_data = download_series(variable, start_time=start_time)
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
