// Set new default font family and font color to mimic Bootstrap's default styling
Chart.defaults.global.defaultFontFamily = 'Nunito', '-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
Chart.defaults.global.defaultFontColor = '#858796';

let API_RESPONSE = {
    'labels': [],
    'values': []
};
let HOURS_AGO_CHART;

function renderCharts() {
    fetchDataFor().then(response => {
        API_RESPONSE = response;
        render_hours_ago_consumption_chart();
    });
}

function fetchDataFor(){
    return $.ajax({
        url: '/api/consumption-hours-ago?hours=24',
        method: 'GET',
        contentType: 'application/json',
        success: response => console.log("RESPONSE DATA: ", response),
        error: error => console.log(error)
    });
}

function render_hours_ago_consumption_chart(dataset = API_RESPONSE){
    // Area Chart Example
    var context = document.getElementById("myAreaChart");
    HOURS_AGO_CHART = new Chart(context, {
        type: 'line',
        data: {
            labels: dataset.labels,
            datasets: [{
                label: "Flow Rate",
                backgroundColor: "#8cd4e5",
                hoverBackgroundColor: "#144e69",
                borderColor: "#8cd4e5",
                data: dataset.values,
            }],
        },
        options: {
            maintainAspectRatio: false,
            layout: {
                padding: {
                    left: 0,
                    right: 0,
                    top: 25,
                    bottom: 0
                }
            },
            scales: {
                xAxes: [{
                    time: {
                        unit: 'date'
                    },
                    scaleLabel: {
                      labelString: 'Time (Last 24 Hours)',
                      display: true,
                      padding: 0,
                    },
                    gridLines: {
                        display: true,
                        drawBorder: false
                    },
                    ticks: {
                        maxTicksLimit: 24
                    }
                }],
                yAxes: [{
                    ticks: {
                        min: 0,
                        maxTicksLimit: 5,
                        padding: 10,
                    },
                    gridLines: {
                        color: "rgb(234, 236, 244)",
                        zeroLineColor: "rgb(234, 236, 244)",
                        drawBorder: false,
                        borderDash: [2],
                        zeroLineBorderDash: [2]
                    },
                    scaleLabel: {
                        labelString: 'Flow Rate (m3)',
                        display: true,
                    }
                }],
            },
            legend: {
                display: false
            },
            tooltips: {
                backgroundColor: "rgb(255,255,255)",
                bodyFontColor: "#858796",
                titleMarginBottom: 10,
                titleFontColor: '#6e707e',
                titleFontSize: 14,
                borderColor: '#dddfeb',
                borderWidth: 1,
                xPadding: 15,
                yPadding: 15,
                displayColors: false,
                intersect: false,
                mode: 'index',
                caretPadding: 10,
                callbacks: {
                    label: function (tooltipItem, chart) {
                        let datasetLabel = chart.datasets[tooltipItem.datasetIndex].label || '';
                        let value = Helper.round(tooltipItem.yLabel);
                        if (isNaN(value)) value = 'n/a';
                        return datasetLabel + ' : ' + value;
                    }
                }
            }
        }
    });
}

// get new data every 3 seconds
//setInterval(getData, 3000);
var getData = function () {
    nextDate = new Date(2019, 2, 6);


    // prepare date label
    nextDateString = nextDate.getFullYear() + '-'
        + ('0' + (nextDate.getMonth() + 1)).slice(-2) + '-'
        + ('0' + nextDate.getDate()).slice(-2);

    //  get chart's underlying data structures
    var data = myBarChart.data.datasets[0].data;
    // add data point
    data.push(getRandomIntInclusive(500, 1500));
    // remove oldest data point (leftmost value)
    data.shift();

    // add new data point's label
    myBarChart.data.labels.push(nextDateString);
    // remove oldest data point's label (leftmost label)
    myBarChart.data.labels.splice(0, 1);

    // re-render the chart
    myBarChart.update();

    // incremeant date
    nextDate.setHours(nextDate.getHours() + 24);
};
