import { useState } from 'react'
import RCAForm from './RCAForm.jsx'

const transitions = {
  OPEN: ['INVESTIGATING'],
  INVESTIGATING: ['RESOLVED'],
  RESOLVED: ['CLOSED'],
  CLOSED: [],
}

export default function IncidentDetail({ incident, signals, request, onChanged }) {
  const [busyStatus, setBusyStatus] = useState('')
  const [message, setMessage] = useState('')

  if (!incident) {
    return (
      <section className="panel detail-panel">
        <div className="empty-detail">Select an incident to inspect raw signals and manage RCA.</div>
      </section>
    )
  }

  const changeStatus = async (status) => {
    setBusyStatus(status)
    setMessage('')
    try {
      await request(`/api/incidents/${incident.id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      })
      setMessage(`Moved to ${status}`)
      await onChanged()
    } catch (err) {
      setMessage(err.message)
    } finally {
      setBusyStatus('')
    }
  }

  return (
    <section className="detail-grid">
      <div className="panel detail-panel">
        <div className="panel-header">
          <h2>{incident.component_id}</h2>
          <span className={`severity ${incident.severity}`}>{incident.severity}</span>
        </div>

        <div className="facts">
          <div><span>Status</span><strong>{incident.status}</strong></div>
          <div><span>Type</span><strong>{incident.component_type}</strong></div>
          <div><span>Error</span><strong>{incident.error_code}</strong></div>
          <div><span>MTTR</span><strong>{incident.mttr_minutes ? `${incident.mttr_minutes.toFixed(2)} min` : 'n/a'}</strong></div>
        </div>

        <p className="incident-message">{incident.message}</p>

        <div className="actions">
          {(transitions[incident.status] || []).map((status) => (
            <button key={status} disabled={busyStatus === status} onClick={() => changeStatus(status)}>
              {busyStatus === status ? 'Working' : `Move to ${status}`}
            </button>
          ))}
        </div>
        {message && <div className="inline-message">{message}</div>}

        <div className="signals">
          <h3>Linked Raw Signals</h3>
          <div className="signal-list">
            {signals.map((signal) => (
              <article key={signal._id} className="signal-row">
                <div>
                  <strong>{signal.error_code}</strong>
                  <span>{new Date(signal.timestamp).toLocaleString()}</span>
                </div>
                <p>{signal.message}</p>
              </article>
            ))}
            {signals.length === 0 && <div className="empty">No linked signals found.</div>}
          </div>
        </div>
      </div>

      <RCAForm incident={incident} request={request} onSaved={onChanged} />
    </section>
  )
}

