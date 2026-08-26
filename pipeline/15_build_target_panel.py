"""Build the hourly SMARD target panel: what actually gets compared against
PECD potential.

Pure data processing -- no charts. Combines the five separately-downloaded
SMARD series into one hourly panel, aligned to a common index and renamed
to match `pecd_potential_panel_file`'s technology columns.

Outer join, not inner: wind offshore/load/price start 2018-09-30 (the
DE-LU market area's actual creation date), while pv/wind_onshore's raw
files carry an index back to 2016-12-30. Truncating here on index range
alone would miss a real data-quality issue, not just a coverage gap --
see below.

PV/wind_onshore before 2018-10-01 is invalid, not just noisier, and is
nulled out rather than kept: checked directly, SMARD's `DE-LU`-region
query returns implausibly tiny placeholder values before that date (June
2017's *daily peak* is 87 MW; June 2019's is 30,141 MW -- a ~350x jump
inconsistent with any real two-year capacity growth), with a clean,
sub-day-precise cutover exactly at 2018-10-01 00:00 (the last bogus value
is 2018-09-30 23:00 at 68 MW; the first real one is 2018-10-01 00:00 at a
four-digit MW level). This matches `DE-LU`'s actual creation date as a
distinct SMARD market area/bidding zone -- the region code technically
existed further back in SMARD's own index, but had nothing real behind it
yet.
"""

import pandas as pd

from pkg.paths import ProjPaths

paths = ProjPaths()
paths.ensure_directories()

RENAME = {
    "pv": ("solar", "pv_mw"),
    "wind_onshore": ("wind_onshore", "wind_onshore_mw"),
    "wind_offshore": ("wind_offshore", "wind_offshore_mw"),
    "load": ("total_load", "load_mw"),
    "price_de_lu": ("price_de_lu", "price_de_lu_eur_mwh"),
}

DE_LU_CREATION_DATE = pd.Timestamp("2018-10-01")
INVALID_BEFORE_CREATION = {"pv_mw", "wind_onshore_mw"}  # wind_offshore/load/price's raw files already start at/after this date

columns = {}
for file_stem, (raw_col, final_col) in RENAME.items():
    series = pd.read_parquet(paths.smard_raw_file(file_stem))[raw_col]
    if final_col in INVALID_BEFORE_CREATION:
        n_invalid = (series.index < DE_LU_CREATION_DATE).sum()
        series = series.where(series.index >= DE_LU_CREATION_DATE)
        print(f"{final_col}: nulled {n_invalid:,} hours before {DE_LU_CREATION_DATE.date()} (bogus placeholder values, not real generation)")
    columns[final_col] = series
    print(f"{final_col}: {series.notna().sum():,} valid hours ({series.dropna().index.min()} .. {series.dropna().index.max()})")

target_panel = pd.DataFrame(columns).sort_index()
target_panel.index.name = "timestamp"
target_panel.to_parquet(paths.target_panel_file)
print(f"\nSaved {target_panel.shape} -> {paths.target_panel_file}")
print(f"Full index range: {target_panel.index.min()} .. {target_panel.index.max()}")
