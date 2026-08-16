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

function appendTraceColorSwatch(colorsContainer, id, label, color, traceIndex, part) {
    colorsContainer.append(
        $('<div>', { class: 'd-flex align-items-center justify-content-between gap-3 mb-1' }).append(
            $('<label>', { for: id, class: 'text-truncate', text: label }),
            $('<input>', {
                id,
                type: 'color',
                class: 'form-control form-control-color plotly-trace-color',
                value: plotlyColorInputValue(color),
                'data-trace-index': traceIndex,
                'data-trace-part': part,
                title: `Choose color for ${label}`
            })
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
                    `${name} — Line`, trace.line.color, index, 'line'
                );
                appendTraceColorSwatch(
                    colorsContainer, `${dialogID}-color-${index}-marker`,
                    `${name} — Points`, trace.marker.color, index, 'marker'
                );
            } else {
                appendTraceColorSwatch(
                    colorsContainer, `${dialogID}-color-${index}`, name,
                    hasLineColor ? trace.line.color : trace.marker?.color,
                    index, hasLineColor ? 'line' : 'marker'
                );
            }
        });
    },
    apply(dialogID, graph) {
        $(`#${dialogID} .plotly-trace-color`).each(function() {
            const traceIndex = Number($(this).data('trace-index'));
            const part = $(this).data('trace-part');
            const trace = graph.data[traceIndex];
            if (!trace) {
                return;
            }
            const color = $(this).val();
            Plotly.restyle(graph, { [`${part}.color`]: color }, [traceIndex]);
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
    }
};




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
                        $('<label>', { class: 'form-label mb-1', for: `${dialogID}-x-tick`, text: 'X-axis tick interval' }),
                        $('<input>', { id: `${dialogID}-x-tick`, type: 'number', step: 'any', class: 'form-control form-control-sm', placeholder: 'Auto' })
                    ),
                    $('<div>', { class: 'col-sm-6' }).append(
                        $('<label>', { class: 'form-label mb-1', for: `${dialogID}-y-tick`, text: 'Y-axis tick interval' }),
                        $('<input>', { id: `${dialogID}-y-tick`, type: 'number', step: 'any', class: 'form-control form-control-sm', placeholder: 'Auto' })
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
        $(`#${dialogID}-x-tick`).val(graph.layout.xaxis?.dtick ?? '');
        $(`#${dialogID}-y-tick`).val(graph.layout.yaxis?.dtick ?? '');

        const colors = $(`#${dialogID}-colors`).empty();
        colorsModule.populate(colors, dialogID, graph);
        return true;
    }

    // tick interval only accepts a positive number 
    function parseTick(value) {
        const trimmed = value.trim();
        if (!trimmed) {
            return null;
        }
        const numeric = Number(trimmed);
        return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
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

        Plotly.relayout(graph, {
            'title.text': $(`#${dialogID}-title`).val(),
            'title.font.color': $(`#${dialogID}-title-color`).val(),
            'title.font.family': $(`#${dialogID}-title-font`).val() || null,
            'title.font.size': parseFontSize($(`#${dialogID}-title-size`).val()),
            // fix for the title is beigng cut off
            'title.automargin': true,
            'title.pad': { t: 5, b: 5 },
            'xaxis.title.text': $(`#${dialogID}-x-label`).val(),
            'yaxis.title.text': $(`#${dialogID}-y-label`).val(),
            'xaxis.dtick': parseTick($(`#${dialogID}-x-tick`).val()),
            'yaxis.dtick': parseTick($(`#${dialogID}-y-tick`).val())
        });

        colorsModule.apply(dialogID, graph);
    }

    editButton
        .off('click.plotlyChartSettings')
        .on('click.plotlyChartSettings', function() {
            if (populateDialog()) {
                dialog.fadeIn(200);
            }
        });

    $(`#${dialogID}-close-1, #${dialogID}-close-2`)
        .off('click.plotlyChartSettings')
        .on('click.plotlyChartSettings', function() {
            applySettings();
            dialog.fadeOut(200);
        });
}