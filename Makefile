.PHONY: run dry-run serve report-dagster

# Run the full pipeline (only rebuilds what's out of date)
run:
	uv run dvc repro

# Preview what would be executed without running anything
dry-run:
	uv run dvc repro --dry

# Serve the book locally with live-reload
serve:
	cd book && uv run myst start

# Tell the energy-data-hub Dagster instance this book was just rebuilt --
# run by hand after a real `run` + book publish, not part of `run` itself.
# DAGSTER_HOME must match the one `dagster dev` was started with (see
# ~/research/energy-data-hub/README.md) or this reports into an unrelated,
# throwaway instance instead. See dagster_book_asset.py.
report-dagster:
	DAGSTER_HOME=$${DAGSTER_HOME:-$(HOME)/research/energy-data-hub/.dagster_home} uv run python -c "\
	from dagster import AssetMaterialization, DagsterInstance; \
	DagsterInstance.get().report_runless_asset_event(\
	    AssetMaterialization(asset_key='book_pecd_power_validity_de')\
	)"
