$(document).ready(function() {
    $('[data-bs-toggle="tooltip"]').tooltip();
    let map = createLeafletTileLayer('div-map-container', MTO_INIT);

    // offcanvas map controls
    setOffCanvasMapControlAgriculture('daily');

    ////////////
    // Modal Expand Charts
    $('.daily-cropsuit-select2').select2({
        minimumResultsForSearch: -1,
        dropdownParent: $('#daily-cropsuit-control')
    });
    $('#btn-div-chart-cropsuit').on('click', () => {
        setCropSuitabilityExpandModal('daily', 'div-chart-cropsuit');
    });

    ////////////
    // initialize map
    const map_options = {};
    displayAgricultureAnalysisMap('daily', map_options, map);

    // display map when offcanvas hidden
    $('#map-control-offcanvas-dataselect').on('hidden.bs.offcanvas', () => {
        displayAgricultureAnalysisMap('daily', map_options, map);
    });

    // 
    $('#map-control-redraw').on('click', () => {
        displayAgricultureAnalysisMap('daily', map_options, map);
    });

    ////////////
    $('#input-time-navigation').on('blur', async () => {
        const ret = await setMapDatesNavInput('daily', 'cs');
        if (ret) {
            displayAgricultureAnalysisMap('daily', map_options, map);
        }
    });

    $('#prev-time-navigation').on('click', async () => {
        const ret = await setMapDatesNavPrev('daily', 'cs');
        if (ret) {
            displayAgricultureAnalysisMap('daily', map_options, map);
        }
    });

    $('#next-time-navigation').on('click', async () => {
        const ret = await setMapDatesNavNext('daily', 'cs');
        if (ret) {
            displayAgricultureAnalysisMap('daily', map_options, map);
        }
    });

    ///////////
    // display preview time series on click on map
    mapClickLayersSpatialAverage(preview_cropsuitability_display_charts, 'daily', map);
});