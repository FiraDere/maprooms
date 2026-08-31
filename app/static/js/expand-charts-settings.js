// converts an rgb(a) match from a regex to a #rrggbb hex string
function rgbTripleToHex(rgbMatch) {
    return `#${rgbMatch.slice(1, 4).map(value =>
        Number(value).toString(16).padStart(2, '0')
    ).join('')}`;
}

// to resolve css color names to rgb
function resolveCssColorToRgb(color) {
    const probe = document.createElement('span');
    probe.style.color = '';
    probe.style.color = color;
    if (!probe.style.color) {
        return null;
    }
    probe.style.display = 'none';
    document.body.appendChild(probe);
    const resolved = getComputedStyle(probe).color;
    probe.remove();
    return resolved || null;
}

function dotPathsToNestedObject(flat) {
    const nested = {};
    Object.entries(flat).forEach(([path, value]) => {
        const keys = path.split('.');
        let obj = nested;
        keys.forEach((key, i) => {
            if (i === keys.length - 1) {
                obj[key] = value;
            } else {
                obj[key] = obj[key] || {};
                obj = obj[key];
            }
        });
    });
    return nested;
}

// ---------------------------------------------------------------------
// tick-interval helpers
//
// The chart-settings popup lets the user type a manual tick interval for
// either axis, on every expand-modal chart. Those charts don't all plot
// the same kind of data on their axes - some are dates (Raw, Climato,
// Anomaly, Enso, rainy-season onset/cessation...), some are whole-number
// axes (a year axis, a count), some are floats (rainfall totals,
// anomalies, probabilities...). A single "must be a positive number"
// check doesn't know any of that apart, and that gap is what used to
// freeze the tab: on a `type: 'date'` axis, Plotly reads a numeric dtick
// as *milliseconds*, so a user typing "1" meaning "1 day" produced a
// tick every millisecond across years of data - literally thousands of
// ticks computed and rendered by Plotly, which is what stalls the page.
// The helpers below make the tick input axis-aware (a date axis is
// entered in days, not milliseconds; a whole-number axis rejects
// fractional intervals) and bound the resulting tick count against how
// many ticks the axis can actually fit on screen - not an arbitrary
// large number - so no interval, on any axis type, can ever ask Plotly
// to lay out more ticks than the chart has pixels for, on this chart or
// any future one that goes through this same settings popup.
// ---------------------------------------------------------------------

const MS_PER_DAY = 86400000;
// average calendar month, used only to size-check a month/year interval
// against the axis's pixel budget (see getPlotlyAxisMaxTicks) - the
// actual applied dtick uses Plotly's own 'M<n>' convention (below),
// which places ticks on real calendar month boundaries, not this
// average
const AVG_MONTH_MS = 30.436875 * MS_PER_DAY;

// the unit options offered for a *date* axis's tick-interval field, and
// how each converts a "magnitude" typed by the user into both (a) an ms
// figure to size-check against the axis's pixel budget and (b) the
// actual value handed to Plotly as dtick. Days/weeks are fixed-length,
// so they're plain milliseconds; months/years are calendar lengths, so
// they use Plotly's own 'M<n>' dtick convention (n months) instead of an
// approximate day count - that's what keeps ticks landing on real month/
// year boundaries instead of drifting.
const TICK_INTERVAL_UNITS = [
    { value: 'day', label: 'Days', approxMs: MS_PER_DAY, wholeOnly: false,
        toDtick: n => n * MS_PER_DAY },
    { value: 'week', label: 'Weeks', approxMs: 7 * MS_PER_DAY, wholeOnly: false,
        toDtick: n => n * 7 * MS_PER_DAY },
    { value: 'month', label: 'Months', approxMs: AVG_MONTH_MS, wholeOnly: true,
        toDtick: n => `M${n}` },
    { value: 'year', label: 'Years', approxMs: 12 * AVG_MONTH_MS, wholeOnly: true,
        toDtick: n => `M${n * 12}` }
];

function getTickIntervalUnit(unitValue) {
    return TICK_INTERVAL_UNITS.find(u => u.value === unitValue) || TICK_INTERVAL_UNITS[0];
}

// Plotly needs roughly this many horizontal/vertical pixels per tick
// label before they start overlapping - this is what actually bounds
// the tick count (see getPlotlyAxisMaxTicks), not a flat constant
const MIN_PIXELS_PER_TICK = 32;

// only used if an axis's rendered pixel length genuinely isn't
// available yet (shouldn't normally happen - the dialog only opens
// after the chart has already been drawn once)
const FALLBACK_MAX_TICKS = 60;

// resolves an axis's effective type ('date', 'linear', 'log',
// 'category', ...). graph._fullLayout holds Plotly's *resolved* type,
// filled in after every render - that's needed because some charts
// never declare `type: 'date'` on the layout literal and instead let
// Plotly infer it from the plotted values (e.g. the rainy-season
// onset/cessation view plots real Date objects but never sets
// xaxis.type), so checking graph.layout alone would miss those.
function getPlotlyAxisType(graph, axisName) {
    const resolvedType = graph._fullLayout?.[axisName]?.type;
    if (resolvedType && resolvedType !== '-') {
        return resolvedType;
    }
    const declaredType = graph.layout?.[axisName]?.type;
    if (declaredType && declaredType !== '-') {
        return declaredType;
    }
    // last resort, in case Plotly hasn't resolved _fullLayout yet -
    // sniff the actual plotted values for this axis
    const key = axisName === 'xaxis' ? 'x' : 'y';
    const sample = (graph.data || [])
        .flatMap(trace => Array.isArray(trace[key]) ? trace[key] : [])
        .find(value => value !== null && value !== undefined);
    const looksLikeDate = sample instanceof Date ||
        (typeof sample === 'string' && Number.isNaN(Number(sample)) && !Number.isNaN(Date.parse(sample)));
    return looksLikeDate ? 'date' : 'linear';
}

// classifies a non-date axis as 'integer' or 'float', so a whole-number
// axis (a year, a count of events...) can reject a fractional tick
// interval that wouldn't land on any real value. Prefers the axis's own
// pre-set tickvals when present (the chart author's own signal of what
// "a valid position on this axis" looks like); falls back to sampling
// the plotted data otherwise.
function getPlotlyAxisNumberKind(graph, axisName) {
    const key = axisName === 'xaxis' ? 'x' : 'y';
    const explicitTicks = graph.layout?.[axisName]?.tickvals;
    const sample = Array.isArray(explicitTicks) && explicitTicks.length
        ? explicitTicks
        : (graph.data || []).flatMap(trace => Array.isArray(trace[key]) ? trace[key] : []);
    const numeric = sample.map(Number).filter(Number.isFinite);
    return numeric.length && numeric.every(Number.isInteger) ? 'integer' : 'float';
}

// the axis's own rendered length in pixels, straight from Plotly's
// resolved layout - the real-world constraint on how many ticks can
// actually fit without overlapping
function getPlotlyAxisPixelLength(graph, axisName) {
    const length = graph._fullLayout?.[axisName]?._length;
    return Number.isFinite(length) && length > 0 ? length : null;
}

// how many manual ticks this axis can hold before labels start
// overlapping - this, not a flat number, is what makes a runaway
// interval structurally impossible: even the smallest allowed interval
// can only ever ask for as many ticks as the chart has pixels for
function getPlotlyAxisMaxTicks(graph, axisName) {
    const pixelLength = getPlotlyAxisPixelLength(graph, axisName);
    return pixelLength
        ? Math.max(2, Math.floor(pixelLength / MIN_PIXELS_PER_TICK))
        : FALLBACK_MAX_TICKS;
}

// the current span of an axis, expressed in the same unit a dtick value
// for it would use (milliseconds for a date axis, raw units otherwise)
function getPlotlyAxisRangeSpan(graph, axisName, isDate) {
    const toNumeric = value => (isDate ? new Date(value).getTime() : Number(value));
    const resolvedRange = graph._fullLayout?.[axisName]?.range || graph.layout?.[axisName]?.range;
    if (Array.isArray(resolvedRange) && resolvedRange.length === 2) {
        const span = Math.abs(toNumeric(resolvedRange[1]) - toNumeric(resolvedRange[0]));
        if (Number.isFinite(span) && span > 0) {
            return span;
        }
    }
    // fall back to the plotted data's own min/max, in case the axis
    // range hasn't been resolved yet
    const key = axisName === 'xaxis' ? 'x' : 'y';
    const values = (graph.data || [])
        .flatMap(trace => Array.isArray(trace[key]) ? trace[key] : [])
        .map(toNumeric)
        .filter(Number.isFinite);
    return values.length ? Math.max(...values) - Math.min(...values) : 0;
}

// rejects (falls back to Auto) any interval that would place more ticks
// across the axis's current span than it has room for
function clampTickInterval(candidate, rangeSpan, maxTicks) {
    if (!Number.isFinite(candidate) || candidate <= 0) {
        return null;
    }
    if (rangeSpan > 0 && rangeSpan / candidate > maxTicks) {
        return null;
    }
    return candidate;
}

// smallest interval that still respects getPlotlyAxisMaxTicks, in
// whatever unit the tick-interval *input field* currently displays (a
// TICK_INTERVAL_UNITS entry for a date axis, raw units otherwise) - used
// only to hint the field's `min` attribute, not as the authoritative
// check (clampTickInterval is)
function getPlotlyAxisMinDisplayInterval(graph, axisName, isDate, unitValue) {
    const rangeSpan = getPlotlyAxisRangeSpan(graph, axisName, isDate);
    if (rangeSpan <= 0) {
        return null;
    }
    const maxTicks = getPlotlyAxisMaxTicks(graph, axisName);
    const minInternalMs = rangeSpan / maxTicks;
    if (!isDate) {
        return Math.ceil(minInternalMs * 100) / 100;
    }
    const unit = getTickIntervalUnit(unitValue);
    const minDisplay = minInternalMs / unit.approxMs;
    // round up (never down) so the hinted minimum is never itself
    // rejected by clampTickInterval due to display rounding
    return unit.wholeOnly ? Math.max(1, Math.ceil(minDisplay)) : Math.ceil(minDisplay * 100) / 100;
}

// picks the best-fitting unit + magnitude to show in the tick-interval
// field for a date axis: decodes an existing dtick (either Plotly's own
// 'M<n>' month/year string, or a plain ms number for days/weeks) back
// into one of TICK_INTERVAL_UNITS; with no dtick set yet (Auto), picks a
// sensible default unit from the axis's own span instead of always
// defaulting to "Days" (a 40-year chart defaulting to "Days" would just
// make the user do the years-to-days math themselves).
function decomposeDateDtick(dtick, rangeSpanMs) {
    if (typeof dtick === 'string') {
        const match = /^M(\d+)$/.exec(dtick);
        if (match) {
            const n = Number(match[1]);
            return (n > 0 && n % 12 === 0)
                ? { unit: 'year', magnitude: n / 12 }
                : { unit: 'month', magnitude: n };
        }
    }
    if (typeof dtick === 'number' && Number.isFinite(dtick) && dtick > 0) {
        const days = dtick / MS_PER_DAY;
        return (days >= 7 && Number.isInteger(days / 7))
            ? { unit: 'week', magnitude: days / 7 }
            : { unit: 'day', magnitude: days };
    }
    const days = rangeSpanMs / MS_PER_DAY;
    const unit = days > 3 * 365 ? 'year' : days > 90 ? 'month' : days > 14 ? 'week' : 'day';
    return { unit, magnitude: null };
}

// returns a valid hex color string for Plotly's color inputs
function plotlyColorInputValue(color, fallback = '#0d6efd') {
    if (typeof color !== 'string') {
        return fallback;
    }

    if (/^#[0-9a-f]{6}$/i.test(color)) {
        return color;
    }

    const rgb = color.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
    if (rgb) {
        return rgbTripleToHex(rgb);
    }

    const resolved = resolveCssColorToRgb(color);
    const resolvedRgb = resolved && resolved.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
    if (resolvedRgb) {
        return rgbTripleToHex(resolvedRgb);
    }

    return fallback;
}

// auto-capitalize a text input (title, axis labels) as the user types,
function capitalizePlotlyTextInput(input) {
    const el = input.get(0);
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const capitalized = el.value.charAt(0).toUpperCase() + el.value.slice(1);
    if (capitalized !== el.value) {
        el.value = capitalized;
        if (start !== null) {
            el.setSelectionRange(start, end);
        }
    }
}

function plotlyAxisTitle(axis) {
    if (!axis || !axis.title) {
        return '';
    }
    return typeof axis.title === 'string' ? axis.title : (axis.title.text || '');
}

// font options
const PLOTLY_TITLE_FONTS = [
    { value: '', label: 'Font' },
    { value: 'Arial, sans-serif', label: 'Arial' },
    { value: '"Times New Roman", serif', label: 'Times New Roman' },
    { value: 'Georgia, serif', label: 'Georgia' },
    { value: '"Courier New", monospace', label: 'Courier New' },
    { value: 'Verdana, sans-serif', label: 'Verdana' },
    { value: '"Trebuchet MS", sans-serif', label: 'Trebuchet MS' }
];

// lines (trend/mean/median...)thickness

function appendTraceWidthInput(id, label, width) {
    return $('<input>', {
        id: `${id}-width`,
        type: 'number',
        min: 1,
        step: 1,
        class: 'form-control form-control-sm plotly-trace-width',
        style: 'width: 62px;',
        value: width,
        title: `Line thickness for ${label}`
    });
}

function appendTraceColorSwatch(colorsContainer, id, label, color, traceIndex, part, width) {
    const controls = [];
    if (part === 'line' && typeof width === 'number') {
        controls.push(appendTraceWidthInput(id, label, width));
    }
    controls.push(
        $('<input>', {
            id,
            type: 'color',
            class: 'form-control form-control-color plotly-trace-color',
            value: plotlyColorInputValue(color),
            'data-trace-index': traceIndex,
            'data-trace-part': part,
            title: `Choose color for ${label}`
        })
    );

    colorsContainer.append(
        $('<div>', { class: 'd-flex align-items-center justify-content-between gap-3 mb-1' }).append(
            $('<label>', { for: id, class: 'text-truncate', text: label }),
            $('<div>', { class: 'd-flex align-items-center gap-2' }).append(controls)
        )
    );
}


const defaultTraceColorsModule = {
    populate(colorsContainer, dialogID, graph) {
        graph.data.forEach((trace, index) => {
           //skip traces that are not selected
            if (trace.visible === false || trace.visible === 'legendonly') {
                return;
            }

            const name = trace.name || `Series ${index + 1}`;
            const hasLineColor = typeof trace.line?.color === 'string';
            const hasMarkerColor = typeof trace.marker?.color === 'string';

            if (hasLineColor && hasMarkerColor) {
                appendTraceColorSwatch(
                    colorsContainer, `${dialogID}-color-${index}-line`,
                    `${name} — Line`, trace.line.color, index, 'line', trace.line.width
                );
                appendTraceColorSwatch(
                    colorsContainer, `${dialogID}-color-${index}-marker`,
                    `${name} — Points`, trace.marker.color, index, 'marker'
                );
            } else {
                appendTraceColorSwatch(
                    colorsContainer, `${dialogID}-color-${index}`, name,
                    hasLineColor ? trace.line.color : trace.marker?.color,
                    index, hasLineColor ? 'line' : 'marker',
                    hasLineColor ? trace.line.width : undefined
                );
            }
        });
    },
    apply(dialogID, graph) {
        const colors = {};
        $(`#${dialogID} .plotly-trace-color`).each(function() {
            const traceIndex = Number($(this).data('trace-index'));
            const part = $(this).data('trace-part');
            const trace = graph.data[traceIndex];
            if (!trace) {
                return;
            }
            const color = $(this).val();
            Plotly.restyle(graph, { [`${part}.color`]: color }, [traceIndex]);
            // keyed by name (not index) so it can be matched back up
            // after a redraw where trace order/count may have changed
            const name = trace.name || `Series ${traceIndex + 1}`;
            colors[`${name}|${part}`] = color;

            if (part === 'line') {
                const width = Number($(`#${$(this).attr('id')}-width`).val());
                if (Number.isFinite(width) && width > 0) {
                    Plotly.restyle(graph, { 'line.width': width }, [traceIndex]);
                    colors[`${name}|line-width`] = width;
                }
            }
        });
        return colors;
    },
    // reapply colors saved from a previous session/redraw onto a chart
    // that was just (re)plotted
    restore(colors, graph) {
        if (!colors) {
            return;
        }
        graph.data.forEach((trace, index) => {
            const name = trace.name || `Series ${index + 1}`;
            ['line', 'marker'].forEach((part) => {
                const color = colors[`${name}|${part}`];
                if (color) {
                    Plotly.restyle(graph, { [`${part}.color`]: color }, [index]);
                }
            });
            const width = colors[`${name}|line-width`];
            if (typeof width === 'number') {
                Plotly.restyle(graph, { 'line.width': width }, [index]);
            }
        });
    }
};

// for postive an negative anomaly charts
const anomalySignColorsModule = {
    populate(colorsContainer, dialogID, graph) {
        const trace = graph.data[0];
        const values = trace?.y || [];
        const colorArray = Array.isArray(trace?.marker?.color) ? trace.marker.color : [];
        const colorForSign = (predicate, fallback) => {
            const i = values.findIndex(predicate);
            return plotlyColorInputValue(i >= 0 ? colorArray[i] : null, fallback);
        };

        [
            { id: 'positive', label: 'Positive', fallback: '#198754' },
            { id: 'negative', label: 'Negative', fallback: '#fd7e14' }
        ].forEach(entry => {
            colorsContainer.append(
                $('<div>', { class: 'd-flex align-items-center justify-content-between gap-3 mb-1' }).append(
                    $('<label>', {
                        for: `${dialogID}-color-${entry.id}`,
                        class: 'text-truncate',
                        text: entry.label
                    }),
                    $('<input>', {
                        id: `${dialogID}-color-${entry.id}`,
                        type: 'color',
                        class: `form-control form-control-color plotly-sign-color-${entry.id}`,
                        value: colorForSign(v => entry.id === 'positive' ? v > 0 : v < 0, entry.fallback),
                        title: `Choose color for ${entry.label.toLowerCase()} values`
                    })
                )
            );
        });
    },
    apply(dialogID, graph) {
        const trace = graph.data[0];
        if (!trace) {
            return;
        }
        const values = trace.y || [];
        const oldColors = Array.isArray(trace.marker?.color) ? trace.marker.color : [];
        const positive = $(`#${dialogID}-color-positive`).val();
        const negative = $(`#${dialogID}-color-negative`).val();
        const neutralIndex = values.findIndex(v => v === 0);
        const neutral = plotlyColorInputValue(
            neutralIndex >= 0 ? oldColors[neutralIndex] : null, '#6c757d'
        );

        const newColors = values.map(v => (v > 0 ? positive : v < 0 ? negative : neutral));
        Plotly.restyle(graph, { 'marker.color': [newColors] }, [0]);

        return { positive, negative, neutral };
    },
    // reapply saved positive/negative/neutral colors onto a chart that
    // was just (re)plotted
    restore(colors, graph) {
        if (!colors) {
            return;
        }
        const trace = graph.data[0];
        if (!trace) {
            return;
        }
        const values = trace.y || [];
        const newColors = values.map(v => (
            v > 0 ? colors.positive : v < 0 ? colors.negative : colors.neutral
        ));
        Plotly.restyle(graph, { 'marker.color': [newColors] }, [0]);
    }
};

// for a bar chart whose per-bar color comes from a small, fixed set of
// category values (e.g. a discrete score/index) rather than a sign split
// (that's anomalySignColorsModule above) or one color per trace (that's
// defaultTraceColorsModule) - e.g. the crop-suitability chart, whose bars
// are colored from a 6-step score palette (0-5) plus a "no data" gray.
// Categories are read from each point's `customdata` (the chart's raw,
// pre-color value, since `y` itself may be adjusted for display - e.g.
// crop suitability nudges a 0 score up to 0.08 so the bar is still
// visible), paired with that point's current `marker.color`, so this
// works for any chart following the pattern without hardcoding how many
// categories there are or what colors they start as.
const categoricalMarkerColorsModule = {
    populate(colorsContainer, dialogID, graph) {
        const trace = graph.data[0];
        const values = trace?.customdata || trace?.y || [];
        const colorArray = Array.isArray(trace?.marker?.color) ? trace.marker.color : [];

        const colorByKey = new Map();
        values.forEach((value, i) => {
            const key = value === null || value === undefined ? 'null' : String(value);
            if (!colorByKey.has(key)) {
                colorByKey.set(key, colorArray[i]);
            }
        });

        [...colorByKey.keys()]
            .sort((a, b) => (a === 'null' ? 1 : b === 'null' ? -1 : Number(a) - Number(b)))
            .forEach(key => {
                const label = key === 'null' ? 'No data' : key;
                colorsContainer.append(
                    $('<div>', { class: 'd-flex align-items-center justify-content-between gap-3 mb-1' }).append(
                        $('<label>', {
                            for: `${dialogID}-color-cat-${key}`,
                            class: 'text-truncate',
                            text: label
                        }),
                        $('<input>', {
                            id: `${dialogID}-color-cat-${key}`,
                            type: 'color',
                            class: 'form-control form-control-color plotly-category-color',
                            value: plotlyColorInputValue(colorByKey.get(key), key === 'null' ? '#6c757d' : undefined),
                            'data-category-key': key,
                            title: `Choose color for ${label}`
                        })
                    )
                );
            });
    },
    apply(dialogID, graph) {
        const trace = graph.data[0];
        if (!trace) {
            return;
        }
        const values = trace.customdata || trace.y || [];
        const oldColors = Array.isArray(trace.marker?.color) ? trace.marker.color : [];

        const colorByKey = {};
        $(`#${dialogID} .plotly-category-color`).each(function() {
            colorByKey[$(this).data('category-key')] = $(this).val();
        });

        const newColors = values.map((value, i) => {
            const key = value === null || value === undefined ? 'null' : String(value);
            return colorByKey[key] ?? oldColors[i];
        });
        Plotly.restyle(graph, { 'marker.color': [newColors] }, [0]);

        return colorByKey;
    },
    // reapply saved per-category colors onto a chart that was just
    // (re)plotted
    restore(colors, graph) {
        if (!colors) {
            return;
        }
        const trace = graph.data[0];
        if (!trace) {
            return;
        }
        const values = trace.customdata || trace.y || [];
        const oldColors = Array.isArray(trace.marker?.color) ? trace.marker.color : [];
        const newColors = values.map((value, i) => {
            const key = value === null || value === undefined ? 'null' : String(value);
            return colors[key] ?? oldColors[i];
        });
        Plotly.restyle(graph, { 'marker.color': [newColors] }, [0]);
    }
};

// to store the saved settings for each chart by its ID, so they can be reapplied after a redraw
const plotlyChartSettingsStore = {};

// to store the colors module for each chart by its ID, so the correct module can be used to restore colors after a redraw
const plotlyChartSettingsModules = {};

// chartID -> that chart's xaxis/yaxis dtick+tickvals+ticktext exactly as
// they were server-authored, captured fresh every time the chart is
// redrawn with new/changed data (never when a settings-driven redraw
// happens - see isApplyingPlotlyTickSettings below). This is what
// "Auto" restores to when the user clears a manual tick interval -
// including on an axis whose own baked-in default was itself a manual
// dtick (e.g. Climato/Telecon set `dtick: 'M1'`/`dtick: 5` directly, not
// through this dialog), which would otherwise get wiped to null the
// first time the field is touched at all, even without typing anything
// invalid in it.
const plotlyChartOriginalTickArrays = {};

// true only for the instant applySettings() itself is pushing a manual
// dtick/title/label change through Plotly.newPlot(). Lets the newPlot
// wrapper below tell that redraw (which must NOT overwrite the cache
// above with its own dtick-only, tickvals-cleared layout) apart from a
// genuine data-driven redraw (variable/date-range change, initial
// draw...), which SHOULD refresh the cache with whatever tick config the
// newly plotted data came with.
let isApplyingPlotlyTickSettings = false;

function snapshotPlotlyAxisTickArrays(gd) {
    plotlyChartOriginalTickArrays[gd.id] = {
        xaxis: {
            dtick: gd.layout.xaxis?.dtick ?? null,
            tickvals: gd.layout.xaxis?.tickvals ?? null,
            ticktext: gd.layout.xaxis?.ticktext ?? null
        },
        yaxis: {
            dtick: gd.layout.yaxis?.dtick ?? null,
            tickvals: gd.layout.yaxis?.tickvals ?? null,
            ticktext: gd.layout.yaxis?.ticktext ?? null
        }
    };
}

function savePlotlyChartSettings(chartID, settings) {
    plotlyChartSettingsStore[chartID] = settings;
}

function getPlotlyChartSettings(chartID) {
    return plotlyChartSettingsStore[chartID] || null;
}

// reapply any saved customization to a chart that was just plotted
function reapplyPlotlyChartSettings(gd) {
    if (!gd || !gd.id) {
        return;
    }
    const settings = getPlotlyChartSettings(gd.id);
    if (!settings) {
        return;
    }
    if (settings.layout) {
        Plotly.relayout(gd, settings.layout);
    }
    if (settings.colors) {
        const colorsModule = plotlyChartSettingsModules[gd.id] || defaultTraceColorsModule;
        colorsModule.restore(settings.colors, gd);
    }
}

// wrap Plotly.newPlot to reapply saved settings after a redraw
// for the same chart, and to reattach the rangeslider title position fix
(function(nativeNewPlot) {
    Plotly.newPlot = function(...args) {
        return nativeNewPlot.apply(Plotly, args).then((gd) => {
            gd.on('plotly_afterplot', () => fixRangesliderTitlePosition(gd));
            if (!isApplyingPlotlyTickSettings) {
                snapshotPlotlyAxisTickArrays(gd);
            }
            reapplyPlotlyChartSettings(gd);
            fixRangesliderTitlePosition(gd);
            return gd;
        });
    };
})(Plotly.newPlot);

// changed the name
function buildPlotlyChartSettingsForm(dialogID){
    const dialog = $('<div>', {
            id: dialogID,
            class: 'container-fluid dialog-box-settings plotly-chart-settings-dialog'
        }).append(
            $('<div>', { class: 'row m-2' }).append(
                $('<div>', { class: 'col-sm-11 d-flex justify-content-start' }).append(
                    $('<span>', { class: 'fw-bolder', text: 'Chart settings' })
                ),
                $('<div>', { class: 'col-sm-1 d-flex justify-content-end' }).append(
                    $('<button>', {
                        id: `${dialogID}-close-1`,
                        type: 'button',
                        class: 'btn btn-md position-absolute top-0 end-0 me-1 p-1',
                        'aria-label': 'Close'
                    }).append($('<i>', { class: 'bi bi-x-circle-fill' }))
                ),
                $('<hr>', { class: 'w-100' })
            ),
            $('<div>', { class: 'container mt-2 mb-1 mx-0 px-2' }).append(
                $('<div>', { class: 'mb-2' }).append(
                    $('<label>', { class: 'form-label mb-1', for: `${dialogID}-title`, text: 'Title' }),
                    $('<div>', { class: 'd-flex flex-wrap align-items-center gap-2' }).append(
                        $('<input>', { id: `${dialogID}-title`, type: 'text', class: 'form-control form-control-sm' })
                            .on('input', function() { capitalizePlotlyTextInput($(this)); }),
                        $('<select>', {
                            id: `${dialogID}-title-font`,
                            class: 'form-select form-select-sm',
                            style: 'width: 160px;',
                            title: 'Title font'
                        }).append(
                            PLOTLY_TITLE_FONTS.map(font =>
                                $('<option>', { value: font.value, text: font.label, style: `font-family: ${font.value || 'inherit'};` })
                            )
                        ),
                        $('<input>', {
                            id: `${dialogID}-title-size`,
                            type: 'number',
                            min: 1,
                            class: 'form-control form-control-sm',
                            style: 'width: 90px;',
                            placeholder: 'Title size',
                            title: 'Title size'
                        }),
                        $('<input>', {
                            id: `${dialogID}-title-color`,
                            type: 'color',
                            class: 'form-control form-control-color',
                            title: 'Title color'
                        })
                    )
                ),
                $('<div>', { class: 'row g-2' }).append(
                    $('<div>', { class: 'col-sm-6' }).append(
                        $('<label>', { class: 'form-label mb-1', for: `${dialogID}-x-label`, text: 'X-axis label' }),
                        $('<input>', { id: `${dialogID}-x-label`, type: 'text', class: 'form-control form-control-sm' })
                            .on('input', function() { capitalizePlotlyTextInput($(this)); })
                    ),
                    $('<div>', { class: 'col-sm-6' }).append(
                        $('<label>', { class: 'form-label mb-1', for: `${dialogID}-y-label`, text: 'Y-axis label' }),
                        $('<input>', { id: `${dialogID}-y-label`, type: 'text', class: 'form-control form-control-sm' })
                            .on('input', function() { capitalizePlotlyTextInput($(this)); })
                    ),
                    $('<div>', { class: 'col-sm-6' }).append(
                        $('<label>', { id: `${dialogID}-x-tick-label`, class: 'form-label mb-1', for: `${dialogID}-x-tick`, text: 'X-axis tick interval' }),
                        $('<div>', { class: 'd-flex align-items-center gap-2' }).append(
                            $('<input>', { id: `${dialogID}-x-tick`, type: 'number', step: 'any', class: 'form-control form-control-sm', placeholder: 'Auto' }),
                            $('<select>', { id: `${dialogID}-x-tick-unit`, class: 'form-select form-select-sm d-none', style: 'width: 100px;' }).append(
                                TICK_INTERVAL_UNITS.map(u => $('<option>', { value: u.value, text: u.label }))
                            )
                        )
                    ),
                    $('<div>', { class: 'col-sm-6' }).append(
                        $('<label>', { id: `${dialogID}-y-tick-label`, class: 'form-label mb-1', for: `${dialogID}-y-tick`, text: 'Y-axis tick interval' }),
                        $('<div>', { class: 'd-flex align-items-center gap-2' }).append(
                            $('<input>', { id: `${dialogID}-y-tick`, type: 'number', step: 'any', class: 'form-control form-control-sm', placeholder: 'Auto' }),
                            $('<select>', { id: `${dialogID}-y-tick-unit`, class: 'form-select form-select-sm d-none', style: 'width: 100px;' }).append(
                                TICK_INTERVAL_UNITS.map(u => $('<option>', { value: u.value, text: u.label }))
                            )
                        )
                    )
                ),
                $('<fieldset>', { class: 'border border-secondary rounded-3 p-2 mt-3' }).append(
                    $('<legend>', { class: 'legend-label px-1', text: 'Chart colors' }),
                    $('<div>', { id: `${dialogID}-colors`, class: 'plotly-chart-settings-colors' })
                )
            ),
            $('<div>', { class: 'd-flex justify-content-end m-2' }).append(
                $('<button>', {
                    id: `${dialogID}-close-2`,
                    type: 'button',
                    class: 'btn btn-sm btn-primary',
                    text: 'Close and apply'
                })
            )
        )
    return dialog;
}
// changed the name
function enablePlotlyChartSettings(
    buttonID,
    chartID,
    inputsFunction = buildPlotlyChartSettingsForm,
    colorsModule = defaultTraceColorsModule
) {
    const dialogID = `plotly-chart-settings-${buttonID}`;
    // remember which colorsModule this chart uses so saved settings can
    // be restored correctly even on a redraw the dialog wasn't open for
    plotlyChartSettingsModules[chartID] = colorsModule;
    const editButton = $(`#plotly-chart-edit-${buttonID}`);
    const modalHost = editButton.closest('.modal');
    const dialogHost = modalHost.length ? modalHost : $(document.body);
    let dialog = $(`#${dialogID}`);

    if (!dialog.length) {
        dialog = inputsFunction(dialogID);
        dialog.appendTo(dialogHost);
    } else if (!dialog.parent().is(dialogHost)) {

        dialog.appendTo(dialogHost);
    }

    function getGraph() {
        return document.getElementById(chartID);
    }

    function populateDialog() {
        const graph = getGraph();
        if (!graph || !graph.layout || !graph.data) {
            return false;
        }

        const theme = $('html').attr('data-bs-theme');
        const defaultTitleColor = (plotly_themecolors[theme] || plotly_themecolors.light).fontcolor;

        $(`#${dialogID}-title`).val(graph.layout.title?.text || '');
        $(`#${dialogID}-title-color`).val(
            plotlyColorInputValue(graph.layout.title?.font?.color, defaultTitleColor)
        );

        const titleFont = graph.layout.title?.font?.family || '';
        const titleFontSelect = $(`#${dialogID}-title-font`);
        titleFontSelect.val(titleFontSelect.find(`option[value='${titleFont}']`).length ? titleFont : '');

        $(`#${dialogID}-title-size`).val(graph.layout.title?.font?.size ?? '');
        $(`#${dialogID}-x-label`).val(plotlyAxisTitle(graph.layout.xaxis));
        $(`#${dialogID}-y-label`).val(plotlyAxisTitle(graph.layout.yaxis));

        // the tick-interval field means different things on different
        // axes (see the tick-interval helpers block near the top of this
        // file) - relabel it, mark whole-number-only axes, show/hide and
        // populate the unit dropdown for a date axis, and convert the
        // stored dtick (always in Plotly's own unit - ms, or 'M<n>' for
        // months/years) back to what the field displays, every time the
        // dialog opens, since the same dialog can be reused by a chart
        // whose axis type depends on the currently selected variable
        // (e.g. rainy-season onset/cessation vs. length)
        ['xaxis', 'yaxis'].forEach(axisName => {
            const side = axisName === 'xaxis' ? 'x' : 'y';
            const input = $(`#${dialogID}-${side}-tick`);
            const unitSelect = $(`#${dialogID}-${side}-tick-unit`);
            const isDate = getPlotlyAxisType(graph, axisName) === 'date';
            const isInteger = !isDate && getPlotlyAxisNumberKind(graph, axisName) === 'integer';

            $(`#${dialogID}-${side}-tick-label`).text(
                `${side.toUpperCase()}-axis tick interval` + (isInteger ? ' (whole numbers)' : '')
            );
            unitSelect.toggleClass('d-none', !isDate);

            if (isDate) {
                const rangeSpan = getPlotlyAxisRangeSpan(graph, axisName, true);
                const { unit, magnitude } = decomposeDateDtick(graph.layout[axisName]?.dtick, rangeSpan);
                unitSelect.val(unit);
                input.val(magnitude ?? '');
            } else {
                const dtick = graph.layout[axisName]?.dtick;
                input.val(typeof dtick === 'number' && Number.isFinite(dtick) ? dtick : '');
            }
            refreshTickInputConstraints(axisName);
        });

        const colors = $(`#${dialogID}-colors`).empty();
        colorsModule.populate(colors, dialogID, graph);
        return true;
    }

    // keeps a tick-interval input's step/min in sync with what it
    // currently means - the axis's type/kind, and for a date axis, the
    // unit the user has selected (Days/Weeks/Months/Years). Called on
    // dialog open and again whenever the unit dropdown changes.
    function refreshTickInputConstraints(axisName) {
        const graph = getGraph();
        if (!graph) {
            return;
        }
        const side = axisName === 'xaxis' ? 'x' : 'y';
        const input = $(`#${dialogID}-${side}-tick`);
        const isDate = getPlotlyAxisType(graph, axisName) === 'date';
        const isInteger = !isDate && getPlotlyAxisNumberKind(graph, axisName) === 'integer';
        const unitValue = isDate ? $(`#${dialogID}-${side}-tick-unit`).val() : null;
        const wholeOnly = isInteger || (isDate && getTickIntervalUnit(unitValue).wholeOnly);

        input.attr('step', wholeOnly ? '1' : 'any');
        const minInterval = getPlotlyAxisMinDisplayInterval(graph, axisName, isDate, unitValue);
        if (minInterval !== null) {
            input.attr('min', minInterval);
        } else {
            input.removeAttr('min');
        }
    }

    // tick interval: axis-aware and bounded, not just "positive number".
    // On a date axis the field's meaning depends on the paired unit
    // dropdown (days/weeks convert to Plotly's millisecond dtick;
    // months/years convert to Plotly's own 'M<n>' calendar-based dtick,
    // and only accept whole numbers - there's no such thing as half a
    // calendar month); on a whole-number axis a fractional entry is
    // rejected outright (it wouldn't land on a real value); on any axis,
    // the result is clamped so it can never ask Plotly to lay out more
    // ticks than the axis has pixels for - see the tick-interval helpers
    // block near the top of this file.
    function parseTick(value, unitValue, axisName) {
        const trimmed = value.trim();
        if (!trimmed) {
            return null;
        }
        const numeric = Number(trimmed);
        if (!Number.isFinite(numeric) || numeric <= 0) {
            return null;
        }
        const graph = getGraph();
        if (!graph) {
            return null;
        }
        const isDate = getPlotlyAxisType(graph, axisName) === 'date';
        const maxTicks = getPlotlyAxisMaxTicks(graph, axisName);

        if (isDate) {
            const unit = getTickIntervalUnit(unitValue);
            if (unit.wholeOnly && !Number.isInteger(numeric)) {
                return null;
            }
            const rangeSpan = getPlotlyAxisRangeSpan(graph, axisName, true);
            const withinBudget = clampTickInterval(numeric * unit.approxMs, rangeSpan, maxTicks);
            return withinBudget === null ? null : unit.toDtick(numeric);
        }

        if (!Number.isInteger(numeric) && getPlotlyAxisNumberKind(graph, axisName) === 'integer') {
            return null;
        }
        const rangeSpan = getPlotlyAxisRangeSpan(graph, axisName, false);
        return clampTickInterval(numeric, rangeSpan, maxTicks);
    }


     // for the title font size picker
    function parseFontSize(value) {
        const trimmed = value.trim();
        if (!trimmed) {
            return null;
        }
        const numeric = Number(trimmed);
        return Number.isFinite(numeric) && numeric > 0 ? Math.round(numeric) : null;
    }

    function applySettings() {
        const graph = getGraph();
        if (!graph || !graph.layout || !graph.data) {
            return;
        }
        // added .trim() to remove any leading/trailing whitespace from the title and axis labels
        const layoutUpdate = {
            'title.text': $(`#${dialogID}-title`).val().trim(),
            'title.font.color': $(`#${dialogID}-title-color`).val(),
            'title.font.family': $(`#${dialogID}-title-font`).val() || null,
            'title.font.size': parseFontSize($(`#${dialogID}-title-size`).val()),
        // fix for the title is being cut off
            'title.automargin': true,
            'title.pad': { t: 5, b: 5 },
            'xaxis.title.text': $(`#${dialogID}-x-label`).val().trim(),
            'yaxis.title.text': $(`#${dialogID}-y-label`).val().trim(),
            'xaxis.dtick': parseTick($(`#${dialogID}-x-tick`).val(), $(`#${dialogID}-x-tick-unit`).val(), 'xaxis'),
            'yaxis.dtick': parseTick($(`#${dialogID}-y-tick`).val(), $(`#${dialogID}-y-tick-unit`).val(), 'yaxis')
        };

        // a manual dtick and the axis's original tick config (explicit
        // tickvals/ticktext - several charts pre-set these, mostly on Y
        // but also X for e.g. rainy-season/probability CDF views - or a
        // baked-in dtick like Climato/Telecon's own `dtick: 'M1'`/`5`)
        // can't coexist: Plotly favors an "array" tick mode over dtick
        // whenever tickvals is present, so leaving the old array in
        // place would silently ignore the dtick the user just asked
        // for. Make the two mutually exclusive: setting a valid manual
        // dtick clears the array; clearing the field (or typing
        // something invalid, which parseTick already turned into null)
        // restores the axis's own original tick config exactly as the
        // chart was actually drawn with, dtick included - not just a
        // blanket null, which would otherwise wipe out a chart's own
        // non-numeric default (e.g. 'M1') the first time this dialog is
        // touched at all, even without entering anything.
        const originalTicks = plotlyChartOriginalTickArrays[chartID] || {};
        ['xaxis', 'yaxis'].forEach(axisName => {
            const original = originalTicks[axisName] || {};
            const manualDtick = layoutUpdate[`${axisName}.dtick`];
            if (manualDtick !== null) {
                layoutUpdate[`${axisName}.tickmode`] = 'linear';
                layoutUpdate[`${axisName}.tickvals`] = null;
                layoutUpdate[`${axisName}.ticktext`] = null;
            } else {
                layoutUpdate[`${axisName}.dtick`] = original.dtick ?? null;
                layoutUpdate[`${axisName}.tickmode`] = null;
                layoutUpdate[`${axisName}.tickvals`] = original.tickvals ?? null;
                layoutUpdate[`${axisName}.ticktext`] = original.ticktext ?? null;
            }
        });

        // title, so if the user shrinks the title text or removes it entirely

        const mergedLayout = deepMerge(graph.layout, dotPathsToNestedObject(layoutUpdate));
        // tell the newPlot wrapper this redraw is a settings apply, not
        // a fresh data draw, so it doesn't overwrite the "original tick
        // arrays" cache with this dtick-only, tickvals-cleared layout
        isApplyingPlotlyTickSettings = true;
        Plotly.newPlot(graph, graph.data, mergedLayout, graph._context)
            .finally(() => { isApplyingPlotlyTickSettings = false; });
        const colors = colorsModule.apply(dialogID, graph);

        // save the updated settings
        savePlotlyChartSettings(chartID, { layout: layoutUpdate, colors });
    }

    editButton
        .off('click.plotlyChartSettings')
        .on('click.plotlyChartSettings', function() {
            if (populateDialog()) {
                dialog.fadeIn(200);
            }
        });

    // switching Days/Weeks/Months/Years should immediately update the
    // paired input's step (whole numbers only for months/years) and
    // minimum hint for the newly selected unit, not just at dialog-open
    $(`#${dialogID}-x-tick-unit`)
        .off('change.plotlyChartSettings')
        .on('change.plotlyChartSettings', () => refreshTickInputConstraints('xaxis'));
    $(`#${dialogID}-y-tick-unit`)
        .off('change.plotlyChartSettings')
        .on('change.plotlyChartSettings', () => refreshTickInputConstraints('yaxis'));

    $(`#${dialogID}-close-1, #${dialogID}-close-2`)
        .off('click.plotlyChartSettings')
        .on('click.plotlyChartSettings', function() {
            applySettings();
            dialog.fadeOut(200);
        });
}
