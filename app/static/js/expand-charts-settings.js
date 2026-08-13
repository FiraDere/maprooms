function plotlyColorInputValue(color, fallback = '#0d6efd') {
    if (typeof color !== 'string') {
        return fallback;
    }

    if (/^#[0-9a-f]{6}$/i.test(color)) {
        return color;
    }

    const rgb = color.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
    if (rgb) {
        return `#${rgb.slice(1, 4).map(value =>
            Number(value).toString(16).padStart(2, '0')
        ).join('')}`;
    }

    return fallback;
}

function plotlyAxisTitle(axis) {
    if (!axis || !axis.title) {
        return '';
    }
    return typeof axis.title === 'string' ? axis.title : (axis.title.text || '');
}

function setPlotlyChartSettingsDialog(buttonID, chartID, inputsFunction) {
    const dialogID = `plotly-chart-settings-${buttonID}`;
    const editButton = $(`#plotly-chart-edit-${buttonID}`);
    const modalHost = editButton.closest('.modal');
    const dialogHost = modalHost.length ? modalHost : $(document.body);
    let dialog = $(`#${dialogID}`);

    if (!dialog.length) {
        dialog = inputsFunction(dialogID);
        dialog.appendTo(dialogHost);
    } else if (!dialog.parent().is(dialogHost)) {
        // Bootstrap traps focus inside an open modal. Keep the editor within that
        // modal so its text and color inputs can receive focus.
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

        $(`#${dialogID}-title`).val(graph.layout.title?.text || '');
        $(`#${dialogID}-x-label`).val(plotlyAxisTitle(graph.layout.xaxis));
        $(`#${dialogID}-y-label`).val(plotlyAxisTitle(graph.layout.yaxis));
        $(`#${dialogID}-x-tick`).val(graph.layout.xaxis?.dtick ?? '');
        $(`#${dialogID}-y-tick`).val(graph.layout.yaxis?.dtick ?? '');

        const colors = $(`#${dialogID}-colors`).empty();
        graph.data.forEach((trace, index) => {
            const traceColor = trace.line?.color || trace.marker?.color;
            colors.append(
                $('<div>', { class: 'd-flex align-items-center justify-content-between gap-3 mb-1' }).append(
                    $('<label>', {
                        for: `${dialogID}-color-${index}`,
                        class: 'text-truncate',
                        text: trace.name || `Series ${index + 1}`
                    }),
                    $('<input>', {
                        id: `${dialogID}-color-${index}`,
                        type: 'color',
                        class: 'form-control form-control-color plotly-trace-color',
                        value: plotlyColorInputValue(traceColor),
                        'data-trace-index': index,
                        title: `Choose color for ${trace.name || `series ${index + 1}`}`
                    })
                )
            );
        });
        return true;
    }

    function parseTick(value) {
        const trimmed = value.trim();
        if (!trimmed) {
            return null;
        }
        const numeric = Number(trimmed);
        return Number.isNaN(numeric) ? trimmed : numeric;
    }

    function applySettings() {
        const graph = getGraph();
        if (!graph || !graph.layout || !graph.data) {
            return;
        }

        Plotly.relayout(graph, {
            'title.text': $(`#${dialogID}-title`).val(),
            'xaxis.title.text': $(`#${dialogID}-x-label`).val(),
            'yaxis.title.text': $(`#${dialogID}-y-label`).val(),
            'xaxis.dtick': parseTick($(`#${dialogID}-x-tick`).val()),
            'yaxis.dtick': parseTick($(`#${dialogID}-y-tick`).val())
        });

        $(`#${dialogID} .plotly-trace-color`).each(function() {
            const traceIndex = Number($(this).data('trace-index'));
            const trace = graph.data[traceIndex];
            const color = $(this).val();
            const update = {};

            if (trace.line || trace.type === 'scatter') {
                update['line.color'] = color;
            }
            if (trace.marker || trace.type === 'bar' || (trace.mode || '').includes('markers')) {
                update['marker.color'] = color;
            }
            Plotly.restyle(graph, update, [traceIndex]);
        });
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

function test_climate_analysis_season_daily(dialogID){
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
                    $('<input>', { id: `${dialogID}-title`, type: 'text', class: 'form-control form-control-sm' })
                ),
                $('<div>', { class: 'row g-2' }).append(
                    $('<div>', { class: 'col-sm-6' }).append(
                        $('<label>', { class: 'form-label mb-1', for: `${dialogID}-x-label`, text: 'X-axis label' }),
                        $('<input>', { id: `${dialogID}-x-label`, type: 'text', class: 'form-control form-control-sm' })
                    ),
                    $('<div>', { class: 'col-sm-6' }).append(
                        $('<label>', { class: 'form-label mb-1', for: `${dialogID}-y-label`, text: 'Y-axis label' }),
                        $('<input>', { id: `${dialogID}-y-label`, type: 'text', class: 'form-control form-control-sm' })
                    ),
                    $('<div>', { class: 'col-sm-6' }).append(
                        $('<label>', { class: 'form-label mb-1', for: `${dialogID}-x-tick`, text: 'X-axis tick interval' }),
                        $('<input>', { id: `${dialogID}-x-tick`, type: 'text', class: 'form-control form-control-sm', placeholder: 'Auto' })
                    ),
                    $('<div>', { class: 'col-sm-6' }).append(
                        $('<label>', { class: 'form-label mb-1', for: `${dialogID}-y-tick`, text: 'Y-axis tick interval' }),
                        $('<input>', { id: `${dialogID}-y-tick`, type: 'text', class: 'form-control form-control-sm', placeholder: 'Auto' })
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