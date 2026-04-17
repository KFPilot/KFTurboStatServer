import { fetchJson } from '../main.js';
import { fmt, escapeHtml, sortableTable } from '../format.js';

const ALL_PERKS = [
    { name: 'Sharpshooter',       color: '#b62324' },
    { name: 'Demolitions',        color: '#c45918' },
    { name: 'Support Specialist', color: '#9e6a03' },
    { name: 'Commando',           color: '#1a7f37' },
    { name: 'Firebug',            color: '#0c7d9d' },
    { name: 'Field Medic',        color: '#1f6feb' },
    { name: 'Berserker',          color: '#6639a6' },
];

function perkColor(name) {
    const entry = ALL_PERKS.find(p => p.name === name);
    return entry ? entry.color : '#636e7b';
}

function wrapLabel(name) {
    return name.includes(' ') ? name.split(' ') : name;
}

export async function renderPerks(root, params) {
    const data = await fetchJson('/api/perks', params);
    const perks = data.perks || [];

    if (!perks.length) {
        root.innerHTML = `<h1>Perk Usage</h1><p class="text-muted">No perk data available.</p>`;
        return;
    }

    const damageFmt = n => Math.round(n).toLocaleString();

    root.innerHTML = `
        <h1>Perk Usage</h1>
        <div class="row mb-4">
            <div class="col-md-4">
                <div class="card h-100"><div class="card-body">
                    <h5 class="card-title">Waves Played</h5>
                    <canvas id="usageChart" height="300"></canvas>
                </div></div>
            </div>
            <div class="col-md-8">
                <div class="card h-100"><div class="card-body">
                    <h5 class="card-title">Averages</h5>
                    <div class="table-responsive">
                        <table class="table table-striped table-sortable mb-0" id="perksTable">
                            <thead><tr>
                                <th data-type="string">Perk</th>
                                <th data-type="number">Players</th>
                                <th data-type="number">Waves</th>
                                <th data-type="number">Kills</th>
                                <th data-type="number">Kills/Wave</th>
                                <th data-type="number">Damage/Wave</th>
                                <th data-type="number">Heals/Wave</th>
                                <th data-type="number">Accuracy</th>
                            </tr></thead>
                            <tbody>
                                ${perks.map(p => `
                                    <tr>
                                        <td><strong>${escapeHtml(p.perk)}</strong></td>
                                        <td>${p.unique_players}</td>
                                        <td>${fmt(p.waves)}</td>
                                        <td>${fmt(p.kills)}</td>
                                        <td>${p.kills_per_wave}</td>
                                        <td>${damageFmt(p.damage_per_wave)}</td>
                                        <td>${p.heals_per_wave}</td>
                                        <td>${p.accuracy}%</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div></div>
            </div>
        </div>
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="card h-100"><div class="card-body">
                    <h5 class="card-title">Kill Distribution</h5>
                    <canvas id="killChart" height="300"></canvas>
                </div></div>
            </div>
            <div class="col-md-6">
                <div class="card h-100"><div class="card-body">
                    <h5 class="card-title">Damage Output</h5>
                    <canvas id="damageChart" height="300"></canvas>
                </div></div>
            </div>
        </div>
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="card"><div class="card-body">
                    <h5 class="card-title">Fleshpound Kills</h5>
                    <canvas id="fpKillChart" height="300"></canvas>
                </div></div>
            </div>
            <div class="col-md-6">
                <div class="card"><div class="card-body">
                    <h5 class="card-title">Scrake Kills</h5>
                    <canvas id="scKillChart" height="300"></canvas>
                </div></div>
            </div>
        </div>
    `;

    sortableTable(document.getElementById('perksTable'));

    const perkDataMap = {};
    perks.forEach(p => { perkDataMap[p.perk] = p; });

    const pieLabels = ALL_PERKS.map(p => p.name);
    const pieData = ALL_PERKS.map(p => (perkDataMap[p.name] || {}).waves || 0);
    const pieColors = ALL_PERKS.map(p => p.color);

    new Chart(document.getElementById('usageChart'), {
        type: 'doughnut',
        data: {
            labels: pieLabels,
            datasets: [{
                data: pieData,
                backgroundColor: pieColors,
                borderWidth: 4,
                borderColor: '#161b22'
            }]
        },
        options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
    });

    new Chart(document.getElementById('killChart'), {
        type: 'bar',
        data: {
            labels: perks.map(p => wrapLabel(p.perk)),
            datasets: [
                { label: 'Other', data: perks.map(p => p.kills_other), backgroundColor: '#484f58' },
                { label: 'Scrake', data: perks.map(p => p.kills_sc), backgroundColor: '#9e6a03' },
                { label: 'Fleshpound', data: perks.map(p => p.kills_fp), backgroundColor: '#b62324' },
            ]
        },
        options: {
            responsive: true,
            scales: { x: { stacked: true }, y: { stacked: true } },
            plugins: { legend: { position: 'bottom', reverse: true } }
        }
    });

    const fpSorted = [...perks].sort((a, b) => b.kills_fp - a.kills_fp).filter(p => p.kills_fp > 0);
    new Chart(document.getElementById('fpKillChart'), {
        type: 'bar',
        data: {
            labels: fpSorted.map(p => p.perk),
            datasets: [{
                label: 'FP Kills',
                data: fpSorted.map(p => p.kills_fp),
                backgroundColor: fpSorted.map(p => perkColor(p.perk))
            }]
        },
        options: { responsive: true, plugins: { legend: { display: false } } }
    });

    const scSorted = [...perks].sort((a, b) => b.kills_sc - a.kills_sc).filter(p => p.kills_sc > 0);
    new Chart(document.getElementById('scKillChart'), {
        type: 'bar',
        data: {
            labels: scSorted.map(p => p.perk),
            datasets: [{
                label: 'SC Kills',
                data: scSorted.map(p => p.kills_sc),
                backgroundColor: scSorted.map(p => perkColor(p.perk))
            }]
        },
        options: { responsive: true, plugins: { legend: { display: false } } }
    });

    new Chart(document.getElementById('damageChart'), {
        type: 'bar',
        data: {
            labels: perks.map(p => wrapLabel(p.perk)),
            datasets: [
                { label: 'Other', data: perks.map(p => p.damage - p.damage_fp - p.damage_sc), backgroundColor: '#484f58' },
                { label: 'Scrake', data: perks.map(p => p.damage_sc), backgroundColor: '#9e6a03' },
                { label: 'Fleshpound', data: perks.map(p => p.damage_fp), backgroundColor: '#b62324' },
            ]
        },
        options: {
            responsive: true,
            scales: { x: { stacked: true }, y: { stacked: true } },
            plugins: { legend: { position: 'bottom', reverse: true } }
        }
    });
}
