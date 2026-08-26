"""Project paths configuration.

All paths are resolved relative to the project root, making scripts runnable
from any working directory. Add a @property for each new data file introduced
in the pipeline.
"""

from pathlib import Path


class ProjPaths:
    """Centralized project paths.

    The root is inferred from the location of this file (pkg/), so scripts
    run correctly regardless of the working directory they are invoked from.
    """

    def __init__(self):
        self._pkg_path = Path(__file__).resolve().parent  # pkg/
        self._project_path = self._pkg_path.parent        # project root

    # ------------------------------------------------------------------ #
    # Top-level directories                                                #
    # ------------------------------------------------------------------ #

    @property
    def project_path(self) -> Path:
        """Root project directory."""
        return self._project_path

    @property
    def pkg_path(self) -> Path:
        """Source package directory (pkg/)."""
        return self._pkg_path

    @property
    def pipeline_path(self) -> Path:
        """Pipeline scripts directory."""
        return self._project_path / "pipeline"

    # ------------------------------------------------------------------ #
    # Data directories                                                     #
    # ------------------------------------------------------------------ #

    @property
    def data_path(self) -> Path:
        """Main data directory."""
        return self._project_path / "data"

    @property
    def downloads_path(self) -> Path:
        """Raw downloaded data."""
        return self.data_path / "downloads"

    @property
    def processed_data_path(self) -> Path:
        """Processed/transformed data."""
        return self.data_path / "processed"

    # ------------------------------------------------------------------ #
    # Output directories                                                   #
    # ------------------------------------------------------------------ #

    @property
    def output_path(self) -> Path:
        """Generated outputs root."""
        return self._project_path / "output"

    @property
    def images_path(self) -> Path:
        """Chart/figure images saved by pipeline scripts."""
        return self.output_path / "images"

    @property
    def reports_path(self) -> Path:
        """Report files."""
        return self.output_path / "reports"

    # ------------------------------------------------------------------ #
    # External sibling-project inputs                                      #
    # ------------------------------------------------------------------ #
    #
    # This project deliberately does not re-derive MaStR's region
    # assignment/crosswalk logic (raw MaStR download alone is ~12GB, plus
    # substantial region-matching logic) -- it consumes the already-built,
    # already-crosswalked processed panels from the sibling projects that
    # own that logic. See PROJECT.md for the reasoning. These absolute
    # paths only resolve on a machine with both sibling repos cloned as
    # siblings of this one; `pipeline/07_fetch_external_capacity_panels.py`
    # copies them into `data/downloads/external/` so everything downstream
    # only ever reads from within this repo.

    @property
    def mastr_project_path(self) -> Path:
        """Root of the sibling mastr-power-capacities-germany checkout."""
        return self._project_path.parent / "mastr-power-capacities-germany"

    @property
    def pecd_replication_project_path(self) -> Path:
        """Root of the sibling pecd-replication checkout."""
        return self._project_path.parent / "pecd-replication"

    @property
    def external_mastr_capacity_by_peon_month_source(self) -> Path:
        """Monthly onshore-wind installed capacity by PEON zone, as built by
        mastr-power-capacities-germany's `pipeline/07_build_wind_zone_panel.py`
        (fractional per-zone split via PECD's own rasterized region mask).
        """
        return self.mastr_project_path / "data" / "processed" / "capacity_by_peon_month.parquet"

    @property
    def external_mastr_capacity_by_peof_month_source(self) -> Path:
        """Monthly offshore-wind installed capacity by PEOF zone, same
        project/method as `external_mastr_capacity_by_peon_month_source`.
        """
        return self.mastr_project_path / "data" / "processed" / "capacity_by_peof_month.parquet"

    @property
    def external_mastr_capacity_by_offshore_month_source(self) -> Path:
        """Monthly offshore-wind capacity by the two North Sea/Baltic Sea
        pseudo-regions (`DEZZ-NORDSEE`/`DEZZ-OSTSEE`) -- reference/
        cross-check only, PEOF is the primary offshore weighting input.
        """
        return self.mastr_project_path / "data" / "processed" / "capacity_by_offshore_month.parquet"

    @property
    def external_mastr_capacity_by_nuts2_month_source(self) -> Path:
        """Monthly solar+onshore-wind capacity by NUTS2 region, split by
        MaStR's own behind-the-meter feed-in category (not PECD's
        technology codes) -- reference/cross-check only; see
        `external_pecd_replication_solar_capacity_by_nuts2_month_source`
        for the technology-coded panel actually used to weight PECD's
        solar capacity factors.
        """
        return self.mastr_project_path / "data" / "processed" / "capacity_by_nuts2_month.parquet"

    @property
    def external_pecd_replication_solar_capacity_by_nuts2_month_source(self) -> Path:
        """Monthly solar capacity by NUTS2 region x PECD's 4 technology
        codes (60/61/62/63), as built by pecd-replication's
        `pipeline/24_build_solar_capacity_by_nuts2_month.py`. Not
        available from mastr-power-capacities-germany directly -- that
        project's own NUTS2 panel splits by feed-in category instead, and
        pecd-replication's build needs additional raw MaStR technical
        fields (panel orientation/tilt) that aren't in the sibling
        project's own output, so this is consumed as its own external
        input rather than rebuilt here too.
        """
        return self.pecd_replication_project_path / "data" / "processed" / "solar_capacity_by_nuts2_month.parquet"

    @property
    def external_capacity_downloads_path(self) -> Path:
        """Local copies of the external capacity panels above."""
        return self.downloads_path / "external"

    @property
    def capacity_by_peon_month_file(self) -> Path:
        """Local copy of `external_mastr_capacity_by_peon_month_source`."""
        return self.external_capacity_downloads_path / "capacity_by_peon_month.parquet"

    @property
    def capacity_by_peof_month_file(self) -> Path:
        """Local copy of `external_mastr_capacity_by_peof_month_source`."""
        return self.external_capacity_downloads_path / "capacity_by_peof_month.parquet"

    @property
    def capacity_by_offshore_month_file(self) -> Path:
        """Local copy of `external_mastr_capacity_by_offshore_month_source`."""
        return self.external_capacity_downloads_path / "capacity_by_offshore_month.parquet"

    @property
    def capacity_by_nuts2_month_file(self) -> Path:
        """Local copy of `external_mastr_capacity_by_nuts2_month_source`."""
        return self.external_capacity_downloads_path / "capacity_by_nuts2_month.parquet"

    @property
    def solar_capacity_by_nuts2_month_file(self) -> Path:
        """Local copy of
        `external_pecd_replication_solar_capacity_by_nuts2_month_source`.
        """
        return self.external_capacity_downloads_path / "solar_capacity_by_nuts2_month.parquet"

    # ------------------------------------------------------------------ #
    # PECD v4.2 capacity factors (official product)                       #
    # ------------------------------------------------------------------ #

    @property
    def pecd_downloads_path(self) -> Path:
        """Directory for raw PECD CDS downloads."""
        return self.downloads_path / "pecd"

    def pecd_capacity_factor_zip(self, kind: str, technology: str) -> Path:
        """Raw PECD capacity-factor download, all of Europe, 2015-2025, one
        file per (kind, technology). `kind` is one of "solar",
        "wind_onshore", "wind_offshore"; `technology` is PECD's technology
        code (e.g. "60" for solar industrial rooftop, "30" for existing
        onshore wind). See `pipeline/01_download_pecd_capacity_factors.py`.
        """
        return self.pecd_downloads_path / f"pecd_{kind}_tech{technology}.zip"

    @property
    def pecd_solar_capacity_factors_file(self) -> Path:
        """PECD solar PV capacity factor, Germany-only, hourly, 2015-2025.

        MultiIndex columns (technology, region): 4 solar sub-types
        (60/61/62/63) x ~38 DE NUTS2 regions. See
        `pipeline/02_process_pecd_capacity_factors.py`.
        """
        return self.processed_data_path / "pecd_solar_capacity_factors.parquet"

    @property
    def pecd_wind_onshore_capacity_factors_file(self) -> Path:
        """PECD wind-onshore capacity factor, Germany-only, hourly,
        2015-2025, columns = 7 PEON zones (DE01-DE07).
        """
        return self.processed_data_path / "pecd_wind_onshore_capacity_factors.parquet"

    @property
    def pecd_wind_offshore_capacity_factors_file(self) -> Path:
        """PECD wind-offshore capacity factor, Germany-only, hourly,
        2015-2025, columns = PEOF zones (DE0xx_OFF) -- codes already match
        the external MaStR PEOF panel's `region_code`.
        """
        return self.processed_data_path / "pecd_wind_offshore_capacity_factors.parquet"

    @property
    def peon_mask_file(self) -> Path:
        """PECD v4.2 PEON (onshore wind zone) rasterized region mask, all of
        Europe: fractional 0.25-degree grid-cell coverage per zone. See
        `pipeline/08_download_pecd_masks.py`.
        """
        return self.pecd_downloads_path / "peon_region_mask.nc"

    @property
    def peof_mask_file(self) -> Path:
        """PECD v4.2 PEOF (offshore wind zone) rasterized region mask, same
        structure as `peon_mask_file`.
        """
        return self.pecd_downloads_path / "peof_region_mask.nc"

    # ------------------------------------------------------------------ #
    # Region geometries (Eurostat/GISCO)                                   #
    # ------------------------------------------------------------------ #

    @property
    def nuts_regions_file(self) -> Path:
        """German NUTS region geometries (levels 0-3), GeoJSON. See
        `pipeline/09_download_region_geometries.py`.
        """
        return self.downloads_path / "nuts_regions.geojson"

    @property
    def country_borders_file(self) -> Path:
        """Country-level (LEVL_CODE 0) outlines for Germany and its
        North/Baltic Sea neighbors, for map context around offshore wind
        zones. See `pipeline/09_download_region_geometries.py`.
        """
        return self.downloads_path / "country_borders.geojson"

    # ------------------------------------------------------------------ #
    # SMARD (Bundesnetzagentur)                                            #
    # ------------------------------------------------------------------ #

    @property
    def smard_downloads_path(self) -> Path:
        """Directory for raw SMARD downloads."""
        return self.downloads_path / "smard"

    def smard_raw_file(self, name: str) -> Path:
        """Raw hourly SMARD series parquet.

        `name` is one of: pv, wind_onshore, wind_offshore, load,
        price_de_lu.
        """
        return self.smard_downloads_path / f"{name}.parquet"

    def smard_capacity_file(self, name: str) -> Path:
        """Raw monthly SMARD installed-capacity series parquet.

        `name` is one of: solar, wind_onshore, wind_offshore -- a
        national, independent cross-check against the MaStR-derived
        capacity panels above.
        """
        return self.smard_downloads_path / f"capacity_{name}.parquet"

    @property
    def redispatch_by_source_file(self) -> Path:
        """Monthly SMARD redispatch-by-energy-source parquet (tidy: month,
        direction, energy_source, gwh), since 2022-07. See
        `pkg/smard_redispatch.py` and
        `pipeline/05_download_redispatch_by_source.py`.
        """
        return self.smard_downloads_path / "redispatch_by_source.parquet"

    # ------------------------------------------------------------------ #
    # netztransparenz.de                                                   #
    # ------------------------------------------------------------------ #

    @property
    def netztransparenz_downloads_path(self) -> Path:
        """Directory for raw netztransparenz.de downloads."""
        return self.downloads_path / "netztransparenz"

    @property
    def redispatch_measures_file(self) -> Path:
        """Per-measure Redispatch export (Format 5), raw CSV: one row per
        redispatch measure, with start/end time, direction, MW/MWh,
        affected plant name, and primary energy type, since 2021-01. See
        `pkg/redispatch_measures.py` and
        `pipeline/06_download_redispatch_measures.py`.
        """
        return self.netztransparenz_downloads_path / "redispatch_measures.csv"

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def ensure_directories(self) -> None:
        """Create all standard directories if they do not yet exist."""
        dirs = [
            self.downloads_path,
            self.processed_data_path,
            self.images_path,
            self.reports_path,
            self.pecd_downloads_path,
            self.smard_downloads_path,
            self.netztransparenz_downloads_path,
            self.external_capacity_downloads_path,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
