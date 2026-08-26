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
# # Installed capacity: a monthly snapshot, not one fixed number
#
# Before weighting PECD's capacity factors up to a national potential, it's
# worth being explicit about what "installed capacity" actually means here:
# **a separate snapshot for every month from 2015-01 to the present**, not
# one fixed value applied across the whole backtest. Germany's renewable
# fleet grew substantially over this period (especially solar), so using a
# single snapshot -- today's capacity, say -- would badly overstate
# potential output in 2015 and misattribute how much of the observed
# growth in generation is really "more sun/wind" versus "more panels/
# turbines." The potential-panel stage
# (`pipeline/14_build_pecd_potential_panel.py`) picks each hour's own
# calendar month from these panels when weighting that hour's capacity
# factor -- this notebook shows what that time-varying capacity actually
# looks like, nationally and regionally.

# %%
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.colors import LinearSegmentedColormap
from shapely.geometry import box

from pkg.paths import ProjPaths

paths = ProjPaths()

# %% [markdown]
# ## National installed capacity by technology, 2015-present

# %%
solar_capacity = pd.read_parquet(paths.solar_capacity_by_nuts2_month_file)
peon_capacity = pd.read_parquet(paths.capacity_by_peon_month_file)
peof_capacity = pd.read_parquet(paths.capacity_by_peof_month_file)

national_by_month = pd.DataFrame({
    "Solar PV": solar_capacity.groupby("month")["capacity_mw"].sum(),
    "Wind onshore": peon_capacity.groupby("month")["capacity_mw"].sum(),
    "Wind offshore": peof_capacity.groupby("month")["capacity_mw"].sum(),
})

colors = {"Solar PV": "#eda100", "Wind onshore": "#2a78d6", "Wind offshore": "#1baf7a"}

fig, ax = plt.subplots(figsize=(12, 5))
for tech, color in colors.items():
    ax.plot(national_by_month.index, national_by_month[tech], label=tech, linewidth=1.6, color=color)
ax.set_ylabel("Installed capacity (MW)")
ax.set_title("Germany's installed renewable capacity by technology, 2015-present")
ax.legend()
fig.tight_layout()
fig.savefig(paths.images_path / "13_national_capacity_over_time.png", dpi=150, bbox_inches="tight")
plt.show()

# %% [markdown]
# ```{figure} ../../output/images/13_national_capacity_over_time.png
# :name: fig-13-national-capacity
# National installed capacity by technology, from the monthly MaStR-derived
# panels this project consumes directly (solar: NUTS2 x PECD technology
# panel from `pecd-replication`; wind onshore/offshore: PEON/PEOF panels
# from `mastr-power-capacities-germany`). Solar's build-out visibly
# accelerates after 2022; wind onshore grows steadily; offshore grows in
# discrete jumps, consistent with a market where wind farms come online in
# large, discrete projects rather than continuous incremental additions.
# ```

# %% [markdown]
# ## Same story, regionally: choropleth animations
#
# The national total above hides *where* capacity was added. The three
# animations below replay each technology's own regional panel, one frame
# per quarter, on the same spatial resolution PECD itself publishes
# capacity factors at -- NUTS2 for solar, the PEON/PEOF wind zones for
# wind (introduced in
# [the region-maps notebook](../notebooks/11_eda_region_maps.ipynb)).
#
# A shared, fixed color scale across all frames of a given animation (not
# rescaled per frame) is what makes "growth over time" actually readable --
# a per-frame rescale would flatten every month to look equally "full."

# %%
SEQUENTIAL_CMAP = LinearSegmentedColormap.from_list("capacity_seq", ["#f7f4ec", "#2a78d6"])
FRAME_MONTHS = pd.date_range("2015-03-31", pd.Timestamp.today().normalize(), freq="QE")


def nearest_available_month(available: pd.DatetimeIndex, target: pd.Timestamp) -> pd.Timestamp:
    return available[np.argmin(np.abs(available - target))]


def render_choropleth_gif(regions: gpd.GeoDataFrame, values_by_region_month: pd.DataFrame, output_path, title: str, context_draw=None):
    """`values_by_region_month`: index=region id (matching `regions`'s join
    key), columns=month, values=capacity_mw. Renders one frame per column
    in `FRAME_MONTHS` (nearest available month), same color scale
    throughout.
    """
    vmax = values_by_region_month.to_numpy().max()
    available_months = values_by_region_month.columns

    fig, ax = plt.subplots(figsize=(7, 8.5))

    def draw_frame(frame_month):
        ax.clear()
        actual_month = nearest_available_month(available_months, frame_month)
        frame_values = regions["region_key"].map(values_by_region_month[actual_month])
        if context_draw is not None:
            context_draw(ax)
        regions.assign(_value=frame_values).plot(
            ax=ax, column="_value", cmap=SEQUENTIAL_CMAP, vmin=0, vmax=vmax, edgecolor="#52514e", linewidth=0.4, zorder=2
        )
        ax.set_title(f"{title}\n{actual_month:%Y-%m}")
        ax.axis("off")

    anim = FuncAnimation(fig, draw_frame, frames=FRAME_MONTHS)
    anim.save(output_path, writer=PillowWriter(fps=4))
    plt.close(fig)
    print(f"Saved {len(FRAME_MONTHS)}-frame animation -> {output_path}")


# %% [markdown]
# ### Solar PV, by NUTS2 region

# %%
nuts = gpd.read_file(paths.nuts_regions_file)
nuts2 = nuts[nuts["LEVL_CODE"] == 2].rename(columns={"NUTS_ID": "region_key"})

solar_by_region_month = solar_capacity.groupby(["nuts2_region", "month"])["capacity_mw"].sum().unstack("month")

render_choropleth_gif(
    nuts2,
    solar_by_region_month,
    paths.images_path / "13_solar_capacity_choropleth.gif",
    "Solar PV installed capacity by NUTS2 region",
)

# %% [markdown]
# ```{figure} ../../output/images/13_solar_capacity_choropleth.gif
# :name: fig-13-solar-choropleth
# Solar PV installed capacity by NUTS2 region, quarterly, 2015-present.
# ```

# %% [markdown]
# ### Wind onshore, by PEON zone
#
# PEON has no published vector polygons (see the region-maps notebook), so
# each zone's shape here is dissolved from its own raw grid cells --
# built once (geometry never changes across frames, only the fill color).

# %%
GRID_RESOLUTION_DEG = 0.25
MIN_WEIGHT = 1e-6


def zone_polygons(mask_file, zone_prefix: str = "DE") -> gpd.GeoDataFrame:
    """One dissolved polygon per zone -- each cell assigned to its
    highest-weight (argmax) zone, then unioned by zone.
    """
    ds = xr.open_dataset(mask_file)
    zones = sorted(z for z in ds["region"].values.tolist() if str(z).startswith(zone_prefix))
    mask_values = ds["mask"].sel(region=zones).values
    lats, lons = ds["latitude"].values, ds["longitude"].values
    ds.close()

    total = mask_values.sum(axis=0)
    lat_idx, lon_idx = np.nonzero(total > 0)
    half = GRID_RESOLUTION_DEG / 2

    rows = []
    for i, j in zip(lat_idx, lon_idx):
        weights = mask_values[:, i, j]
        if weights.max() <= MIN_WEIGHT:
            continue
        winning_zone = zones[int(np.argmax(weights))]
        rows.append({"region_key": winning_zone, "geometry": box(lons[j] - half, lats[i] - half, lons[j] + half, lats[i] + half)})

    cells = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    return cells.dissolve(by="region_key").reset_index()


peon_regions = zone_polygons(paths.peon_mask_file)
peon_by_region_month = peon_capacity.groupby(["region_code", "month"])["capacity_mw"].sum().unstack("month")

render_choropleth_gif(
    peon_regions,
    peon_by_region_month,
    paths.images_path / "13_wind_onshore_capacity_choropleth.gif",
    "Wind onshore installed capacity by PEON zone",
    context_draw=lambda ax: nuts2.boundary.plot(ax=ax, color="#c9c6be", linewidth=0.3, zorder=1),
)

# %% [markdown]
# ```{figure} ../../output/images/13_wind_onshore_capacity_choropleth.gif
# :name: fig-13-wind-onshore-choropleth
# Wind onshore installed capacity by PEON zone, quarterly, 2015-present
# (real NUTS2 boundaries in light gray for context).
# ```

# %% [markdown]
# ### Wind offshore, by PEOF zone

# %%
peof_regions = zone_polygons(paths.peof_mask_file)
peof_by_region_month = peof_capacity.groupby(["region_code", "month"])["capacity_mw"].sum().unstack("month")
country_borders = gpd.read_file(paths.country_borders_file)

render_choropleth_gif(
    peof_regions,
    peof_by_region_month,
    paths.images_path / "13_wind_offshore_capacity_choropleth.gif",
    "Wind offshore installed capacity by PEOF zone",
    context_draw=lambda ax: country_borders.plot(ax=ax, facecolor="#f2f0ea", edgecolor="#c9c6be", linewidth=0.4, zorder=1),
)

# %% [markdown]
# ```{figure} ../../output/images/13_wind_offshore_capacity_choropleth.gif
# :name: fig-13-wind-offshore-choropleth
# Wind offshore installed capacity by PEOF zone, quarterly, 2015-present.
# 3 of PEOF's 6 zones carry essentially no capacity throughout -- consistent
# with `pecd-replication`'s finding that PECD itself never modeled
# `DE013_OFF`/`DE014_OFF`/`DE015_OFF`'s capacity factors either.
# ```

# %% [markdown]
# ## Takeaways
#
# - Every capacity figure this project uses is **month-specific**, not a
#   single fixed fleet snapshot -- the potential-panel stage looks up each
#   hour's own calendar month, the same way these animations do.
# - Solar's national growth is the steepest and most recent (a visible
#   inflection from ~2022 onward); wind onshore grows more steadily; wind
#   offshore grows in discrete steps, each one a specific project coming
#   online rather than continuous incremental build-out.
# - Regionally, growth is uneven -- worth keeping in mind before assuming a
#   single national capacity-factor bias applies equally everywhere.
