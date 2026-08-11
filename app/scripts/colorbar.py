import numpy as np
import re
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d
from .colorlist import _make_color_dict
plt.switch_backend('Agg')

def colorRampPalette(colors):
    rgbs = [mcolors.to_rgb(c) for c in colors]
    nc = len(rgbs)

    if nc == 1:
        rgbs = [rgbs[0], rgbs[0]]
        nc = 2

    x = np.linspace(0, 1, nc)
    palette = (interp1d(x, np.array([rgbs[i][0] for i in range(nc)])),
               interp1d(x, np.array([rgbs[i][1] for i in range(nc)])),
               interp1d(x, np.array([rgbs[i][2] for i in range(nc)])))

    def roundcolor(cl):
        return np.array([max(min(1.0, e), 0) for e in cl])

    def ramp(n):
        x = np.linspace(0, 1, n)
        rgb = (roundcolor(palette[0](x)),
               roundcolor(palette[1](x)),
               roundcolor(palette[2](x)))
        kol = []
        for j in range(n):
            kl = (rgb[0][j], rgb[1][j], rgb[2][j])
            kol = kol + [mcolors.rgb2hex(kl)]
        return kol

    return ramp

def get_ColorScale(ckeyfile):
    with open(ckeyfile) as cf:
        ckey = [l.strip(' ') for l in cf]
        ckey = [x.rstrip('\n') for x in ckey if not x.startswith('#')]
        ckey = [x for x in ckey if x != '']
        ckey = [';'.join(x.split()) for x in ckey]
        ckey = [x.split(';') for x in ckey]
        ckey = [x for x in ckey if len(x) > 2]
        ck = []
        for x in ckey:
            c = []
            for y in x:
                if y.startswith('!'):
                    break
                else:
                    c = c + [y]
            ck = ck + [c]
        ckey = [x if len(x) == 3 else x[0:2] + [' '.join([x[i] for i in range(2, len(x))])] for x in ck]

    breaks = [x[0] for x in ckey[1:]]
    pattern = re.compile('\\.')
    precFloat = [not pattern.search(x) == None for x in breaks]
    if any(precFloat):
        breaks = [float(x) for x in breaks]
    else:
        breaks = [int(x) for x in breaks]

    kol_ext = [ckey[0][2], ckey[len(ckey) - 1][2]]
    kol_ext = [x.lower() for x in kol_ext]
    kol = [x[2] for x in ckey[1:-1]]
    kol = [x.lower() for x in kol]

    kol_dict = _make_color_dict()
    kol_dict = dict((key.lower(), value) for (key, value) in kol_dict.items())

    colors_ext = []
    for k in kol_ext:
        if not k.startswith('#'):
            if k in list(kol_dict.keys()):
                k = kol_dict[k]
        colors_ext = colors_ext + [k]

    colors = []
    for k in kol:
        if not k.startswith('#'):
            if k in list(kol_dict.keys()):
                k = kol_dict[k]
        colors = colors + [k]

    return breaks, colors, colors_ext

def format_ColorScale(breaks, colors, colors_ext):
    kol = [None] * (len(colors) + 2)

    for j in range(len(kol)):
        if j == 0:
            kol[j] = colors_ext[0]
        elif j == len(kol) - 1:
            kol[j] = colors_ext[1]
        else:
            kol[j] = colors[j - 1]

    breaks = [round(x, 4) for x in breaks]
    if all(not isinstance(x, float) or x.is_integer() for x in breaks):
        breaks = [int(x) if isinstance(x, float) else x for x in breaks]
    breaks = [str(x) for x in breaks]

    return {'labels': breaks, 'colors': kol}

def get_ColorBarName(color, n, inverse=False):
    if n < 4:
        raise Exception(f'n must be greater than 3')
    listedCmap = plt.get_cmap(color, n)
    kolor = [None] * n
    for j in range(n):
        kolor[j] = mcolors.to_hex(listedCmap(j))

    if inverse:
        kolor.reverse()

    return {
        'colors': kolor[1:-1],
        'ext': [kolor[0], kolor[-1]]
    }

def convert_NameToHex(color_list):
    return [mcolors.to_hex(c) for c in color_list]

def matplotlib_invalid_colors(list_colors, transparent=False):
    if transparent:
        is_colors = [
            not mcolors.is_color_like(k)
            if k != 'transparent' else False
            for k in list_colors
        ]
    else:
        is_colors = [
            not mcolors.is_color_like(k)
            for k in list_colors
        ]

    if any(is_colors):
        tmp = zip(list_colors, is_colors)
        wcolors = [k for k, w in tmp if w]
        return wcolors
    else:
        return None
