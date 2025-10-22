import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || window.__RAG_API_URL__ || ''

export default function App() {
  const [status, setStatus] = useState('unknown')
  const [loadingHealth, setLoadingHealth] = useState(false)

  const [bucket, setBucket] = useState('')
  const [objectName, setObjectName] = useState('')
  const [sending, setSending] = useState(false)
  const [responseJson, setResponseJson] = useState(null)
  const [error, setError] = useState(null)

  const resultRef = useRef(null)

  useEffect(() => {
    if (!API_BASE) {
      setStatus('no-api-configured')
      return
    }
    checkHealth()
  }, [])

  async function checkHealth() {
    if (!API_BASE) return
    setLoadingHealth(true)
    setError(null)
    try {
      const r = await axios.get(`${API_BASE.replace(/\/$/, '')}/health`, { timeout: 5000 })
      setStatus(r.data.status || 'ok')
    } catch (e) {
      setStatus('down')
      setError(e.message)
    } finally {
      setLoadingHealth(false)
    }
  }

  // Build Pub/Sub push style object and send to backend POST /
  // Payload shape expected by backend: { "message": { "data": "<base64>", ... } }
  function makePubSubMessage(bucketName, objectName) {
    const payload = { bucket: bucketName, name: objectName }
    const json = JSON.stringify(payload)
    const b64 = typeof window !== 'undefined' ? btoa(unescape(encodeURIComponent(json))) : Buffer.from(json).toString('base64')
    return { message: { data: b64 } }
  }

  async function sendPubSub(e) {
    e && e.preventDefault()
    setSending(true)
    setResponseJson(null)
    setError(null)
    try {
      if (!API_BASE) throw new Error('API_BASE not configured')
      if (!bucket || !objectName) throw new Error('Bucket and object name required')
      const body = makePubSubMessage(bucket.trim(), objectName.trim())
      const resp = await axios.post(`${API_BASE.replace(/\/$/, '')}/`, body, { timeout: 120000 })
      setResponseJson(resp.data)
      // scroll to result
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth' }), 100)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || String(err))
    } finally {
      setSending(false)
    }
  }

  function clear() {
    setBucket('')
    setObjectName('')
    setResponseJson(null)
    setError(null)
  }

  return (
    <div className="page">
      <header>
        <h1>RAG Pub/Sub Frontend</h1>
        <div className="meta">
          <div>API: <strong>{API_BASE || '(unset)'}</strong></div>
          <div>Health: <strong>{status}</strong> {loadingHealth ? '(checking...)' : ''}</div>
          <div className="controls">
            <button onClick={checkHealth} disabled={loadingHealth || !API_BASE}>Check Health</button>
            <button onClick={clear}>Clear</button>
          </div>
        </div>
      </header>

      <main>
        <section className="panel">
          <h2>Send test Pub/Sub push</h2>
          <p className="muted">Enter a GCS bucket and object name that the backend can access.</p>
          <form onSubmit={sendPubSub} className="form">
            <label>
              Bucket
              <input value={bucket} onChange={e => setBucket(e.target.value)} placeholder="my-bucket" />
            </label>
            <label>
              Object name (path)
              <input value={objectName} onChange={e => setObjectName(e.target.value)} placeholder="docs/mydoc.pdf" />
            </label>
            <div className="actions">
              <button type="submit" disabled={sending || !API_BASE}>{sending ? 'Sending...' : 'Send Pub/Sub'}</button>
            </div>
          </form>
        </section>

        <section className="panel" ref={resultRef}>
          <h2>Result</h2>
          {error && <pre className="error">{error}</pre>}
          {responseJson ? (
            <pre className="result">{JSON.stringify(responseJson, null, 2)}</pre>
          ) : (
            <div className="muted">No result yet. Send a test message to see the backend response.</div>
          )}
        </section>
      </main>

      <footer>
        <small>Note: backend must allow CORS or you should serve frontend/proxy under same origin.</small>
      </footer>

      <style>{`
        :root{ --bg:#0f1720; --card:#071426; --muted:#9aa4b2; --accent:#4f46e5; --danger:#b02a2a; }
        *{box-sizing:border-box}
        body,html,#root{height:100%;margin:0;font-family:Inter,system-ui,Arial;background:linear-gradient(180deg,#061025,#071430);color:#e6eef8}
        .page{max-width:980px;margin:18px auto;padding:18px}
        header{display:flex;flex-direction:row;justify-content:space-between;align-items:center}
        h1{margin:0;font-size:20px}
        .meta{display:flex;gap:16px;align-items:center}
        .controls button{margin-left:8px}
        main{display:flex;flex-direction:column;gap:14px;margin-top:16px}
        .panel{background:var(--card);padding:14px;border-radius:8px}
        .muted{color:var(--muted);font-size:13px}
        .form{display:flex;flex-direction:column;gap:8px}
        .form label{display:flex;flex-direction:column;font-size:14px}
        .form input{padding:8px;border-radius:6px;border:1px solid #123;background:transparent;color:inherit}
        .actions{margin-top:8px}
        button{padding:8px 12px;border-radius:6px;border:0;background:var(--accent);color:white}
        pre{background:#02101a;padding:12px;border-radius:6px;overflow:auto}
        .error{color:var(--danger);background:#2b0b0b}
      `}</style>
    </div>
  )
}
