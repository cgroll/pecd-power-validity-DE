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
# # Two redispatch data sources, compared
#
# This project has two independent, real ground-truth sources for
# grid-congestion curtailment -- one input needed later to explain the gap
# between PECD potential and SMARD's reported generation. They measure
# related but not identical things, so before using either as "the"
# curtailment number, it's worth seeing how far they actually agree.
#
# | Attribute | SMARD redispatch-by-source | netztransparenz per-measure |
# |---|---|---|
# | Grid level | TSO **and** DSO combined | TSO-**issued** (can still cover a DSO-connected plant) |
# | Frequency | Monthly | Per-measure, real start/end timestamps |
# | Scope | Folds in countertrading + grid-reserve volume, not redispatch-only | Redispatch measures specifically |
# | Methodology | Ex-post, counterfactual ("Ausfallarbeit") | Likely ex-post but mechanical (instructed power x duration) |
# | Technology label | Always present (energy-source column) | Only reliable for offshore wind by name; onshore wind/PV mostly anonymous substation codes ("ambiguous") |
# | Coverage starts | 2022-07 | 2021-01 |
#
# This notebook is a first, descriptive comparison -- not the full
# entity-attribution exercise (statistically assigning each "ambiguous"
# netztransparenz measure a likely technology from its seasonal shape) that
# `pecd-replication`'s `pipeline/46_attribute_ambiguous_redispatch_entities.py`
# builds; that's a candidate to reuse later if the gap-explanation chapters
# need it, not something this exploratory pass repeats.

# %%
import matplotlib.pyplot as plt
import pandas as pd

from pkg.paths import ProjPaths
from pkg.redispatch_measures import load_redispatch_measures

paths = ProjPaths()

smard = pd.read_parquet(paths.redispatch_by_source_file)
measures = load_redispatch_measures(paths.redispatch_measures_file)
colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

smard_reduction = smard.loc[smard["direction"] == "reduction"]
measures_reduction = measures.loc[measures["direction"] == "reduction"]

# %% [markdown]
# ## Each source's own view of renewable curtailment over time

# %%
RENEWABLE_SMARD_SOURCES = ["Wind_Offshore", "Wind_Onshore", "Photovoltaik"]
RENEWABLE_TECHS = ["offshore_wind", "onshore_wind_named", "pv"]

smard_wide = smard_reduction.pivot(index="month", columns="energy_source", values="gwh")
measures_monthly = measures_reduction.groupby(["month", "tech"])["mwh"].sum().unstack("tech").fillna(0.0) / 1000  # MWh -> GWh

fig, axes = plt.subplots(1, 2, figsize=(15, 5), sharey=True)

for i, source in enumerate(RENEWABLE_SMARD_SOURCES):
    axes[0].plot(smard_wide.index, smard_wide[source], label=source.replace("_", " "), linewidth=1.3, color=colors[i])
axes[0].set_title("SMARD redispatch-by-source (monthly)")
axes[0].set_ylabel("GWh curtailed (reduction)")
axes[0].legend()

for i, tech in enumerate(RENEWABLE_TECHS):
    axes[1].plot(measures_monthly.index, measures_monthly[tech], label=tech.replace("_", " "), linewidth=1.3, color=colors[i])
axes[1].plot(measures_monthly.index, measures_monthly["ambiguous"], label="ambiguous", linewidth=1.0, color="gray", linestyle="--")
axes[1].set_title("netztransparenz per-measure (aggregated monthly)")
axes[1].legend()

fig.suptitle("Renewable curtailment (reduction) by source, as each dataset reports it")
fig.tight_layout()
fig.savefig(paths.images_path / "12_redispatch_sources_side_by_side.png", dpi=150, bbox_inches="tight")
plt.show()

# %% [markdown]
# ```{figure} ../../output/images/12_redispatch_sources_side_by_side.png
# :name: fig-12-redispatch-side-by-side
# The same underlying phenomenon (renewable redispatch curtailment), as
# each source reports it. netztransparenz's per-measure export carries a
# large "ambiguous" bucket that SMARD's own technology-labeled series has
# no equivalent for -- SMARD already knows the technology behind every GWh.
# ```

# %% [markdown]
# ## Offshore wind: a clean, directly comparable technology
#
# Offshore wind farms are almost always individually named in
# netztransparenz's export (`OWP ...`), so -- unlike onshore wind and PV --
# its `offshore_wind` classification isn't a guess. Over the period both
# sources cover, do the two totals actually agree?

# %%
overlap_start = max(smard_reduction["month"].min(), measures_reduction["month"].min())
overlap_end = min(smard_reduction["month"].max(), measures_reduction["month"].max())
print(f"Comparable window: {overlap_start.date()} .. {overlap_end.date()}")

smard_offshore = smard_wide.loc[overlap_start:overlap_end, "Wind_Offshore"].sum()
measures_offshore = measures_monthly.loc[overlap_start:overlap_end, "offshore_wind"].sum()
print(f"SMARD offshore wind reduction:          {smard_offshore:,.0f} GWh")
print(f"netztransparenz offshore wind reduction: {measures_offshore:,.0f} GWh")
print(f"Ratio (netztransparenz / SMARD):         {measures_offshore / smard_offshore:.1%}")

# %% [markdown]
# ## Onshore wind + PV: how much of SMARD's figure shows up at all?
#
# Two different questions here, easy to conflate:
#
# 1. **How much is directly, individually attributable** -- summing only
#    measures whose *plant name itself* reveals the technology
#    (`onshore_wind_named` + `pv`).
# 2. **How much of the volume shows up at all**, technology-labeled or
#    not -- summing every non-offshore measure netztransparenz's own
#    coarse `primary_energy_type` already flags as `Erneuerbar` (this
#    includes the anonymous-cluster `ambiguous` rows too, as long as the
#    entity itself is tagged renewable -- no attribution guessing, just a
#    coarser filter than the name-based split).
#
# The gap between the two numbers below is exactly the anonymous-cluster
# problem: real renewable volume that netztransparenz's export can't name
# a specific technology for.

# %%
smard_onshore_pv = smard_wide.loc[overlap_start:overlap_end, ["Wind_Onshore", "Photovoltaik"]].sum().sum()
print(f"SMARD onshore wind + PV reduction: {smard_onshore_pv:,.0f} GWh\n")

measures_onshore_pv_named = measures_monthly.loc[overlap_start:overlap_end, ["onshore_wind_named", "pv"]].sum().sum()
print(f"netztransparenz named onshore wind + PV:            {measures_onshore_pv_named:,.0f} GWh ({measures_onshore_pv_named / smard_onshore_pv:.1%} of SMARD)")

window_mask = (measures_reduction["month"] >= overlap_start) & (measures_reduction["month"] <= overlap_end)
non_offshore_renewable = measures_reduction.loc[
    window_mask & (measures_reduction["primary_energy_type"] == "Erneuerbar") & (measures_reduction["tech"] != "offshore_wind")
]
measures_non_offshore_renewable_mwh = non_offshore_renewable["mwh"].sum() / 1000  # MWh -> GWh
print(f"netztransparenz all non-offshore 'Erneuerbar' rows: {measures_non_offshore_renewable_mwh:,.0f} GWh ({measures_non_offshore_renewable_mwh / smard_onshore_pv:.1%} of SMARD)")

# %% [markdown]
# ## Takeaways
#
# - Offshore wind is the one technology where the two sources measure
#   (almost) the same thing, since netztransparenz's naming convention
#   happens to name offshore farms individually and completely.
# - Onshore wind and PV are a different story: almost none of
#   netztransparenz's export can be attributed to either technology by
#   plant name alone, but a much larger share is at least flagged
#   `Erneuerbar` under an anonymous cluster code -- real volume that's
#   there, just not split between onshore wind and PV without a further
#   attribution step (the statistical approach `pecd-replication` built,
#   not repeated here).
# - Neither source is simply "the truth" -- SMARD's monthly figure folds in
#   countertrading/grid-reserve volume and comes from an ex-post
#   counterfactual model; netztransparenz's export is finer-grained but its
#   technology label is unreliable outside offshore wind. Any later use of
#   "curtailment" as ground truth needs to pick a source (or a reconciled
#   combination) deliberately, with these tradeoffs in view.
