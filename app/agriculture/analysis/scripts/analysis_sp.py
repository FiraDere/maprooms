import os
import json
import numpy as np
import pandas as pd
import xarray as xr
from datetime import date, datetime

from app.dst_api.scripts import (
    get_zarr_dataset,
    aggregate_climatology
)
from app.scripts.imagepng import create_imagePng
from app.scripts.colorbar import check_invalid_colors
from app.scripts._cache import cache, hash_params_rainy_season
from app.misc.scripts.soilgrids_tawc import get_gyga_af_tawc
from app.misc.scripts.extract_data import regrid2D_dataArray
from app.misc.scripts.rainy_season import compute_rainy_season
from app.scripts.util import (
    load_yaml_file,
    parse_json_spatial_data
)
from app.scripts._global import GLOBAL_CONFIG
from app.dst_api.scripts import (
    download_analysis_dailydata,
    get_daily_index_season,
    year_daily_index_season
)

def agriculture_analysis_sp_data(params):
    check = check_invalid_colors(params['colorbar'])
    if check['status'] == -1: return check

    if params['mapPage'] in ['rainy-season', 'decision-support']:
        ret = _get_rainy_season_data(params)
        if ret['status'] == -1:
            return ret
        data, rainy_season, params = ret['data']
    elif params['mapPage'] == 'crops-suitability':
        ret = _get_crop_suitability_data(params)
        if ret['status'] == -1:
            return ret
        data = ret['data']
    else:
        return {'status': -1, 'message': 'Unknown maproom page.'}

    if params['colorbar']['color_type'] == 'preset':
        map_png = create_imagePng(
            data,
            breaks=params['colorbar']['break_cbar'],
            color_name=params['colorbar']['color_cbar'],
            colors_ext=params['colorbar']['color_ext']
        )
    else:
        map_png = create_imagePng(
            data,
            breaks=params['colorbar']['break_cbar'],
            colors=params['colorbar']['color_cbar'],
            colors_ext=params['colorbar']['color_ext']
        )

    if params['mapPage'] in ['rainy-season', 'decision-support']:
        map_png = _format_ckey_labels_dates(
            map_png, rainy_season, params
        )
        if params['mapType'] == 'climatology':
            map_png['date'] = ''
        else:
            map_png['date'] = f"{params['Year']} season"

        map_png['ckeys']['title'] = _get_ckey_title(params)
    else:
        map_png['date'] = data['date']
        map_png['ckeys']['title'] = f"{data['longname']} ({data['units']})"

    return {'status': 0, 'data': map_png}

def _get_rainy_season_data(params):
    season_data = get_rainy_season(params)
    if season_data['status'] == -1:
        return season_data
    rainy_season = season_data['data']

    rainy_season_key = hash_params_rainy_season(
        params['rainy_season']
    )

    if params['mapType'] == 'climatology':
        proba_thres, proba_unit = _get_proba_info(params)

        clim_data = _get_clim_data(
            rainy_season[params['variable']],
            params['climStats'],
            params['minYear'],
            rainy_season_key,
            proba_thres,
            proba_unit
        )
        if clim_data['status'] == -1:
            return clim_data

        data = {
            'lon': clim_data['data']['lon'].values,
            'lat': clim_data['data']['lat'].values,
            'data': clim_data['data'].values
        }
    else:
        if params['mapPage'] == 'decision-support':
            data_year = (
                rainy_season[params['variable']]
                .isel(year=-1)
            )
            params['Year'] = data_year.year.values.item()
        else:
            data_year = (
                rainy_season[params['variable']]
                .sel(year=params['Year'])
            )

        if params['mapType'] == 'anomaly':
            clim_data = _get_clim_data(
                rainy_season[params['variable']],
                'mean', params['minYear'],
                rainy_season_key
            )
            if clim_data['status'] == -1:
                return clim_data

            data_year = data_year - clim_data['data']

        data = {
            'lon': data_year['lon'].values,
            'lat': data_year['lat'].values,
            'data': data_year.values
        }
    params = _format_ckey_labels_num(rainy_season, params)
    return {
        'status': 0,
        'data': (data, rainy_season, params)
    }

def _get_crop_suitability_data(params):
    if params['mvariable'] == 'suitability':
        suitability_data = _compute_crop_suitability(params)
        if suitability_data['status'] == -1:
            return suitability_data

        crop_suit = suitability_data['data']['crop_suit']
        if crop_suit.chunks is not None:
            crop_suit = crop_suit.compute(
                scheduler='single-threaded'
            )

        start = datetime(
            params['Year'], params['startMonth'], params['startDay']
        )
        end_year = params['Year']
        if (
            params['endMonth'], params['endDay']
        ) < (
            params['startMonth'], params['startDay']
        ):
            end_year += 1
        end = datetime(
            end_year, params['endMonth'], params['endDay']
        )

        return {
            'status': 0,
            'data': {
                'date': (
                    f"{start.strftime('%Y-%m-%d')} - "
                    f"{end.strftime('%Y-%m-%d')}"
                ),
                'lon': crop_suit['lon'].values,
                'lat': crop_suit['lat'].values,
                'data': crop_suit.values,
                'longname': 'Crop climate suitability',
                'units': 'index',
                'varid': 'crop_suit',
                'dimensions': crop_suit.dims
            }
        }
    else:
        params = _create_params_dailyanalysis(params)
        json_data = download_analysis_dailydata(params)
        data = parse_json_spatial_data(json_data, 'Date')
        return {'status': 0, 'data': data}

def _create_params_dailyanalysis(params):
    if params['mvariable'] == 'rainfall':
        params['variable'] = 'rainfall'
        params['seasParams'] = 'TotRain'
    if params['mvariable'] == 'tempMax':
        params['variable'] = 'temperature'
        params['seasParams'] = 'MaxTemp'
    if params['mvariable'] == 'tempMin':
        params['variable'] = 'temperature'
        params['seasParams'] = 'MinTemp'

    params['minFrac'] = 0.95

    pars = {
        'geomExtract': 'original',
        'outFormat': 'JSON-Format',
        'gridded': True,
        'webApp': True,
        'finalOutput': True,
        'httpMethod': 'POST'
    }
    return pars | params

def _get_proba_info(params):
    proba_thres = 0
    proba_unit = 'perc'

    if params['climStats'] in ['probExc', 'probNoExc']:
        if params['variable'] == 'length':
            proba_thres = int(params['probaThres'])
        else:
            if params['variable'] == 'onset':
                proba_thres = _format_days_proba_threshold(
                    params['probaThres'],
                    params['rainy_season']['startMonthO'],
                    params['rainy_season']['startDayO']
                )
            if params['variable'] == 'cessation':
                proba_thres = _format_days_proba_threshold(
                    params['probaThres'],
                    params['rainy_season']['startMonthC'],
                    params['rainy_season']['startDayC']
                )
        proba_unit = params['probaUnit']

    return proba_thres, proba_unit

def _format_days_proba_threshold(
    proba_thres,
    start_month,
    start_day
):
    start = date(2025, start_month, start_day)
    m, d = map(int, proba_thres.split("-"))
    seas = date(2025, m, d)
    if seas < start:
        seas = date(2026, m, d)

    return (seas - start).days

def _get_ckey_title(params):
    if params['variable'] == 'onset':
        var_name = 'Rainy season onset'
        var_unit = ''
    elif params['variable'] == 'cessation':
        var_name = 'Rainy season cessation'
        var_unit = ''
    else:
        var_name = 'Rainy season length'
        var_unit = 'days'

    if params['mapType'] == 'climatology':
        clim_names = {
            'mean': 'average',
            'median': 'median',
            'stdev': 'standard deviation',
            'cv': 'coefficient of variation',
            'probExc': 'probability of exceeding',
            'probNoExc': 'probability of non-exceeding'
        }
        clim_fun = clim_names[params['climStats']]
        var_name = f'{var_name}, {clim_fun}'
        if params['climStats'] in ['probExc', 'probNoExc']:
            if params['variable'] == 'length':
                pt = int(params['probaThres'])
                pt = f'{pt} days'
            else:
                pt = f'2026-{params['probaThres']}'
                pt = datetime.strptime(pt, '%Y-%m-%d')
                pt = pt.strftime('%b %d')

            if params['probaUnit'] == 'perc':
                var_unit = '%'
            else:
                var_unit = ''
        else:
            pt = ''
            if params['variable'] == 'length':
                clim_units = {
                    'mean': 'days',
                    'median': 'days',
                    'stdev': 'days',
                    'cv': '%'
                }
            else:
                clim_units = {
                    'mean': '',
                    'median': '',
                    'stdev': 'days',
                    'cv': '%'
                }

            var_unit = clim_units[params['climStats']]

        var_name = f'{var_name} {pt}'

    if params['mapType'] == 'anomaly':
        var_name = f'{var_name} anomaly'
        var_unit = 'days'

    if var_unit == '':
        ckey_title = var_name
    else:
        ckey_title = f'{var_name} (units: {var_unit})'

    ckey_title = ' '.join(ckey_title.split())
    return ckey_title

def _format_ckey_labels_num(rainy_season, params):
    if params['colorbar']['break_type'] != 'user':
        return params

    format_breaks = False
    if params['mapType'] == 'climatology':
        if params['variable'] in ['onset', 'cessation']:
            breaks = params['colorbar']['break_cbar']
            if params['variable'] == 'onset':
                start = rainy_season.onset_start.values[0]
            if params['variable'] == 'cessation':
                start = rainy_season.cessation_start.values[0]
            format_breaks = True

    if params['mapType'] == 'rawdata':
        if params['variable'] in ['onset', 'cessation']:
            breaks = params['colorbar']['break_cbar']
            if params['variable'] == 'onset':
                start = (
                    rainy_season.onset_start
                    .sel(year=params['Year']).values
                )
            if params['variable'] == 'cessation':
                start = (
                    rainy_season.cessation_start
                    .sel(year=params['Year']).values
                )
            format_breaks = True

    if format_breaks:
        start = pd.to_datetime(start)
        year = start.strftime('%Y')
        brks = [f"{year}-{b}" for b in breaks]
        brks = pd.to_datetime(brks, format='%Y-%b-%d')
        mask = brks < brks[0]
        brks = brks.where(~mask, brks + pd.DateOffset(years=1))
        brks = (brks - start).days.tolist()
        params['colorbar']['break_cbar'] = brks

    return params

def _format_ckey_labels_dates(
    map_png,
    rainy_season,
    params
):
    format_labels = False
    if params['mapType'] == 'climatology':
        if params['variable'] in ['onset', 'cessation']:
            if params['climStats'] in ['mean', 'median']:
                labels = map_png['ckeys']['labels']
                if params['variable'] == 'onset':
                    year = rainy_season.onset_start.values[0]
                if params['variable'] == 'cessation':
                    year = rainy_season.cessation_start.values[0]
                format_labels = True

    if params['mapType'] == 'rawdata':
        if params['variable'] in ['onset', 'cessation']:
            labels = map_png['ckeys']['labels']
            if params['variable'] == 'onset':
                year = (
                    rainy_season.onset_start
                    .sel(year=params['Year']).values
                )
            if params['variable'] == 'cessation':
                year = (
                    rainy_season.cessation_start
                    .sel(year=params['Year']).values
                )
            format_labels = True

    if format_labels:
        dlab = [
            year + np.timedelta64(int(float(l)), 'D')
            for l in labels
        ]
        dlab = (
            pd.to_datetime(dlab)
            .strftime('%b-%d').tolist()
        )
        map_png['ckeys']['labels'] = dlab

    return map_png

def get_rainy_season(params):
    cache_key = hash_params_rainy_season(
        params['rainy_season']
    )
    cached_data = cache.get(cache_key)

    if cached_data is None:
        try:
            cached_data = _compute_rainy_season(params)
            cached_data = cached_data.compute(
                scheduler='single-threaded'
            )
        except Exception as e:
            return {'status': -1, 'message': str(e)}
        cache.set(cache_key, cached_data)

    return {'status': 0, 'data': cached_data}

def check_rainy_season_cache_status(params):
    rainy_season = params.get('rainy_season')
    if not isinstance(rainy_season, dict):
        return {
            'status': -1,
            'message': 'Missing rainy-season parameters.'
        }

    cache_key = hash_params_rainy_season(rainy_season)
    return {
        'status': 0,
        'cached': cache.has(cache_key)
    }

def _compute_rainy_season(params):
    params_data = {
        k: params[k]
        for k in ['temporalRes', 'dataset']
    }
    params_precip = params_data.copy()
    params_precip['variable'] = 'precip'
    precip = get_zarr_dataset(params_precip)
    precip_da = precip['precip']

    params_et0 = params_data.copy()
    params_et0['variable'] = 'et0'
    et0 = get_zarr_dataset(params_et0)
    et0_da = et0['et0']

    bbox = {
        'minLon': precip_da['lon'].min().values.item(),
        'maxLon': precip_da['lon'].max().values.item(),
        'minLat': precip_da['lat'].min().values.item(),
        'maxLat': precip_da['lat'].max().values.item()
    }
    taw = get_gyga_af_tawc('agg_erzd', bbox)
    taw_da = regrid2D_dataArray(
        precip_da, taw['tawc_agg_erzd']
    )

    return compute_rainy_season(
        precip_da, et0_da, taw_da,
        params['rainy_season']
    )

def _get_clim_data(
    xr_da, clim_fun, min_year,
    rainy_season_key,
    proba_thres=0,
    proba_unit='perc'
):
    params = {
        'type': 'rainy_season_climatology',
        'cache_key': rainy_season_key,
        'clim_fun': clim_fun,
        'min_year': min_year,
        'proba_thres': proba_thres,
        'proba_unit': proba_unit
    }
    cache_key = hash_params_rainy_season(params)
    cached_data = cache.get(cache_key)

    if cached_data is None:
        try:
            cached_data = aggregate_climatology(
                xr_da, 
                clim_fun,
                min_year=min_year,
                proba_thres=proba_thres,
                proba_unit=proba_unit,
                time_dim='year',
            )
            if cached_data.chunks is not None:
                cached_data = cached_data.compute(
                    scheduler='single-threaded'
                )
            cache.set(cache_key, cached_data)
        except Exception as e:
            return {'status': -1, 'message': str(e)}

    return {'status': 0, 'data': cached_data}

def _get_default_params():
    params = {'temporalRes': 'daily'}
    app_dir = GLOBAL_CONFIG['app_dir']

    file0 = os.path.join(
        app_dir, 'agriculture', 'analysis',
        'yaml', 'rainy-season.yaml'
    )
    tmp = load_yaml_file(file0)
    params['dataset'] = tmp['dataset']['use']

    file1 = os.path.join(
        app_dir, 'yaml', 'season-definition.yaml'
    )
    tmp = load_yaml_file(file1)
    tmp = tmp['rainy_season']
    p_onset = {}
    for k, v in tmp['onset'].items():
        kn = k if k == 'rainThres' else f'{k}O'
        p_onset[kn] = v
    p_cessation = {
        f'{k}C': v 
        for k, v in tmp['cessation'].items()
    }
    p_rseas = p_onset | p_cessation
    p_rseas = p_rseas | tmp['computation']
    p_rseas = {
        k: int(v) if isinstance(v, float) and v.is_integer() else v
        for k, v in p_rseas.items()
    }
    params['rainy_season'] = p_rseas
    return params

def init_rainy_season():
    params = _get_default_params()
    season_data = get_rainy_season(params)
    if season_data['status'] == -1:
        raise ValueError(season_data['message'])

def _read_crop_suitability_data(params):
    params_data = {
        k: params[k]
        for k in ['temporalRes', 'dataset']
    }
    params_precip = params_data.copy()
    params_precip['variable'] = 'precip'
    precip = get_zarr_dataset(params_precip)
    precip_da = precip['precip']

    params_tmax = params_data.copy()
    params_tmax['variable'] = 'tmax'
    tmax = get_zarr_dataset(params_tmax)
    tmax_da = tmax['tmax']

    params_tmin = params_data.copy()
    params_tmin['variable'] = 'tmin'
    tmin = get_zarr_dataset(params_tmin)
    tmin_da = tmin['tmin']

    return precip_da, tmax_da, tmin_da

def _get_crop_suitability_year(params):
    precip, tmax, tmin =  _read_crop_suitability_data(params)
    precip_data = _get_crop_suitability_season(precip, params)
    if precip_data['status'] == -1:
        return precip_data
    precip = precip_data['data']
    tmax_data = _get_crop_suitability_season(tmax, params)
    if tmax_data['status'] == -1:
        return tmax_data
    tmax = tmax_data['data']
    tmin_data = _get_crop_suitability_season(tmin, params)
    if tmin_data['status'] == -1:
        return tmin_data
    tmin = tmin_data['data']
    return {'status': 0, 'data': (precip, tmax, tmin)}

def _get_crop_suitability_season(xr_da, params):
    tindex = get_daily_index_season(
        xr_da['time'].values,
        params['startMonth'],
        params['startDay'],
        params['endMonth'],
        params['endDay']
    )
    cyear = year_daily_index_season(
        tindex, params['Year']
    )
    if cyear: return cyear

    index = tindex['index'][params['Year']]
    frac = tindex['length'][params['Year']]['frac']
    nb_seas = tindex['length'][params['Year']]['nb_seas']
    if frac < params['minFrac']:
        msg = 'Not enough data to compute the seasonal parameter'
        return {'status': -1, 'message': msg}

    xr_da = xr_da.isel(time=index)
    xr_nomiss = xr_da.notnull().sum(dim='time')
    xr_frac = xr_nomiss / nb_seas
    xr_da = xr_da.where(xr_frac >= params['minFrac'], np.nan)
    return {'status': 0, 'data': xr_da}

def _compute_crop_suitability(params):
    cs_data = _get_crop_suitability_year(params)
    if cs_data['status'] == -1:
        return cs_data
    precip, tmax, tmin = cs_data['data']

    spatial_coords = {
        'lat': precip['lat'],
        'lon': precip['lon']
    }
    if not (
        precip['lat'].equals(tmax['lat'])
        and precip['lon'].equals(tmax['lon'])
    ):
        tmax = tmax.interp(spatial_coords)
    if not (
        precip['lat'].equals(tmin['lat'])
        and precip['lon'].equals(tmin['lon'])
    ):
        tmin = tmin.interp(spatial_coords)

    precip, tmax, tmin = xr.align(
        precip, tmax, tmin, join='inner'
    )
    if precip.sizes['time'] == 0:
        return {
            'status': -1,
            'message': 'Rainfall and temperature have no common dates.'
        }

    max_temp = (
        tmax.mean(dim='time', skipna=True)
        <= float(params['tempHigh'])
    )
    min_temp = (
        tmin.mean(dim='time', skipna=True)
        >= float(params['tempLow'])
    )
    temp_range = (
        (tmax - tmin).mean(dim='time', skipna=True)
        <= float(params['tempOptim'])
    )
    wet_days = (
        (precip >= float(params['rainThres'])).sum(dim='time')
        >= int(params['nbWetDays'])
    )
    total_precip = precip.sum(dim='time', skipna=True)
    precip_range = (
        (total_precip >= float(params['precipLow']))
        & (total_precip <= float(params['precipHigh']))
    )

    valid = (
        precip.notnull().any(dim='time')
        & tmax.notnull().any(dim='time')
        & tmin.notnull().any(dim='time')
    )
    crop_suit = (
        max_temp.astype(np.int8)
        + min_temp.astype(np.int8)
        + temp_range.astype(np.int8)
        + precip_range.astype(np.int8)
        + wet_days.astype(np.int8)
    ).where(valid)

    suitability = xr.Dataset(
        data_vars={
            'max_temp': max_temp.where(valid),
            'min_temp': min_temp.where(valid),
            'temp_range': temp_range.where(valid),
            'precip_range': precip_range.where(valid),
            'wet_days': wet_days.where(valid),
            'crop_suit': crop_suit,
        },
        attrs={
            'title': 'Crop climate suitability',
            'target_year': int(params['Year']),
            'season_start': (
                f"{int(params['startMonth']):02d}-"
                f"{int(params['startDay']):02d}"
            ),
            'season_end': (
                f"{int(params['endMonth']):02d}-"
                f"{int(params['endDay']):02d}"
            ),
        }
    )
    suitability['crop_suit'].attrs = {
        'long_name': 'Crop climate suitability',
        'units': 'index',
        'valid_range': [0, 5],
    }
    return {'status': 0, 'data': suitability}
