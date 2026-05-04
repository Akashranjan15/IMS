import { useEffect, useState } from 'react'

const categories = ['INFRA', 'CODE', 'NETWORK', 'HUMAN_ERROR', 'UNKNOWN']

function toDatetimeLocal(value) {
  if (!value) return ''
  const date = new Date(value)
  const offsetMs = date.getTimezoneOffset() * 60000
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16)
}

export default function RCAForm({ incident, request, onSaved }) {
  // basic validation, not perfect but good enough
  const [form, setForm] = useState({
    incident_start: toDatetimeLocal(incident.start_time),
    incident_end: toDatetimeLocal(incident.end_time || new Date()),
    root_cause_category: incident.rca?.root_cause_category || 'UNKNOWN',
    fix_applied: incident.rca?.fix_applied || '',
    prevention_steps: incident.rca?.prevention_steps || '',
  })
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setForm({
      incident_start: toDatetimeLocal(incident.start_time),
      incident_end: toDatetimeLocal(incident.end_time || new Date()),
      root_cause_category: incident.rca?.root_cause_category || 'UNKNOWN',
      fix_applied: incident.rca?.fix_applied || '',
      prevention_steps: incident.rca?.prevention_steps || '',
    })
    setMessage('')
  }, [incident])

  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }))

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setMessage('')
    try {
      await request(`/api/incidents/${incident.id}/rca`, {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          incident_start: new Date(form.incident_start).toISOString(),
          incident_end: new Date(form.incident_end).toISOString(),
        }),
      })
      setMessage('RCA saved')
      await onSaved()
    } catch (err) {
      setMessage(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="panel rca-form" onSubmit={submit}>
      <div className="panel-header">
        <h2>RCA</h2>
        <span>{incident.rca ? 'Submitted' : 'Required to close'}</span>
      </div>

      <label>
        Incident start
        <input type="datetime-local" value={form.incident_start} onChange={(event) => update('incident_start', event.target.value)} required />
      </label>
      <label>
        Incident end
        <input type="datetime-local" value={form.incident_end} onChange={(event) => update('incident_end', event.target.value)} required />
      </label>
      <label>
        Root cause category
        <select value={form.root_cause_category} onChange={(event) => update('root_cause_category', event.target.value)}>
          {categories.map((category) => <option key={category} value={category}>{category}</option>)}
        </select>
      </label>
      <label>
        Fix applied
        <textarea minLength="20" value={form.fix_applied} onChange={(event) => update('fix_applied', event.target.value)} required />
      </label>
      <label>
        Prevention steps
        <textarea minLength="20" value={form.prevention_steps} onChange={(event) => update('prevention_steps', event.target.value)} required />
      </label>
      <button type="submit" disabled={saving}>{saving ? 'Saving' : 'Save RCA'}</button>
      {message && <div className="inline-message">{message}</div>}
    </form>
  )
}
