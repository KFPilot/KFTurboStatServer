import { escapeHtml } from './format.js';

let allGametypes = [];
let allDifficulties = [];
let gametypeNames = {};
let difficultyNames = {};
let perkNames = {};

export async function initFilters() {
    const r = await fetch('/api/filters');
    if (!r.ok) throw new Error('Failed to load filter metadata');
    const data = await r.json();
    allGametypes = data.gametypes || [];
    allDifficulties = data.difficulties || [];
    gametypeNames = data.gametype_names || {};
    difficultyNames = data.difficulty_names || {};
    perkNames = data.perk_names || {};
    renderNavbar();
    window.addEventListener('hashchange', updateLinkStates);
}

function renderNavbar() {
    const navLinks = document.getElementById('navLinks');
    const links = [
        { path: '/', label: 'Overview' },
        { path: '/leaderboards', label: 'Leaderboards' },
        { path: '/sessions', label: 'Sessions' },
        { path: '/perks', label: 'Perks' },
        { path: '/cards', label: 'Cards', noFilter: true },
    ];
    navLinks.innerHTML = links.map(l =>
        `<li class="nav-item"><a class="nav-link" data-path="${l.path}" data-nofilter="${l.noFilter ? '1' : ''}" href="#${l.path}">${escapeHtml(l.label)}</a></li>`
    ).join('');

    if (allGametypes.length) {
        const gt = document.getElementById('gametypeFilter');
        gt.hidden = false;
        gt.querySelector('.btn-group').innerHTML = allGametypes.map(g =>
            `<button type="button" class="btn btn-sm btn-outline-secondary" data-gametype="${escapeHtml(g)}">${escapeHtml(gametypeName(g))}</button>`
        ).join('');
    }
    if (allDifficulties.length) {
        const df = document.getElementById('difficultyFilter');
        df.hidden = false;
        df.querySelector('.btn-group').innerHTML = allDifficulties.map(d =>
            `<button type="button" class="btn btn-sm btn-outline-secondary" data-difficulty="${d}">${escapeHtml(difficultyName(d))}</button>`
        ).join('');
    }

    bindFilter('gametypeFilter', 'gametype');
    bindFilter('difficultyFilter', 'difficulty');
    updateLinkStates();
}

function bindFilter(id, attr) {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('click', e => {
        const btn = e.target.closest(`button[data-${attr}]`);
        if (!btn) return;
        btn.classList.toggle('active');
        applyFilter();
    });
}

function applyFilter() {
    const params = new URLSearchParams();
    const gtActive = document.querySelectorAll('#gametypeFilter button.active');
    if (gtActive.length) gtActive.forEach(b => params.append('gametypes', b.dataset.gametype));
    else params.append('gametypes', '');
    const dfActive = document.querySelectorAll('#difficultyFilter button.active');
    if (dfActive.length) dfActive.forEach(b => params.append('difficulties', b.dataset.difficulty));
    else params.append('difficulties', '');

    const { path } = parseCurrentHash();
    location.hash = '#' + path + '?' + params.toString();
}

function parseCurrentHash() {
    const h = location.hash.replace(/^#/, '') || '/';
    const [path, query = ''] = h.split('?');
    return { path, query };
}

function getSelectedGametypes() {
    const { query } = parseCurrentHash();
    const p = new URLSearchParams(query);
    if (!p.has('gametypes')) return [...allGametypes];
    return p.getAll('gametypes').filter(v => v && allGametypes.includes(v));
}

function getSelectedDifficulties() {
    const { query } = parseCurrentHash();
    const p = new URLSearchParams(query);
    if (!p.has('difficulties')) return [...allDifficulties];
    return p.getAll('difficulties').map(Number).filter(v => allDifficulties.includes(v));
}

export function getFilterQS() {
    const { query } = parseCurrentHash();
    return query;
}

function updateLinkStates() {
    const selGT = getSelectedGametypes();
    document.querySelectorAll('#gametypeFilter button[data-gametype]').forEach(b => {
        b.classList.toggle('active', selGT.includes(b.dataset.gametype));
    });
    const selDF = getSelectedDifficulties();
    document.querySelectorAll('#difficultyFilter button[data-difficulty]').forEach(b => {
        b.classList.toggle('active', selDF.includes(Number(b.dataset.difficulty)));
    });
    const qs = getFilterQS();
    document.querySelectorAll('#navLinks a[data-path]').forEach(a => {
        const noFilter = a.dataset.nofilter === '1';
        a.href = '#' + a.dataset.path + (!noFilter && qs ? '?' + qs : '');
    });
    const { path } = parseCurrentHash();
    const gt = document.getElementById('gametypeFilter');
    if (gt) {
        if (path === '/cards') gt.style.setProperty('display', 'none', 'important');
        else gt.style.removeProperty('display');
    }
}

export function gametypeName(code) {
    if (!code) return 'Unknown';
    return gametypeNames[code] || code;
}

export function difficultyName(v) {
    if (v === null || v === undefined || v === '') return 'Unknown';
    return difficultyNames[String(v)] || String(v);
}

export function perkName(code) {
    if (!code) return 'Unknown';
    return perkNames[code] || code;
}
