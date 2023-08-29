// interface grapherObj = {
//     labels: string[],
//     charts: {
//         [chartName: string]: {
//             canvasElement: HTMLElement,
//             dataPoints: number[]
//         },
//     }
// };

function runLineGrapher(grapherObj){
    for (let [chartName, chartData] of Object.entries(grapherObj.charts)){
        new Chart(chartData.canvasElement, {
            type: 'line',
            data: {
                labels: grapherObj.labels,
                datasets: [{
                    label: '',
                    data: chartData.dataPoints,
                    fill: false,
                    backgroundColor: '#' + CYCLABLE_COLORS.greens[0],
                    borderColor: '#' + CYCLABLE_COLORS.greens[0],
                    cubicInterpolationMode: 'monotone',
                    pointRadius: 2,
                }]
            },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: capitalize(chartName),
                    position: 'top'
                },
                scales: {
                    xAxes:[{
                        type: 'time',
                        time:{
                            unit: 'day',
                            tooltipFormat:'MM/DD/YYYY'
                        }
                    }],
                    yAxes: [{
                        ticks: {
                            maxTicksLimit: 7,
                        },
                    }]
                }
            }
        });
    }
}