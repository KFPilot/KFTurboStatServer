import { initFilters } from './filters.js';
import { escapeHtml } from './format.js';
import { renderOverview } from './pages/overview.js';
import { renderLeaderboards } from './pages/leaderboards.js';
import { renderPlayer } from './pages/player.js';
import { renderSessions } from './pages/sessions.js';
import { renderSession } from './pages/session.js';
import { renderCards } from './pages/cards.js';
import { renderPerks } from './pages/perks.js';

const root = document.getElementById('root');

const routes = [
    { pattern: /^\/?$/, render: renderOverview, title: 'Overview' },
    { pattern: /^\/leaderboards$/, render: renderLeaderboards, title: 'Leaderboards' },
    { pattern: /^\/player\/([^/]+)$/, render: renderPlayer, title: 'Player' },
    { pattern: /^\/sessions$/, render: renderSessions, title: 'Sessions' },
    { pattern: /^\/session\/([^/]+)$/, render: renderSession, title: 'Session' },
    { pattern: /^\/cards$/, render: renderCards, title: 'Cards' },
    { pattern: /^\/perks$/, render: renderPerks, title: 'Perks' },
];

function parseHash() {
    const h = location.hash.replace(/^#/, '') || '/';
    const [path, query = ''] = h.split('?');
    return { path, params: new URLSearchParams(query) };
}

async function dispatch() {
    const { path, params } = parseHash();
    root.innerHTML = '<p class="text-muted">Loading…</p>';
    for (const r of routes) {
        const m = path.match(r.pattern);
        if (m) {
            document.title = `Turbo Stats — ${r.title}`;
            try {
                await r.render(root, params, ...m.slice(1));
            } catch (err) {
                console.error(err);
                root.innerHTML = `<div class="alert alert-danger">Error: ${escapeHtml(err.message)}</div>`;
            }
            return;
        }
    }
    document.title = 'Turbo Stats — Not Found';
    root.innerHTML = '<h1>Not Found</h1>';
}

export async function fetchJson(path, params) {
    const qs = params && params.toString();
    const url = qs ? `${path}?${qs}` : path;
    const r = await fetch(url);
    if (r.status === 404) throw new Error('Not found');
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
}

window.addEventListener('hashchange', dispatch);
window.addEventListener('DOMContentLoaded', async () => {
    try {
        await initFilters();
    } catch (err) {
        console.error(err);
        root.innerHTML = `<div class="alert alert-danger">Failed to load filter metadata: ${escapeHtml(err.message)}</div>`;
        return;
    }
    if (!location.hash) location.hash = '#/';
    else dispatch();
});
