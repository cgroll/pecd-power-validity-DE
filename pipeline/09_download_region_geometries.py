"""Download German NUTS region geometries and neighboring-country outlines.

Pure data acquisition -- no charts. Two public, unauthenticated
Eurostat/GISCO sources:

  - NUTS region geometries (all levels), Germany only -- for a plain map
    of NUTS2 (the resolution PECD publishes solar capacity factors at).
  - Country-level (LEVL_CODE 0) outlines for Germany and its North/Baltic
    Sea neighbors, for map context around the offshore wind zones (which
    sit in international/German waters, outside any NUTS region).

This is a lightweight, standalone download of plain public geometry data
(no MaStR-derived logic involved), so it's rebuilt here rather than
consumed from a sibling project -- unlike this project's actual capacity
panels (see pipeline/07_fetch_external_capacity_panels.py). Pattern
adapted from mastr-power-capacities-germany/pipeline/02_download_nuts.py,
trimmed to just the geometries (this project doesn't need the LAU-NUTS3
municipality crosswalk, which is only relevant to MaStR's own raw-unit
region assignment).
"""

import geopandas as gpd

from pkg.paths import ProjPaths

paths = ProjPaths()
paths.ensure_directories()

NUTS_URL = (
    "https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/"
    "NUTS_RG_01M_2024_4326.geojson"
)
NEIGHBOR_COUNTRIES = ["DE", "NL", "BE", "DK", "PL", "SE", "LU"]

nuts = gpd.read_file(NUTS_URL)

nuts_de = nuts[nuts["CNTR_CODE"] == "DE"][
    ["NUTS_ID", "LEVL_CODE", "NUTS_NAME", "NAME_LATN", "geometry"]
].reset_index(drop=True)
nuts_de.to_file(paths.nuts_regions_file, driver="GeoJSON")
print(f"Saved {len(nuts_de):,} NUTS regions (levels 0-3) -> {paths.nuts_regions_file}")

country_borders = nuts[(nuts["LEVL_CODE"] == 0) & (nuts["CNTR_CODE"].isin(NEIGHBOR_COUNTRIES))][
    ["CNTR_CODE", "NAME_LATN", "geometry"]
].reset_index(drop=True)
country_borders.to_file(paths.country_borders_file, driver="GeoJSON")
print(f"Saved {len(country_borders):,} country outlines -> {paths.country_borders_file}")
