from flask import (
    Blueprint,
    render_template,
    request,
    session
)
from flask import current_app as app
import json
import config
from threading import Lock

from .scripts.monitoring_sp import climate_monitoring_sp_data
from .scripts.monitoring_ts import climate_monitoring_ts_cumul

climate_monitoring = Blueprint(
    'climate_monitoring',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/static/climate_monitoring',
)

matplotlib_render_lock = Lock()

dataUser = dict()
@climate_monitoring.before_request
def before_request():
    global dataUser
    if 'logged_in' not in session:
        dataUser = {'uid': -1}
    else:
        if session['logged_in']:
            dataUser = session['data']
        else:
            dataUser = {'uid': -1}

@climate_monitoring.route('/climate_monitoring_map', methods=['POST'])
def climate_monitoring_map():
    params = request.get_json()
    try:
        map_data = climate_monitoring_sp_data(params)
        return json.dumps(map_data)
    except Exception as e:
        return json.dumps({'status': -1, 'message': str(e)})

@climate_monitoring.route('/climate_monitoring_cumul', methods=['POST'])
def climate_monitoring_cumul():
    params = request.get_json()
    try:
        cumul_data = climate_monitoring_ts_cumul(params)
        return json.dumps(cumul_data)
    except Exception as e:
        return json.dumps({'status': -1, 'message': str(e)})
