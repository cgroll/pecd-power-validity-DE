# PECD Power Validity DE

How much of Germany's actual wind and solar power output can be
reconstructed from PECD's **official** capacity factors and the
Marktstammdatenregister (MaStR) installed-capacity register — and where
does that reconstruction structurally have to fall short of what SMARD
reports as generated?

This project does **not** replicate PECD's own capacity-factor methodology
from weather data — that is
[pecd-replication](https://github.com/cgroll/pecd-replication)'s job. It
takes PECD's official product as given and asks a narrower question:
capacity factor × installed capacity gives a **potential** output — how
far is that from what SMARD reports was actually produced, and can the
gap be explained by known intermediate mechanisms (maintenance/outage
unavailability, price-driven curtailment at negative prices, and
grid-congestion curtailment/redispatch) rather than left as unexplained
noise?

## Current status

The full planned analysis chain is built: PECD potential vs. SMARD
observed generation, then decomposing the gap between them by known
mechanism, 2019-2025 (the window `pecd-replication` also uses):

| Technology | Potential-vs-observed (nMAE / corr) | Redispatch-explained share of gap | After subtracting redispatch (nMAE) |
|---|---|---|---|
| Solar | 17.7% / 0.981 | 11.2% | 19.0% (barely moves) |
| Wind onshore | 13.9% / 0.986 | 33.3% | 6.7% |
| Wind offshore | 24.8% / 0.902 | 70.7% | 8.0% |

(`nMAE` = mean absolute error relative to that technology's own mean
observed output; the capacity-factor-normalized accuracy numbers land
within rounding distance of `pecd-replication`'s own published table — a
real cross-project validation, since this project's potential panel is
built by an entirely separate pipeline. The "after redispatch" column is
monthly, matching SMARD's own resolution — redoing it at native **hourly**
resolution for offshore, using netztransparenz's per-measure export
instead, gives a materially more modest improvement (27.9% → 18.3%, not
24.5% → 8.0%): monthly aggregation smooths away hour-to-hour timing
mismatches and flatters how much redispatch actually fixes.)

Redispatch curtailment explains most of wind offshore's gap, a third of
onshore's, but little of solar's — solar's own remaining gap (89% of it)
lines up plausibly with behind-the-meter self-consumption capability
(~44% of national solar capacity is registered self-consumption-capable),
though that's a plausibility argument from capacity shares, not a direct
measurement. Wind offshore's own residual, unexpectedly, *grows* over
2022-2025 rather than shrinking as redispatch reporting matures — a
genuinely open pattern, not resolved here. See the book (once published)
for the full notebook-by-notebook detail and [PROJECT.md](PROJECT.md) for
the running log of what was checked and found along the way.

## The core problem: potential ≠ observed generation

PECD capacity factor × MaStR installed capacity is **not** directly
comparable to SMARD's reported generation. Several real, non-trivial
steps sit between "theoretical potential" and "SMARD's after-redispatch
generation":

```
PECD capacity factor × MaStR installed capacity     (potential)
  − unavailable capacity (maintenance / outages)
  − voluntary curtailment (negative day-ahead prices)
  − congestion curtailment (redispatch instructions)
  = generation actually fed into the grid              (pre-redispatch)
  ± redispatch                                          (SMARD reports *after* redispatch)
  = SMARD reported net generation
```

Comparing PECD potential directly against SMARD without accounting for
this chain over- or understates how good PECD's product actually is at
describing the real market. This project's job is to make the chain
explicit and quantify each step, not to close the gap by any means
necessary — some of it (behind-the-meter self-consumption, unattributed
outages) may simply not be closable with public data.

## Building a Germany-wide estimate from regional capacity factors

PECD v4.2 publishes capacity factors at different spatial resolutions per
technology — solar PV at NUTS2, wind onshore at PEON zones (7 for
Germany), wind offshore at PEOF zones (6 for Germany, none of them NUTS
codes). None of these line up with MaStR's own region codes without a
crosswalk. Getting one Germany-wide potential number means:

1. A capacity panel keyed by the *same* regions PECD publishes for that
   technology (NUTS2 for solar, PEON for onshore wind, PEOF for offshore
   wind), built from MaStR. See
   [mastr-power-capacities-germany](https://github.com/cgroll/mastr-power-capacities-germany),
   which already builds this crosswalk — via PECD's own rasterized region
   masks, since neither zone scheme's polygons are published directly —
   and maintains it as a monthly panel.
2. Weighting each region's capacity factor by its month's installed
   capacity and summing across regions to one national hourly potential
   series per technology.

## Data sources

| Source | What we get | Built |
|---|---|---|
| **PECD v4.2** (Copernicus CDS) | Official hourly capacity factors: solar PV (NUTS2, 4 technology sub-classes), wind onshore (PEON), wind offshore (PEOF) | Standalone in this repo (`pipeline/01`-`02`, `pkg/cds.py`) — pattern adapted from [pecd-replication](https://github.com/cgroll/pecd-replication) |
| **MaStR** | Installed capacity by NUTS2 / PEON / PEOF / offshore pseudo-region, monthly | Consumed directly from [mastr-power-capacities-germany](https://github.com/cgroll/mastr-power-capacities-germany) and (for solar's PECD-technology split) [pecd-replication](https://github.com/cgroll/pecd-replication) — not re-derived (`pipeline/07`) |
| **SMARD** (Bundesnetzagentur) | Hourly DE-LU net generation (solar, wind onshore, wind offshore), load, day-ahead price; monthly installed capacities | Standalone in this repo (`pipeline/03`-`04`, `pkg/smard.py`) |
| **Redispatch / congestion** | SMARD's monthly redispatch-by-source (since 2022-07); netztransparenz.de's per-measure redispatch export (since 2021-01) | Standalone in this repo (`pipeline/05`-`06`, `pkg/smard_redispatch.py`, `pkg/redispatch_measures.py`) |

See [PROJECT.md](PROJECT.md) for the full pipeline stage list and open
questions.

## Running it

```bash
# Install uv if you haven't already — https://docs.astral.sh/uv/
curl -LsSf https://astral.sh/uv/install.sh | sh

uv sync
```

```bash
make dry-run   # preview what would run
make run       # execute the pipeline (dvc repro)
make serve     # open http://localhost:3000 — live book preview
```

## Project layout

```
project-root/
├── pkg/                  # Python package — shared utilities (pending rename, see PROJECT.md)
│   └── paths.py          # Centralized path config
├── pipeline/             # Pipeline scripts
│   ├── 01_download_*     # Data acquisition
│   └── 02_analyse_*      # Analysis → notebook
├── book/                 # MyST book source
│   ├── notebooks/        # Executed notebooks (DVC output)
│   ├── markdown/         # Static content
│   └── myst.yml          # TOC and site settings
├── data/                 # Git-ignored data (cached by DVC)
├── output/images/        # Figures (tracked in git)
├── dvc.yaml              # Pipeline DAG
├── dvc.lock              # Pipeline state (checksums) — tracked in git
├── AGENTS.md              # Detailed conventions for contributors/AI
└── PROJECT.md            # Current state, roadmap, lessons learned
```

See [AGENTS.md](AGENTS.md) for full details on adding pipeline stages,
writing analysis scripts, and DVC usage.

## Common DVC commands

| Command | Effect |
|---------|--------|
| `dvc repro --dry` | Dry run — show what would execute |
| `dvc repro` | Run pipeline (only rebuilds what's out of date) |
| `dvc repro -f <stage>` | Force-re-run a specific stage |
| `dvc repro <stage>` | Build one specific stage (and its dependencies) |
| `dvc repro --force` | Re-run everything unconditionally |
| `dvc dag` | Print the pipeline DAG |
