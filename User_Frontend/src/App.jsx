import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || window.__RAG_API_URL__ || ''

function ChatBubble({who, text}){
  return (
    <div className={`bubble ${who}`}>
      <div className="bubble-text">{text}</div>
    </div>
  )
}

export default function App(){
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState([])
  const [status, setStatus] = useState('unknown')
  const qRef = useRef(null)

  useEffect(()=>{
    const h = localStorage.getItem('chat_history')
    if(h) setHistory(JSON.parse(h))
    checkHealth()
  }, [])

  useEffect(()=>{
    localStorage.setItem('chat_history', JSON.stringify(history))
  }, [history])

  async function checkHealth(){
    if(!API_BASE) return setStatus('no-api')
    try{
      const res = await axios.get(`${API_BASE.replace(/\/$/,'')}/health`, {timeout:5000})
      setStatus(res.data.status || 'unknown')
    }catch(e){
      setStatus('down')
    }
  }

  // --- sendQuestion now uses fetch so we can read streaming responses if present
  async function sendQuestion(e){
    e && e.preventDefault()
    const q = question.trim()
    if(!q) return
    const entry = {id: Date.now(), question: q, answer: '', status: 'pending'}
    setHistory(h => [entry, ...h])
    setQuestion('')
    setLoading(true)

    const url = `${API_BASE.replace(/\/$/,'')}/ask`
    // timeout in ms for the request (adjust as needed)
    const REQ_TIMEOUT = 120000
    const controller = new AbortController()
    const timeoutId = setTimeout(()=> controller.abort(), REQ_TIMEOUT)

    try{
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify({ question: q }),
        signal: controller.signal
      })

      clearTimeout(timeoutId)

      if (!res.ok) {
        // try read JSON error or text
        let detail = await res.text().catch(()=> null)
        try {
          const j = JSON.parse(detail)
          detail = j.detail || j.error || JSON.stringify(j)
        } catch(_) {}
        throw new Error(detail || `HTTP ${res.status}`)
      }

      const contentType = (res.headers.get('content-type') || '').toLowerCase()

      if (contentType.includes('application/json')) {
        // non-streaming: parse whole JSON
        const data = await res.json()
        const answer = typeof data.answer === 'string' ? data.answer : JSON.stringify(data.answer, null, 2)
        setHistory(h => h.map(x => x.id===entry.id ? {...x, answer, status:'done'} : x))
      } else {
        // streaming or plain text: read the response body progressively
        if (!res.body) {
          // fallback: read as text if no body stream available
          const txt = await res.text()
          setHistory(h => h.map(x => x.id===entry.id ? {...x, answer: txt, status:'done'} : x))
        } else {
          const reader = res.body.getReader()
          const decoder = new TextDecoder()
          let done = false
          let full = ''
          // update UI progressively
          while (!done) {
            const { value, done: streamDone } = await reader.read()
            done = streamDone
            if (value) {
              const chunk = decoder.decode(value, { stream: true })
              full += chunk
              // incremental update
              setHistory(h => h.map(x => x.id===entry.id ? {...x, answer: full, status:'pending'} : x))
            }
          }
          // final commit
          setHistory(h => h.map(x => x.id===entry.id ? {...x, answer: full, status:'done'} : x))
        }
      }
    }catch(err){
      clearTimeout(timeoutId)
      const isAbort = err.name === 'AbortError'
      const detail = isAbort ? `Request timed out after ${REQ_TIMEOUT/1000}s` : (err.message || String(err))
      setHistory(h => h.map(x => x.id===entry.id ? {...x, answer: `Error: ${detail}`, status:'error'} : x))
    }finally{
      setLoading(false)
      qRef.current && qRef.current.focus()
    }
  }

  function clearHistory(){
    setHistory([])
    localStorage.removeItem('chat_history')
  }

  return (
    <div className="page">
      <header>
        <h1>Mini RAG Chat</h1>
        <div className="meta">
          <span>API: <strong>{API_BASE || '(unset)'}</strong></span>
          <span>Health: <strong>{status}</strong></span>
          <button onClick={checkHealth}>Check</button>
          <button onClick={clearHistory}>Clear</button>
        </div>
      </header>

      <main>
        <form onSubmit={sendQuestion} className="ask-form">
          <input ref={qRef} placeholder="Ask anything..." value={question} onChange={e=>setQuestion(e.target.value)} />
          <button type="submit" disabled={loading || !API_BASE}>{loading ? '...' : 'Send'}</button>
        </form>

        <div className="chat-list">
          {history.length===0 && <div className="empty">No messages yet — ask something.</div>}
          {history.map(entry => (
            <div className="chat-entry" key={entry.id}>
              <ChatBubble who="user" text={entry.question} />
              <ChatBubble who={entry.status==='error' ? 'error' : 'bot'} text={entry.answer || (entry.status==='pending' ? 'Thinking...' : '')} />
            </div>
          ))}
        </div>
      </main>

      <footer>
        <small>Built for RAG backend — set VITE_API_URL at build time to point to your backend.</small>
      </footer>

      <style>{`
        :root{ --bg:#0f1720; --card:#0b1220; --muted:#9aa4b2; --accent:#4f46e5; }
        *{box-sizing:border-box}
        body,html,#root{height:100%;margin:0;font-family:Inter,system-ui,Arial}
        .page{display:flex;flex-direction:column;height:100vh;background:linear-gradient(180deg,#071026, #071936);color:#e6eef8;padding:16px}
        header{display:flex;align-items:center;justify-content:space-between}
        h1{margin:0;font-size:20px}
        .meta{display:flex;gap:12px;align-items:center}
        main{flex:1;display:flex;flex-direction:column;gap:12px;margin-top:12px}
        .ask-form{display:flex;gap:8px}
        .ask-form input{flex:1;padding:10px;border-radius:8px;border:1px solid #123; background:#071126;color:inherit}
        .ask-form button{padding:10px 14px;border-radius:8px;border:0;background:var(--accent);color:white}
        .chat-list{overflow:auto;padding:8px;display:flex;flex-direction:column-reverse;gap:12px}
        .bubble{max-width:80%;padding:10px;border-radius:12px}
        .bubble.user{align-self:flex-end;background:#0b3b3b}
        .bubble.bot{align-self:flex-start;background:#0b2a44}
        .bubble.error{align-self:flex-start;background:#4b1b1b}
        .bubble-text{white-space:pre-wrap}
        footer{font-size:12px;color:var(--muted);margin-top:8px}
      `}</style>
    </div>
  )
}
