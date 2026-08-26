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
# # What's left: the residual gap, and what public data can (and can't) say about it
#
# [The previous notebook](../notebooks/17_analyse_curtailment_gap.ipynb)
# found that redispatch-reported curtailment explains most of wind
# offshore's gap, a third of onshore's, and little of solar's -- and that
# negative-price hours carry a real, if unsized, voluntary-curtailment
# signature for all three. This notebook looks at what's left after
# subtracting redispatch, asks whether a second public data source can
# plausibly account for it, and is explicit about which part of the gap
# this project's own data simply cannot close.

# %%
import matplotlib.pyplot as plt
import pandas as pd

from pkg.paths import ProjPaths

paths = ProjPaths()

TECH_COLORS = {"solar": "#eda100", "wind_onshore": "#2a78d6", "wind_offshore": "#1baf7a"}
PAIRS = {
    "solar": ("potential_solar_mw", "pv_mw"),
    "wind_onshore": ("potential_wind_onshore_mw", "wind_onshore_mw"),
    "wind_offshore": ("potential_wind_offshore_mw", "wind_offshore_mw"),
}
REDISPATCH_SOURCE_NAME = {"solar": "Photovoltaik", "wind_onshore": "Wind_Onshore", "wind_offshore": "Wind_Offshore"}

potential = pd.read_parquet(paths.pecd_potential_panel_file)
target = pd.read_parquet(paths.target_panel_file)
df = potential.join(target, how="inner")
for tech, (p_col, o_col) in PAIRS.items():
    df[f"gap_{tech}_mw"] = df[p_col] - df[o_col]

redispatch = pd.read_parquet(paths.redispatch_by_source_file)
redispatch_reduction = redispatch.loc[redispatch["direction"] == "reduction"].copy()
redispatch_reduction["month"] = redispatch_reduction["month"].dt.to_period("M")
redispatch_reduction = redispatch_reduction.set_index(["month", "energy_source"])["gwh"]

monthly_gap_gwh = (df[[f"gap_{tech}_mw" for tech in PAIRS]].resample("MS").sum() / 1000).rename(
    columns={f"gap_{tech}_mw": tech for tech in PAIRS}
)
monthly_gap_gwh.index = monthly_gap_gwh.index.to_period("M")

comparison = {}
for tech in PAIRS:
    redispatch_tech = redispatch_reduction.xs(REDISPATCH_SOURCE_NAME[tech], level="energy_source")
    sub = pd.DataFrame({"gap_gwh": monthly_gap_gwh[tech], "redispatch_gwh": redispatch_tech}).dropna()
    sub["residual_gwh"] = sub["gap_gwh"] - sub["redispatch_gwh"]
    sub["residual_share"] = sub["residual_gwh"] / sub["gap_gwh"]
    comparison[tech] = sub

# %% [markdown]
# ## Wind: does the residual shrink as redispatch reporting matures?
#
# Redispatch 2.0's renewable reporting was still ramping up in
# 2022-2023 (`pecd-replication`'s own finding, corroborated in
# [this project's own redispatch-comparison notebook](../notebooks/12_eda_redispatch_comparison.ipynb)) --
# a natural hypothesis is that the *residual* (gap minus reported
# redispatch) should shrink over time as reporting catches up. Checked
# directly, year by year, rather than assumed:

# %%
residual_by_year = pd.DataFrame({
    tech: comparison[tech].assign(year=comparison[tech].index.year).groupby("year")["residual_share"].mean()
    for tech in ["wind_onshore", "wind_offshore"]
})
residual_by_year.round(3)

# %% [markdown]
# **This is not what the hypothesis predicted.** Onshore's residual share
# is noisy without a clear trend (52-105% across 2022-2024, no monotonic
# improvement); offshore's residual share *grows* -- from ~18% in
# 2022-2023 to ~40-45% in 2024-2025, the opposite direction a maturing-
# reporting story would predict. Something else is driving offshore's
# growing residual specifically. One plausible, unconfirmed candidate:
# newly commissioned offshore capacity awaiting its grid export
# connection produces potential that can't reach the grid at all -- a
# different mechanism from an *instructed* redispatch measure, and one
# `pecd-replication`'s own analysis flagged as a well-documented real
# issue in German offshore wind. This project's data can show the pattern
# is real; it can't confirm that specific mechanism without plant-level
# commissioning/grid-connection dates this project doesn't have.

# %%
fig, ax = plt.subplots(figsize=(9, 5))
for tech in ["wind_onshore", "wind_offshore"]:
    ax.plot(residual_by_year.index, residual_by_year[tech], marker="o", label=tech.replace("_", " ").title(), color=TECH_COLORS[tech])
ax.axhline(0, color="#3a3a3a", linewidth=0.8)
ax.set_xlabel("Year")
ax.set_ylabel("Residual as share of gap (gap − redispatch) / gap")
ax.set_title("Wind's unexplained residual, by year")
ax.legend()
fig.tight_layout()
fig.savefig(paths.images_path / "18_wind_residual_by_year.png", dpi=150, bbox_inches="tight")
plt.show()

# %% [markdown]
# ```{figure} ../../output/images/18_wind_residual_by_year.png
# :name: fig-18-wind-residual-by-year
# Share of each year's wind gap left over after subtracting reported
# redispatch curtailment. Offshore's residual grows over time rather than
# shrinking -- inconsistent with "redispatch reporting is just still
# catching up," and a genuinely open pattern this project doesn't resolve.
# ```

# %% [markdown]
# ## Solar: is the residual plausibly self-consumption?
#
# Redispatch explains only 11% of solar's gap (previous notebook) --
# strikingly little compared to wind. Solar has a mechanism wind
# structurally doesn't: behind-the-meter self-consumption, invisible to
# both SMARD's generation figure and redispatch reporting. MaStR's own
# feed-in categories are a plausibility check, not a direct measurement --
# self-consumption *capability* (a unit is registered as such) is not the
# same as self-consumption actually happening at any given hour.

# %%
nuts2_capacity = pd.read_parquet(paths.capacity_by_nuts2_month_file)
solar_by_category = nuts2_capacity[nuts2_capacity["series"].str.startswith("solar")]
category_by_month = solar_by_category.groupby(["month", "series"])["capacity_mw"].sum().unstack("series")
category_share = category_by_month.div(category_by_month.sum(axis=1), axis=0)

CATEGORY_LABELS = {
    "solar_full_feed_in": "Full feed-in (cannot self-consume)",
    "solar_self_consumption_no_storage": "Self-consumption, no storage",
    "solar_self_consumption_with_storage": "Self-consumption, with storage",
    "solar_unknown": "Unknown",
}
CATEGORY_COLORS = ["#9a9a9a", "#eda100", "#e34948", "#e8e6e0"]

fig, ax = plt.subplots(figsize=(11, 5))
ax.stackplot(
    category_share.index,
    [category_share[c] for c in CATEGORY_LABELS],
    labels=[CATEGORY_LABELS[c] for c in CATEGORY_LABELS],
    colors=CATEGORY_COLORS,
)
ax.set_ylabel("Share of national solar capacity")
ax.set_title("Solar capacity by MaStR feed-in category, over time")
ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
fig.tight_layout()
fig.savefig(paths.images_path / "18_solar_feed_in_category_share.png", dpi=150, bbox_inches="tight")
plt.show()

latest = category_share.iloc[-1]
print(f"Latest month ({category_share.index[-1]}): {latest['solar_full_feed_in']:.1%} full feed-in, "
      f"{latest['solar_self_consumption_no_storage'] + latest['solar_self_consumption_with_storage']:.1%} self-consumption-capable")

# %% [markdown]
# ```{figure} ../../output/images/18_solar_feed_in_category_share.png
# :name: fig-18-solar-feed-in-category
# Share of national solar capacity by MaStR feed-in category. Roughly
# 44% of capacity is registered with self-consumption capability -- easily
# enough, in principle, to plausibly account for most of the ~89% of
# solar's gap that redispatch curtailment doesn't explain, though this
# chart cannot say how much of that *capability* is actually exercised in
# any given hour.
# ```

# %% [markdown]
# ## Synthesis: what's explained, what's plausible, what's genuinely open
#
# | Technology | Redispatch-explained | Remaining gap | Most plausible driver of the remainder |
# |---|---|---|---|
# | Solar | 11% | 89% | Behind-the-meter self-consumption (plausible from capacity shares above, not directly measurable) |
# | Wind onshore | 33% | 67%, noisy year to year | A mix of unmodeled outages (no public isolating series exists) and negative-price voluntary curtailment (shown correlationally, not sized) |
# | Wind offshore | 71% | 29%, *growing* since 2022 | Possibly delayed grid-connection issues for newly commissioned capacity -- a real, documented phenomenon this project's data can't directly confirm |
#
# **What this project cannot close with public data, on principle, not just
# for lack of trying:**
#
# - **Self-consumed solar MWh.** By definition, behind-the-meter output
#   never reaches a meter SMARD or MaStR can read -- only the *capability*
#   (registered feed-in category) is observable, never the actual hourly
#   volume.
# - **Plant-level outages/maintenance.** No published series isolates
#   "generation lost to an outage" from any other cause -- the same gap
#   found throughout `pecd-replication`'s own work.
# - **The exact size of negative-price voluntary curtailment.** Negative
#   prices are an observable *incentive*, not a metered *volume*; sizing
#   it needs a calibrated model (as `pecd-replication` built for wind),
#   deliberately out of scope for this project's descriptive approach.
# - **PECD's own methodology limitations.** This project deliberately
#   takes PECD's official capacity factors as given rather than
#   replicating them -- any bias inherent to PECD's own product (e.g. the
#   high-wind overestimate or solar's year-over-year drift
#   `pecd-replication` documents from first-principles physics) isn't
#   re-verified here, only inherited.
#
# The offshore residual's growth over 2022-2025 is the one finding in this
# notebook that's genuinely unresolved rather than merely "not
# measurable" -- worth flagging as the natural next question for anyone
# picking this project back up, not a closed item.
