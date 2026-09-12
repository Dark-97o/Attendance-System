/**
 * Chart.js Analytics Controller for Attendance Trends
 * Visualizes Daily, Weekly, and Monthly Attendance Distributions
 */

let dailyChartInstance = null;
let weeklyChartInstance = null;

function initCharts(analyticsData) {
    const dailyCtx = document.getElementById('dailyChart');
    const weeklyCtx = document.getElementById('weeklyChart');

    if (!dailyCtx || !weeklyCtx) return;

    // Daily Trend Line Chart
    const dailyLabels = analyticsData.daily_trend.map(d => d.date);
    const dailyCounts = analyticsData.daily_trend.map(d => d.count);

    if (dailyChartInstance) {
        dailyChartInstance.destroy();
    }

    dailyChartInstance = new Chart(dailyCtx, {
        type: 'line',
        data: {
            labels: dailyLabels.length ? dailyLabels : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
            datasets: [{
                label: 'Present Students',
                data: dailyCounts.length ? dailyCounts : [6, 7, 8, 7, 8],
                borderColor: '#00f0ff',
                backgroundColor: 'rgba(0, 240, 255, 0.12)',
                borderWidth: 3,
                tension: 0.35,
                fill: true,
                pointBackgroundColor: '#00f0ff',
                pointBorderColor: '#fff',
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(14, 22, 38, 0.95)',
                    titleColor: '#fff',
                    bodyColor: '#00f0ff',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11 } }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11 }, precision: 0 }
                }
            }
        }
    });

    // Weekly / Monthly Bar Chart
    const weeklyLabels = analyticsData.weekly_trend.map(w => w.week);
    const weeklyCounts = analyticsData.weekly_trend.map(w => w.count);

    if (weeklyChartInstance) {
        weeklyChartInstance.destroy();
    }

    weeklyChartInstance = new Chart(weeklyCtx, {
        type: 'bar',
        data: {
            labels: weeklyLabels.length ? weeklyLabels : ['Week 34', 'Week 35', 'Week 36', 'Week 37'],
            datasets: [{
                label: 'Unique Attendees',
                data: weeklyCounts.length ? weeklyCounts : [8, 8, 7, 8],
                backgroundColor: 'rgba(16, 185, 129, 0.65)',
                borderColor: '#10b981',
                borderWidth: 2,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(14, 22, 38, 0.95)',
                    titleColor: '#fff',
                    bodyColor: '#10b981',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11 } }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8', font: { family: 'Plus Jakarta Sans', size: 11 }, precision: 0 }
                }
            }
        }
    });
}
