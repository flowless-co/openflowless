// Set new default font family and font color to mimic Bootstrap's default styling
Chart.defaults.global.defaultFontFamily = 'Nunito', '-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
Chart.defaults.global.defaultFontColor = '#858796';
Chart.plugins.unregister(ChartDataLabels);

// styles
let colors = ['#ffa532', '#29689c', '#2d91d2', '#68b0c8', '#ffc423'];
let hoverBackgroundColors = ['#ffa532', '#29689c', '#2d91d2', '#68b0c8', '#ffc423'];
let hoverBorderColor = 'rgba(234, 236, 244, 1)';
let tooltipsStyling = {
  backgroundColor: 'rgb(255,255,255)',
  bodyFontColor: '#858796',
  borderColor: '#dddfeb',
  borderWidth: 1,
  xPadding: 15,
  yPadding: 15,
  displayColors: false,
  caretPadding: 10,
};

// references
let apiResponse = {};
let dataset = {
    zoneLabels: [],
    zoneConsumption: [],
    zoneLeaks: []
  };

let consumptionPieChart;
let leaksBarChart;
let againstNrwBarChart;

function renderCharts(filterYear, filterMonth) {
  fetchDataFor(filterYear,filterMonth).then(response => {
    apiResponse = response;
    visualizeAllStats(dissectGlobalApiResponse());
  });
}

function fetchDataFor(year, month){
  return $.ajax({
    url: `/api/monthly-reports-data/?year=${year}&month=${month}`,
    method: 'GET',
    contentType: 'application/json',
    success: response => console.log("RESPONSE DATA: ", response),
    error: error => console.log(error)
  });
}

// Visualizers
function visualizeAllStats(data) {
  visualizeZonalConsumption(data);
  visualizeZonalLeaks(data);
  visualizeZonalConsumptionAgainstNRW(data);
}

function visualizeZonalConsumption(dataset) {
  if (dataset.zoneLabels.length != dataset.zoneConsumption.length)
    return;

  if(consumptionPieChart)
    consumptionPieChart.destroy();

  let consumptionPieChartCtx = document.getElementById("PieChart");
  consumptionPieChart = new Chart(consumptionPieChartCtx, {
    type: 'doughnut',
    plugins: [ChartDataLabels],
    data: {
      labels: dataset.zoneLabels,
      datasets: [{
        data: dataset.zoneConsumption,
        backgroundColor: getCycledColors(dataset.zoneConsumption.length, colors),
        hoverBackgroundColor: getCycledColors(dataset.zoneConsumption.length, hoverBackgroundColors),
        hoverBorderColor: hoverBorderColor,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      tooltips: Object.assign(tooltipsStyling, {
        callbacks: {
          label: function(tooltipItem, data) {
            let dataLabel = data.labels[tooltipItem.index] || '';
            let dataValue = data.datasets[tooltipItem.datasetIndex].data[tooltipItem.index];
            let label = '';

            if (dataLabel)
              label += dataLabel + ': ';

            label += `${dataValue} m³`;

            let sumOfAll = data.datasets[tooltipItem.datasetIndex].data.reduce((acc,x) => acc+x, 0);
            if(sumOfAll > 0)
              label += ' (' + Math.round(dataValue/sumOfAll * 10000) / 100 + '%)';

            return label;
          }
        }
      }),
      cutoutPercentage: 40,
      plugins: {
        datalabels: {
          font: {
            size: 14,
            style: 'bold'
          },
          color: "#fff",
          formatter: function (value, context) {
            return value + " Ltr";
          }
        }
      }
    },
  });
}

function visualizeZonalLeaks(dataset) {
  if (dataset.zoneLabels.length != dataset.zoneLeaks.length)
    return;

  if(leaksBarChart)
    leaksBarChart.destroy();

  let sBarCanvas = document.getElementById("StackedBarChart");
  leaksBarChart = new Chart(sBarCanvas, {
    type: 'bar',
    data: {
      labels: dataset.zoneLabels,
      datasets: [{
        label: 'Leaks',
        data: dataset.zoneLeaks,
        backgroundColor: 'rgb(255,165,50)'
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      tooltips: {
        enabled: false
      },
      scales: {
        yAxes: [{
          ticks: {
              beginAtZero: true
          }
        }]
      }
    }
  });
}

function visualizeZonalConsumptionAgainstNRW(dataset) {
  if (dataset.zoneLabels.length != dataset.zoneConsumption.length)
    return;

  if(againstNrwBarChart)
    againstNrwBarChart.destroy();

  let hBarCanvas = document.getElementById("HBarChart");
  againstNrwBarChart = new Chart(hBarCanvas, {
    type: 'horizontalBar',
    plugins: [ChartDataLabels],
    data: {
      labels: dataset.zoneLabels,
      datasets: [
        {
          label: 'Consumption',
          borderColor: "#144e69",
          borderWidth: 1,
          backgroundColor: "#2c7db7",
          data: dataset.zoneConsumption,
          fill: true,
          datalabels: {
            color: '#c8f0ff'
          }
        },
        {
          label: 'Non-revenue Water',
          borderColor: '#144e69',
          borderWidth: 1,
          backgroundColor: "#ffa532",
          data: dataset.zoneLeaks,
          fill: false,
          datalabels: {
            color: '#3e311e'
          }
        },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      tooltips: {
        mode: 'index',
        callbacks: {
          label: function(tooltipItems, data) {
            let i = data.datasets[tooltipItems.datasetIndex].label || "";
            return i && (i += ": "),
                tooltipItems.value == null ? i += tooltipItems.yLabel : i += tooltipItems.value + " m³",
                i
          },
          // Use the footer callback to display the sum of the items showing in the tooltip
          footer: function (tooltipItems, data) {
            let firstValue = parseFloat(tooltipItems[0].value);
            let secondValue = parseFloat(tooltipItems[1].value);

            let sum = firstValue + secondValue;
            return "Total: " + sum + " m³";
          },
        },
        footerFontStyle: 'bold'
      },
      plugins: {
        // Change options for ALL labels of THIS CHART
        datalabels: {
          font: {
            size: 15,
            style: 'bold'
          },
          color: '#fff',
          formatter: function (value, context) {
            let datasetIdx = context.datasetIndex;
            if (datasetIdx == 1 && context.chart.config.data.datasets.length > 0) {
              let consumptionValue = context.chart.config.data.datasets[0].data[context.dataIndex];
              return formatNumber(value / (consumptionValue + value) * 100, 1) + "%"
            }
            return value + " Ltr";
          }
        }
      },
      scales: {
        yAxes: [{stacked: true}],
        xAxes: [{stacked: true}],
      },
    }
  });
}

// Response Parsers
function dissectGlobalApiResponse() {
  return {
    zoneLabels: extractZoneLabelsFromApiResponse(apiResponse),
    zoneConsumption: extractZoneConsumptionFromApiResponse(apiResponse),
    zoneLeaks: extractZoneLeaksFromApiResponse(apiResponse)
  }
}

function extractZoneLabelsFromApiResponse(apiResponse) {
  if (!apiResponse.hasOwnProperty('zoneMetaData'))
    return;

  let zoneLabels = [];
  for (let zoneId in apiResponse.zoneMetaData) {
    zoneLabels.push(apiResponse.zoneMetaData[zoneId].name)
  }

  return zoneLabels;
}

function extractZoneConsumptionFromApiResponse(apiResponse) {
  if (!apiResponse.hasOwnProperty('zoneStats'))
    return;

  let zoneConsumption = [];
  for (let zoneId in apiResponse.zoneStats) {
    zoneConsumption.push(parseFloat(apiResponse.zoneStats[zoneId].consumption))
  }

  return zoneConsumption;
}

function extractZoneLeaksFromApiResponse(apiResponse) {
  if (!apiResponse.hasOwnProperty('zoneStats'))
    return;

  let zoneLeaks = [];
  for (let zoneId in apiResponse.zoneStats) {
    zoneLeaks.push(parseFloat(apiResponse.zoneStats[zoneId].leak))
  }

  return zoneLeaks;
}


// Helpers
function getCycledColors(n, colorsList){
  let cycledList = [];

  for (let i = 0; i < n; i++)
    cycledList.push(colorsList[i % colorsList.length]);

  return cycledList;
}

function formatNumber(number, decimalPlaces = 3) {
  let roundUp = number.toFixed(decimalPlaces);
  let toNumber = parseFloat(roundUp);
  return toNumber.toString();
}