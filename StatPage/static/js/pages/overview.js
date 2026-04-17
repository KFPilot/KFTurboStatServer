import { fetchJson } from '../main.js';
import { gametypeName, difficultyName, getFilterQS } from '../filters.js';
import { escapeHtml, statusBadge } from '../format.js';

const STATUS_COLORS = {
    'Win': '#1a7f37',
    'Lose': '#9e2a2a',
    'Abort': '#484f58',
    'Ended': '#484f58',
    'InProgress': '#9e6a03',
};

export async function renderOverview(root, params) {
    const overview = await fetchJson('/api/overview', params);
    const wins = overview.status_counts.Win || 0;
    const losses = overview.status_counts.Lose || 0;

    const summary = `
        <h1>Overview</h1>
        <div class="row g-3 mb-4">
            ${statCard('Total Sessions', overview.total_sessions)}
            ${statCard('Total Players', overview.total_players)}
            ${statCard('Wins', wins)}
            ${statCard('Losses', losses)}
        </div>
    `;

    const charts = overview.top_maps && overview.top_maps.length ? `
        <div class="row mb-4">
            <div class="col-md-4">
                <div class="card"><div class="card-body">
                    <h5 class="card-title">Game Results</h5>
                    <div style="height: 400px;"><canvas id="statusChart"></canvas></div>
                </div></div>
            </div>
            <div class="col-md-4">
                <div class="card"><div class="card-body">
                    <h5 class="card-title">Top Maps (Games)</h5>
                    <div style="height: 400px;"><canvas id="mapChart"></canvas></div>
                </div></div>
            </div>
            <div class="col-md-4">
                <div class="card"><div class="card-body">
                    <h5 class="card-title">Top Maps (Waves)</h5>
                    <div style="height: 400px;"><canvas id="mapWavesChart"></canvas></div>
                </div></div>
            </div>
        </div>
    ` : '';

    const recent = overview.recent_sessions && overview.recent_sessions.length ? `
        <div class="card"><div class="card-body">
            <h5 class="card-title">Recent Sessions</h5>
            <div class="table-responsive">
                <table class="table table-striped table-hover mb-0" id="recentSessionsTable">
                    <thead><tr>
                        <th>Time</th><th>Map</th><th>Mode</th><th>Difficulty</th><th>Result</th><th>Version</th>
                    </tr></thead>
                    <tbody>
                        ${overview.recent_sessions.map(s => `
                            <tr data-sessionid="${escapeHtml(s.sessionid)}" style="cursor: pointer;">
                                <td title="${escapeHtml(s.time)}">${escapeHtml(s.elapsed)}</td>
                                <td>${escapeHtml(s.map)}</td>
                                <td>${escapeHtml(gametypeName(s.gametype))}</td>
                                <td>${escapeHtml(difficultyName(s.difficulty))}</td>
                                <td>${statusBadge(s.status)}</td>
                                <td class="text-muted">${escapeHtml(s.version)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div></div>
    ` : '';

    root.innerHTML = summary + charts + recent;

    if (overview.top_maps && overview.top_maps.length) {
        drawStatusChart(overview.status_counts);
        drawMapChart(overview.top_maps);
        drawMapWavesChart(overview.top_maps_by_waves || []);
    }

    const recentTable = document.getElementById('recentSessionsTable');
    if (recentTable) {
        recentTable.querySelector('tbody').addEventListener('click', e => {
            const tr = e.target.closest('tr[data-sessionid]');
            if (!tr) return;
            location.hash = '#/session/' + encodeURIComponent(tr.dataset.sessionid);
        });
    }
}

function statCard(label, value) {
    return `
        <div class="col-md-3">
            <div class="card text-center"><div class="card-body">
                <h5 class="card-title text-muted">${escapeHtml(label)}</h5>
                <p class="display-6">${escapeHtml(value)}</p>
            </div></div>
        </div>
    `;
}

function drawStatusChart(statusData) {
    const labels = Object.keys(statusData);
    if (!labels.length) return;
    new Chart(document.getElementById('statusChart'), {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{
                data: labels.map(k => statusData[k]),
                backgroundColor: labels.map(k => STATUS_COLORS[k] || '#484f58'),
                borderWidth: 4,
                borderColor: '#161b22'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } }
        }
    });
}

function drawMapChart(mapData) {
    new Chart(document.getElementById('mapChart'), {
        type: 'bar',
        data: {
            labels: mapData.map(m => m.map),
            datasets: [{
                label: 'Games Played',
                data: mapData.map(m => m.count),
                backgroundColor: '#1f6feb'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: { legend: { display: false } }
        }
    });
}

function drawMapWavesChart(mapData) {
    new Chart(document.getElementById('mapWavesChart'), {
        type: 'bar',
        data: {
            labels: mapData.map(m => m.map),
            datasets: [{
                label: 'Waves Played',
                data: mapData.map(m => m.waves),
                backgroundColor: '#6639a6'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: { legend: { display: false } }
        }
    });
}
