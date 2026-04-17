import { fetchJson } from '../main.js';
import { getFilterQS } from '../filters.js';
import { fmt, escapeHtml, sortableTable } from '../format.js';

export async function renderLeaderboards(root, params) {
    const data = await fetchJson('/api/leaderboards', params);
    const qs = getFilterQS();
    const playerHref = (p) => `#/player/${encodeURIComponent(p.playertableid)}${qs ? '?' + qs : ''}`;

    root.innerHTML = `
        <h1>Player Leaderboards</h1>
        <div class="table-responsive">
            <table class="table table-striped table-sortable" id="leaderboard">
                <thead>
                    <tr>
                        <th data-col="playername" data-type="string">Player</th>
                        <th data-col="kills" data-type="number">Kills</th>
                        <th data-col="damage" data-type="number">Damage</th>
                        <th data-col="accuracy" data-type="number">Accuracy</th>
                        <th data-col="headshot_pct" data-type="number">Headshot %</th>
                        <th data-col="heals" data-type="number">Heals</th>
                        <th data-col="deaths" data-type="number">Deaths</th>
                        <th data-col="wins" data-type="number">Wins</th>
                        <th data-col="losses" data-type="number">Losses</th>
                        <th data-col="win_rate" data-type="number">Win Rate</th>
                        <th data-col="waves_played" data-type="number">Waves</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.players.map(p => `
                        <tr>
                            <td><a href="${playerHref(p)}">${escapeHtml(p.playername)}</a></td>
                            <td>${fmt(p.kills)}</td>
                            <td>${fmt(p.damage)}</td>
                            <td>${p.accuracy}%</td>
                            <td>${p.headshot_pct}%</td>
                            <td>${fmt(p.heals)}</td>
                            <td>${fmt(p.deaths)}</td>
                            <td>${p.wins}</td>
                            <td>${p.losses}</td>
                            <td>${p.win_rate}%</td>
                            <td>${p.waves_played}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;

    sortableTable(document.getElementById('leaderboard'));
}
