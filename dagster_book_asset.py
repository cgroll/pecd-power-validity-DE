"""This book as a Dagster external asset (pilot -- see
~/research/energy-data-hub/README.md#books-external-assets).

Declares what this book actually consumes from the hub, so it shows up in
the hub's Asset Graph -- but Dagster never materializes it itself. This
repo's own `dvc repro` + `myst build` remain the only thing that actually
builds the book, exactly as today.

After a real book rebuild, run `make report-dagster` (or the two-liner
below directly) so the hub UI reflects it:

    uv run python -c "
    from dagster import AssetMaterialization, DagsterInstance
    DagsterInstance.get().report_runless_asset_event(
        AssetMaterialization(asset_key='book_pecd_power_validity_de')
    )"

That's a deliberate, separate step -- not part of `make run` -- so
`dagster asset materialize`/schedules refreshing hub data never implies
"the book changed", and rebuilding the book is always a choice you make,
not something triggered by new upstream data landing.
"""

from dagster import AssetSpec, Definitions

book_asset = AssetSpec(
    key="book_pecd_power_validity_de",
    deps=[
        "smard_generation_solar",
        "smard_generation_wind_onshore",
        "smard_generation_wind_offshore",
        "smard_load",
        "smard_price_de_lu",
        "smard_capacity_solar",
        "smard_capacity_wind_onshore",
        "smard_capacity_wind_offshore",
        "smard_redispatch_by_source",
        "redispatch_measures",
    ],
    description=(
        "PECD Power Validity DE book (pipeline/03-06 currently still "
        "download these directly -- see PROJECT.md for the planned "
        "switch to reading energy-data-hub's outputs instead)."
    ),
    group_name="books",
)

defs = Definitions(assets=[book_asset])
