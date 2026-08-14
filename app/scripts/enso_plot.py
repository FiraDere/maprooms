import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge, Circle, FancyBboxPatch
from .imagepng import render_image_png

plt.switch_backend('Agg')

def plot_enso_probabilities(proba, figsize=(10, 6)):
    df = proba['table_proba']
    issued_date = proba['issued_date'].strftime('%d %B %Y')

    x = np.arange(len(df))
    width = 0.28
    fig, ax = plt.subplots(figsize=figsize)

    ax.bar(
        x - width,
        df['La Niña'],
        width,
        label='La Niña',
        color='#3366ff',
        edgecolor='blue',
    )
    ax.bar(
        x, df['Neutral'], width, label='Neutral', color='lightgray', edgecolor='gray'
    )
    ax.bar(
        x + width,
        df['El Niño'],
        width,
        label='El Niño',
        color='tomato',
        edgecolor='red',
    )

    ax.set_title(
        f'NOAA CPC ENSO Probabilities (issued {issued_date})', fontsize=18, pad=22
    )
    ax.text(
        0.5,
        1.005,
        'based on -0.5°/+0.5°C thresholds in ERSSTv5 Relative Niño-3.4 index/RONI',
        transform=ax.transAxes,
        ha='center',
        va='bottom',
        fontsize=13,
    )

    ax.set_ylabel('Percent Chance (%)', fontsize=16)
    ax.set_xlabel('Season', fontsize=16)
    ax.set_xticks(x)
    ax.set_xticklabels(df['Season'], fontsize=12)
    ax.set_ylim(0, 100)
    ax.set_yticks(np.arange(0, 101, 10))
    ax.grid(axis='y', alpha=0.3)
    ax.set_axisbelow(True)
    handles, labels = ax.get_legend_handles_labels()
    order = [2, 1, 0]
    ax.legend(
        [handles[i] for i in order],
        [labels[i] for i in order],
        loc='upper left',
        bbox_to_anchor=(1.01, 1.0),
        frameon=True,
        fontsize=12,
    )
    return render_image_png(plt, False, 'tight', 'white')

def plot_enso_strength_probabilities(proba, figsize=(12, 7)):
    df = proba['table_proba'].copy()
    header_info = proba['header_info']
    issue_date = proba['issued_date']

    issue_date = pd.to_datetime(issue_date)
    issued_date = issue_date.strftime('%d %B %Y')

    prob_cols = list(header_info.keys())
    for c in prob_cols:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    season_col = df.columns[0]
    seasons = df[season_col].astype(str).tolist()

    neg_cols = ['col1', 'col2', 'col3', 'col4']
    neu_cols = ['col5']
    pos_cols = ['col6', 'col7', 'col8', 'col9']

    neg_labels = ['\n'.join(header_info[c]) for c in neg_cols]
    neu_labels = ['\n'.join(header_info[c]) for c in neu_cols]
    pos_labels = ['\n'.join(header_info[c]) for c in pos_cols]

    neg_colors = ['#08306b', '#2171b5', '#6baed6', '#bdd7e7']
    neu_colors = ['#d9d9d9']
    pos_colors = ['#fcbba1', '#fb6a4a', '#de2d26', '#a50f15']

    x = np.arange(len(df))
    width = 0.22
    fig, ax = plt.subplots(figsize=figsize)

    # La Nina
    bottom = np.zeros(len(df))
    neg_zip = zip(neg_cols, neg_colors, neg_labels)
    for col, color, label in neg_zip:
        vals = df[col].to_numpy()
        ax.bar(
            x - width,
            vals,
            width,
            label=label,
            bottom=bottom,
            color=color,
            edgecolor='black',
            linewidth=0.4,
        )
        bottom += vals

    # Neutral
    ax.bar(
        x,
        df[neu_cols[0]],
        width,
        label=neu_labels[0],
        color='#d9d9d9',
        edgecolor='black',
        linewidth=0.4,
    )

    # El Nino
    bottom = np.zeros(len(df))
    pos_zip = zip(pos_cols, pos_colors, pos_labels)
    for col, color, label in pos_zip:
        vals = df[col].to_numpy()
        ax.bar(
            x + width,
            vals,
            width,
            label=label,
            bottom=bottom,
            color=color,
            edgecolor='black',
            linewidth=0.4,
        )
        bottom += vals

    ax.set_title(
        f'NOAA CPC ENSO Strength Probabilities (issued {issued_date})',
        fontsize=20,
        pad=22,
    )
    ax.text(
        0.5,
        1.005,
        'based on thresholds in ERSSTv5 Relative Niño-3.4 index/RONI',
        transform=ax.transAxes,
        ha='center',
        va='bottom',
        fontsize=13,
    )

    ax.set_ylabel('Percent Chance (%)', fontsize=14)
    ax.set_xlabel('Season', fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(seasons, fontsize=12)
    ax.set_ylim(0, 100)
    ax.set_yticks(np.arange(0, 101, 10))
    ax.grid(axis='y', color='lightgray', linewidth=0.8)
    ax.set_axisbelow(True)

    ax.legend(
        loc='upper left',
        bbox_to_anchor=(1.01, 1.0),
        # loc='center left',
        # bbox_to_anchor=(1.02, 0.5),
        frameon=True,
        fontsize=10,
    )
    return render_image_png(plt, False, 'tight', 'white')

def plot_enso_oni(
    oni,
    col='oni',
    thres=0.8,
    ymax=2.4,
    ytick=0.4,
    ylab='Relative Niño3.4 index (°C)',
    figsize=(11, 6),
    dispLastValue=False
):
    df = oni.copy()
    df.dropna(inplace=True)
    start = pd.to_datetime(df['start_month'], format='%Y-%m')
    end = pd.to_datetime(df['end_month'], format='%Y-%m')
    df['date'] = start + (end - start) / 2

    y_e = df['year'].iloc[-1]
    s_e = df['season'].iloc[-1]
    v_e = df[col].iloc[-1]
    label_e = f'Latest seasonal value to {y_e} {s_e}: {v_e:+.2f}°C'

    return _plot_enso_data(
            df, col, thres,
            ymax, ytick, ylab,
            dispLastValue, label_e,
            figsize
        )

def plot_enso_weekly(
    enso_df,
    col='anom',
    thres=0.8,
    ymax=2.4,
    ytick=0.4,
    ylab='Niño3.4 index (°C)',
    figsize=(11, 6),
    dispLastValue=False,
    varUnits='°C'
):
    df = enso_df.copy()
    df.dropna(inplace=True)
    df['date'] = pd.to_datetime(df['week'], format='%Y-%m-%d')

    d_e = df['date'].iloc[-1]
    d_e = d_e.strftime('%d %b %Y')
    v_e = df[col].iloc[-1]
    label_e = f'Latest weekly value to {d_e}: {v_e:+.2f}{varUnits}'

    return _plot_enso_data(
            df, col, thres,
            ymax, ytick, ylab,
            dispLastValue, label_e,
            figsize
        )

def plot_enso_monthly(
    enso_df,
    col='anom',
    thres=0.8,
    ymax=2.4,
    ytick=0.4,
    ylab='Niño3.4 index (°C)',
    figsize=(11, 6),
    dispLastValue=False,
    varUnits='°C'
):
    df = enso_df.copy()
    df.dropna(inplace=True)
    df['day'] = 1
    df['date'] = pd.to_datetime(df[['year', 'month', 'day']])

    d_e = df['date'].iloc[-1]
    d_e = d_e.strftime('%B %Y')
    v_e = df[col].iloc[-1]
    label_e = f'Latest monthly value to {d_e}: {v_e:+.2f}{varUnits}'

    return _plot_enso_data(
            df, col, thres,
            ymax, ytick, ylab,
            dispLastValue, label_e,
            figsize
        )

def _plot_enso_data(
    df, col, thres,
    ymax, ytick, ylab,
    disp_last_value, label_e,
    figsize
):
    fig, ax = plt.subplots(figsize=figsize)
    ax.axhspan(thres, ymax + 1, color='mistyrose', zorder=0)
    ax.axhspan(-ymax - 1, -thres, color='lavender', zorder=0)
    ax.axhline(thres, color='red', linestyle='--', linewidth=1)
    ax.axhline(-thres, color='blue', linestyle='--', linewidth=1)
    ax.axhline(0, color='gray', linewidth=0.7)

    ax.plot(df['date'], df[col], color='black', linewidth=1, label=label_e)

    xlim = _set_xaxis_limit(df['date'])
    xmin = df['date'].iloc[0] - pd.DateOffset(months=xlim)
    xmax = df['date'].iloc[-1] + pd.DateOffset(months=xlim)

    yup = np.arange(0, ymax + ytick, ytick)
    if len(yup) > 8:
        ithres = yup <= thres
        yup1 = yup[ithres]
        yup2 = yup[~ithres]
        yup2 = yup2[1::2]
        yup = np.concatenate((yup1, yup2))

    ylow = -1 * np.flip(yup[1:])
    yticks = np.concatenate((ylow, yup))

    ax.set_xlim(xmin, xmax)
    ax.set_ylabel(ylab, fontsize=13)
    ax.set_ylim(-ymax, ymax)
    ax.set_yticks(yticks)

    ax.grid(True, which='major', color='lightgray', linewidth=0.8)
    ax.grid(True, which='minor', color='gainsboro', linestyle=':', linewidth=0.5)

    if disp_last_value:
        ax.legend(
            loc='upper right', frameon=True, framealpha=1, edgecolor='black', fancybox=False
        )
    return render_image_png(plt, False, 'tight', 'white')

def _set_xaxis_limit(date):
    drange = date.max() - date.min()
    dt = drange / pd.Timedelta(days=1)
    if dt <= 720:
        ret = 0
    elif dt > 720 and dt <= 1825:
        ret = 1
    elif dt > 1825 and dt <= 3650:
        ret = 2
    elif dt > 3650 and dt <= 7300:
        ret = 3
    elif dt > 7300 and dt <= 10950:
        ret = 4
    else:
        ret = 6
    return ret
