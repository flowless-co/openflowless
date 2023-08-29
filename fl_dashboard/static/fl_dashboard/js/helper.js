function capitalize(string){
    return string.charAt(0).toUpperCase() + string.slice(1);
}

/** Returns a moment object of current time in SERVER_TIMEZONE by default, or  */
function getNow(machineTime = false){
    if (machineTime)
        return moment.tz(moment.tz.guess());
    else
        return moment.tz(SERVER_TIMEZONE);
}

function trimNumber(value){
    return parseFloat(value.toFixed(2))
}

class Helper {
    /** Returns the number rounded to a specific decimal place, or NaN if parameter is not a valid number. */
    static round(number, decimalPlaces=3){
        if (number == null || isNaN(number))
            return NaN;
        return parseFloat(parseFloat(number).toFixed(decimalPlaces));
    }
}