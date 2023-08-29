// Set new default font family and font color to mimic Bootstrap's default styling
Chart.defaults.global.defaultFontFamily = 'Nunito', '-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
Chart.defaults.global.defaultFontColor = '#858796';

// styles
let LIGHTENED_COLORS = ['#ffc85d', '#3586ca', '#34a7f2', '#9fd8ee', '#ffc423'];
let COLORS = ['#ffa532', '#29689c', '#2d91d2', '#68b0c8', '#ffc423'];
let DARKENED_COLORS = ['#d48533', '#275e91', '#277eb7', '#5693a7', '#ffc423'];

// references
let API_RESPONSE = {};
let ZONE_LABELS = [];
let ZONE_IDS = [];
let DAYS_INDICES = [0,1,2,3,4,5,6];
let FOR_DAY = new Date();

let consumptionPieChart;
let weeklyConsumptionBarChart;
let yesterdayAvgBarChart;

function renderCharts(filterDate) {
  FOR_DAY = new Date(filterDate + ":");
  filterDateInUTC = moment.tz(filterDate, "UTC");

  fetchDataFor(filterDateInUTC.year(), filterDateInUTC.month()+1, filterDateInUTC.date()).then(response => {
    API_RESPONSE = response;
    ZONE_LABELS = Object.keys(response.zoneMetaData).map(zoneId => response.zoneMetaData[zoneId].name);
    ZONE_IDS = Object.keys(response.zoneMetaData).map(zoneId=>zoneId);
    visualizeAllStatsWithGlobalApiResponse();
  });
}

/** Parameters should be in UTC. Server filters on UTC dates. */
function fetchDataFor(year, month, day){
  return $.ajax({
    url: `/api/daily-reports-data/?year=${year}&month=${month}&day=${day}`,
    method: 'GET',
    contentType: 'application/json',
    success: response => console.log("RESPONSE DATA: ", response),
    error: error => console.log(error)
  });
}

// Visualizers
function visualizeAllStatsWithGlobalApiResponse() {
  visualizeZonalConsumption(API_RESPONSE);
  visualizeWeeklyConsumption(API_RESPONSE);
  visualizeYesterdayAvgConsumption(API_RESPONSE);
}

function visualizeZonalConsumption(dataset) {
  if(consumptionPieChart)
    consumptionPieChart.destroy();

  let consumptionPieChartCtx = document.getElementById("PieChart");
  consumptionPieChart = new Chart(consumptionPieChartCtx, {
    type: 'doughnut',
    data: {
      labels: ZONE_LABELS,
      datasets: [{
        data: Object.keys(dataset.zoneStats).map(zoneId=>dataset.zoneStats[zoneId][0].consumption),
        backgroundColor: getCycledColors(ZONE_LABELS.length, COLORS),
        hoverBackgroundColor: getCycledColors(ZONE_LABELS.length, DARKENED_COLORS),
        hoverBorderColor: "rgba(234, 236, 244, 1)",
      }],
    },
    options: {
      responsive:true,
      maintainAspectRatio: false,
      tooltips: {
        backgroundColor: "rgb(255,255,255)",
        bodyFontColor: "#858796",
        borderColor: '#dddfeb',
        borderWidth: 1,
        xPadding: 15,
        yPadding: 15,
        displayColors: false,
        caretPadding: 10,
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
      },
      cutoutPercentage: 40,
    },
  });
}

function visualizeWeeklyConsumption(dataset){
  if(weeklyConsumptionBarChart)
    weeklyConsumptionBarChart.destroy();

  let dataset_list = [
    {
      label: 'Avg. Daily',
      data: DAYS_INDICES.map(dayId=>ZONE_IDS.reduce((acc, zoneId)=> acc + parseFloat(dataset.zoneStats[zoneId][dayId].average),0)).reverse(),
      type: 'line',
      backgroundColor: '#dd5900',
      borderColor: 'rgba(189,189,189,0.51)',
      fill: false
    }
  ];

  ZONE_IDS.map((zoneId, idx)=>dataset_list.push({
    label: dataset.zoneMetaData[zoneId].name,
    data: DAYS_INDICES.map(dayIdx => parseFloat(dataset.zoneStats[zoneId][dayIdx].consumption)).reverse(),
    backgroundColor: LIGHTENED_COLORS[idx % LIGHTENED_COLORS.length]
  }));

  // Temporarily Remove Avg Line:
  dataset_list = dataset_list.filter(dataset => dataset.label !== 'Avg. Daily');

  let canvas = document.getElementById("StackedBarChart");
  weeklyConsumptionBarChart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: DAYS_INDICES.map(dayIdx => {
        let daysDelta = 6 - dayIdx;
        let day = new Date(FOR_DAY.getTime());
        day.setDate(day.getDate() - daysDelta);
        let formattableDay = moment(day);
        return formattableDay.format("D/M/Y");
      }),
      datasets: dataset_list,
    },
    options: {
      responsive:true,
      maintainAspectRatio: false,
      scales: {
        yAxes: [{
          stacked: true,
          ticks:{ suggestedMin:0 }
        }],
        xAxes: [{stacked: true}],
      },
      tooltips: {
        callbacks: {
          label: function(tooltipItem, data){
            let dataLabel = data.labels[tooltipItem.index] || '';
            let dataValue = data.datasets[tooltipItem.datasetIndex].data[tooltipItem.index];
            let label = '';

            if (dataLabel)
              label += dataLabel + ': ';

            label += `${dataValue} m³`;

            let sumOfAll = data.datasets
                .filter(dataset => dataset.label !== "Avg. Daily") // exclude from percentage calculation
                .reduce((acc, dataset) => acc + dataset.data[tooltipItem.index], 0);
            if(sumOfAll > 0)
              // exclude percentage from showing up in average data point tooltips
              // guard against division by zero error
              label += ' (' + Math.round(dataValue/sumOfAll * 10000) / 100 + '%)';

            return label;
          }
        }
      }
    },
  });
}

function visualizeYesterdayAvgConsumption(dataset){
  if(yesterdayAvgBarChart)
    yesterdayAvgBarChart.destroy();


  let canvas = document.getElementById("HBarChart");
  yesterdayAvgBarChart = new Chart(canvas, {
    type: 'horizontalBar',
    data: {
      labels: ZONE_LABELS,
      datasets: [{
        label: 'Yesterday ',
        borderColor: "#b47224",
        borderWidth: 1,
        backgroundColor: "#ffa532",
        data: Object.keys(dataset.zoneStats).map(zoneId=>dataset.zoneStats[zoneId][1]['consumption']),
        fill: true
      }, {
        label: 'Daily Average',
        borderColor: 'navy',
        borderWidth: 1,
        backgroundColor: "#2c7db7",
        data: Object.keys(dataset.zoneStats).map(zoneId=>dataset.zoneStats[zoneId][1]['average']),
        fill: false
      },
      ]
    },
    options: {
      responsive:true,
      maintainAspectRatio: false,
      scales: {
        xAxes: [{
          ticks:{
            suggestedMin:100
          }
        }],
      },
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
          footer: function(tooltipItems, data) {
            console.log('footer', tooltipItems, data);
            let firstValue = parseFloat(tooltipItems[0].value);
            let secondValue = parseFloat(tooltipItems[1].value);

            let delta = firstValue - secondValue;
            return `Delta: ${delta >= 0 ? "+": ""}${delta} m³`;
          },
        },
        footerFontStyle: 'normal'
      },
    },
  });
}

// Helpers
function getCycledColors(n, colorsList){
  let cycledList = [];

  for (let i = 0; i < n; i++)
    cycledList.push(colorsList[i % colorsList.length]);

  return cycledList;
}