---
title: Welcome
---

# PECD Power Validity DE

How much of Germany's actual wind and solar power output can be
reconstructed from PECD's **official** capacity factors and the
Marktstammdatenregister (MaStR) installed-capacity register — and where
does that reconstruction structurally have to fall short of what SMARD
reports as generated?

## What this project is (and isn't)

This is **not** an attempt to replicate PECD's own capacity-factor
methodology from weather data — that is a much larger, separate
undertaking (see
[pecd-replication](https://github.com/cgroll/pecd-replication)). Here,
PECD's official product is taken as given. The question is narrower:
capacity factor × installed capacity gives a **potential** output — how
far is that from what SMARD reports as actually produced, and can the
gap be explained by known, named mechanisms rather than left as
unexplained noise?

## The core problem: potential is not observed generation

PECD capacity factor × MaStR installed capacity is not directly
comparable to SMARD's reported generation. Several real steps sit between
"theoretical potential" and "SMARD's after-redispatch generation":

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
describing the real market. This project makes the chain explicit and
quantifies each step it can — some of it (behind-the-meter
self-consumption, unattributed plant outages) may simply not be closable
from public data, and that's a finding in itself, not a gap to paper over.

## From regional capacity factors to one national number

PECD v4.2 publishes capacity factors at a different spatial resolution
per technology: solar PV at NUTS2, wind onshore at PEON zones (7 for
Germany), wind offshore at PEOF zones (6 for Germany — none of them NUTS
codes). None of these line up with MaStR's own region codes without a
crosswalk. Getting one Germany-wide potential series means building a
capacity panel keyed by the *same* regions PECD uses for each technology,
then weighting each region's capacity factor by its month's installed
capacity and summing across regions.

## How to read this book

The chapters are structured as executed notebooks, one per pipeline
script in `pipeline/`, run via DVC. See [PROJECT.md](../../PROJECT.md) in
the repository root for the current pipeline roadmap and open questions.
