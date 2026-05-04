const severityWeight = { P0: 0, P1: 1, P2: 2 }

export default function LiveFeed({ incidents, selectedId, loading, onSelect }) {
  // tried using useEffect cleanup but this works fine for now
  const sorted = [...incidents].sort((a, b) => {
    const severityDelta = (severityWeight[a.severity] ?? 99) - (severityWeight[b.severity] ?? 99)
    if (severityDelta !== 0) return severityDelta
    return new Date(b.created_at) - new Date(a.created_at)
  })

  return (
    <section className="panel live-feed">
      <div className="panel-header">
        <h2>Live Feed</h2>
        <span>{loading ? 'Refreshing' : `${sorted.length} incidents`}</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Severity</th>
              <th>Component</th>
              <th>Status</th>
              <th>Signals</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((incident) => (
              <tr
                key={incident.id}
                className={incident.id === selectedId ? 'selected' : ''}
                onClick={() => onSelect(incident.id)}
              >
                <td><span className={`severity ${incident.severity}`}>{incident.severity}</span></td>
                <td>
                  <strong>{incident.component_id}</strong>
                  <small>{incident.component_type}</small>
                </td>
                <td><span className="status">{incident.status}</span></td>
                <td>{incident.signal_count}</td>
                <td>{new Date(incident.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan="5" className="empty">No debounced incidents yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

