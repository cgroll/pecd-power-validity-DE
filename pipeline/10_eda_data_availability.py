# ---
# jupytext:
#   text_representation:
#     format_name: percent
# kernelspec:
#   display_name: Python 3
#   language: python
#   name: python3
# ---

# %% [markdown]
# # Data availability across all sources
#
# Before combining anything, it's worth knowing exactly which months each
# source actually covers. The sources feeding this project start at very
# different points and update on very different schedules -- PECD's
# official product is a fixed historical download (2015-2025, no gaps by
# construction), SMARD's DE-LU-specific series only exist from the DE-LU
# market area's actual creation (2018-10-01), and the two redispatch
# sources start later still (2021, 2022). Any potential-vs-observed
# comparison later in this project is bounded by the *latest* of these
# start dates, not the earliest.
#
# **One source needed a real fix, not just a start-date check.** SMARD's
# PV and wind-onshore raw files carry an index back to 2016-12-30 --
# looking available two years earlier than wind offshore/load/price. But
# checked directly, values before 2018-10-01 are implausibly tiny
# placeholders, not real generation (June 2017's daily peak: 87 MW; June
# 2019's: 30,141 MW -- a jump no real two-year capacity growth explains),
# with a clean cutover exactly at 2018-10-01 00:00. `pipeline/15_build_
# target_panel.py` nulls these out; the presence table below applies the
# same correction, otherwise this notebook would itself report two years
# of data that isn't actually usable.

# %%
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pkg.paths import ProjPaths
from pkg.redispatch_measures import load_redispatch_measures

paths = ProjPaths()

# %% [markdown]
# ## Building a monthly presence table
#
# Each source is reduced to "was there at least one observation in this
# calendar month?" -- coarse enough to compare an hourly series against a
# monthly one on the same axis, fine enough to show real gaps (like the
# DE-LU series' pre-2018-10 absence) rather than hiding them behind a
# single start/end date.

# %%
FULL_RANGE = pd.period_range("2015-01", pd.Timestamp.today().to_period("M"), freq="M")


def monthly_presence_from_index(index: pd.DatetimeIndex) -> pd.Series:
    months_present = pd.PeriodIndex(index, freq="M").unique()
    return pd.Series(1, index=months_present).reindex(FULL_RANGE, fill_value=0)


def monthly_presence_from_month_column(months: pd.Series) -> pd.Series:
    months_present = pd.PeriodIndex(pd.to_datetime(months), freq="M").unique()
    return pd.Series(1, index=months_present).reindex(FULL_RANGE, fill_value=0)


series_presence = {}

series_presence["PECD solar CF (4 techs)"] = monthly_presence_from_index(
    pd.read_parquet(paths.pecd_solar_capacity_factors_file, columns=[]).index
)
series_presence["PECD wind onshore CF (PEON)"] = monthly_presence_from_index(
    pd.read_parquet(paths.pecd_wind_onshore_capacity_factors_file, columns=[]).index
)
series_presence["PECD wind offshore CF (PEOF)"] = monthly_presence_from_index(
    pd.read_parquet(paths.pecd_wind_offshore_capacity_factors_file, columns=[]).index
)

DE_LU_CREATION_DATE = pd.Timestamp("2018-10-01")
INVALID_BEFORE_CREATION = {"pv", "wind_onshore"}  # see the bogus-placeholder-value finding above

for name, label in [
    ("pv", "SMARD PV generation"),
    ("wind_onshore", "SMARD wind onshore generation"),
    ("wind_offshore", "SMARD wind offshore generation"),
    ("load", "SMARD load"),
    ("price_de_lu", "SMARD day-ahead price (DE-LU)"),
]:
    series = pd.read_parquet(paths.smard_raw_file(name))
    if name in INVALID_BEFORE_CREATION:
        series = series.loc[series.index >= DE_LU_CREATION_DATE]
    series_presence[label] = monthly_presence_from_index(series.index)

for name, label in [
    ("solar", "SMARD capacity: solar"),
    ("wind_onshore", "SMARD capacity: wind onshore"),
    ("wind_offshore", "SMARD capacity: wind offshore"),
]:
    series_presence[label] = monthly_presence_from_index(pd.read_parquet(paths.smard_capacity_file(name), columns=[]).index)

series_presence["SMARD redispatch-by-source (monthly)"] = monthly_presence_from_month_column(
    pd.read_parquet(paths.redispatch_by_source_file)["month"]
)
series_presence["netztransparenz redispatch measures (per-measure)"] = monthly_presence_from_month_column(
    load_redispatch_measures(paths.redispatch_measures_file)["month"]
)

for filename, label in [
    ("capacity_by_peon_month.parquet", "MaStR capacity: PEON zones (wind onshore)"),
    ("capacity_by_peof_month.parquet", "MaStR capacity: PEOF zones (wind offshore)"),
    ("capacity_by_offshore_month.parquet", "MaStR capacity: offshore pseudo-regions"),
    ("capacity_by_nuts2_month.parquet", "MaStR capacity: NUTS2 (feed-in category)"),
    ("solar_capacity_by_nuts2_month.parquet", "MaStR capacity: NUTS2 x PECD solar tech"),
]:
    series_presence[label] = monthly_presence_from_month_column(
        pd.read_parquet(paths.external_capacity_downloads_path / filename)["month"]
    )

presence = pd.DataFrame(series_presence).T
presence.columns = [str(m) for m in presence.columns]
presence.shape

# %% [markdown]
# ## Availability heatmap
#
# One row per source, one column per calendar month. Filled = data
# present that month.

# %%
GROUP_BOUNDARIES = [3, 8, 11, 13]  # rows after which a group ends (PECD | SMARD gen | SMARD capacity | redispatch | external)
PRESENT_COLOR = "#2a78d6"
ABSENT_COLOR = "#e8e6e0"

fig, ax = plt.subplots(figsize=(16, 6))
data = presence.to_numpy()
cmap = plt.matplotlib.colors.ListedColormap([ABSENT_COLOR, PRESENT_COLOR])
ax.imshow(data, aspect="auto", cmap=cmap, vmin=0, vmax=1, interpolation="none")

for boundary in GROUP_BOUNDARIES:
    ax.axhline(boundary - 0.5, color="white", linewidth=2)

year_starts = [i for i, col in enumerate(presence.columns) if col.endswith("-01")]
ax.set_xticks(year_starts)
ax.set_xticklabels([presence.columns[i][:4] for i in year_starts])
ax.set_yticks(range(len(presence.index)))
ax.set_yticklabels(presence.index, fontsize=8)
ax.set_title("Monthly data availability by source, 2015-present")
fig.tight_layout()
fig.savefig(paths.images_path / "10_data_availability_heatmap.png", dpi=150, bbox_inches="tight")
plt.show()

# %% [markdown]
# ```{figure} ../../output/images/10_data_availability_heatmap.png
# :name: fig-10-data-availability
# Monthly data availability across every source this project uses. PECD's
# official product and the MaStR-derived capacity panels cover the full
# window; all five SMARD series only start once the DE-LU market area
# existed (2018-10) -- PV/wind onshore's own raw files reach back further,
# but their pre-2018-10 values are bogus (see above) and excluded here;
# the two redispatch sources start later still (2021-01 and 2022-07).
# ```

# %% [markdown]
# ## The binding constraint: usable backtest window
#
# The latest common start date across everything needed for a
# potential-vs-observed-plus-curtailment comparison sets the real usable
# window -- not any single source's own start date.

# %%
first_available = {label: FULL_RANGE[np.argmax(row.to_numpy())] for label, row in presence.iterrows()}
first_available_sorted = pd.Series(first_available).sort_values(ascending=False)
first_available_sorted
