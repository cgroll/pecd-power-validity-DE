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
# # The three region schemes: NUTS2, PEON, PEOF
#
# PECD v4.2 publishes capacity factors at a different spatial resolution
# per technology -- solar PV at NUTS2 (Eurostat's standard regional
# breakdown), wind onshore at PEON zones, wind offshore at PEOF zones.
# Neither PEON nor PEOF is a NUTS scheme at all; this notebook shows what
# each actually looks like on a map of Germany, since none of the later
# analysis makes sense without a clear picture of what region a "zone" or
# "NUTS2 code" actually refers to.

# %%
import geopandas as gpd
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from shapely.geometry import box

from pkg.paths import ProjPaths

paths = ProjPaths()

# Fixed categorical hue order (validated for CVD-safe adjacent contrast),
# reused unchanged from mastr-power-capacities-germany's own zone-map EDA.
CATEGORICAL_COLORS = [
    "#2a78d6",  # blue
    "#008300",  # green
    "#e87ba4",  # magenta
    "#eda100",  # yellow
    "#1baf7a",  # aqua
    "#eb6834",  # orange
    "#4a3aa7",  # violet
    "#e34948",  # red
]

# %% [markdown]
# ## NUTS2 regions -- solar's spatial resolution
#
# Germany's ~38 NUTS2 regions, plain boundaries for orientation (too many
# regions for a distinct-color-per-region scheme to stay legible).

# %%
nuts = gpd.read_file(paths.nuts_regions_file)
nuts2 = nuts[nuts["LEVL_CODE"] == 2]

fig, ax = plt.subplots(figsize=(8, 10))
nuts2.plot(ax=ax, facecolor="#eef2fb", edgecolor="#2a78d6", linewidth=0.6)
ax.set_title(f"Germany's NUTS2 regions (n={len(nuts2)}) -- solar PV's PECD resolution")
ax.axis("off")
fig.tight_layout()
fig.savefig(paths.images_path / "11_nuts2_regions.png", dpi=150, bbox_inches="tight")
plt.show()

# %% [markdown]
# ```{figure} ../../output/images/11_nuts2_regions.png
# :name: fig-11-nuts2-regions
# Germany's NUTS2 regions -- the resolution PECD v4.2 publishes solar PV
# capacity factors at.
# ```

# %% [markdown]
# ## PEON / PEOF zones -- wind's spatial resolution
#
# PECD offers **no** NUTS-anything for wind -- only these two pan-European
# zone schemes. Their boundaries aren't published as a shapefile, only as
# a rasterized "region mask" (fractional 0.25-degree grid-cell coverage
# per zone), so the map below shows the raw grid cells actually used for
# any capacity crosswalk, colored by each cell's highest-weight
# ("winning") zone -- not a smoothed/dissolved polygon, since that's what
# mastr-power-capacities-germany's own PEON/PEOF capacity panels are
# actually built on. Adapted unchanged from that project's own
# `pipeline/08_pecd_zones_eda.py`.

# %%
GRID_RESOLUTION_DEG = 0.25
MIN_WEIGHT = 1e-6  # floating-point noise floor below which a zone's coverage doesn't count as "present"


def zone_grid_cells(mask_file, zone_prefix: str = "DE") -> tuple[gpd.GeoDataFrame, list[str]]:
    """One row per grid cell touched by any of `zone_prefix`'s zones.

    `zone_id`/`weight` are the cell's argmax (highest-weight) zone;
    `n_nonzero` counts zones with weight > MIN_WEIGHT at that cell --
    where more than one, a real wind unit's capacity would be fractionally
    split across regions rather than assigned whole to one.
    """
    ds = xr.open_dataset(mask_file)
    zones = sorted(z for z in ds["region"].values.tolist() if str(z).startswith(zone_prefix))
    mask_values = ds["mask"].sel(region=zones).values  # (zone, lat, lon)
    lats, lons = ds["latitude"].values, ds["longitude"].values
    ds.close()

    total = mask_values.sum(axis=0)
    lat_idx, lon_idx = np.nonzero(total > 0)

    half = GRID_RESOLUTION_DEG / 2
    rows = []
    for i, j in zip(lat_idx, lon_idx):
        weights = mask_values[:, i, j]
        order = np.argsort(weights)[::-1]
        n_nonzero = int((weights > MIN_WEIGHT).sum())
        rows.append(
            {
                "zone_id": zones[order[0]],
                "weight": weights[order[0]],
                "n_nonzero": n_nonzero,
                "geometry": box(lons[j] - half, lats[i] - half, lons[j] + half, lats[i] + half),
            }
        )
    return gpd.GeoDataFrame(rows, crs="EPSG:4326"), zones


CELL_INCH = 0.42  # figure inches per 0.25-degree grid cell
MAP_PAD_DEG = 0.4


def render_zone_map(cells: gpd.GeoDataFrame, zones: list[str], title: str, draw_context):
    minx, miny, maxx, maxy = cells.total_bounds
    xlim = (minx - MAP_PAD_DEG, maxx + MAP_PAD_DEG)
    ylim = (miny - MAP_PAD_DEG, maxy + MAP_PAD_DEG)
    n_lon_cells = (xlim[1] - xlim[0]) / GRID_RESOLUTION_DEG
    n_lat_cells = (ylim[1] - ylim[0]) / GRID_RESOLUTION_DEG
    figsize = (max(n_lon_cells * CELL_INCH, 8), max(n_lat_cells * CELL_INCH, 6))

    fig, ax = plt.subplots(figsize=figsize)
    draw_context(ax)

    color_map = dict(zip(zones, CATEGORICAL_COLORS))
    for zone in zones:
        subset = cells[cells["zone_id"] == zone]
        if subset.empty:
            continue
        subset.plot(ax=ax, color=color_map[zone], edgecolor="white", linewidth=0.15, zorder=2)

    boundary_cells = cells[cells["n_nonzero"] > 1]
    handles = [mpatches.Patch(color=color_map[z], label=z) for z in zones]
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=8, ncol=2)
    ax.set_title(f"{title} (n={len(zones)} zones, {len(boundary_cells)} multi-zone cells)")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    fig.tight_layout()
    return fig, boundary_cells


# %%
peon_cells, peon_zones = zone_grid_cells(paths.peon_mask_file)

fig, boundary_cells_peon = render_zone_map(
    peon_cells,
    peon_zones,
    "PEON onshore wind zones",
    draw_context=lambda ax: nuts2.boundary.plot(ax=ax, color="#52514e", linewidth=0.4, zorder=3),
)
fig.savefig(paths.images_path / "11_peon_zone_grid.png", dpi=150, bbox_inches="tight")
plt.show()

print(f"PEON: {len(peon_cells):,} cells total, {len(boundary_cells_peon):,} multi-zone (boundary) cells")

# %% [markdown]
# ```{figure} ../../output/images/11_peon_zone_grid.png
# :name: fig-11-peon-zone-grid
# PECD v4.2's 7 PEON onshore wind zones, as the raw 0.25-degree grid cells
# any capacity-weighting is actually built on (real NUTS2 boundaries in
# gray for context) -- these are a different partition of Germany
# entirely, not NUTS regions grouped together.
# ```

# %%
peof_cells, peof_zones = zone_grid_cells(paths.peof_mask_file)
country_borders = gpd.read_file(paths.country_borders_file)

fig, boundary_cells_peof = render_zone_map(
    peof_cells,
    peof_zones,
    "PEOF offshore wind zones",
    draw_context=lambda ax: country_borders.plot(ax=ax, facecolor="#f2f0ea", edgecolor="#52514e", linewidth=0.5, zorder=1),
)
fig.savefig(paths.images_path / "11_peof_zone_grid.png", dpi=150, bbox_inches="tight")
plt.show()

print(f"PEOF: {len(peof_cells):,} cells total, {len(boundary_cells_peof):,} multi-zone (boundary) cells")

# %% [markdown]
# ```{figure} ../../output/images/11_peof_zone_grid.png
# :name: fig-11-peof-zone-grid
# PECD v4.2's 6 PEOF offshore wind zones -- 5 North Sea sub-zones plus one
# zone covering the entire Baltic Sea -- against neighboring countries'
# coastlines, since offshore has no NUTS region of its own.
# ```

# %% [markdown]
# ## Takeaways
#
# - Solar's NUTS2 resolution is the familiar Eurostat regional breakdown;
#   wind's PEON/PEOF zones are a completely separate, ENTSO-E-defined
#   partition that happens to also tile Germany, but not along NUTS
#   boundaries -- a code-based join between MaStR's NUTS-based region
#   assignment and PECD's wind capacity factors is never possible without
#   the crosswalk mastr-power-capacities-germany already built (which is
#   exactly why this project consumes that project's PEON/PEOF panels
#   directly rather than re-deriving them).
# - PEOF's Baltic zone (`DE02_OFF`) is a single large area; the North Sea
#   is split into 5 finer sub-zones -- a coarser proxy for spatial
#   variation in Baltic offshore wind than the North Sea gets.
