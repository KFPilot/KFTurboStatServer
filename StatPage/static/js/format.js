export function fmt(n) {
    if (n === null || n === undefined) return '0';
    return Number(n).toLocaleString();
}

export function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
}

const STATUS_MAP = {
    'Win': ['success', 'Win'],
    'Lose': ['danger', 'Loss'],
    'Abort': ['secondary', 'Abort'],
    'Ended': ['secondary', 'Ended'],
    'InProgress': ['warning', 'In Progress'],
    'Complete': ['success', 'Complete'],
};

export function statusBadge(status, { fs } = {}) {
    const [cls, label] = STATUS_MAP[status] || ['secondary', status || ''];
    const extra = fs ? ` fs-${fs}` : '';
    return `<span class="badge bg-${cls}${extra}">${escapeHtml(label)}</span>`;
}

export function sortableTable(table) {
    const ths = table.querySelectorAll('thead th');
    ths.forEach((th, idx) => {
        if (!th.dataset.type) return;
        th.style.cursor = 'pointer';
        th.addEventListener('click', e => {
            e.stopPropagation();
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const type = th.dataset.type;
            const asc = !th.classList.contains('sorted-asc');
            ths.forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));
            th.classList.add(asc ? 'sorted-asc' : 'sorted-desc');
            rows.sort((a, b) => {
                let va = a.children[idx].textContent.trim();
                let vb = b.children[idx].textContent.trim();
                if (type === 'number') {
                    va = parseFloat(va.replace(/[,%]/g, '')) || 0;
                    vb = parseFloat(vb.replace(/[,%]/g, '')) || 0;
                    return asc ? va - vb : vb - va;
                }
                return asc ? va.localeCompare(vb) : vb.localeCompare(va);
            });
            rows.forEach(r => tbody.appendChild(r));
        });
    });
}
