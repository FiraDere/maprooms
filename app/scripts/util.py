import os
import yaml
import json
import numpy as np

def load_yaml_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            conf = yaml.safe_load(f)
        except yaml.YAMLError as e:
            print(f'Error {e}')

    return conf

def list_yaml_maproom_items(app_dir, file):
    yaml_paths = []
    for root, subdirs, files in os.walk(app_dir):
        yaml_file = os.path.join(root, 'yaml', file)

        if os.path.isfile(yaml_file):
            yaml_file = os.path.normpath(yaml_file)
            lpth = yaml_file.split(os.sep)
            i0 = lpth.index('app') + 1
            i1 = len(lpth) - 1
            yaml_paths = yaml_paths + [lpth[i0:i1]]

    return [yl for yl in yaml_paths if len(yl) > 0]

def pretty(low, high, n):
    if low == high:
        low = low - 1.0e-6
        high = high + 1.0e-6

    vrange = _nicenumber(high - low, False)
    d = _nicenumber(vrange / (n - 1), True)
    miny = np.floor(low / d) * d
    maxy = np.ceil(high / d) * d

    return np.arange(miny, maxy + 0.5 * d, d)

def _nicenumber(x, round):
    exp = np.floor(np.log10(x))
    f = x / 10 ** exp

    if round:
        if f < 1.5:
            nf = 1.0
        elif f < 3.0:
            nf = 2.0
        elif f < 7.0:
            nf = 5.0
        else:
            nf = 10.0
    else:
        if f <= 1.0:
            nf = 1.0
        elif f <= 2.0:
            nf = 2.0
        elif f <= 5.0:
            nf = 5.0
        else:
            nf = 10.0

    return nf * 10.0 ** exp

def str2numeric_dict_args(args):
    for key in args:
        val = args[key]
        if type(val) is str:
            if not val.isalpha():
                val = int(val) if val.isdigit() else float(val)
        args[key] = val

    return args

def remove_duplicates_list(x):
    # respect order
    y = [j for i, j in enumerate(x) if j not in x[:i]]
    # y = list(dict.fromkeys(x))
    # not respecting order
    # y = list(set(x))
    return y

def parse_json_spatial_data(json_data, date_key):
    jsd = json.loads(json_data)
    if jsd['status'] == -1: return jsd
    jsd = json.loads(jsd['data'])
    lat = np.array(jsd['Latitude'])
    lon = np.array(jsd['Longitude'])
    data = np.array(jsd['Data'])
    data = np.where(data == jsd['Missing'], np.nan, data)

    return {
        'status': 0,
        'date': jsd[date_key],
        'lon': lon,
        'lat': lat,
        'data': data,
        'longname': jsd['VariableName'],
        'units': jsd['VariableUnits'],
        'varid': jsd['VariableVarId'],
        'dimensions': jsd['Dimensions']
    }
