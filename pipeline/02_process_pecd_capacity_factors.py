"""Process downloaded PECD v4.2 capacity factor ZIPs into wide-format hourly
parquets, Germany-only.

Pure data processing -- no charts. Reads the ZIPs downloaded by
pipeline/01_download_pecd_capacity_factors.py (each holding one CSV per
requested year, 2015-2025, covering all of Europe) and combines them into
three Germany-only, wide-format parquet files:

  - pecd_solar_capacity_factors_file: MultiIndex columns (technology,
    region) -- 4 solar sub-types x ~38 NUTS2 regions.
  - pecd_wind_onshore_capacity_factors_file: columns = 7 PEON zones
    (DE01..DE07).
  - pecd_wind_offshore_capacity_factors_file: columns = PEOF zones
    (DE0xx_OFF) -- codes already match the external MaStR PEOF panel.

Pattern adapted from
pecd-replication/pipeline/17_process_pecd_capacity_factors.py.
"""

import pandas as pd

from pkg.paths import ProjPaths
from pkg.pecd_io import load_region_timeseries_zip

paths = ProjPaths()
paths.ensure_directories()


# --- Solar: 4 technology sub-types, combined into one MultiIndex frame ---
SOLAR_TECHNOLOGIES = ["60", "61", "62", "63"]
solar_parts = {}
for tech in SOLAR_TECHNOLOGIES:
    print(f"Loading solar tech {tech} ...")
    df = load_region_timeseries_zip(paths.pecd_capacity_factor_zip("solar", tech))
    print(f"  {len(df):,} rows x {len(df.columns)} DE NUTS2 regions - {df.index.min()} .. {df.index.max()}")
    solar_parts[tech] = df

solar = pd.concat(solar_parts, axis=1, names=["technology", "region"])

# PECD's solar CF timestamps run 1 hour ahead of true UTC -- confirmed
# empirically in pecd-replication (shifting this series back by 1 hour cuts
# its MAE against SMARD's actual PV generation roughly in half). Not
# present in PECD's wind product. Most likely inherited from ERA5's
# solar-radiation variables being *accumulated over the preceding hour*
# while wind speed is instantaneous -- a labeling convention PECD's own
# product apparently doesn't correct for.
solar.index = solar.index - pd.Timedelta(hours=1)

solar.to_parquet(paths.pecd_solar_capacity_factors_file)
print(f"Saved solar: {solar.shape} -> {paths.pecd_solar_capacity_factors_file}\n")

# --- Wind onshore (PEON) ---
print("Loading wind onshore (PEON) ...")
wind_onshore = load_region_timeseries_zip(paths.pecd_capacity_factor_zip("wind_onshore", "30"))
print(f"  {len(wind_onshore):,} rows x {len(wind_onshore.columns)} DE PEON zones: {sorted(wind_onshore.columns)}")
wind_onshore.to_parquet(paths.pecd_wind_onshore_capacity_factors_file)
print(f"Saved wind onshore -> {paths.pecd_wind_onshore_capacity_factors_file}\n")

# --- Wind offshore (PEOF) ---
print("Loading wind offshore (PEOF) ...")
wind_offshore = load_region_timeseries_zip(paths.pecd_capacity_factor_zip("wind_offshore", "20"))
print(f"  {len(wind_offshore):,} rows x {len(wind_offshore.columns)} DE PEOF zones: {sorted(wind_offshore.columns)}")
wind_offshore.to_parquet(paths.pecd_wind_offshore_capacity_factors_file)
print(f"Saved wind offshore -> {paths.pecd_wind_offshore_capacity_factors_file}")
