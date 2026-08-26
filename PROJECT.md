# Project State

Tracks the current state, roadmap, and lessons learned for this project.
See [AGENTS.md](AGENTS.md) for structure/tooling conventions.

## Current State

Data-acquisition pipeline plus a first round of exploratory notebooks
built and verified end-to-end (2026-08-26). See
[README.md](README.md) for the full problem statement. In short: this
project checks how well PECD's **official** capacity-factor product,
weighted by MaStR installed capacity, reconstructs Germany's actual
renewable power output — and quantifies the gap to SMARD's reported
generation via known intermediate mechanisms (unavailability,
negative-price curtailment, congestion curtailment/redispatch), rather
than treating the gap as unexplained error. It deliberately does **not**
attempt to replicate PECD's own methodology from ERA5 weather data — that
is [pecd-replication](https://github.com/cgroll/pecd-replication)'s job,
and this project consumes PECD's official product as a given input
instead.

All 7 acquisition stages (`dvc repro`) run cleanly against live sources —
CDS, SMARD, netztransparenz.de, and the two sibling repos' processed
outputs. Real data now in `data/downloads/`/`data/processed/`:

- PECD v4.2 official capacity factors, hourly, 2015-2025: solar (NUTS2 x
  4 technologies), wind onshore (7 PEON zones), wind offshore (6 PEOF
  zones).
- SMARD hourly generation/load/price, DE-LU: PV and wind onshore from
  2016-12-30; wind offshore, load, and price only from 2018-09-30 (the
  DE-LU market area didn't exist as a separate SMARD region before then —
  confirms the gap flagged in delu-headline-forecast's data-sources doc).
- SMARD monthly installed-capacity series (national cross-check).
- SMARD monthly redispatch-by-source (1,196 rows, 2022-07 to 2026-04) and
  netztransparenz's per-measure redispatch export (16.3 MB CSV, 2021-01
  onward).
- The 5 external capacity panels copied in from
  `mastr-power-capacities-germany` and `pecd-replication` (see below).

`pkg/` still has the template placeholder — `init_project.py` (package
abbreviation) has not been run yet; not blocking, deferred.

## Roadmap — data pipeline

**Acquisition — done, verified against live sources (2026-08-26)**

1. `01_download_pecd_capacity_factors.py` / `02_process_pecd_capacity_factors.py`
   — official PECD v4.2 capacity factors via `cdsapi` (dataset
   `sis-energy-pecd`): solar PV (NUTS2, technology 60/61/62/63 —
   industrial rooftop, residential rooftop, utility fixed, utility
   tracker), wind onshore (PEON zones, technology 30), wind offshore
   (PEOF zones, technology 20), full 2015-2025 history. Each CDS request
   queues server-side for several minutes; budget ~50 min total for a
   clean run of all 6 (solar x4 + wind x2).
2. `03_download_smard.py` — hourly DE-LU net generation (solar, wind
   onshore, wind offshore), load, and day-ahead price (needed for the
   negative-price curtailment step below). Incremental.
3. `04_download_smard_capacities.py` — SMARD's own monthly installed
   capacities (national, per technology) as an independent cross-check
   against MaStR's figures.
4. `05_download_redispatch_by_source.py` — SMARD's monthly
   redispatch-by-energy-source series (curtailment volume by carrier,
   available from 2022-07). Always re-fetched in full (SMARD restates
   recent months).
5. `06_download_redispatch_measures.py` — netztransparenz.de's per-measure
   Redispatch export (real timestamps, TSO-attributed, from 2021-01).
6. `07_fetch_external_capacity_panels.py` — copies 5 already-built,
   already-crosswalked capacity panels in from sibling repos rather than
   re-deriving MaStR's raw-data/region-assignment logic (raw MaStR alone
   is ~12GB): `capacity_by_peon_month.parquet`,
   `capacity_by_peof_month.parquet`, `capacity_by_offshore_month.parquet`,
   `capacity_by_nuts2_month.parquet` from
   `mastr-power-capacities-germany`, plus
   `solar_capacity_by_nuts2_month.parquet` (MaStR capacity crosswalked to
   PECD's 4 solar technology codes — needed to weight the 4 solar CF
   series above, and *not* available from
   `mastr-power-capacities-germany` itself, which splits solar capacity
   by feed-in category instead) from `pecd-replication`. Requires both
   sibling repos cloned alongside this one with their own pipelines
   already run at least once; re-run `dvc repro -f
   fetch_external_capacity_panels` after refreshing them.

Everything else (PECD CDS zips, SMARD, redispatch downloads) is this
project's own standalone code — small enough (SMARD ~5MB, redispatch
~16MB, PECD CF zips ~400MB combined) to rebuild independently rather than
depend on a sibling repo's copy, per the "rebuild it here if it's not
huge" rule of thumb (contrast MaStR's raw feed at ~12GB, genuinely worth
reusing instead).

**Exploratory EDA — done (2026-08-26)**

7. `08_download_pecd_masks.py` / `09_download_region_geometries.py` — two
   small standalone downloads (CDS zone masks, GISCO region geometries)
   feeding the map notebook below; not needed for the actual potential
   calculation, only to visualize what a "zone" or "NUTS2 region" is.
8. `10_eda_data_availability.py` — monthly presence heatmap across all 18
   downloaded series. Confirms the real binding constraint: the usable
   backtest window is set by SMARD's DE-LU history (wind offshore/load/
   price only from 2018-09), not by PECD's or MaStR's own 2015+ coverage.
9. `11_eda_region_maps.py` — Germany's NUTS2 regions (solar's PECD
   resolution) plus the PEON/PEOF wind zones as raw grid cells (adapted
   from `mastr-power-capacities-germany`'s own zone EDA). Makes concrete
   that PEON/PEOF is a wholly separate ENTSO-E partition, not a NUTS
   grouping.
10. `12_eda_redispatch_comparison.py` — SMARD's monthly
    redispatch-by-source vs. netztransparenz's per-measure export.
    Offshore wind matches almost exactly (100.0%) since netztransparenz
    names offshore farms individually; onshore wind + PV only reaches
    39.2% of SMARD's figure when counted via
    `primary_energy_type=="Erneuerbar"` (vs. 1.7% if restricted to
    measures individually name-attributable to a technology) — consistent
    with `pecd-replication`'s own finding (38.7%) on the same comparison.
    Deliberately stops short of `pecd-replication`'s own statistical
    entity-attribution step (`pipeline/46`); flagged as reusable later if
    the gap-explanation chapters need a finer split.

**Processing / analysis — not yet started**

11. `13_build_pecd_potential_panel.py` — PECD capacity factor × capacity,
    per region/technology/month, weighted up to one Germany-wide hourly
    **potential** series per technology (solar, wind onshore, wind
    offshore). This is the "regional capacity factors → one national
    estimate" step. Solar needs a (NUTS2 x PECD-technology) weighted sum
    across all 4 sub-series; wind onshore/offshore are a straight
    (PEON/PEOF-zone x month) weighted sum — zone codes already match
    PECD's own column names on both sides.
12. `14_build_target_panel.py` — SMARD generation + price, hourly, aligned
    to the same index as the potential panel.
13. `15_analyse_potential_vs_observed.py` — the headline comparison:
    potential vs. SMARD reported generation, by technology, full period —
    the gap this project exists to explain.
14. `16_analyse_curtailment_gap.py` — how much of the gap each mechanism
    explains: redispatch-sourced congestion curtailment, and negative
    day-ahead price hours (voluntary curtailment).
15. `17_analyse_remaining_gap.py` — what's left after both mechanisms
    (behind-the-meter self-consumption for solar, unmodeled
    maintenance/outages, PECD-product-own bias) and what would be needed
    to close it further.

**Open questions**

- Whether the congestion-curtailment chapter should be scoped to
  2022-07-onward only (SMARD's redispatch-by-source series' actual
  start), with the negative-price mechanism covering the full period
  instead, or whether the netztransparenz per-measure series (2021-01
  onward) can extend congestion coverage a bit further back.
- The overall usable backtest window is bounded by SMARD's DE-LU wind
  offshore/load/price history (2018-09-30 onward), not PECD's or MaStR's
  own (both cover 2015+) — confirm this is an acceptable window before
  building the potential/target comparison.
- Package abbreviation for `init_project.py` — not yet decided/run.

## Lessons Learned

### 2026-08-26 — Project scoped

- Surveyed `pecd-replication`, `mastr-power-capacities-germany`, and
  `delu-headline-forecast`. `pecd-replication` already computes almost
  everything this project's phase 1 needs — a "PECD official × MaStR"
  comparison against SMARD, plus a full congestion/curtailment/
  residual-load analysis (its book chapters "Congestion & curtailment"
  and "Residual load") — but only as one output of a much larger project
  whose main effort is replicating PECD's own methodology from ERA5. This
  project deliberately narrows to just the official-product validity
  question, dropping the ERA5/GWA/per-plant-physics replication entirely,
  and is meant to consume processed outputs from the sibling projects
  rather than re-deriving them — following the established convention in
  this project family (see `delu-headline-forecast`'s
  `docs/data_sources.md`, which already consumes
  `mastr-power-capacities-germany`'s processed panels the same way).

### 2026-08-26 — Acquisition pipeline built standalone, MaStR reused

- Decided (per direct user guidance): rebuild anything that isn't huge
  standalone in this repo — PECD capacity factors, SMARD, and both
  redispatch sources are all small/medium downloads (a few MB to a few
  hundred MB) with self-contained, previously-validated download code in
  `pecd-replication`'s `pecdr` package, so that code was ported into this
  project's own `pkg/` (`cds.py`, `pecd_io.py`, `smard.py`,
  `smard_redispatch.py`, `redispatch_measures.py`) rather than adding a
  cross-repo dependency on `pecdr` itself.
- MaStR is the one exception: raw MaStR alone is ~12GB and region
  assignment (offshore pseudo-regions, fractional PEON/PEOF splitting via
  PECD's own rasterized masks, solar's near-total lack of coordinates) is
  substantial, already-validated logic — reused directly by copying
  `mastr-power-capacities-germany`'s processed panels
  (`pipeline/07_fetch_external_capacity_panels.py`).
- One nuance worth flagging explicitly (the user suspected there might be
  one): the *solar* weighting input isn't purely a MaStR product.
  `mastr-power-capacities-germany`'s own NUTS2 panel splits solar capacity
  by MaStR's feed-in/self-consumption category, not by PECD's 4 technology
  codes (industrial/residential rooftop, utility fixed/tracking) — the
  split actually needed to weight PECD's 4 solar CF sub-series. That
  technology crosswalk is built in `pecd-replication` instead
  (`pipeline/24_build_solar_capacity_by_nuts2_month.py`, needs additional
  raw MaStR technical fields — panel orientation/tilt — that
  `mastr-power-capacities-germany` doesn't expose), so this project
  consumes `pecd-replication`'s `solar_capacity_by_nuts2_month.parquet` for
  solar rather than `mastr-power-capacities-germany`'s own NUTS2 file.
- All 7 acquisition stages tested end-to-end against live sources, not
  just dry-run: `dvc repro` is a clean, reproducible pipeline as of this
  writing. Full PECD CF download took ~50 minutes wall-clock (CDS
  server-side queueing, not this project's bottleneck).

### 2026-08-26 — `pkg/paths.py` deliberately not tracked as a DVC dep

- User asked directly whether `pkg/paths.py` is listed as a `deps:` entry
  anywhere in `dvc.yaml` (worried that a shared, ever-growing file would
  retrigger every stage on any unrelated edit). Checked: it already isn't,
  anywhere — only the narrower logic modules (`cds.py`, `smard.py`,
  `pecd_io.py`, `smard_redispatch.py`, `redispatch_measures.py`) are
  tracked as deps, matching `mastr-power-capacities-germany`'s convention
  (`pecd-replication` is inconsistent here — it lists `pecdr/paths.py` as
  a dep on its analysis/notebook stages, not its acquisition ones,
  needlessly invalidating those notebook stages' cache on any unrelated
  path addition). Keep it this way: `paths.py` stays pure path
  construction with no data-transformation logic, so leaving it untracked
  is safe — if it ever needs real logic, that logic belongs in its own
  module (same pattern as the existing ones), not inline in `paths.py`.

### 2026-08-26 — First EDA pass surfaced one real correction

- Initially computed netztransparenz's "how much of SMARD's onshore
  wind + PV redispatch figure is captured" using only individually
  name-attributable measures (`onshore_wind_named` + `pv`), getting 1.7%
  — technically correct for that narrow question, but a misleading
  headline number on its own, since it silently excluded real renewable
  volume sitting under anonymous cluster codes. Fixed by also computing
  the broader `primary_energy_type == "Erneuerbar"` (minus offshore) sum,
  which reproduces `pecd-replication`'s own 38.7% finding almost exactly
  (39.2% here) — the notebook now reports both numbers side by side so
  the distinction itself is visible, not just the corrected total.
