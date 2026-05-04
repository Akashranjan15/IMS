import { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, RefreshCw, ShieldCheck } from 'lucide-react'
import IncidentDetail from './components/IncidentDetail.jsx'
import LiveFeed from './components/LiveFeed.jsx'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const DEFAULT_TOKEN = import.meta.env.VITE_API_TOKEN || ''

export default function App() {
  // will probably need react-router properly if this grows
  const [incidents, setIncidents] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [selectedIncident, setSelectedIncident] = useState(null)
  const [signals, setSignals] = useState([])
  const [token, setToken] = useState(() => localStorage.getItem('ims_token') || DEFAULT_TOKEN)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const headers = useMemo(() => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
    'X-Request-ID': crypto.randomUUID(),
  }), [token])

  const request = useCallback(async (path, options = {}) => {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: { ...headers, ...(options.headers || {}) },
    })
    if (!response.ok) {
      const detail = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(detail.detail || response.statusText)
    }
    return response.json()
  }, [headers])

  const loadIncidents = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      setError('')
      const data = await request('/api/incidents')
      setIncidents(data)
      if (!selectedId && data.length > 0) setSelectedId(data[0].id)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [request, selectedId, token])

  const loadIncidentDetail = useCallback(async (id) => {
    if (!id || !token) return
    try {
      setError('')
      const data = await request(`/api/incidents/${id}`)
      setSelectedIncident(data.incident)
      setSignals(data.signals)
    } catch (err) {
      setError(err.message)
    }
  }, [request, token])

  useEffect(() => {
    loadIncidents()
    const handle = setInterval(loadIncidents, 10000)
    return () => clearInterval(handle)
  }, [loadIncidents])

  useEffect(() => {
    loadIncidentDetail(selectedId)
  }, [loadIncidentDetail, selectedId])

  const saveToken = () => {
    localStorage.setItem('ims_token', token)
    loadIncidents()
  }

  const refreshAll = async () => {
    await loadIncidents()
    await loadIncidentDetail(selectedId)
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <Activity size={26} />
          <div>
            <h1>Incident Management System</h1>
            <span>Live operations console</span>
          </div>
        </div>
        <div className="auth-panel">
          <ShieldCheck size={18} />
          <input
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="JWT token"
            aria-label="JWT token"
          />
          <button onClick={saveToken}>Use Token</button>
          <button className="icon-button" onClick={refreshAll} aria-label="Refresh">
            <RefreshCw size={17} />
          </button>
        </div>
      </header>

      {error && <div className="banner error">{error}</div>}

      <section className="workspace">
        <LiveFeed incidents={incidents} selectedId={selectedId} loading={loading} onSelect={setSelectedId} />
        <IncidentDetail
          incident={selectedIncident}
          signals={signals}
          request={request}
          onChanged={refreshAll}
        />
      </section>
    </main>
  )
}

