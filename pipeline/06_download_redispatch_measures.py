"""Download netztransparenz.de's per-measure Redispatch export (Format 5).

Pure data acquisition -- no charts. The per-measure counterpart to
pipeline/05's SMARD download: real start/end timestamps, per-plant/cluster
names, TSO attribution -- richer, but only comprehensively
technology-labeled for offshore wind (see
`pkg/redispatch_measures.classify_entity_name`).

Always re-fetches the whole 2021-01-01..today range: netztransparenz gives
no incremental/delta endpoint, and the file is a few MB, cheap to re-pull
in full each run.

Pattern adapted from
pecd-replication/pipeline/47_download_redispatch_measures.py.
"""

from pkg.paths import ProjPaths
from pkg.redispatch_measures import download_redispatch_measures

paths = ProjPaths()
paths.ensure_directories()

csv_bytes = download_redispatch_measures()
paths.redispatch_measures_file.write_bytes(csv_bytes)

print(f"Saved {len(csv_bytes):,} bytes -> {paths.redispatch_measures_file}")
