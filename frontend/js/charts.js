/**
 * Chart.js Analytics Controller for Attendance Trends
 * Visualizes Daily, Weekly, and Monthly Attendance Distributions
 * Styled for Premium Light Theme
 */

let dailyChartInstance = null;
let weeklyChartInstance = null;

function initCharts(analyticsData) {
    const dailyCtx = document.getElementById('dailyChart');
    const weeklyCtx = document.getElementById('weeklyChart');

    if (!dailyCtx || !weeklyCtx) return;

    // Daily Trend Line Chart
    const dailyTrend = (analyticsData && analyticsData.daily_trend) ? analyticsData.daily_trend : [];
    const dailyLabels = dailyTrend.map(d => d.date);
    const dailyCounts = dailyTrend.map(d => d.count);

    if (dailyChartInstance) {
        dailyChartInstance.destroy();
    }

    dailyChartInstance = new Chart(dailyCtx, {
        type: 'line',
        data: {
            labels: dailyLabels.length ? dailyLabels : ['No Sessions Recorded'],
            datasets: [{
                label: 'Present Students',
                data: dailyCounts.length ? dailyCounts : [0],
                borderColor: '#4f46e5',
                backgroundColor: 'rgba(79, 70, 229, 0.08)',
                borderWidth: 2.5,
                tension: 0.35,
                fill: true,
                pointBackgroundColor: '#4f46e5',
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
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
                    backgroundColor: '#0f172a',
                    titleColor: '#f8fafc',
                    bodyColor: '#a5b4fc',
                    borderColor: '#e2e8f0',
                    borderWidth: 1,
                    padding: 10,
                    boxPadding: 4,
                    cornerRadius: 8,
                    titleFont: { family: 'Plus Jakarta Sans', size: 12, weight: 'bold' },
                    bodyFont: { family: 'Plus Jakarta Sans', size: 12 }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(15, 23, 42, 0.05)', drawBorder: false },
                    ticks: { color: '#64748b', font: { family: 'Plus Jakarta Sans', size: 11, weight: '500' } }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(15, 23, 42, 0.05)', drawBorder: false },
                    ticks: { color: '#64748b', font: { family: 'Plus Jakarta Sans', size: 11, weight: '500' }, precision: 0 }
                }
            }
        }
    });

    // Weekly / Monthly Bar Chart
    const weeklyTrend = (analyticsData && analyticsData.weekly_trend) ? analyticsData.weekly_trend : [];
    const weeklyLabels = weeklyTrend.map(w => w.week);
    const weeklyCounts = weeklyTrend.map(w => w.count);

    if (weeklyChartInstance) {
        weeklyChartInstance.destroy();
    }

    weeklyChartInstance = new Chart(weeklyCtx, {
        type: 'bar',
        data: {
            labels: weeklyLabels.length ? weeklyLabels : ['No Records'],
            datasets: [{
                label: 'Unique Attendees',
                data: weeklyCounts.length ? weeklyCounts : [0],
                backgroundColor: 'rgba(16, 185, 129, 0.85)',
                borderColor: '#10b981',
                borderWidth: 1.5,
                borderRadius: 8,
                maxBarThickness: 45
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#0f172a',
                    titleColor: '#f8fafc',
                    bodyColor: '#6ee7b7',
                    borderColor: '#e2e8f0',
                    borderWidth: 1,
                    padding: 10,
                    boxPadding: 4,
                    cornerRadius: 8,
                    titleFont: { family: 'Plus Jakarta Sans', size: 12, weight: 'bold' },
                    bodyFont: { family: 'Plus Jakarta Sans', size: 12 }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: '#64748b', font: { family: 'Plus Jakarta Sans', size: 11, weight: '500' } }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(15, 23, 42, 0.05)', drawBorder: false },
                    ticks: { color: '#64748b', font: { family: 'Plus Jakarta Sans', size: 11, weight: '500' }, precision: 0 }
                }
            }
        }
    });
}
