$(document).ready(function() {
    $('[data-bs-toggle="tooltip"]').tooltip();
    let map = createLeafletTileLayer('div-map-container', MTO_INIT);

    // offcanvas map controls
    setOffCanvasMapControlAgriculture('daily');

    ////////////
    // Modal Expand Charts

    ['series', 'proba', 'anom'].map(x => {
        const d = `div-chart-${x}`;
        initiDialogBoxSelect2(
            `.daily-${x}-select2`,
            `#daily-${x}-rseason-control`
        );
        $(`#btn-${d}`).on('click', () => {
            setRainySeasonExpandModal('daily', x, d);
        });
    });

    ////////////
    // initialize map
    const map_options = {};
    displayAgricultureAnalysisMap('daily', map_options, map);

    $('#map-control-offcanvas-dataselect')
        .on('hide.bs.offcanvas', (event) => {
            queryParamsAgricultureAnalysisMap('daily', event);
        });

    // display map when offcanvas hidden
    $('#map-control-offcanvas-dataselect')
        .on('hidden.bs.offcanvas', () => {
            displayAgricultureAnalysisMap('daily', map_options, map);
        });

    // 
    $('#map-control-redraw').on('click', () => {
        displayAgricultureAnalysisMap('daily', map_options, map);
    });

    ////////////
    $('#input-time-navigation').on('blur', async () => {
        const ret = await setMapDatesNavInput('daily');
        if (ret) {
            displayAgricultureAnalysisMap('daily', map_options, map);
        }
    });

    $('#prev-time-navigation').on('click', async () => {
        const ret = await setMapDatesNavPrev('daily');
        if (ret) {
            displayAgricultureAnalysisMap('daily', map_options, map);
        }
    });

    $('#next-time-navigation').on('click', async () => {
        const ret = await setMapDatesNavNext('daily');
        if (ret) {
            displayAgricultureAnalysisMap('daily', map_options, map);
        }
    });

    ///////////
    // display preview time series on click on map
    mapClickLayersSpatialAverage(preview_rainyseason_display_charts, 'daily', map);

    //// grid point only 
    $('#support-spatial-average').prop('disabled', true);
    $('#list-spatial-average').prop('disabled', true);
});