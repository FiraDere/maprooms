import os
import json
import numpy as np
import pandas as pd
from datetime import date

from app.dst_api.scripts import (
    get_zarr_dataset,
    aggregate_climatology
)
from app.scripts.imagepng import create_imagePng
from app.scripts.colorbar import matplotlib_invalid_colors
from app.scripts._cache import cache, hash_params_rainy_season
from app.misc.scripts.soilgrids_tawc import get_gyga_af_tawc
from app.misc.scripts.extract_data import regrid2D_dataArray
from app.misc.scripts.rainy_season import compute_rainy_season
from app.scripts.util import load_yaml_file
from app.scripts._global import GLOBAL_CONFIG

def agriculture_analysis_sp_data(params):
    if params['colorbar']['color_type'] == 'user':
        user_col = matplotlib_invalid_colors(
            params['colorbar']['color_cbar']
        )
        if user_col is not None:
            wrng_col = ', '.join(user_col)
            msg = f'Matplotlib invalid colors: {wrng_col}'
            return {'status': -1, 'message': msg}
        if params['colorbar']['color_add_ext']:
            ext_col = matplotlib_invalid_colors(
                params['colorbar']['color_ext'],
                transparent=True
            )
            if ext_col is not None:
                wrng_col = ', '.join(ext_col)
                msg = f'Matplotlib invalid colors extensions: {wrng_col}'
                return {'status': -1, 'message': msg}

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

    map_png = _format_ckey_labels_dates(
        map_png, rainy_season, params
    )

    if params['mapType'] == 'climatology':
        map_png['date'] = ''
    else:
        map_png['date'] = f"{params['Year']} season"

    map_png['ckeys']['title'] = _get_ckey_title(params)

    return {'status': 0, 'data': map_png}

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
        var_name = f'{var_name} climatology'

    if params['mapType'] == 'anomaly':
        var_name = f'{var_name} anomaly'
        var_unit = 'days'

    if var_unit == '':
        ckey_title = var_name
    else:
        ckey_title = f'{var_name} ({var_unit})'

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
        except Exception as e:
            return {'status': -1, 'message': str(e)}
        cache.set(cache_key, cached_data)

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
