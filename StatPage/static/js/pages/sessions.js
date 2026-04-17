import { fetchJson } from '../main.js';
import { gametypeName, difficultyName } from '../filters.js';
import { escapeHtml, statusBadge, sortableTable } from '../format.js';

export async function renderSessions(root, params) {
    const data = await fetchJson('/api/sessions', params);
    const sessions = data.sessions || [];

    if (!sessions.length) {
        root.innerHTML = `
            <h1>Sessions</h1>
            <p class="text-muted">No sessions match the current filter.</p>
        `;
        return;
    }

    root.innerHTML = `
        <h1>Sessions</h1>
        <p class="text-muted">${sessions.length} session${sessions.length === 1 ? '' : 's'}. Click a row for details.</p>
        <div class="table-responsive">
            <table class="table table-striped table-sortable table-hover" id="sessionsTable">
                <thead>
                    <tr>
                        <th data-col="elapsed" data-type="string">When</th>
                        <th data-col="map" data-type="string">Map</th>
                        <th data-col="gametype" data-type="string">Mode</th>
                        <th data-col="difficulty" data-type="number">Difficulty</th>
                        <th data-col="waves" data-type="number">Waves</th>
                        <th data-col="status" data-type="string">Result</th>
                        <th data-col="version" data-type="string">Version</th>
                    </tr>
                </thead>
                <tbody>
                    ${sessions.map(s => `
                        <tr data-sessionid="${escapeHtml(s.sessionid)}" style="cursor: pointer;">
                            <td title="${escapeHtml(s.time)}">${escapeHtml(s.elapsed)}</td>
                            <td>${escapeHtml(s.map)}</td>
                            <td>${escapeHtml(gametypeName(s.gametype))}</td>
                            <td>${escapeHtml(difficultyName(s.difficulty))}</td>
                            <td>${s.waves}</td>
                            <td>${statusBadge(s.status)}</td>
                            <td class="text-muted">${escapeHtml(s.version)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;

    const table = document.getElementById('sessionsTable');
    sortableTable(table);
    table.querySelector('tbody').addEventListener('click', e => {
        const tr = e.target.closest('tr[data-sessionid]');
        if (!tr) return;
        location.hash = '#/session/' + encodeURIComponent(tr.dataset.sessionid);
    });
}
