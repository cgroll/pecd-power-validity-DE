"""Fetch installed-capacity panels from sibling projects, unchanged.

Pure data acquisition -- no charts, no transformation. This project
deliberately does not re-derive MaStR's region assignment/crosswalk logic:
the raw MaStR bulk download alone is ~12GB, and correctly assigning each
unit to a NUTS/PEON/PEOF region (offshore units have no municipality;
onshore units get fractionally split across PEON zones via PECD's own
rasterized region mask; solar units mostly lack coordinates at all) is
substantial, already-validated logic that lives in
~/research/mastr-power-capacities-germany and (for the PECD-technology
solar split specifically) ~/research/pecd-replication. See PROJECT.md for
the full reasoning.

This script just copies the already-built, already-crosswalked parquet
files into this project's own data/downloads/external/, so every
downstream stage only ever reads from within this repo. Requires both
sibling repos to be cloned alongside this one, with their own pipelines
already run (`dvc repro` there) at least once.
"""

import shutil

from pkg.paths import ProjPaths

paths = ProjPaths()
paths.ensure_directories()

SOURCES_AND_TARGETS = [
    (paths.external_mastr_capacity_by_peon_month_source, paths.capacity_by_peon_month_file),
    (paths.external_mastr_capacity_by_peof_month_source, paths.capacity_by_peof_month_file),
    (paths.external_mastr_capacity_by_offshore_month_source, paths.capacity_by_offshore_month_file),
    (paths.external_mastr_capacity_by_nuts2_month_source, paths.capacity_by_nuts2_month_file),
    (paths.external_pecd_replication_solar_capacity_by_nuts2_month_source, paths.solar_capacity_by_nuts2_month_file),
]

missing = [src for src, _ in SOURCES_AND_TARGETS if not src.exists()]
if missing:
    missing_list = "\n".join(f"  - {p}" for p in missing)
    raise FileNotFoundError(
        f"Missing external capacity panel(s):\n{missing_list}\n\n"
        "Clone/refresh the sibling projects and run `dvc repro` there first:\n"
        "  ~/research/mastr-power-capacities-germany\n"
        "  ~/research/pecd-replication"
    )

for source, target in SOURCES_AND_TARGETS:
    shutil.copy2(source, target)
    print(f"{source} -> {target}")
