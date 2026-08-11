$(document).ready(function() {
    $('[data-bs-toggle="tooltip"]').tooltip();
    let map = createLeafletTileLayer('div-map-container', MTO_INIT);

    // hide map navigation
    $('#container-map-navigation').hide();

    // offcanvas map controls
    setOffCanvasMapControlAgriculture('daily');

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
});