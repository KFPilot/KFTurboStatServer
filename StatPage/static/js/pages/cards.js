import { fetchJson } from '../main.js';
import { escapeHtml, sortableTable } from '../format.js';

export async function renderCards(root) {
    const data = await fetchJson('/api/cards');
    const cards = data.cards || [];
    const cardNames = data.card_names || {};
    const cardLabel = id => cardNames[id] || id;

    if (!cards.length) {
        root.innerHTML = `<h1>Card Analytics</h1><p class="text-muted">No card data available.</p>`;
        return;
    }

    root.innerHTML = `
        <h1>Card Analytics</h1>
        <div class="d-flex align-items-center gap-2 mb-3">
            <span class="text-muted">Category:</span>
            <div class="btn-group" id="cardCategoryFilter">
                <button type="button" class="btn btn-sm btn-outline-secondary active" data-category="all">All</button>
                <button type="button" class="btn btn-sm btn-outline-secondary" data-category="SUPER_">Super</button>
                <button type="button" class="btn btn-sm btn-outline-secondary" data-category="GOOD_">Good</button>
                <button type="button" class="btn btn-sm btn-outline-secondary" data-category="PROCON_">Pro/Con</button>
                <button type="button" class="btn btn-sm btn-outline-secondary" data-category="EVIL_">Evil</button>
            </div>
        </div>
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="card"><div class="card-body">
                    <h5 class="card-title">Most Picked Cards</h5>
                    <canvas id="pickChart" height="300"></canvas>
                </div></div>
            </div>
            <div class="col-md-6">
                <div class="card"><div class="card-body">
                    <h5 class="card-title">Least Picked Cards</h5>
                    <canvas id="leastPickedChart" height="300"></canvas>
                </div></div>
            </div>
        </div>
        <div class="table-responsive">
            <table class="table table-striped table-sortable" id="cardTable">
                <thead><tr>
                    <th data-col="cardid" data-type="string">Card</th>
                    <th data-col="shown" data-type="number">Shown</th>
                    <th data-col="selected" data-type="number">Picked</th>
                    <th data-col="pick_rate" data-type="number">Pick Rate</th>
                    <th data-col="wins" data-type="number">Wins</th>
                    <th data-col="losses" data-type="number">Losses</th>
                    <th data-col="win_rate" data-type="number">Win Rate</th>
                </tr></thead>
                <tbody></tbody>
            </table>
        </div>
    `;

    let pickChart = null;
    let leastPickedChart = null;

    function sizeCanvas(id, barCount) {
        const canvas = document.getElementById(id);
        const height = Math.max(180, barCount * 22 + 80);
        canvas.parentElement.style.height = height + 'px';
        canvas.style.height = height + 'px';
    }

    function filterCards(category) {
        return category === 'all' ? cards : cards.filter(c => c.cardid.startsWith(category));
    }

    function buildCharts(category) {
        const filtered = filterCards(category);
        const yAxisOpts = { ticks: { autoSkip: false, font: { size: 11 } } };

        const mostPicked = [...filtered].sort((a, b) => b.selected - a.selected).slice(0, 40);
        sizeCanvas('pickChart', mostPicked.length);
        if (pickChart) pickChart.destroy();
        pickChart = new Chart(document.getElementById('pickChart'), {
            type: 'bar',
            data: {
                labels: mostPicked.map(c => cardLabel(c.cardid)),
                datasets: [{
                    label: 'Times Picked',
                    data: mostPicked.map(c => c.selected),
                    backgroundColor: '#1f6feb'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                layout: { padding: { bottom: 10 } },
                plugins: { legend: { display: false } },
                scales: { x: { ticks: { stepSize: 1, precision: 0 } }, y: yAxisOpts }
            }
        });

        const leastPicked = [...filtered]
            .filter(c => c.shown >= 2)
            .map(c => ({ ...c, skip_rate: (c.shown - c.selected) / c.shown * 100 }))
            .sort((a, b) => b.skip_rate - a.skip_rate)
            .slice(0, 40);
        sizeCanvas('leastPickedChart', leastPicked.length);
        if (leastPickedChart) leastPickedChart.destroy();
        leastPickedChart = new Chart(document.getElementById('leastPickedChart'), {
            type: 'bar',
            data: {
                labels: leastPicked.map(c => cardLabel(c.cardid)),
                datasets: [{
                    label: 'Skip Rate %',
                    data: leastPicked.map(c => c.skip_rate.toFixed(1)),
                    backgroundColor: '#9e2a2a'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                layout: { padding: { bottom: 10 } },
                plugins: { legend: { display: false } },
                scales: { y: yAxisOpts }
            }
        });
    }

    const tbody = document.querySelector('#cardTable tbody');
    function buildTable(category) {
        const filtered = filterCards(category);
        tbody.innerHTML = filtered.map(c => `
            <tr>
                <td title="${escapeHtml(c.cardid)}">${escapeHtml(cardLabel(c.cardid))}</td>
                <td>${c.shown}</td>
                <td>${c.selected}</td>
                <td>${c.pick_rate}%</td>
                <td>${c.wins}</td>
                <td>${c.losses}</td>
                <td>${c.win_rate}%</td>
            </tr>
        `).join('');
    }

    buildCharts('all');
    buildTable('all');

    document.getElementById('cardCategoryFilter').addEventListener('click', function(e) {
        const btn = e.target.closest('button[data-category]');
        if (!btn) return;
        this.querySelectorAll('button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        buildCharts(btn.dataset.category);
        buildTable(btn.dataset.category);
    });

    sortableTable(document.getElementById('cardTable'));
}
