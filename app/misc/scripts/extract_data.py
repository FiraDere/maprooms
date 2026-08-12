import xarray as xr

def extract2D_region(xr_ds: xr.Dataset, bbox: dict) -> xr.Dataset:
    lon = xr_ds['lon'].values
    lat = xr_ds['lat'].values
    lat_s = (
        slice(bbox['maxLat'], bbox['minLat'])
        if lat[0] > lat[-1]
        else slice(bbox['minLat'], bbox['maxLat'])
    )
    lon_s = (
        slice(bbox['maxLon'], bbox['minLon'])
        if lon[0] > lon[-1]
        else slice(bbox['minLon'], bbox['maxLon'])
    )
    subset = xr_ds.sel(lon=lon_s, lat=lat_s)
    if subset.sizes['lat'] == 0 or subset.sizes['lon'] == 0:
        msg = 'No grid points were found inside the requested region.'
        raise ValueError(msg)

    reset_chunk = {k: -1 for k in subset.chunksizes}
    return subset.chunk(reset_chunk)

def extract3D_region_period(
    xr_ds: xr.Dataset, bbox: dict, period: dict
) -> xr.Dataset:
    xr_ds =  extract2D_region(xr_ds, bbox)
    time_slice = slice(period['start'], period['end'])
    subset = xr_ds.sel(time=time_slice)
    if subset.sizes['time'] == 0:
        msg = 'No dates were found inside the requested period.'
        raise ValueError(msg)
    return subset.chunk({'time': -1})

def regrid2D_dataArray(
    da_ref: xr.DataArray,
    da_var: xr.DataArray
) -> xr.DataArray:
    eq_lon = da_ref.indexes['lon'].equals(da_var.indexes['lon'])
    eq_lat = da_ref.indexes['lat'].equals(da_var.indexes['lat'])

    if eq_lon and eq_lat:
        return da_var
    else:
        da_out = da_var.interp(
            lat=da_ref['lat'],
            lon=da_ref['lon'],
            method='linear'
        )
        reset_chunk = {k: -1 for k in da_out.chunksizes}
        return da_out.chunk(reset_chunk)
