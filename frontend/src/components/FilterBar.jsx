const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];

export default function FilterBar({ filters, setFilters, members, role, onExport, onReset, busyExport }) {
  const set = (k) => (e) => setFilters({ ...filters, [k]: e.target.value });
  const setMulti = (k) => (e) => setFilters({ ...filters, [k]: Array.from(e.target.selectedOptions).map((o) => o.value) });
  return (
    <div className="filter-bar card">
      <div className="filter-grid">
        <div className="field">
          <label>Month</label>
          <select className="select" value={filters.month || ''} onChange={set('month')}>
            <option value="">All</option>
            {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Year</label>
          <input className="input" type="number" min="2000" max="2100" placeholder="e.g. 2026" value={filters.year || ''} onChange={set('year')} />
        </div>
        <div className="field">
          <label>Specific date</label>
          <input className="input" type="date" value={filters.date || ''} onChange={set('date')} />
        </div>
        <div className="field">
          <label>From</label>
          <input className="input" type="date" value={filters.from || ''} onChange={set('from')} />
        </div>
        <div className="field">
          <label>To</label>
          <input className="input" type="date" value={filters.to || ''} onChange={set('to')} />
        </div>
        <div className="field">
          <label>Project</label>
          <input className="input" placeholder="Contains…" value={filters.project || ''} onChange={set('project')} />
        </div>
        {role === 'leader' && (
          <div className="field" style={{ gridColumn: 'span 2' }}>
            <label>Members (leave empty for all)</label>
            <select className="select" multiple value={filters.user_ids || []} onChange={setMulti('user_ids')} style={{ minHeight: 96 }}>
              {members.map((m) => (
                <option key={m.id} value={m.id}>{m.username} — {m.role}</option>
              ))}
            </select>
          </div>
        )}
      </div>
      <div className="filter-actions">
        <button className="btn btn-ghost" onClick={onReset}>Reset</button>
        <button className="btn btn-primary" onClick={onExport} disabled={busyExport}>
          {busyExport ? <span className="spinner" /> : '📤 Export Excel'}
        </button>
      </div>
    </div>
  );
}
