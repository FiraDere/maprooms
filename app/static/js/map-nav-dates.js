async function setMapDatesNavInput(tempRes, suffixID = 'map-date') {
    const this_date = $('#input-time-navigation').val().trim();
    if (this_date === '') {
        flashMessage(JS_TEXT.date_missing, 'error');
        return false;
    }

    const tstepID = `${tempRes}-${suffixID}`;
    const maptype = $(`#${tempRes}-map-type`).val();
    if (maptype === 'climatology') {
        let cl_date = null;
        if (tempRes === 'monthly' || tempRes === 'seasonal') {
            const months = getListOfMonthsCalendar().long;
            const m = months.indexOf(this_date);
            if (m !== -1) {
                cl_date = m + 1;
            }
        } else if (tempRes === 'dekadal') {
            const dekads = getListOfDekadsCalendar();
            const d = dekads.map(x => x.short).indexOf(this_date);
            if (d !== -1) {
                cl_date = dekads[d].value;
            }
        } else {
            return false;
        }

        if (cl_date === null) {
            flashMessage(JS_TEXT.date_invalid, 'error');
            return false;
        }
        $(`#${tstepID}-calendar`).val(cl_date).trigger('change');
    } else {
        let str_time;
        if (tempRes === 'monthly' || tempRes === 'seasonal') {
            str_time = `${this_date}-01 00:00:00`;
        } else if (tempRes === 'dekadal') {
            str_time = `${this_date} 00:00:00`;
        } else if (tempRes === 'daily') {
            str_time = `${this_date}-01-01 00:00:00`;
        } else {
            return false;
        }

        const this_time = new Date(str_time);
        if (isNaN(this_time.getTime())) {
            flashMessage(JS_TEXT.date_invalid, 'error');
            return false;
        }

        const variable = $(`#${tempRes}-map-variable`).val();
        const temp_cov = getTempCoverageCalendar(
            DATA_SET.use, tempRes, variable
        );
        const start = new Date(temp_cov.start);
        const end = new Date(temp_cov.end);
        if (this_time < start || this_time > end) {
            flashMessage(JS_TEXT.date_outrange, 'error');
            return false;
        }

        if (tempRes === 'daily') {
            $(`#${tstepID}-tseries-year`).val(this_date);
        } else {
            const calendarElement = document.getElementById(`${tstepID}-calendar`);
            const calendar = calendarElement.calendar;
            if (calendar) {
                calendar.setValue(str_time);
            } else {
                flashMessage(JS_TEXT.date_calendar, 'error');
                return false;
            }
        }
    }

    return true;
}

async function setMapDatesNavPrev(tempRes, suffixID = 'map-date') {
    const this_date = $('#input-time-navigation').val().trim();
    if (this_date === '') {
        flashMessage(JS_TEXT.date_missing, 'error');
        return false;
    }

    const tstepID = `${tempRes}-${suffixID}`;
    const maptype = $(`#${tempRes}-map-type`).val();
    if (maptype === 'climatology') {
        let cl_date = null;
        let cl_input = null;
        if (tempRes === 'monthly' || tempRes === 'seasonal') {
            const months = getListOfMonthsCalendar().long;
            let m = months.indexOf(this_date);
            if (m !== -1) {
                m = m - 1;
                if (m < 0) {
                    m = 11;
                }
                cl_date = m + 1;
                cl_input = months[m];
            }
        } else if (tempRes === 'dekadal') {
            const dekads = getListOfDekadsCalendar();
            let d = dekads.map(x => x.short).indexOf(this_date);
            if (d !== -1) {
                d = d - 1;
                if (d < 0) {
                    d = 35;
                }
                cl_date = dekads[d].value;
                cl_input = dekads[d].short;
            }
        } else {
            return false;
        }

        if (cl_date === null) {
            flashMessage(JS_TEXT.date_invalid, 'error');
            return false;
        }

        $('#input-time-navigation').val(cl_input);
        $(`#${tstepID}-calendar`).val(cl_date).trigger('change');
    } else {
        let str_time;
        if (tempRes === 'monthly' || tempRes === 'seasonal') {
            str_time = `${this_date}-01 00:00:00`;
        } else if (tempRes === 'dekadal') {
            str_time = `${this_date} 00:00:00`;
        } else if (tempRes === 'daily') {
            str_time = `${this_date}-01-01 00:00:00`;
        } else {
            return false;
        }

        const this_time = new Date(str_time);
        if (isNaN(this_time.getTime())) {
            flashMessage(JS_TEXT.date_invalid, 'error');
            return false;
        }

        const variable = $(`#${tempRes}-map-variable`).val();
        const temp_cov = getTempCoverageCalendar(
            DATA_SET.use, tempRes, variable
        );
        const start = new Date(temp_cov.start);
        const end = new Date(temp_cov.end);

        let input_date;
        let str_date;
        if (tempRes === 'monthly' || tempRes === 'seasonal') {
            let prev_mon = addDateMonths(this_time, -1);
            if (prev_mon < start) {
                prev_mon = end;
            }
            str_date = formatDateToString(prev_mon);
            input_date = str_date.slice(0, 7);
        } else if (tempRes === 'dekadal') {
            let prev_dek = addDateDekads(this_time, -1);
            if (prev_dek < start) {
                prev_dek = end;
            }
            str_date = formatDateToString(prev_dek);
            input_date = str_date.slice(0, 10);
        } else if (tempRes === 'daily') {
            let prev_year = new Date(this_time);
            const this_year = prev_year.getFullYear();
            prev_year.setFullYear(this_year - 1);
            if (prev_year < start) {
                prev_year = end;
            }
            str_date = formatDateToString(prev_year);
            input_date = str_date.slice(0, 4);
        } else {
            return false;
        }
        $('#input-time-navigation').val(input_date);

        if (tempRes === 'daily') {
            $(`#${tstepID}-tseries-year`).val(input_date);
        } else {
            const calendarElement = document.getElementById(`${tstepID}-calendar`);
            const calendar = calendarElement.calendar;
            if (calendar) {
                calendar.setValue(`${str_date} 00:00:00`);
            } else {
                flashMessage(JS_TEXT.date_calendar, 'error');
                return false;
            }
        }
    }

    return true;
}

async function setMapDatesNavNext(tempRes, suffixID = 'map-date') {
    const this_date = $('#input-time-navigation').val().trim();
    if (this_date === '') {
        flashMessage(JS_TEXT.date_missing, 'error');
        return false;
    }

    const tstepID = `${tempRes}-${suffixID}`;
    const maptype = $(`#${tempRes}-map-type`).val();
    if (maptype === 'climatology') {
        let cl_date = null;
        let cl_input = null;
        if (tempRes === 'monthly' || tempRes === 'seasonal') {
            const months = getListOfMonthsCalendar().long;
            let m = months.indexOf(this_date);
            if (m !== -1) {
                m = m + 1;
                if (m > 11) {
                    m = 0;
                }
                cl_date = m + 1;
                cl_input = months[m];
            }
        } else if (tempRes === 'dekadal') {
            const dekads = getListOfDekadsCalendar();
            let d = dekads.map(x => x.short).indexOf(this_date);
            if (d !== -1) {
                d = d + 1;
                if (d > 35) {
                    d = 0;
                }
                cl_date = dekads[d].value;
                cl_input = dekads[d].short;
            }
        } else {
            return false;
        }

        if (cl_date === null) {
            flashMessage(JS_TEXT.date_invalid, 'error');
            return false;
        }

        $('#input-time-navigation').val(cl_input);
        $(`#${tstepID}-calendar`).val(cl_date).trigger('change');
    } else {
        let str_time;
        if (tempRes === 'monthly' || tempRes === 'seasonal') {
            str_time = `${this_date}-01 00:00:00`;
        } else if (tempRes === 'dekadal') {
            str_time = `${this_date} 00:00:00`;
        } else if (tempRes === 'daily') {
            str_time = `${this_date}-01-01 00:00:00`;
        } else {
            return false;
        }

        const this_time = new Date(str_time);
        if (isNaN(this_time.getTime())) {
            flashMessage(JS_TEXT.date_invalid, 'error');
            return false;
        }

        const variable = $(`#${tempRes}-map-variable`).val();
        const temp_cov = getTempCoverageCalendar(
            DATA_SET.use, tempRes, variable
        );
        const start = new Date(temp_cov.start);
        const end = new Date(temp_cov.end);

        let input_date;
        let str_date;
        if (tempRes === 'monthly' || tempRes === 'seasonal') {
            let prev_mon = addDateMonths(this_time, 1);
            if (prev_mon > end) {
                prev_mon = start;
            }
            str_date = formatDateToString(prev_mon);
            input_date = str_date.slice(0, 7);
        } else if (tempRes === 'dekadal') {
            let prev_dek = addDateDekads(this_time, 1);
            if (prev_dek > end) {
                prev_dek = start;
            }
            str_date = formatDateToString(prev_dek);
            input_date = str_date.slice(0, 10);
        } else if (tempRes === 'daily') {
            let prev_year = new Date(this_time);
            const this_year = prev_year.getFullYear();
            prev_year.setFullYear(this_year + 1);
            if (prev_year > end) {
                prev_year = start;
            }
            str_date = formatDateToString(prev_year);
            input_date = str_date.slice(0, 4);
        } else {
            return false;
        }
        $('#input-time-navigation').val(input_date);

        if (tempRes === 'daily') {
            $(`#${tstepID}-tseries-year`).val(input_date);
        } else {
            const calendarElement = document.getElementById(`${tstepID}-calendar`);
            const calendar = calendarElement.calendar;
            if (calendar) {
                calendar.setValue(`${str_date} 00:00:00`);
            } else {
                flashMessage(JS_TEXT.date_calendar, 'error');
                return false;
            }
        }
    }

    return true;
}