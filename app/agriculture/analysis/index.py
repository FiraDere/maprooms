from flask import (
    Blueprint,
    render_template,
    request,
    session
)
from flask import current_app as app
import json
import config

from .scripts.analysis_sp import (
    agriculture_analysis_sp_data,
    check_rainy_season_cache_status
)
from .scripts.analysis_ts import (
    agriculture_analysis_ts_series,
    agriculture_analysis_ts_proba,
    agriculture_analysis_ts_anom,
    agriculture_analysis_ts_cropsuit
)

agriculture_analysis = Blueprint(
    'agriculture_analysis',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/static/agriculture_analysis',
)

dataUser = dict()
@agriculture_analysis.before_request
def before_request():
    global dataUser
    if 'logged_in' not in session:
        dataUser = {'uid': -1}
    else:
        if session['logged_in']:
            dataUser = session['data']
        else:
            dataUser = {'uid': -1}

@agriculture_analysis.route('/agriculture_analysis_map', methods=['POST'])
def agriculture_analysis_map():
    params = request.get_json()
    try:
        map_data = agriculture_analysis_sp_data(params)
        return json.dumps(map_data)
    except Exception as e:
        return json.dumps({'status': -1, 'message': str(e)})

@agriculture_analysis.route('/rainy_season_cache_status', methods=['POST'])
def rainy_season_cache_status():
    params = request.get_json()
    try:
        status = check_rainy_season_cache_status(params)
        return json.dumps(status)
    except Exception as e:
        return json.dumps({'status': -1, 'message': str(e)})

@agriculture_analysis.route('/agriculture_analysis_series', methods=['POST'])
def agriculture_analysis_series():
    params = request.get_json()
    try:
        data_series = agriculture_analysis_ts_series(params)
        return json.dumps(data_series)
    except Exception as e:
        return json.dumps({'status': -1, 'message': str(e)})

@agriculture_analysis.route('/agriculture_analysis_proba', methods=['POST'])
def agriculture_analysis_proba():
    params = request.get_json()
    try:
        data_proba = agriculture_analysis_ts_proba(params)
        return json.dumps(data_proba)
    except Exception as e:
        return json.dumps({'status': -1, 'message': str(e)})

@agriculture_analysis.route('/agriculture_analysis_anom', methods=['POST'])
def agriculture_analysis_anom():
    params = request.get_json()
    try:
        data_anom = agriculture_analysis_ts_anom(params)
        return json.dumps(data_anom)
    except Exception as e:
        return json.dumps({'status': -1, 'message': str(e)})

@agriculture_analysis.route('/agriculture_analysis_cropsuit', methods=['POST'])
def agriculture_analysis_cropsuit():
    params = request.get_json()
    try:
        data_cs = agriculture_analysis_ts_cropsuit(params)
        return json.dumps(data_cs)
    except Exception as e:
        return json.dumps({'status': -1, 'message': str(e)})
