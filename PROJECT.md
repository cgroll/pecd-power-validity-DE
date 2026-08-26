# Project State

Tracks the current state, roadmap, and lessons learned for this project.
See [AGENTS.md](AGENTS.md) for structure/tooling conventions.

## Current State

Scoped, not yet implemented (as of 2026-08-26). See [README.md](README.md)
for the full problem statement. In short: this project checks how well
PECD's **official** capacity-factor product, weighted by MaStR installed
capacity, reconstructs Germany's actual renewable power output — and
quantifies the gap to SMARD's reported generation via known intermediate
mechanisms (unavailability, negative-price curtailment, congestion
curtailment/redispatch), rather than treating the gap as unexplained
error. It deliberately does **not** attempt to replicate PECD's own
methodology from ERA5 weather data — that is
[pecd-replication](https://github.com/cgroll/pecd-replication)'s job, and
this project consumes PECD's official product as a given input instead.

`pkg/` still has the template placeholder — `init_project.py` (package
abbreviation) has not been run yet.

## Roadmap — data pipeline

**Acquisition**

1. `01_download_pecd_capacity_factors.py` — official PECD v4.2 capacity
   factors: solar PV (NUTS2, technology 60/61/62/63 — industrial rooftop,
   residential rooftop, utility fixed, utility tracker), wind onshore
   (PEON zones, technology 30, "existing technologies"), wind offshore
   (PEOF zones, technology 20), full 2015-2025 history. Pattern:
   `pecd-replication/pipeline/16_download_pecd_capacity_factors.py`
   (`cdsapi`, dataset `sis-energy-pecd`). Requires a `~/.cdsapirc` key.
2. `02_fetch_mastr_capacity_panels.py` — consume
   `mastr-power-capacities-germany`'s already-built, already-crosswalked
   processed panels directly rather than re-deriving from raw MaStR:
   `capacity_by_nuts2_month.parquet`, `capacity_by_peon_month.parquet`,
   `capacity_by_peof_month.parquet`, `capacity_by_offshore_month.parquet`.
3. `03_download_smard.py` — hourly DE-LU net generation (solar, wind
   onshore, wind offshore), load, and day-ahead price (needed for the
   negative-price curtailment step below). Pattern:
   `pecd-replication/pipeline/13_download_smard.py`.
4. `04_download_smard_capacities.py` — SMARD's own monthly installed
   capacities (national, per technology) as an independent cross-check
   against MaStR's figures.
5. `05_download_redispatch_by_source.py` — SMARD's monthly
   redispatch-by-energy-source series (curtailment volume by carrier,
   available from 2022-07). Pattern:
   `pecd-replication/pipeline/43_download_redispatch_by_source.py`.
6. `06_download_redispatch_measures.py` — netztransparenz.de's per-measure
   Redispatch export (real timestamps, TSO-attributed, from 2021-01).
   Pattern: `pecd-replication/pipeline/47_download_redispatch_measures.py`.

**Processing / analysis**

7. `07_build_pecd_potential_panel.py` — PECD capacity factor × MaStR
   capacity, per region/technology/month, weighted up to one
   Germany-wide hourly **potential** series per technology (solar, wind
   onshore, wind offshore). This is the "regional capacity factors → one
   national estimate" step.
8. `08_build_target_panel.py` — SMARD generation + price, hourly, aligned
   to the same index as the potential panel.
9. `09_analyse_potential_vs_observed.py` — the headline comparison:
   potential vs. SMARD reported generation, by technology, full period —
   the gap this project exists to explain.
10. `10_analyse_curtailment_gap.py` — how much of the gap each mechanism
    explains: redispatch-sourced congestion curtailment, and negative
    day-ahead price hours (voluntary curtailment).
11. `11_analyse_remaining_gap.py` — what's left after both mechanisms
    (behind-the-meter self-consumption for solar, unmodeled
    maintenance/outages, PECD-product-own bias) and what would be needed
    to close it further.

**Open questions**

- Whether to depend on `pecd-replication`'s `pecdr` package (its SMARD /
  CDS / redispatch download functions, which already handle the
  unofficial-SMARD-endpoint and CDS-retry logic) as a path dependency, or
  reimplement thin equivalents here. Decide before writing stages 1, 3, 5,
  6 — reusing avoids duplicating non-trivial API integration code, but
  adds a cross-repo dependency that needs the sibling repo present and
  in sync.
- Whether the congestion-curtailment chapter should be scoped to
  2022-07-onward only (SMARD's redispatch-by-source series' actual
  start), with the negative-price mechanism covering the full period
  instead, or whether the netztransparenz per-measure series (2021-01
  onward) can extend congestion coverage a bit further back.
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
