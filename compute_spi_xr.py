"""SPI/SPEI calculation for xarray.DataArray objects (NumPy or Dask backed).

The gamma estimator is the L-moment estimator used by R's
``lmomco::lmoms`` + ``lmomco::pargam``.  Therefore gamma SPI values are
numerically comparable with the original R implementation.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import xarray as xr
from scipy import stats

MIN_NON_NA = 5


def _validate(data: xr.DataArray) -> xr.DataArray:
    if not isinstance(data, xr.DataArray):
        raise TypeError("data must be an xarray.DataArray")
    if "time" not in data.dims:
        raise ValueError("data must have a 'time' dimension")
    if not np.issubdtype(data.time.dtype, np.datetime64):
        raise TypeError("the 'time' coordinate must contain datetime64 values")
    return data


def _season_index(data: xr.DataArray, time_res: str) -> xr.DataArray:
    if time_res == "monthly":
        season = data.time.dt.month
    elif time_res == "dekadal":
        dekad = xr.where(data.time.dt.day <= 10, 1, xr.where(data.time.dt.day <= 20, 2, 3))
        season = (data.time.dt.month - 1) * 3 + dekad
    else:
        raise ValueError("time_res must be 'monthly' or 'dekadal'")
    return season.astype(np.int16).rename("season_index")


def SPEI_Aggregate_data(data: xr.DataArray, tscale: int = 1) -> xr.DataArray:
    """Return trailing time-scale sums while retaining xarray metadata."""
    data = _validate(data)
    if tscale < 1:
        raise ValueError("tscale must be at least 1")
    if tscale == 1:
        return data.copy(deep=False)
    # min_periods=1 matches R's sum(..., na.rm=TRUE) within complete windows.
    result = data.rolling(time=tscale, min_periods=1).sum(skipna=True)
    leading = xr.DataArray(np.arange(data.sizes["time"]) < tscale - 1,
                           dims="time", coords={"time": data.time})
    return result.where(~leading)


def _gamma_lmoments(values: np.ndarray) -> tuple[float, float] | None:
    """Hosking gamma L-moment fit, equivalent to lmomco::pargam."""
    x = np.sort(values[np.isfinite(values) & (values > 0)])
    n = x.size
    if n < MIN_NON_NA or n < 2:
        return None
    if np.unique(x).size == 1:
        # This only mirrors the R safeguard; a fixed seed makes Dask reproducible.
        x = np.sort(x + np.random.default_rng(0).uniform(0.1, 0.5, n))
    l1 = float(np.mean(x))
    b1 = float(np.sum((np.arange(n) / (n - 1)) * x) / n)
    l2 = 2 * b1 - l1
    if not np.isfinite(l1) or not np.isfinite(l2) or l1 <= 0 or l2 <= 0 or l2 >= l1:
        return None
    tau = l2 / l1
    if tau < 0.5:
        z = np.pi * tau * tau
        shape = (1 - 0.3080 * z) / (z - 0.05812 * z**2 + 0.01765 * z**3)
    else:
        z = 1 - tau
        shape = z * (0.7213 - 0.5947 * z) / (1 - 2.1817 * z + 1.2113 * z**2)
    return float(shape), float(l1 / shape)


def _params_1d(values: np.ndarray, seasons: np.ndarray, frequency: int,
               distribution: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    first = np.full(frequency, np.nan)
    second = np.full(frequency, np.nan)
    pzero = np.full(frequency, np.nan)
    for season in range(1, frequency + 1):
        x = values[seasons == season]
        x = x[np.isfinite(x)]
        if x.size < MIN_NON_NA:
            continue
        if distribution == "gamma":
            pzero[season - 1] = np.mean(x == 0)
            fitted = _gamma_lmoments(x)
            if fitted is not None:
                first[season - 1], second[season - 1] = fitted
        elif distribution == "zscore":
            first[season - 1] = np.mean(x)
            second[season - 1] = np.std(x, ddof=1)
        else:
            raise ValueError("xarray implementation supports 'gamma' and 'zscore'")
    return first, second, pzero


def SPEI_Compute_params(data: xr.DataArray, tscale: int = 1, frequency: int | None = None,
                        distribution: str = "gamma", time_res: str = "monthly") -> xr.Dataset:
    """Fit one distribution per season and grid cell, lazily for Dask input."""
    data = _validate(data)
    expected = 36 if time_res == "dekadal" else 12
    frequency = expected if frequency is None else int(frequency)
    seasons = _season_index(data, time_res)
    kwargs = {"frequency": frequency, "distribution": distribution}
    shape, scale, pzero = xr.apply_ufunc(
        _params_1d, data, seasons,
        input_core_dims=[["time"], ["time"]],
        output_core_dims=[["season"], ["season"], ["season"]],
        vectorize=True, dask="parallelized", output_dtypes=[float, float, float],
        kwargs=kwargs,
        dask_gufunc_kwargs={"output_sizes": {"season": frequency}, "allow_rechunk": True},
    )
    names = ("shape", "scale") if distribution == "gamma" else ("mean", "sd")
    result = xr.Dataset({names[0]: shape, names[1]: scale, "pzero": pzero})
    result = result.assign_coords(season=np.arange(1, frequency + 1))
    result.attrs.update(distribution=distribution, time_res=time_res, tscale=tscale)
    return result


def _spi_1d(values: np.ndarray, seasons: np.ndarray, first: np.ndarray,
            second: np.ndarray, pzero: np.ndarray, distribution: str) -> np.ndarray:
    result = np.full(values.shape, np.nan, dtype=float)
    for i, value in enumerate(values):
        if not np.isfinite(value):
            continue
        k = int(seasons[i]) - 1
        if k < 0 or k >= first.size or not np.isfinite(first[k]):
            continue
        if distribution == "gamma":
            probability = stats.gamma.cdf(value, first[k], scale=second[k])
            probability = pzero[k] + (1 - pzero[k]) * probability
            result[i] = stats.norm.ppf(probability)
        else:
            result[i] = (value - first[k]) / second[k]
            if not np.isfinite(result[i]):
                result[i] = 0
    result[np.isneginf(result)] = -5
    result[np.isposinf(result)] = 5
    return result


def SPEI_computation(data: xr.DataArray, params: xr.Dataset, tscale: int = 1,
                     frequency: int | None = None, distribution: str = "gamma",
                     time_res: str = "monthly") -> xr.DataArray:
    """Transform data to SPI using a parameter Dataset from SPEI_Compute_params."""
    data = _validate(data)
    seasons = _season_index(data, time_res)
    first_name, second_name = (("shape", "scale") if distribution == "gamma" else ("mean", "sd"))
    result = xr.apply_ufunc(
        _spi_1d, data, seasons, params[first_name], params[second_name], params["pzero"],
        input_core_dims=[["time"], ["time"], ["season"], ["season"], ["season"]],
        output_core_dims=[["time"]], vectorize=True, dask="parallelized",
        output_dtypes=[float], kwargs={"distribution": distribution},
        dask_gufunc_kwargs={"allow_rechunk": True},
    ).transpose(*data.dims)
    result = result.assign_coords(data.coords).rename("spi")
    result.attrs.update(units="standard deviations", long_name="Standardized Precipitation Index",
                        distribution=distribution, time_scale=tscale, time_resolution=time_res)
    return result


def SPI_computation_wrapper(precip: xr.DataArray, params: Mapping[str, Any]) -> xr.DataArray:
    """Compute SPI from a ``time × ...`` precipitation DataArray."""
    precip = _validate(precip)
    tscale = int(params["time_scale"])
    time_res = str(params["time_res"])
    distribution = str(params.get("distribution", "gamma"))
    if time_res == "dekadal" and tscale > 1:
        raise ValueError("Time scale must be 1 for dekadal data")
    aggregated = SPEI_Aggregate_data(precip, tscale)
    fitted = SPEI_Compute_params(aggregated, tscale, distribution=distribution, time_res=time_res)
    result = SPEI_computation(aggregated, fitted, tscale, distribution=distribution, time_res=time_res)
    return result.isel(time=slice(tscale - 1, None))


def SPEI_computation_wrapper(precip: xr.DataArray, etp: xr.DataArray,
                             params: Mapping[str, Any]) -> xr.DataArray:
    """Compute SPEI from aligned precipitation and evapotranspiration arrays."""
    precip, etp = xr.align(_validate(precip), _validate(etp), join="exact")
    balance = (precip - etp).rename("climatic_water_balance")
    tscale = int(params["time_scale"])
    time_res = str(params["time_res"])
    distribution = str(params.get("distribution", "gamma"))
    if time_res == "dekadal" and tscale > 1:
        raise ValueError("Time scale must be 1 for dekadal data")
    aggregated = SPEI_Aggregate_data(balance, tscale)
    fitted = SPEI_Compute_params(aggregated, tscale, distribution=distribution, time_res=time_res)
    result = SPEI_computation(aggregated, fitted, tscale, distribution=distribution, time_res=time_res)
    result.name = "spei"
    result.attrs["long_name"] = "Standardized Precipitation Evapotranspiration Index"
    return result.isel(time=slice(tscale - 1, None))
