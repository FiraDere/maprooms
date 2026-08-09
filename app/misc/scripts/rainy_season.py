from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import xarray as xr
from scipy.spatial import cKDTree
import calendar

from ._util import (
    _validate_cube,
    _empty_spatial_dates,
    _max_true_run
)
# from .water_balance import simple_water_balance
from .rm_isolated import remove_isolated_pixels_3d

def compute_rainy_season(
    precip: xr.DataArray,
    et0: xr.DataArray,
    taw: xr.DataArray,
    rp: dict[str, Any],
) -> xr.Dataset:
    precip = _validate_cube(precip, 'precip')
    et0 = _validate_cube(et0, 'et0')
    if (not isinstance(taw, xr.DataArray) or 
        not {'lat', 'lon'} <= set(taw.dims)):
        raise ValueError(
            'taw must be an xarray.DataArray with lat and lon dimensions'
        )
    taw = taw.transpose('lat', 'lon')

    onset_data = compute_season_onset(precip, rp)
    # wb_data = simple_water_balance(precip, et0, taw)
    # cessation_data = compute_season_cessation_1(wb_data, rp)
    cessation_data = compute_season_cessation_2(
        precip, et0, taw, rp
    )

    if rp['interpolate']:
        empty_cells = precip.isnull().all('time')
        if empty_cells.chunks is not None:
            empty_cells = empty_cells.chunk({'lat': -1, 'lon': -1})
        onset = (
            interp_rainy_season(
                onset_data,
                max_search=int(rp['searchDaysO'])
            )
            .where(~empty_cells)
        )
        cessation = (
            interp_rainy_season(
                cessation_data,
                max_search=int(rp['searchDaysC'])
            )
            .where(~empty_cells)
        )
    else:
        onset = onset_data
        cessation = cessation_data

    years = np.union1d(
        onset_data.year.values,
        cessation_data.year.values,
    ).astype(np.int32)
    onset = onset.reindex(year=years)
    cessation = cessation.reindex(year=years)
    onset_start = onset_data.start.reindex(year=years)
    cessation_start = cessation_data.start.reindex(year=years)

    output_coords = {
        'year': years,
        'lat': precip.lat,
        'lon': precip.lon,
    }
    onset = xr.DataArray(
        onset.data,
        dims=('year', 'lat', 'lon'),
        coords=output_coords,
        name='onset',
    )
    cessation = xr.DataArray(
        cessation.data,
        dims=('year', 'lat', 'lon'),
        coords=output_coords,
        name='cessation',
    )

    start_difference = (
        cessation_start.values
        .astype('datetime64[D]')
        - onset_start.values.astype('datetime64[D]')
    ) / np.timedelta64(1, 'D')
    start_difference = xr.DataArray(
        np.asarray(start_difference, dtype=float),
        dims='year',
        coords={'year': years},
    )
    season_length = cessation - onset + start_difference

    invalid = season_length <= int(rp['numberDaysO'])
    onset = onset.where(~invalid).astype('float32')
    cessation = cessation.where(~invalid).astype('float32')
    season_length = season_length.where(~invalid).astype('float32')

    if rp['rmIsolatedPix']:
        onset = onset.copy(
            data=remove_isolated_pixels_3d(onset.data)
        )
        cessation = cessation.copy(
            data=remove_isolated_pixels_3d(cessation.data)
        )
        season_length = season_length.copy(
            data=remove_isolated_pixels_3d(season_length.data)
        )

    full_months = list(calendar.month_name)[1:]
    method = (
        "Onset is the first qualifying rainfall window from "
        f"{full_months[rp['startMonthO'] - 1]} {rp['startDayO']} and "
        f"within the annual {int(rp['searchDaysO'])}-day onset search period: "
        f"at least {float(rp['rainTotalO']):g} mm over {int(rp['numberDaysO'])} days, "
        f"with rain >= {float(rp['rainThres']):g} mm on at least "
        f"{int(rp['minNbDaysO'])} days. A candidate is rejected as a false "
        f"onset when a dry spell lasting at least {int(rp['drySpellO'])} "
        f"days occurs during the following {int(rp['drySpellDaysO'])} days. "
        "Cessation is calculated from a daily bucket water balance, initialized "
        "to one third of total available water and updated as rainfall minus "
        "reference evapotranspiration within bounds of zero and TAW. It is the "
        f"first of {int(rp['numberDaysC'])} consecutive days with water balance "
        f"below {float(rp['waterBalanceC']):g} mm starting from "
        f"{full_months[rp['startMonthC'] - 1]} {rp['startDayC']} and "
        f"within the annual {int(rp['searchDaysC'])}-day cessation search period. "
        "Missing spatial values are filled from the nearest valid grid cell within the configured "
        "maximum interpolation distance when at least five valid cells exist."
    )

    onset.attrs = {
        'long_name': 'Onset of the rainy season',
        'units': "days since 'onset_start' for each 'year'"
    }
    cessation.attrs = {
        'long_name': 'Cessation of the rainy season',
        'units': "days since 'cessation_start' for each 'year'"
    }
    season_length.name = 'length'
    season_length.attrs = {
        'long_name': 'Length of the rainy season',
        'units': 'days'
    }

    return xr.Dataset(
        data_vars={
            'onset': onset,
            'cessation': cessation,
            'length': season_length,
            'onset_start': ('year', onset_start.values),
            'cessation_start': ('year', cessation_start.values),
        },
        attrs={
            'title': 'Rainy season: onset, cessation and length',
            'method': method
        }
    )

def compute_season_onset(
    precip: xr.DataArray,
    rp: dict[str, Any]
) -> xr.DataArray:
    precip = _validate_cube(precip, 'precip')
    periods = index_daily_season(
        precip.time.values,
        int(rp['startMonthO']),
        int(rp['startDayO'])
    )
    start_dates = periods['range_date'][:, 0]
    rows = []
    for idx, start in zip(periods['index'], start_dates):
        found = get_year_season_onset(precip.isel(time=idx), rp)
        start_date = pd.Timestamp(start).to_datetime64()
        offsets = (
            (found - start_date) / np.timedelta64(1, 'D')
            - int(rp['numberDaysO'])
            + 1
        )
        offsets = offsets.clip(min=0)
        rows.append(offsets)

    years = (
        pd.DatetimeIndex(start_dates).year
        .astype(np.int32)
    )
    return (
        xr.concat(
            rows, dim=xr.IndexVariable('year', years)
        )
        .assign_coords(
            start=('year', periods['range_date'][:, 0]),
            end=('year', periods['range_date'][:, 1])
        )
        .rename('days')
        .astype(float)
    )

def compute_season_cessation_1(
    wb: xr.DataArray,
    rp: dict[str, Any]
) -> xr.DataArray:
    wb = _validate_cube(wb, 'wb')
    periods = index_daily_season(
        wb.time.values,
        int(rp['startMonthC']),
        int(rp['startDayC'])
    )
    start_dates = periods['range_date'][:, 0]
    rows = []
    for idx, start in zip(periods['index'], start_dates):
        found = get_year_season_cessation(wb.isel(time=idx), rp)
        start_date = pd.Timestamp(start).to_datetime64()
        offsets = (found - start_date) / np.timedelta64(1, 'D')
        rows.append(offsets)

    years = (
        pd.DatetimeIndex(start_dates).year
        .astype(np.int32)
    )
    return (
        xr.concat(
            rows, dim=xr.IndexVariable('year', years)
        )
        .assign_coords(
            start=('year', periods['range_date'][:, 0]),
            end=('year', periods['range_date'][:, 1])
        )
        .rename('days')
        .astype(float)
    )

def compute_season_cessation_2(
    precip: xr.DataArray,
    et0: xr.DataArray,
    taw: xr.DataArray,
    rp: dict[str, Any],
) -> xr.DataArray:
    """
    Compute cessation without materializing the daily water-balance cube.

    Water balance is carried continuously through the complete time series
    inside each spatial block. Only the current two-dimensional balance and
    the annual cessation results are retained in memory.
    """
    precip = _validate_cube(precip, 'precip')
    et0 = _validate_cube(et0, 'et0')
    if not isinstance(taw, xr.DataArray):
        raise TypeError('taw must be an xarray.DataArray')
    if set(taw.dims) != {'lat', 'lon'}:
        raise ValueError(
            "taw must contain exactly the dimensions 'lat' and 'lon'"
        )

    taw = taw.transpose('lat', 'lon')
    spatial_coords = {'lat': precip.lat, 'lon': precip.lon}
    if not (
        precip.lat.equals(et0.lat)
        and precip.lon.equals(et0.lon)
    ):
        et0 = et0.interp(spatial_coords)
    if not (
        precip.lat.equals(taw.lat)
        and precip.lon.equals(taw.lon)
    ):
        taw = taw.interp(spatial_coords)

    precip, et0 = xr.align(precip, et0, join='inner')
    if precip.sizes['time'] == 0:
        raise ValueError(
            'precip and et0 have no common time coordinates'
        )

    periods = index_daily_season(
        precip.time.values,
        int(rp['startMonthC']),
        int(rp['startDayC'])
    )
    start_dates = periods['range_date'][:, 0]
    years = pd.DatetimeIndex(start_dates).year.astype(np.int32)
    search_year = np.full(precip.sizes['time'], -1, dtype=np.int32)
    search_offset = np.full(precip.sizes['time'], -1, dtype=np.int32)
    search_lengths = np.zeros(len(years), dtype=np.int32)
    max_days = int(rp['searchDaysC'])
    for year_index, indices in enumerate(periods['index']):
        selected = indices[:max_days]
        search_lengths[year_index] = len(selected)
        search_year[selected] = year_index
        search_offset[selected] = np.arange(
            len(selected), dtype=np.int32
        )

    if precip.chunks is not None:
        precip = precip.chunk({'time': -1})
        target_chunks = {
            'time': -1,
            'lat': precip.chunksizes['lat'],
            'lon': precip.chunksizes['lon'],
        }
        et0 = et0.chunk(target_chunks)
        taw = taw.chunk({
            'lat': precip.chunksizes['lat'],
            'lon': precip.chunksizes['lon'],
        })

    result = xr.apply_ufunc(
        _stream_cessation_block,
        precip,
        et0,
        taw,
        input_core_dims=[['time'], ['time'], []],
        output_core_dims=[['year']],
        vectorize=False,
        dask='parallelized',
        output_dtypes=[float],
        kwargs={
            'search_year': search_year,
            'search_offset': search_offset,
            'search_lengths': search_lengths,
            'rainyseas_pars': rp,
        },
        dask_gufunc_kwargs={
            'allow_rechunk': False,
            'output_sizes': {'year': len(years)},
        },
    )
    return (
        result
        .transpose('year', 'lat', 'lon')
        .assign_coords(
            year=years,
            start=('year', periods['range_date'][:, 0]),
            end=('year', periods['range_date'][:, 1]),
        )
        .rename('days')
        .astype(float)
    )

def _stream_cessation_block(
    precip: np.ndarray,
    et0: np.ndarray,
    taw: np.ndarray,
    search_year: np.ndarray,
    search_offset: np.ndarray,
    search_lengths: np.ndarray,
    rainyseas_pars: dict[str, Any],
) -> np.ndarray:
    """
    Stream water balance and cessation for one spatial Dask block.
    """
    rain_values = np.asarray(precip)
    et0_values = np.asarray(et0)
    taw_values = np.asarray(taw, dtype=np.float64)
    spatial_shape = rain_values.shape[:-1]
    year_count = len(search_lengths)

    balance = taw_values / 3.0
    dry_run = np.zeros(spatial_shape, dtype=np.int32)
    valid_input = np.zeros(spatial_shape, dtype=bool)
    valid_search = np.zeros(
        (*spatial_shape, year_count), dtype=np.int32
    )
    result = np.full(
        (*spatial_shape, year_count), np.nan, dtype=np.float64
    )

    threshold = float(rainyseas_pars['waterBalanceC']) or 0.01
    required_run = int(rainyseas_pars['numberDaysC'])

    for day in range(rain_values.shape[-1]):
        rain_day = rain_values[..., day]
        et0_day = et0_values[..., day]
        valid_day = ~np.isnan(rain_day) & ~np.isnan(et0_day)
        valid_input |= valid_day

        if day > 0:
            balance = np.clip(
                balance
                + np.where(valid_day, rain_day, 0.0)
                - np.where(valid_day, et0_day, 0.0),
                0.0,
                taw_values,
            )

        year_index = search_year[day]
        if year_index < 0:
            continue
        offset = search_offset[day]
        if offset == 0:
            dry_run.fill(0)

        valid_search[..., year_index] += ~np.isnan(balance)
        below = (balance < threshold) & ~np.isnan(balance)
        dry_run = np.where(below, dry_run + 1, 0)
        newly_found = (
            np.isnan(result[..., year_index])
            & (dry_run >= required_run)
        )
        result[..., year_index][newly_found] = (
            offset - required_run + 1
        )

    min_frac = float(rainyseas_pars['minFrac'])
    for year_index, search_length in enumerate(search_lengths):
        if search_length == 0:
            continue
        unresolved = np.isnan(result[..., year_index])
        result[..., year_index][unresolved] = search_length - 1
        usable = (
            valid_search[..., year_index] / search_length >= min_frac
        )
        result[..., year_index][~usable] = np.nan

    result[~valid_input] = np.nan
    return result

def get_year_season_onset(
    precip: xr.DataArray,
    rainyseas_pars: dict[str, Any]
) -> xr.DataArray:
    precip = _validate_cube(precip, 'precip')
    n = min(
        int(rainyseas_pars['searchDaysO']),
        precip.sizes['time']
    )
    rain = _single_time_chunk(
        precip.isel(time=slice(0, n))
    )
    if n == 0:
        return _empty_spatial_dates(rain)

    result_idx = xr.apply_ufunc(
        _onset_index_1d,
        rain,
        input_core_dims=[['time']],
        output_core_dims=[[]],
        vectorize=True,
        dask='parallelized',
        output_dtypes=[float],
        kwargs={
            'rainyseas_pars': rainyseas_pars
        },
        dask_gufunc_kwargs={
            'allow_rechunk': False
        }
    )
    return _indices_to_date_array(
        result_idx, rain.time.values
    )

def get_year_season_cessation(
    wb_data: xr.DataArray,
    rainyseas_pars: dict[str, Any]
) -> xr.DataArray:
    wb_data = _validate_cube(wb_data, 'wb')
    n = min(
        int(rainyseas_pars['searchDaysC']),
        wb_data.sizes['time']
    )
    wb = _single_time_chunk(
        wb_data.isel(time=slice(0, n))
    )
    if n == 0:
        return _empty_spatial_dates(wb)
    result_idx = xr.apply_ufunc(
        _cessation_index_block,
        wb,
        input_core_dims=[['time']],
        output_core_dims=[[]],
        vectorize=False,
        dask='parallelized',
        output_dtypes=[float],
        kwargs={'rainyseas_pars': rainyseas_pars},
        dask_gufunc_kwargs={'allow_rechunk': False},
    )
    return _indices_to_date_array(result_idx, wb.time.values)

def _single_time_chunk(
    data: xr.DataArray
) -> xr.DataArray:
    return (
        data.chunk({'time': -1})
        if data.chunks is not None
        else data
    )

def _onset_index_1d(
    values: np.ndarray,
    rainyseas_pars: dict[str, Any]
) -> float:
    rain = np.asarray(values, dtype=float).copy()
    min_frac = float(rainyseas_pars['minFrac'])
    if (
        rain.size == 0
        or np.mean(np.isnan(rain)) > 1 - min_frac
    ):
        return np.nan
    rain[np.isnan(rain)] = 0

    window = int(rainyseas_pars['numberDaysO'])
    cumulative = np.cumsum(rain)
    previous = (
        np.r_[np.zeros(window), cumulative[:-window]]
        if window < rain.size
        else np.zeros_like(cumulative)
    )
    rain_tot = float(rainyseas_pars['rainTotalO'])
    qualifies = (
        cumulative - previous >= rain_tot
    )
    if np.all(qualifies):
        return 0.0

    rainy = rain >= float(rainyseas_pars['rainThres'])
    for pos in np.flatnonzero(qualifies):
        future = ~rainy[
            pos + 1:min(
                rain.size,
                pos + 1 + int(rainyseas_pars['drySpellDaysO'])
            )
        ]
        if _max_true_run(future) >= int(rainyseas_pars['drySpellO']):
            continue
        if np.sum(
            rainy[max(0, pos - window + 1):pos + 1]
        ) >= int(
            rainyseas_pars['minNbDaysO']
        ):
            return float(pos)
    return np.nan

def _cessation_index_block(
    values: np.ndarray,
    rainyseas_pars: dict[str, Any]
) -> np.ndarray:
    """
    Find cessation for every cell in one Dask spatial block.
    """
    wb = np.asarray(values, dtype=float)
    n = wb.shape[-1]
    spatial_shape = wb.shape[:-1]
    min_frac = float(rainyseas_pars['minFrac'])
    usable = np.mean(np.isnan(wb), axis=-1) <= 1 - min_frac
    result = np.full(spatial_shape, n - 1, dtype=float)

    run = int(rainyseas_pars['numberDaysC'])
    if run <= n:
        threshold = float(rainyseas_pars['waterBalanceC']) or 0.01
        below = (wb < threshold) & ~np.isnan(wb)
        cumulative = np.concatenate(
            [
                np.zeros((*spatial_shape, 1), dtype=np.int64),
                np.cumsum(below, axis=-1, dtype=np.int64),
            ],
            axis=-1,
        )
        complete_run = (
            cumulative[..., run:] - cumulative[..., :-run]
        ) >= run
        has_run = np.any(complete_run, axis=-1)
        first_run = np.argmax(complete_run, axis=-1)
        result[has_run] = first_run[has_run]

    result[~usable] = np.nan
    return result

def _indices_to_date_array(
    indices: xr.DataArray,
    dates: np.ndarray,
) -> xr.DataArray:
    date_values = np.asarray(dates, dtype='datetime64[ns]')
    return xr.apply_ufunc(
        _take_dates,
        indices,
        dask='parallelized',
        output_dtypes=[np.dtype('datetime64[ns]')],
        kwargs={'date_values': date_values},
    )

def _take_dates(
    values: np.ndarray,
    date_values: np.ndarray,
) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    result = np.full(
        values.shape,
        np.datetime64('NaT'),
        dtype='datetime64[ns]'
    )
    valid = ~np.isnan(values)
    result[valid] = date_values[values[valid].astype(np.int64)]
    return result

def index_daily_season(
    dates: Any,
    start_month: int,
    start_day: int
) -> dict[str, Any]:
    original = pd.DatetimeIndex(dates)
    if original.empty:
        raise ValueError('dates must not be empty')
    if original.has_duplicates:
        raise ValueError('time coordinate must not contain duplicate dates')
    if not original.is_monotonic_increasing:
        raise ValueError('time coordinate must be sorted in increasing order')

    first, last = original[0].normalize(), original[-1].normalize()
    candidate = pd.Timestamp(first.year, start_month, start_day)
    start = (
        candidate
        if first <= candidate
        else pd.Timestamp(
                first.year + 1,
                start_month,
                start_day
            )
    )
    if (start - first).days in (0, 365, 366):
        start = first
    final_candidate = pd.Timestamp(
        last.year, start_month, start_day
    )
    if final_candidate <= last:
        final_candidate = pd.Timestamp(
            last.year + 1, start_month, start_day
        )
    end = final_candidate - pd.Timedelta(days=1)
    lookup = pd.Series(
        np.arange(len(original)),
        index=original.normalize()
    )
    full = pd.date_range(start, end, freq='D')
    start_flags = (full.month == start_month) & (full.day == start_day)
    boundaries = np.r_[np.flatnonzero(start_flags), len(full)]
    if boundaries[0] != 0:
        boundaries = np.r_[0, boundaries]

    indices, ranges = [], []
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        period = full[left:right]
        matched = lookup.reindex(period).to_numpy()
        indices.append(matched[~pd.isna(matched)].astype(int))
        ranges.append(
            [
                period[0].to_datetime64(),
                period[-1].to_datetime64()
            ]
        )
    return {
        'index': indices,
        'range_date': np.asarray(ranges, dtype='datetime64[ns]')
    }

def interp_rainy_season(
    season_data: xr.DataArray,
    max_search: int | float = np.inf,
    max_dist: float = 0.5,
) -> xr.DataArray:
    if not isinstance(season_data, xr.DataArray):
        raise TypeError('season_data must be an xarray.DataArray')
    season_data = season_data.transpose('year', 'lat', 'lon')
    lon, lat = np.meshgrid(
        season_data.lon.values,
        season_data.lat.values
    )
    coords = np.column_stack(
        [lon.ravel(), lat.ravel()]
    )

    if season_data.chunks is not None:
        season_data = season_data.chunk({'lat': -1, 'lon': -1})
        season_data = season_data.chunk({'year': 1})

    return xr.apply_ufunc(
        _interp_rainy_season_layer,
        season_data,
        input_core_dims=[['lat', 'lon']],
        output_core_dims=[['lat', 'lon']],
        vectorize=True,
        dask='parallelized',
        output_dtypes=[float],
        kwargs={
            'coords': coords,
            'max_search': max_search,
            'max_dist': max_dist,
        },
        dask_gufunc_kwargs={'allow_rechunk': False},
        keep_attrs=True,
    ).transpose('year', 'lat', 'lon')

def _interp_rainy_season_layer(
    layer: np.ndarray,
    coords: np.ndarray,
    max_search: int | float,
    max_dist: float,
) -> np.ndarray:
    """
    Interpolate one spatial layer;
    Dask schedules layers in parallel.
    """
    layer = np.asarray(layer, dtype=float)
    row = layer.ravel()
    valid = ~np.isnan(row)
    if np.count_nonzero(valid) < 5:
        return layer.copy()

    distance, nearest = cKDTree(coords[valid]).query(coords, k=1)
    fill = distance <= max_dist
    filled = row.copy()
    filled[fill] = row[valid][nearest[fill]]
    return np.clip(filled, 0, max_search).reshape(layer.shape)
