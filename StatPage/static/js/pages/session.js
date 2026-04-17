import { fetchJson } from '../main.js';
import { gametypeName, difficultyName } from '../filters.js';
import { fmt, escapeHtml, statusBadge } from '../format.js';

export async function renderSession(root, params, sessionid) {
    const data = await fetchJson(`/api/session/${encodeURIComponent(sessionid)}`);
    const s = data.session;
    const totalKills = (data.participants || []).reduce((a, p) => a + (p.kills || 0), 0);

    const header = `
        <h1>${escapeHtml(s.map)}</h1>
        <p class="text-muted">
            <span title="${escapeHtml(s.time)}">${escapeHtml(s.elapsed)}</span>
            &middot; ${escapeHtml(gametypeName(s.gametype))}
            &middot; ${escapeHtml(difficultyName(s.difficulty))}
            &middot; v${escapeHtml(s.version)}
        </p>
        <div class="row g-3 mb-4">
            ${statCard('Result', statusBadge(s.status, { fs: 5 }), true)}
            ${statCard('Waves Played', (data.waves || []).length)}
            ${statCard('Participants', (data.participants || []).length)}
            ${statCard('Total Kills', fmt(totalKills))}
        </div>
    `;

    const participants = (data.participants && data.participants.length) ? `
        <h3>Participants</h3>
        <div class="table-responsive mb-4">
            <table class="table table-striped">
                <thead><tr>
                    <th>Player</th><th>Perks</th><th>Waves</th><th>Kills</th>
                    <th>FP Kills</th><th>SC Kills</th><th>Damage</th><th>Heals</th>
                    <th>Damage Taken</th><th>Deaths</th><th>Accuracy</th>
                </tr></thead>
                <tbody>
                    ${data.participants.map(p => `
                        <tr>
                            <td><a href="#/player/${encodeURIComponent(p.playertableid)}">${escapeHtml(p.playername)}</a></td>
                            <td>${escapeHtml(p.perks)}</td>
                            <td>${p.waves_played}</td>
                            <td>${fmt(p.kills)}</td>
                            <td>${fmt(p.kills_fp)}</td>
                            <td>${fmt(p.kills_sc)}</td>
                            <td>${fmt(p.damage)}</td>
                            <td>${fmt(p.heals)}</td>
                            <td>${fmt(p.damagetaken)}</td>
                            <td>${p.deaths}</td>
                            <td>${p.accuracy}%</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    ` : '';

    const waves = (data.waves && data.waves.length) ? `
        <h3>Wave Progression</h3>
        <div class="table-responsive">
            <table class="table table-striped">
                <thead><tr><th>Wave</th><th>Status</th><th>Players</th></tr></thead>
                <tbody>
                    ${data.waves.map(w => `
                        <tr>
                            <td>${w.wave}</td>
                            <td>${statusBadge(w.status)}</td>
                            <td>${w.player_count}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    ` : '';

    root.innerHTML = header + participants + waves;
}

function statCard(label, value, isHtml = false) {
    return `
        <div class="col-md-3">
            <div class="card text-center"><div class="card-body">
                <div class="text-muted small">${escapeHtml(label)}</div>
                <div class="stat-highlight">${isHtml ? value : escapeHtml(value)}</div>
            </div></div>
        </div>
    `;
}
