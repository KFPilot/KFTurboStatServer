import { fetchJson } from '../main.js';
import { fmt, escapeHtml, statusBadge } from '../format.js';

const PERK_COLORS = {
    'Sharpshooter': '#b62324',
    'Demolitions': '#c45918',
    'Support Specialist': '#9e6a03',
    'Commando': '#1a7f37',
    'Firebug': '#0c7d9d',
    'Field Medic': '#1f6feb',
    'Berserker': '#6639a6',
};

export async function renderPlayer(root, params, playertableid) {
    const data = await fetchJson(`/api/player/${encodeURIComponent(playertableid)}`, params);
    const player = data.player;

    const header = `
        <h1>${escapeHtml(player.playername)}</h1>
        <div class="row g-3 mb-4">
            ${statCard('Wins', player.wincount || 0)}
            ${statCard('Losses', player.losecount || 0)}
            ${statCard('Deaths', player.deaths || 0)}
            ${statCard('Sessions', (data.session_summary || []).length, 'col-md-3')}
            ${statCard('Waves Played', (data.waves || []).length, 'col-md-3')}
        </div>
    `;

    const perks = (data.perk_summary && data.perk_summary.length) ? `
        <h3>Per-Perk Breakdown</h3>
        <div class="row mb-4">
            <div class="col-md-8">
                <div class="table-responsive">
                    <table class="table table-striped">
                        <thead><tr>
                            <th>Perk</th><th>Waves</th><th>Kills</th><th>FP Kills</th><th>SC Kills</th>
                            <th>Damage</th><th>Heals</th><th>Deaths</th><th>Accuracy</th>
                        </tr></thead>
                        <tbody>
                            ${data.perk_summary.map(p => `
                                <tr>
                                    <td>${escapeHtml(p.perk)}</td>
                                    <td>${p.waves_played}</td>
                                    <td>${fmt(p.kills)}</td>
                                    <td>${fmt(p.kills_fp)}</td>
                                    <td>${fmt(p.kills_sc)}</td>
                                    <td>${fmt(p.damage)}</td>
                                    <td>${fmt(p.heals)}</td>
                                    <td>${p.deaths}</td>
                                    <td>${p.accuracy}%</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="col-md-4">
                <canvas id="perkPie" height="250"></canvas>
            </div>
        </div>
    ` : '';

    const sessions = (data.session_summary && data.session_summary.length) ? `
        <h3>Session History</h3>
        <div class="table-responsive">
            <table class="table table-striped">
                <thead><tr>
                    <th>Map</th><th>Result</th><th>Waves</th><th>Perks Used</th><th>Kills</th><th>Damage</th>
                </tr></thead>
                <tbody>
                    ${data.session_summary.map(s => `
                        <tr>
                            <td>${escapeHtml(s.map)}</td>
                            <td>${statusBadge(s.status)}</td>
                            <td>${s.waves_played}</td>
                            <td>${escapeHtml(s.perks)}</td>
                            <td>${fmt(s.kills)}</td>
                            <td>${fmt(s.damage)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    ` : '';

    root.innerHTML = header + perks + sessions;

    if (data.perk_summary && data.perk_summary.length) {
        new Chart(document.getElementById('perkPie'), {
            type: 'doughnut',
            data: {
                labels: data.perk_summary.map(p => p.perk),
                datasets: [{
                    data: data.perk_summary.map(p => p.waves_played),
                    backgroundColor: data.perk_summary.map(p => PERK_COLORS[p.perk] || '#636e7b'),
                    borderWidth: 4,
                    borderColor: '#161b22'
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: { display: true, text: 'Perk Usage (Waves)' },
                    legend: { position: 'bottom' }
                }
            }
        });
    }
}

function statCard(label, value, colClass = 'col-md-2') {
    return `
        <div class="${colClass}">
            <div class="card text-center"><div class="card-body">
                <div class="text-muted small">${escapeHtml(label)}</div>
                <div class="stat-highlight">${escapeHtml(value)}</div>
            </div></div>
        </div>
    `;
}
