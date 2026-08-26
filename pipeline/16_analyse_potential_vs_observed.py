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
# # PECD potential vs. SMARD observed generation: the headline gap
#
# This is the comparison the whole project exists to make: how far is
# "PECD capacity factor x installed capacity" (potential) from what SMARD
# reports Germany actually produced? Some gap is expected by construction
# -- outages, curtailment, and (for solar) behind-the-meter
# self-consumption all sit between potential and observed, and none of
# them are modeled here yet (that's the next two notebooks). This notebook
# establishes the gap itself: how big it is, whether it's stable over
# time, and how well potential tracks observed generation's actual
# up-and-down pattern, independent of its level.

# %%
import matplotlib.pyplot as plt
import pandas as pd

from pkg.paths import ProjPaths
from pkg.potential import broadcast_capacity_to_hourly

paths = ProjPaths()

TECH_COLORS = {"solar": "#eda100", "wind_onshore": "#2a78d6", "wind_offshore": "#1baf7a"}
POTENTIAL_COLOR = "#7a7a7a"

potential = pd.read_parquet(paths.pecd_potential_panel_file)
target = pd.read_parquet(paths.target_panel_file)

PAIRS = {
    "solar": ("potential_solar_mw", "pv_mw"),
    "wind_onshore": ("potential_wind_onshore_mw", "wind_onshore_mw"),
    "wind_offshore": ("potential_wind_offshore_mw", "wind_offshore_mw"),
}

# %% [markdown]
# ## Total installed capacity, hourly (for the capacity-factor-normalized view)
#
# Comparing raw MW directly rewards a technology just for having more
# capacity; comparing `MW / total installed capacity that hour` (i.e. a
# national capacity factor) is the more informative, size-independent
# view, and the one PECD's own documentation and `pecd-replication`'s
# validation both use -- so results here are directly comparable to that
# project's published numbers as an external sanity check.

# %%
solar_cf = pd.read_parquet(paths.pecd_solar_capacity_factors_file)
solar_cap_long = pd.read_parquet(paths.solar_capacity_by_nuts2_month_file)
solar_cap_wide = solar_cap_long.pivot_table(index="month", columns=["pecd_technology", "nuts2_region"], values="capacity_mw", fill_value=0.0)
solar_cap_wide.columns = solar_cap_wide.columns.set_names(solar_cf.columns.names)
solar_cap_wide = solar_cap_wide.reindex(columns=solar_cf.columns, fill_value=0.0)
solar_total_capacity = broadcast_capacity_to_hourly(solar_cap_wide, solar_cf.index).sum(axis=1)

peon_wide = pd.read_parquet(paths.capacity_by_peon_month_file).pivot(index="month", columns="region_code", values="capacity_mw")
wind_onshore_cf = pd.read_parquet(paths.pecd_wind_onshore_capacity_factors_file)
peon_wide = peon_wide.reindex(columns=wind_onshore_cf.columns, fill_value=0.0)
onshore_total_capacity = broadcast_capacity_to_hourly(peon_wide, wind_onshore_cf.index).sum(axis=1)

peof_wide = pd.read_parquet(paths.capacity_by_peof_month_file).pivot(index="month", columns="region_code", values="capacity_mw")
wind_offshore_cf = pd.read_parquet(paths.pecd_wind_offshore_capacity_factors_file)
peof_wide = peof_wide.reindex(columns=wind_offshore_cf.columns, fill_value=0.0)
offshore_total_capacity = broadcast_capacity_to_hourly(peof_wide, wind_offshore_cf.index).sum(axis=1)

total_capacity = pd.DataFrame({"solar": solar_total_capacity, "wind_onshore": onshore_total_capacity, "wind_offshore": offshore_total_capacity})

df = potential.join(target, how="inner").join(total_capacity, how="inner")
print(f"Joined panel: {df.shape}, {df.index.min()} .. {df.index.max()}")

# %% [markdown]
# ## Full history vs. `pecd-replication`'s 2019-2025 window
#
# An earlier version of this notebook found correlation meaningfully
# worse once 2016-2018 was included -- traced back to a real SMARD data
# bug, not genuine early-year noise (see
# [the data-availability notebook](../notebooks/10_eda_data_availability.ipynb)):
# SMARD's PV/wind-onshore raw files carry a two-year head start on
# implausibly tiny placeholder values, now nulled out in
# `pipeline/15_build_target_panel.py`. With that fixed, the full available
# history and `pecd-replication`'s own 2019-2025 window (61,368 hours)
# give essentially the same accuracy -- confirmed below. This project
# still reports the 2019-2025 window as primary, purely so the headline
# numbers are directly comparable to that project's own published table,
# not because the extra 2016-2018 data is actually worse.

# %%
FULL_WINDOW = df
PRIMARY_WINDOW = df.loc["2019-01-01":"2025-12-31"]


def error_stats(frame: pd.DataFrame, potential_col: str, observed_col: str, capacity_col: str) -> dict:
    sub = frame[[potential_col, observed_col, capacity_col]].dropna()
    potential_cf = sub[potential_col] / sub[capacity_col]
    observed_cf = sub[observed_col] / sub[capacity_col]
    err = potential_cf - observed_cf
    return {
        "n_hours": len(sub),
        "mae_cf": err.abs().mean(),
        "bias_cf": err.mean(),
        "corr": potential_cf.corr(observed_cf),
    }


for label, window in [("2016-2025 (full available)", FULL_WINDOW), ("2019-2025 (primary)", PRIMARY_WINDOW)]:
    print(f"\n{label}:")
    for tech, (p_col, o_col) in PAIRS.items():
        stats = error_stats(window, p_col, o_col, tech)
        print(f"  {tech:15s} n={stats['n_hours']:>7,}  MAE={stats['mae_cf']:.4f}  bias={stats['bias_cf']:+.4f}  corr={stats['corr']:.4f}")

# %% [markdown]
# ## Headline comparison table (2019-2025)

# %%
summary = pd.DataFrame({tech: error_stats(PRIMARY_WINDOW, *PAIRS[tech], tech) for tech in PAIRS}).T
summary[["mae_cf", "bias_cf", "corr"]].round(4)

# %% [markdown]
# These numbers land within rounding distance of `pecd-replication`'s own
# published "PECD official x MaStR" row (solar MAE 0.016/corr 0.981, wind
# onshore MAE 0.029/corr 0.985, wind offshore MAE 0.094/corr 0.902) --
# despite this project's potential panel being built by an entirely
# separate pipeline that only consumes the two sibling projects'
# *processed* capacity panels, not their code. That agreement is a real
# external validation that the capacity-weighting logic here
# (`pkg/potential.py`) is doing the right thing, not just an internally
# consistent one.

# %% [markdown]
# ## What the gap looks like over time
#
# Monthly-mean potential vs. observed, full available history -- coarse
# enough to stay legible over 9+ years, fine enough to show the bias's own
# seasonal and year-over-year pattern.

# %%
monthly = df.resample("MS").mean()

fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
for ax, tech in zip(axes, PAIRS):
    p_col, o_col = PAIRS[tech]
    ax.plot(monthly.index, monthly[p_col], label="PECD potential", color=POTENTIAL_COLOR, linewidth=1.3, linestyle="--")
    ax.plot(monthly.index, monthly[o_col], label="SMARD observed", color=TECH_COLORS[tech], linewidth=1.3)
    ax.set_ylabel("MW")
    ax.set_title(tech.replace("_", " ").title())
    ax.legend(loc="upper left")
axes[-1].set_xlabel("")
fig.suptitle("Monthly-mean potential vs. observed generation, by technology")
fig.tight_layout()
fig.savefig(paths.images_path / "16_potential_vs_observed_monthly.png", dpi=150, bbox_inches="tight")
plt.show()

# %% [markdown]
# ```{figure} ../../output/images/16_potential_vs_observed_monthly.png
# :name: fig-16-monthly-overlay
# Monthly-mean PECD potential vs. SMARD observed generation, by
# technology, full available history. Potential sits visibly above
# observed for all three technologies, consistent with the expected
# direction (potential has nothing subtracted yet) -- and the gap is not
# flat over time, worth explaining rather than treating as a constant
# offset.
# ```

# %% [markdown]
# ## A closer look: three weeks, hourly
#
# The monthly view above shows the *level* gap; this zooms in on whether
# potential tracks observed generation's actual hour-to-hour shape, not
# just its rough level.

# %%
zoom_window = df.loc["2023-03-01":"2023-03-21"]

fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
for ax, tech in zip(axes, PAIRS):
    p_col, o_col = PAIRS[tech]
    ax.plot(zoom_window.index, zoom_window[p_col], label="PECD potential", color=POTENTIAL_COLOR, linewidth=1.1, linestyle="--")
    ax.plot(zoom_window.index, zoom_window[o_col], label="SMARD observed", color=TECH_COLORS[tech], linewidth=1.1)
    ax.set_ylabel("MW")
    ax.set_title(tech.replace("_", " ").title())
    ax.legend(loc="upper left")
fig.suptitle("Potential vs. observed, hourly, 2023-03-01 to 2023-03-21")
fig.tight_layout()
fig.savefig(paths.images_path / "16_potential_vs_observed_zoom.png", dpi=150, bbox_inches="tight")
plt.show()

# %% [markdown]
# ```{figure} ../../output/images/16_potential_vs_observed_zoom.png
# :name: fig-16-zoom
# Three weeks at hourly resolution -- potential tracks observed
# generation's real up-and-down weather pattern closely for all three
# technologies; the gap is overwhelmingly a *level* difference, not a
# *timing* one.
# ```

# %% [markdown]
# ## Scatter view: potential vs. observed, capacity-factor terms

# %%
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
for ax, tech in zip(axes, PAIRS):
    p_col, o_col = PAIRS[tech]
    sub = PRIMARY_WINDOW[[p_col, o_col, tech]].dropna()
    p_cf, o_cf = sub[p_col] / sub[tech], sub[o_col] / sub[tech]
    ax.scatter(o_cf, p_cf, s=1, alpha=0.15, color=TECH_COLORS[tech], rasterized=True)
    lims = [0, max(p_cf.max(), o_cf.max())]
    ax.plot(lims, lims, color="#3a3a3a", linewidth=1, linestyle=":")
    ax.set_xlabel("Observed capacity factor")
    ax.set_ylabel("Potential capacity factor")
    ax.set_title(tech.replace("_", " ").title())
fig.suptitle("Potential vs. observed capacity factor, 2019-2025 (dotted line = y=x)")
fig.tight_layout()
fig.savefig(paths.images_path / "16_potential_vs_observed_scatter.png", dpi=150, bbox_inches="tight")
plt.show()

# %% [markdown]
# ```{figure} ../../output/images/16_potential_vs_observed_scatter.png
# :name: fig-16-scatter
# Potential vs. observed capacity factor, every hour 2019-2025. Points
# sitting above the `y=x` line are hours where potential overstates
# observed generation -- the systematic tilt above the line, especially at
# higher capacity factors, is the signature curtailment and outages are
# expected to leave (more available power is exactly when curtailment is
# most likely to bind).
# ```

# %% [markdown]
# ## Takeaways
#
# - This project's independently-built potential panel reproduces
#   `pecd-replication`'s own published accuracy numbers almost exactly on
#   the same 2019-2025 window -- a real cross-project validation, not
#   just an internal consistency check.
# - Potential tracks observed generation's actual weather-driven shape
#   well for all three technologies (the zoomed-in view); the gap is
#   overwhelmingly a *level* difference between the two, not a timing
#   mismatch -- exactly what the next two notebooks (curtailment and the
#   remaining gap) need to be true for this project's decomposition
#   approach to make sense at all.
# - The gap is not constant over time (the monthly view) and tilts
#   upward at higher output levels (the scatter view) -- both patterns
#   consistent with curtailment (which binds hardest exactly when
#   potential output is highest) rather than a simple constant
#   unavailability rate.
