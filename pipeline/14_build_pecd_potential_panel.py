"""Build the Germany-wide hourly PECD potential panel.

Pure data processing -- no charts. This is the core "regional capacity
factors x regional capacity -> one national estimate" step described in
the README: for each hour, each region's PECD capacity factor times that
region's MaStR-derived installed capacity that month gives that region's
contribution to potential output; summed over regions (and, for solar,
PECD's 4 technology sub-types), that's one Germany-wide hourly potential
series per technology.

Solar's capacity is keyed by (NUTS2 region, PECD technology); wind
onshore/offshore by (PEON/PEOF zone) only, since PECD publishes only one
"existing technologies" wind capacity factor per zone (no technology
split for wind the way solar has 4 sub-types).
"""

import pandas as pd

from pkg.paths import ProjPaths
from pkg.potential import compute_potential, unmodeled_capacity_share

paths = ProjPaths()
paths.ensure_directories()

# --- Solar: (technology, NUTS2 region) columns on both sides ---
solar_cf = pd.read_parquet(paths.pecd_solar_capacity_factors_file)

solar_capacity_long = pd.read_parquet(paths.solar_capacity_by_nuts2_month_file)
solar_capacity_wide = solar_capacity_long.pivot_table(
    index="month", columns=["pecd_technology", "nuts2_region"], values="capacity_mw", fill_value=0.0
)
solar_capacity_wide.columns = solar_capacity_wide.columns.set_names(solar_cf.columns.names)

potential_solar = compute_potential(solar_cf, solar_capacity_wide)
print(f"Solar potential: {len(potential_solar):,} hours, mean {potential_solar.mean():,.0f} MW, max {potential_solar.max():,.0f} MW")

# --- Wind onshore: PEON zone columns on both sides ---
wind_onshore_cf = pd.read_parquet(paths.pecd_wind_onshore_capacity_factors_file)

peon_capacity_long = pd.read_parquet(paths.capacity_by_peon_month_file)
peon_capacity_wide = peon_capacity_long.pivot(index="month", columns="region_code", values="capacity_mw")

potential_wind_onshore = compute_potential(wind_onshore_cf, peon_capacity_wide)
print(f"Wind onshore potential: {len(potential_wind_onshore):,} hours, mean {potential_wind_onshore.mean():,.0f} MW, max {potential_wind_onshore.max():,.0f} MW")

# --- Wind offshore: PEOF zone columns on both sides ---
wind_offshore_cf = pd.read_parquet(paths.pecd_wind_offshore_capacity_factors_file)

peof_capacity_long = pd.read_parquet(paths.capacity_by_peof_month_file)
peof_capacity_wide = peof_capacity_long.pivot(index="month", columns="region_code", values="capacity_mw")

potential_wind_offshore = compute_potential(wind_offshore_cf, peof_capacity_wide)
print(f"Wind offshore potential: {len(potential_wind_offshore):,} hours, mean {potential_wind_offshore.mean():,.0f} MW, max {potential_wind_offshore.max():,.0f} MW")

unmodeled = unmodeled_capacity_share(wind_offshore_cf, peof_capacity_wide)
if not unmodeled.empty:
    print(f"  NOTE: PECD never modeled {list(unmodeled.index)} (100% NaN capacity factor) --")
    print(f"  excluded from the sum above rather than poisoning it; mean capacity there: {unmodeled.to_dict()} MW")

# --- Combine and save ---
potential_panel = pd.DataFrame({
    "potential_solar_mw": potential_solar,
    "potential_wind_onshore_mw": potential_wind_onshore,
    "potential_wind_offshore_mw": potential_wind_offshore,
})
potential_panel.index.name = "timestamp"
potential_panel.to_parquet(paths.pecd_potential_panel_file)
print(f"\nSaved {potential_panel.shape} -> {paths.pecd_potential_panel_file}")
print(f"Period: {potential_panel.index.min()} .. {potential_panel.index.max()}")
