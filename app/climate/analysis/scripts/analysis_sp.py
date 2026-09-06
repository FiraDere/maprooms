import json
import numpy as np
from app.dst_api.scripts import (
    download_climdata,
    download_analysis,
    download_rawdata,
    download_analysis_dailydata,
    download_analysis_dailyclim,
    download_analysis_dailyanom
)
from app.scripts.imagepng import create_imagePng
from app.scripts.colorbar import check_invalid_colors
from app.scripts.util import parse_json_spatial_data

def climate_analysis_sp_data(params):
    check = check_invalid_colors(params['colorbar'])
    if check['status'] == -1: return check

    data = get_climate_analysis_sp_data(params)
    if data['status'] == -1: return data

    if not params['dailyAnalysis']:
        if params['mapType'] == 'climatology':
            if params['climFunction'] == 'trend':
                ix = data['varid'].index('slope')
                data['data'] = data['data'][ix, :, :, :]
                data['longname'] = data['longname'][ix]
                data['units'] = data['units'][ix]
                data['varid'] = data['varid'][ix]

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

    map_png['date'] = data['date']
    map_png['ckeys']['title'] = f"{data['longname']} ({data['units']})"

    return {'status': 0, 'data': map_png}

def get_climate_analysis_sp_data(params):
    if params['dailyAnalysis']:
        if params['mapType'] == 'climatology':
            params = _create_params_sp_clim(params)
            json_data = download_analysis_dailyclim(params)
            data = parse_json_spatial_data(json_data, 'Dates')
        elif params['mapType'] == 'rawdata':
            params = _create_params_sp_raw(params)
            json_data = download_analysis_dailydata(params)
            data = parse_json_spatial_data(json_data, 'Date')
        elif params['mapType'] == 'anomaly':
            params = _create_params_sp_anom(params)
            json_data = download_analysis_dailyanom(params)
            data = parse_json_spatial_data(json_data, 'Date')
        else:
            return {
                'status': -1,
                'message': 'Unknown map data'
            }
    else:
        if params['mapType'] == 'climatology':
            params = _create_params_sp_clim(params)
            json_data = download_climdata(params)
            data = parse_json_spatial_data(json_data, 'Dates')
        elif params['mapType'] == 'rawdata':
            params = _create_params_sp_raw(params)
            json_data = download_rawdata(params)
            data = parse_json_spatial_data(json_data, 'Date')
        elif params['mapType'] == 'anomaly':
            params = _create_params_sp_anom(params)
            json_data = download_analysis(params)
            data = parse_json_spatial_data(json_data, 'Date')
        else:
            return {
                'status': -1,
                'message': 'Unknown map data'
            }

    return data

def _create_params_sp_clim(params):
    pars = {
        'fullYear': False,
        'geomExtract': 'original',
        'outFormat': 'JSON-Format',
        'webApp': True,
        'finalOutput': True,
        'httpMethod': 'POST'
    }
    return pars | params

def _create_params_sp_raw(params):
    pars = {
        'geomExtract': 'original',
        'outFormat': 'JSON-Format',
        'gridded': True,
        'webApp': True,
        'finalOutput': True,
        'httpMethod': 'POST'
    }
    return pars | params

def _create_params_sp_anom(params):
    pars = {
        'analysis': 'anomaly',
        'geomExtract': 'original',
        'outFormat': 'JSON-Format',
        'climFunction': 'mean-stdev',
        'seasStats': 'mean-stdev',
        'fullYear': True,
        'climDate': None,
        'gridded': True,
        'webApp': True,
        'httpMethod': 'POST',
        'outFormat_0': 'JSON-Format'
    }
    return pars | params
