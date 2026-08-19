
from app.dst_api.scripts import (
    download_rawdata,
    download_analysis
)

from app.scripts.colorbar import check_invalid_colors
from app.scripts.util import parse_json_spatial_data
from app.scripts.imagepng import create_imagePng

def climate_monitoring_sp_data(params):
    check = check_invalid_colors(params['colorbar'])
    print(params)

    if check['status'] == -1: return check

    if params['temporalRes'] == 'dekadal':
        if params['map_variable'] == 'rain_dek':
            params = _create_params_sp_dekad(params)
            json_data = download_rawdata(params)
            data = parse_json_spatial_data(json_data, 'Date')
        elif params['map_variable'] in ['anom_dek', 'anom_per_dek']:
            params = _create_params_sp_dkanom(params)
            json_data = download_analysis(params)
            data = parse_json_spatial_data(json_data, 'Date')
        else:
            # all cumul
            return {'status': -1, 'message': 'Monitoring dekadal'}

    elif params['temporalRes'] == 'monthly':
        return {'status': -1, 'message': 'Monitoring monthly'}
    elif params['temporalRes'] == 'seasonal':
        return {'status': -1, 'message': 'Monitoring seasonal'}
    else:
        return {
            'status': -1,
            'message': 'Unknown temporal resolution'
        }

    if data['status'] == -1: return data

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


def _create_params_sp_dekad(params):
    params['variable'] = params['variable'][0]
    pars = {
        'geomExtract': 'original',
        'outFormat': 'JSON-Format',
        'gridded': True,
        'webApp': True,
        'finalOutput': True,
        'httpMethod': 'POST'
    }
    return pars | params

def _create_params_sp_dkanom(params):
    params['variable'] = params['variable'][0]
    pars = {
        'startYear': 1991,
        'endYear': 2020,
        'minYear': 30,
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
