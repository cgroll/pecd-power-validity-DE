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
# # How much of the gap does curtailment explain?
#
# [The previous notebook](../notebooks/16_analyse_potential_vs_observed.ipynb)
# established that PECD potential sits systematically above SMARD's
# observed generation, and that the gap tilts upward at higher output
# levels -- the signature curtailment is expected to leave. This notebook
# checks that directly against the two curtailment mechanisms this
# project actually has ground truth for: grid-congestion redispatch (real
# reported volumes) and negative day-ahead prices (a real, observable
# incentive for voluntary curtailment, not a volume in itself).
#
# This is deliberately a **descriptive** check, not a calibrated model --
# unlike `pecd-replication`'s own curtailment-estimation chapter (which
# fits a wind-calibrated curtailment-vs-oversupply curve and transfers it
# to PV), this notebook reports how much of the gap redispatch volumes
# account for, and whether the remainder still carries a negative-price
# signature, without fitting anything.

# %%
import matplotlib.pyplot as plt
import pandas as pd

from pkg.paths import ProjPaths
from pkg.potential import broadcast_capacity_to_hourly
from pkg.redispatch_measures import distribute_to_hourly, load_redispatch_measures

paths = ProjPaths()

TECH_COLORS = {"solar": "#eda100", "wind_onshore": "#2a78d6", "wind_offshore": "#1baf7a"}
POTENTIAL_COLOR = "#7a7a7a"
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

# %% [markdown]
# ## Mechanism 1: grid-congestion redispatch
#
# SMARD's monthly redispatch-by-source series reports real curtailed
# volume per energy source since 2022-07. Comparing it against the
# monthly gap (both converted to GWh) shows how much of the potential-vs-
# observed shortfall a real, reported mechanism accounts for -- on
# whatever window the two series actually overlap.

# %%
# SMARD's redispatch export stores "month" as the 1st of the month;
# this project's own monthly panels use month-end -- aligned here via
# calendar Period, not raw Timestamp equality, so the two don't silently
# fail to match.
redispatch = pd.read_parquet(paths.redispatch_by_source_file)
redispatch_reduction = redispatch.loc[redispatch["direction"] == "reduction"].copy()
redispatch_reduction["month"] = redispatch_reduction["month"].dt.to_period("M")
redispatch_reduction = redispatch_reduction.set_index(["month", "energy_source"])["gwh"]

monthly_gwh = {}
for tech, (p_col, o_col) in PAIRS.items():
    monthly_gwh[tech] = pd.DataFrame({
        "potential_gwh": df[p_col].resample("MS").sum() / 1000,
        "observed_gwh": df[o_col].resample("MS").sum() / 1000,
        "gap_gwh": df[f"gap_{tech}_mw"].resample("MS").sum() / 1000,
    })
    monthly_gwh[tech].index = monthly_gwh[tech].index.to_period("M")

comparison = {}
for tech in PAIRS:
    source_name = REDISPATCH_SOURCE_NAME[tech]
    redispatch_tech = redispatch_reduction.xs(source_name, level="energy_source")
    comparison[tech] = monthly_gwh[tech].join(redispatch_tech.rename("redispatch_gwh")).dropna()
    comparison[tech].index = comparison[tech].index.to_timestamp()

fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
for ax, tech in zip(axes, PAIRS):
    sub = comparison[tech]
    ax.plot(sub.index, sub["gap_gwh"], label="Potential − observed (gap)", color=TECH_COLORS[tech], linewidth=1.4)
    ax.plot(sub.index, sub["redispatch_gwh"], label="Reported redispatch curtailment", color="#3a3a3a", linewidth=1.2, linestyle="--")
    ax.set_ylabel("GWh / month")
    ax.set_title(tech.replace("_", " ").title())
    ax.legend(loc="upper left")
fig.suptitle("Monthly gap vs. reported redispatch curtailment, 2022-07 onward")
fig.tight_layout()
fig.savefig(paths.images_path / "17_gap_vs_redispatch.png", dpi=150, bbox_inches="tight")
plt.show()

# %% [markdown]
# ```{figure} ../../output/images/17_gap_vs_redispatch.png
# :name: fig-17-gap-vs-redispatch
# Monthly potential-observed gap vs. SMARD's reported redispatch
# curtailment volume, by technology. Where the dashed line tracks the
# solid line closely, curtailment explains most of the gap; a persistent
# solid-above-dashed margin is gap curtailment alone doesn't explain.
# ```

# %%
explained_share = {
    tech: comparison[tech]["redispatch_gwh"].sum() / comparison[tech]["gap_gwh"].sum() for tech in PAIRS
}
pd.Series(explained_share, name="share_of_gap_explained_by_redispatch").to_frame().round(3)

# %% [markdown]
# ## Mechanism 2: negative day-ahead prices
#
# Negative prices are a real, observable incentive for voluntary
# curtailment -- but unlike redispatch, there's no reported *volume* to
# compare against, only the incentive itself. So instead of a volume
# comparison, this checks whether the gap is systematically larger during
# negative-price hours than otherwise -- the pattern voluntary curtailment
# would leave, even without a calibrated estimate of how much of it that
# explains.

# %%
solar_cf = pd.read_parquet(paths.pecd_solar_capacity_factors_file)
solar_cap_long = pd.read_parquet(paths.solar_capacity_by_nuts2_month_file)
solar_cap_wide = solar_cap_long.pivot_table(index="month", columns=["pecd_technology", "nuts2_region"], values="capacity_mw", fill_value=0.0)
solar_cap_wide.columns = solar_cap_wide.columns.set_names(solar_cf.columns.names)
solar_total_capacity = broadcast_capacity_to_hourly(solar_cap_wide.reindex(columns=solar_cf.columns, fill_value=0.0), solar_cf.index).sum(axis=1)

peon_wide = pd.read_parquet(paths.capacity_by_peon_month_file).pivot(index="month", columns="region_code", values="capacity_mw")
wind_onshore_cf = pd.read_parquet(paths.pecd_wind_onshore_capacity_factors_file)
onshore_total_capacity = broadcast_capacity_to_hourly(peon_wide.reindex(columns=wind_onshore_cf.columns, fill_value=0.0), wind_onshore_cf.index).sum(axis=1)

peof_wide = pd.read_parquet(paths.capacity_by_peof_month_file).pivot(index="month", columns="region_code", values="capacity_mw")
wind_offshore_cf = pd.read_parquet(paths.pecd_wind_offshore_capacity_factors_file)
offshore_total_capacity = broadcast_capacity_to_hourly(peof_wide.reindex(columns=wind_offshore_cf.columns, fill_value=0.0), wind_offshore_cf.index).sum(axis=1)

total_capacity = pd.DataFrame({"solar": solar_total_capacity, "wind_onshore": onshore_total_capacity, "wind_offshore": offshore_total_capacity})
df = df.join(total_capacity, how="inner")

is_negative_price = df["price_de_lu_eur_mwh"] < 0
print(f"Negative-price hours: {is_negative_price.sum():,} of {df['price_de_lu_eur_mwh'].notna().sum():,} priced hours ({is_negative_price.mean():.1%})")

# %%
rows = []
for tech in PAIRS:
    gap_cf = df[f"gap_{tech}_mw"] / df[tech]
    valid = gap_cf.notna() & df["price_de_lu_eur_mwh"].notna()
    rows.append({
        "technology": tech,
        "mean_gap_cf_negative_price": gap_cf[valid & is_negative_price].mean(),
        "mean_gap_cf_positive_price": gap_cf[valid & ~is_negative_price].mean(),
    })
price_split = pd.DataFrame(rows).set_index("technology")
price_split["ratio"] = price_split["mean_gap_cf_negative_price"] / price_split["mean_gap_cf_positive_price"]
price_split.round(4)

# %%
fig, ax = plt.subplots(figsize=(8, 5))
x = range(len(PAIRS))
width = 0.35
ax.bar([i - width / 2 for i in x], price_split["mean_gap_cf_positive_price"], width, label="Non-negative price hours", color="#9a9a9a")
ax.bar([i + width / 2 for i in x], price_split["mean_gap_cf_negative_price"], width, label="Negative price hours", color="#e34948")
ax.set_xticks(list(x))
ax.set_xticklabels([t.replace("_", " ").title() for t in PAIRS])
ax.set_ylabel("Mean gap (capacity factor units)")
ax.set_title("Potential-observed gap, split by day-ahead price sign")
ax.legend()
fig.tight_layout()
fig.savefig(paths.images_path / "17_gap_by_price_sign.png", dpi=150, bbox_inches="tight")
plt.show()

# %% [markdown]
# ```{figure} ../../output/images/17_gap_by_price_sign.png
# :name: fig-17-gap-by-price-sign
# Mean potential-observed gap (capacity-factor units), split by whether
# the day-ahead price was negative that hour. A materially larger gap
# during negative-price hours is the pattern voluntary curtailment would
# leave -- present here for all three technologies, most for wind.
# ```

# %% [markdown]
# ## So how well does curtailment-adjusted potential actually match SMARD?
#
# The direct question: subtract reported redispatch curtailment from
# potential, then compare *that* against SMARD's observed generation, the
# same way [the previous notebook](../notebooks/16_analyse_potential_vs_observed.ipynb)
# compared raw potential against it. Redispatch data is monthly, so this
# comparison is necessarily at monthly granularity too (not the hourly
# resolution notebook 16 used) -- both the "before" and "after" rows below
# use the same monthly aggregation, so the comparison between them is
# apples-to-apples even though the absolute numbers aren't directly
# comparable to notebook 16's hourly ones.

# %%
def match_quality(observed: pd.Series, modeled: pd.Series) -> dict:
    err = modeled - observed
    return {
        "mae_gwh": err.abs().mean(),
        "bias_gwh": err.mean(),
        "nmae_pct": err.abs().mean() / observed.mean() * 100,
        "corr": modeled.corr(observed),
    }


match_rows = []
for tech in PAIRS:
    sub = comparison[tech]
    adjusted_potential = sub["potential_gwh"] - sub["redispatch_gwh"]
    before = match_quality(sub["observed_gwh"], sub["potential_gwh"])
    after = match_quality(sub["observed_gwh"], adjusted_potential)
    match_rows.append({"technology": tech, "stage": "raw potential", **before})
    match_rows.append({"technology": tech, "stage": "curtailment-adjusted", **after})

match_quality_table = pd.DataFrame(match_rows).set_index(["technology", "stage"])
match_quality_table.round(2)

# %% [markdown]
# Subtracting reported redispatch curtailment measurably improves the
# match for wind (both directions of error shrink, `nMAE` most visibly for
# offshore, where redispatch explains the most of the gap); solar barely
# moves, consistent with redispatch curtailment not being solar's main
# gap driver in the first place.

# %% [markdown]
# ## Offshore, at hourly resolution: netztransparenz's per-measure data
#
# SMARD's monthly series above starts 2022-07 and can't resolve anything
# finer than a month. netztransparenz's per-measure export (already used
# in [the redispatch-comparison notebook](../notebooks/12_eda_redispatch_comparison.ipynb))
# carries real start/end timestamps (often 15-minute steps) back to
# 2021-01 -- but its technology label is only reliable for offshore wind
# (per-measure names are almost always individually identifiable there;
# onshore wind/PV are overwhelmingly anonymous "ambiguous" cluster codes).
# So this section is offshore-only: distributing each measure's MWh
# across the hours it spans (conserving the total exactly) gives an
# actual hourly curtailment series, letting the match-quality check be
# redone at the resolution PECD/SMARD data natively has, not squeezed
# down to SMARD's monthly grid -- and over a longer window besides.

# %%
measures = load_redispatch_measures(paths.redispatch_measures_file)
offshore_reduction = measures.loc[(measures["direction"] == "reduction") & (measures["tech"] == "offshore_wind")]

hourly_curtailment_mwh = distribute_to_hourly(offshore_reduction["start"], offshore_reduction["end"], offshore_reduction["mwh"])
print(f"{len(offshore_reduction):,} offshore measures -> {len(hourly_curtailment_mwh):,} non-zero hourly bins")
print(f"Total: {hourly_curtailment_mwh.sum():,.0f} MWh (matches the raw per-measure sum exactly, by construction)")

# %%
NETZTRANSPARENZ_WINDOW = df.loc["2021-01-01":"2025-12-31"].index
offshore_hourly = df.loc[NETZTRANSPARENZ_WINDOW, ["potential_wind_offshore_mw", "wind_offshore_mw"]].copy()
# Reindex (not join) so hours with zero curtailment -- the overwhelming
# majority -- correctly become 0, not a dropped/missing row.
offshore_hourly["curtailment_mw"] = hourly_curtailment_mwh.reindex(NETZTRANSPARENZ_WINDOW, fill_value=0.0)
offshore_hourly["adjusted_potential_mw"] = offshore_hourly["potential_wind_offshore_mw"] - offshore_hourly["curtailment_mw"]
offshore_hourly = offshore_hourly.dropna()


def match_quality_gw(observed_mw: pd.Series, modeled_mw: pd.Series) -> dict:
    err_gw = (modeled_mw - observed_mw) / 1000
    return {
        "mae_gw": err_gw.abs().mean(),
        "bias_gw": err_gw.mean(),
        "nmae_pct": err_gw.abs().mean() / (observed_mw.mean() / 1000) * 100,
        "corr": modeled_mw.corr(observed_mw),
    }


hourly_match = pd.DataFrame([
    {"stage": "raw potential", **match_quality_gw(offshore_hourly["wind_offshore_mw"], offshore_hourly["potential_wind_offshore_mw"])},
    {"stage": "curtailment-adjusted (hourly, netztransparenz, 2021-2025)", **match_quality_gw(offshore_hourly["wind_offshore_mw"], offshore_hourly["adjusted_potential_mw"])},
]).set_index("stage")
hourly_match.round(3)

# %% [markdown]
# **This does not tell quite the same story as the monthly comparison.**
# The SMARD-monthly-based result for offshore (further up) showed nMAE
# dropping from 24.5% to 8.0%; this hourly, longer-window version shows a
# real but far more modest improvement (27.9% -> 18.3%, corr 0.888 ->
# 0.930). Monthly aggregation flatters the "after" number: summing a
# whole month's hours before comparing smooths away any hour-to-hour
# mismatch between when curtailment actually happened and when this
# notebook's even-spread-across-the-measure's-duration assumption places
# it, so the monthly view credits redispatch with fixing *shape* problems
# it never touches, only the *level*. The hourly check is the more honest
# one for anything that would eventually need hour-level accuracy (e.g. a
# forecast) -- and by that measure, curtailment closes real ground but
# leaves a bigger remaining gap than the monthly comparison suggested.

# %%
zoom_window = offshore_hourly.loc["2023-03-01":"2023-03-21"]

fig, ax = plt.subplots(figsize=(13, 4))
ax.plot(zoom_window.index, zoom_window["potential_wind_offshore_mw"], label="PECD potential", color=POTENTIAL_COLOR, linewidth=1.1, linestyle="--")
ax.plot(zoom_window.index, zoom_window["adjusted_potential_mw"], label="Potential minus curtailment (hourly)", color="#3a3a3a", linewidth=1.2, linestyle=":")
ax.plot(zoom_window.index, zoom_window["wind_offshore_mw"], label="SMARD observed", color=TECH_COLORS["wind_offshore"], linewidth=1.3)
ax.set_ylabel("MW")
ax.set_title("Wind offshore: potential, curtailment-adjusted potential, and observed, 2023-03-01 to 2023-03-21")
ax.legend(loc="upper left")
fig.tight_layout()
fig.savefig(paths.images_path / "17_offshore_hourly_adjusted.png", dpi=150, bbox_inches="tight")
plt.show()

# %% [markdown]
# ```{figure} ../../output/images/17_offshore_hourly_adjusted.png
# :name: fig-17-offshore-hourly-adjusted
# Same three-week window as notebook 16's zoom chart. The
# curtailment-adjusted line (dotted) sits visibly closer to SMARD's
# observed generation (solid) than raw potential (dashed) does, hour by
# hour -- not just in the monthly-aggregate sense the SMARD-based
# comparison above showed.
# ```

# %% [markdown]
# ## What's left after subtracting reported redispatch curtailment?
#
# Monthly gap minus monthly redispatch curtailment, same 2022-07-onward
# window as the first chart -- a positive residual means redispatch alone
# doesn't close the gap; a residual near (or below) zero means it does.

# %%
residual_gwh = pd.DataFrame({tech: comparison[tech]["gap_gwh"] - comparison[tech]["redispatch_gwh"] for tech in PAIRS})
residual_pct_of_observed = pd.DataFrame({
    tech: residual_gwh[tech] / comparison[tech]["observed_gwh"] * 100 for tech in PAIRS
})

print("Residual, GWh/month:")
display(residual_gwh.describe().loc[["mean", "std", "min", "max"]].round(1))
print("\nResidual as % of that month's observed generation:")
display(residual_pct_of_observed.describe().loc[["mean", "std", "min", "max"]].round(1))

# %% [markdown]
# ## Takeaways
#
# - Subtracting reported redispatch curtailment measurably improves the
#   match against SMARD for both wind technologies (smaller MAE/nMAE,
#   higher correlation) -- see the match-quality table above -- but a
#   persistent residual remains; solar barely improves, since redispatch
#   was never its main gap driver.
# - The gap is measurably larger during negative-price hours for all
#   three technologies -- consistent with voluntary curtailment being a
#   real, additional contributor, though this notebook doesn't attempt to
#   size it the way `pecd-replication`'s calibrated curve does.
# - Offshore's hourly, netztransparenz-based version tells a *more
#   modest* story than SMARD's monthly comparison (nMAE 27.9% -> 18.3%,
#   vs. the monthly view's 24.5% -> 8.0%): monthly aggregation smooths
#   away hour-to-hour timing mismatches and credits redispatch with
#   fixing the *level* only, not the *shape* -- the hourly check is the
#   more honest one for anything that would eventually need hour-level
#   accuracy.
# - What's left after both mechanisms (behind-the-meter self-consumption
#   for solar in particular, unmodeled maintenance/outages, and this
#   project's own potential-side bias) is the subject of the next
#   notebook.
