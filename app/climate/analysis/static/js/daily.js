$(document).ready(function() {
    // $('[data-bs-toggle="tooltip"]').tooltip();
    const tTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tTriggerList].map(t => new bootstrap.Tooltip(t));

    let map = createLeafletTileLayer('div-map-container', MTO_INIT);

    // offcanvas map controls
    setOffCanvasMapControlDaily('daily');

    ////////////
    // Modal Expand Charts

    // ['anom', 'proba', 'season'].map(x => {
    //     $(`.daily-${x}-select2`).select2({
    //         minimumResultsForSearch: -1,
    //         dropdownParent: $(`#daily-${x}-control`)
    //     });
    //     const d = `div-chart-${x}`;
    //     const sf = x.charAt(0).toUpperCase() + x.slice(1);
    //     const fName = `setAnalysisExpandModal${sf}`;

    //     $(`#btn-${d}`).on('click', () => {
    //         if (typeof globalThis[fName] === 'function') {
    //             globalThis[fName]('daily', d);
    //         }
    //     });
    // });

    $('.daily-anom-select2').select2({
        minimumResultsForSearch: -1,
        dropdownParent: $('#daily-anom-control')
    });
    $('#btn-div-chart-anom').on('click', () => {
        setAnalysisExpandModalDailyAnom('daily', 'div-chart-anom');
    });

    $('.daily-proba-select2').select2({
        minimumResultsForSearch: -1,
        dropdownParent: $('#daily-proba-control')
    });
    $('#btn-div-chart-proba').on('click', () => {
        setAnalysisExpandModalProba('daily', 'div-chart-proba');
    });

    $('.daily-season-select2').select2({
        minimumResultsForSearch: -1,
        dropdownParent: $('#daily-season-control')
    });
    $('#btn-div-chart-season').on('click', () => {
        setAnalysisExpandModalSeason('daily', 'div-chart-season');
    });

    ////////////
    // initialize map
    const map_options = {};
    displayClimateAnalysisMap('daily', map_options, map);

    // display map when offcanvas hidden
    $('#map-control-offcanvas-dataselect').on('hidden.bs.offcanvas', () => {
        displayClimateAnalysisMap('daily', map_options, map);
    });

    // 
    $('#map-control-redraw').on('click', () => {
        displayClimateAnalysisMap('daily', map_options, map);
    });

    ////////////
    $('#input-time-navigation').on('blur', async () => {
        const ret = await setMapDatesNavInput('daily');
        if (ret) {
            displayClimateAnalysisMap('daily', map_options, map);
        }
    });

    $('#prev-time-navigation').on('click', async () => {
        const ret = await setMapDatesNavPrev('daily');
        if (ret) {
            displayClimateAnalysisMap('daily', map_options, map);
        }
    });

    $('#next-time-navigation').on('click', async () => {
        const ret = await setMapDatesNavNext('daily');
        if (ret) {
            displayClimateAnalysisMap('daily', map_options, map);
        }
    });

    ///////////
    // display preview time series on click on map, or select polygon
    mapClickLayersSpatialAverage(preview_seasonal_display_charts, 'daily', map);

    $('#select-country-region').on('change', () => {
        mapClickLayersSpatialAverage(preview_seasonal_display_charts, 'daily', map);
    });

    $('#select-region-name').on('change', () => {
        mapClickLayersSpatialAverage(preview_seasonal_display_charts, 'daily', map);
    });
});