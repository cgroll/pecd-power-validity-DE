"""Weight PECD capacity factors by installed capacity into a national
hourly potential series.

The core operation this project is actually about: for each hour, each
region's capacity factor (0-1, dimensionless) times that region's
installed capacity that month (MW) gives that region's contribution to
national potential output (MW); summing over all regions (and, for solar,
technology sub-types) gives one Germany-wide hourly potential series.
"""

import numpy as np
import pandas as pd


def broadcast_capacity_to_hourly(capacity_wide: pd.DataFrame, hourly_index: pd.DatetimeIndex) -> pd.DataFrame:
    """Repeat each month's capacity row across every hour that falls in it.

    `capacity_wide`: monthly index (any day-of-month; only the calendar
    month is used), one column per region (or (technology, region) for
    solar). Every hour in a given calendar month gets that month's own
    capacity snapshot -- capacity does not vary within a month, only
    the capacity factor does.
    """
    monthly = capacity_wide.copy()
    monthly.index = monthly.index.to_period("M")
    monthly = monthly[~monthly.index.duplicated(keep="last")].sort_index()

    hour_periods = hourly_index.to_period("M")
    broadcast = monthly.reindex(hour_periods)
    broadcast.index = hourly_index
    return broadcast


def compute_potential(capacity_factors: pd.DataFrame, capacity_wide: pd.DataFrame) -> pd.Series:
    """National hourly potential (MW): `sum_over_columns(capacity_factor x capacity)`.

    `capacity_factors`: hourly index, one column per region (or
    (technology, region) MultiIndex for solar) -- PECD's own capacity
    factor, 0-1.
    `capacity_wide`: monthly index, same column space (region or
    (technology, region)) -- installed capacity in MW. Columns present in
    one input but not the other are treated as zero capacity/CF, not
    dropped.

    A region/technology PECD never modeled (capacity factor 100% `NaN` --
    e.g. 3 of PEOF's 6 offshore zones, a known PECD data-quality gap also
    found in `pecd-replication`) contributes zero to the sum for every
    hour rather than poisoning the whole row to `NaN` -- effectively
    excluding that region's real capacity from potential whenever PECD
    itself has no data for it. Call `unmodeled_capacity_share` to see how
    much capacity that affects.
    """
    capacity_wide = capacity_wide.reindex(columns=capacity_factors.columns, fill_value=0.0)
    capacity_hourly = broadcast_capacity_to_hourly(capacity_wide, capacity_factors.index)

    product = capacity_factors.to_numpy() * capacity_hourly.to_numpy()
    potential_mw = np.nansum(product, axis=1)
    return pd.Series(potential_mw, index=capacity_factors.index, name="potential_mw")


def unmodeled_capacity_share(capacity_factors: pd.DataFrame, capacity_wide: pd.DataFrame) -> pd.Series:
    """Mean installed capacity (MW) sitting in columns PECD never modeled
    (100% `NaN` capacity factor throughout), one row per such column --
    empty if none. Diagnostic for `compute_potential`'s NaN-as-zero
    handling above.
    """
    capacity_wide = capacity_wide.reindex(columns=capacity_factors.columns, fill_value=0.0)
    unmodeled_columns = capacity_factors.columns[capacity_factors.isna().all()]
    if len(unmodeled_columns) == 0:
        return pd.Series(dtype=float)
    return capacity_wide[unmodeled_columns].mean()
