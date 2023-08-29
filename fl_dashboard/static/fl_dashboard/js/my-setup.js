// Hacking Prototypes
moment.fn.toISODate = function () {
    return this.toISOString().substring(0, 10);
};

// Global Variables
let isOnServerTimezone;
let notOnServerTimezone;
/** Offset from server time, in minutes. */
let serverTimezoneOffset = 0;
let serverTimezoneOffsetMessage = '';

// Global Functions
const serverNow = () => moment.tz(SERVER_TIMEZONE);

function addServerOffsetToLabel($labelElem){
    const labelText = $labelElem.html();
    $labelElem.empty();
    $(`<abbr title="${serverTimezoneOffsetMessage}">${labelText}</abbr>`).appendTo($labelElem);
}

// On Page Ready
$(function () {
    isOnServerTimezone = SERVER_TIMEZONE === moment.tz.guess();
    notOnServerTimezone = !isOnServerTimezone;
    if(notOnServerTimezone){
        let serverTime = moment.tz(SERVER_TIMEZONE);
        let clientTime = moment.tz(moment.tz.guess());
        serverTimezoneOffset = serverTime.utcOffset() - clientTime.utcOffset();
        serverTimezoneOffsetMessage = `You are ${serverTimezoneOffset > 0 ? 'behind' : 'ahead'} server time by ${serverTimezoneOffset >= 60 ? serverTimezoneOffset/60 + ' hours.' : serverTimezoneOffset + ' minutes.' }`;
    }
});

const CYCLABLE_COLORS = {
    blues: [
        '36A0FC',
        '7FCDC6',
        '6468DB'
    ],
    greens: [
        '61E294',
    ],
    purples: [
        '473DA4',
        '80569C'
    ],
    reds: [
        'C80487',
        'B02940'
    ],
    yellows: [
        'F9C80E',
        'AAD246'
    ],
};

function darken(color, v) {
    v = -v;
    if (color.length >6) { color= color.substring(1,color.length)}
    var rgb = parseInt(color, 16);
    var r = Math.abs(((rgb >> 16) & 0xFF)+v); if (r>255) r=r-(r-255);
    var g = Math.abs(((rgb >> 8) & 0xFF)+v); if (g>255) g=g-(g-255);
    var b = Math.abs((rgb & 0xFF)+v); if (b>255) b=b-(b-255);
    r = Number(r < 0 || isNaN(r)) ? 0 : ((r > 255) ? 255 : r).toString(16);
    if (r.length == 1) r = '0' + r;
    g = Number(g < 0 || isNaN(g)) ? 0 : ((g > 255) ? 255 : g).toString(16);
    if (g.length == 1) g = '0' + g;
    b = Number(b < 0 || isNaN(b)) ? 0 : ((b > 255) ? 255 : b).toString(16);
    if (b.length == 1) b = '0' + b;
    return "#" + r + g + b;
}

function getCycledColors(n){
    let allShades = [];
    for(let i of [0,1,2])
        for (let shades of [CYCLABLE_COLORS.blues, CYCLABLE_COLORS.yellows, CYCLABLE_COLORS.purples, CYCLABLE_COLORS.greens, CYCLABLE_COLORS.reds])
            if(shades[i])
                allShades.push(shades[i]);

    return allShades.slice(0, n);
}
