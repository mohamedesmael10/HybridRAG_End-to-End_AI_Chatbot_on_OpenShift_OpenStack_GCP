import React, { useEffect, useRef, useState } from "react";
import axios from "axios";

/*
API base detection:
- build-time: import.meta.env.VITE_API_URL
- runtime override: window.__RAG_API_URL__
- fallback: '' (relative -> '/ask')
*/
const API_BASE = import.meta.env.VITE_API_URL || window.__RAG_API_URL__ || "";

function Avatar({ alt, emoji }) {
  return (
    <div className="avatar" title={alt}>
      <div className="avatar-inner">{emoji}</div>
    </div>
  );
}

function Message({ msg }) {
  const cls = msg.role === "user" ? "msg user" : "msg bot";
  return (
    <div className={cls}>
      {msg.role === "bot" ? <Avatar alt="esmael ai" emoji="🤖" /> : <Avatar alt="you" emoji="🙂" />}
      <div className="bubble">
        <div className="bubble-meta">
          <strong>{msg.role === "bot" ? "esmael ai" : "You"}</strong>
          <span className="time">{msg.time}</span>
        </div>
        <div className="bubble-text">{msg.text}</div>
      </div>
    </div>
  );
}

export default function App() {
  const [input, setInput] = useState("");
  const [history, setHistory] = useState([]); // {role, text, time}
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("unknown");
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const saved = localStorage.getItem("esmael_ai_history");
    if (saved) setHistory(JSON.parse(saved));
    checkHealth();
  }, []);

  useEffect(() => {
    localStorage.setItem("esmael_ai_history", JSON.stringify(history));
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [history]);

  function now() {
    return new Date().toLocaleTimeString();
  }

  async function checkHealth() {
    const base = API_BASE.replace(/\/$/, "");
    const url = (base || "") + "/health";
    try {
      const r = await axios.get(url, { timeout: 5000 });
      setStatus(r.data.status || "ok");
    } catch (e) {
      setStatus("down");
    }
  }

  async function sendQuestion(e) {
    e?.preventDefault();
    const q = input.trim();
    if (!q) return;
    const userMsg = { role: "user", text: q, time: now() };
    setHistory((h) => [...h, userMsg]);
    setInput("");
    setLoading(true);
    inputRef.current?.focus();

    const base = API_BASE.replace(/\/$/, "");
    const url = (base || "") + "/ask";

    try {
      const resp = await axios.post(
        url,
        { question: q },
        { timeout: 120000, headers: { "Content-Type": "application/json" } }
      );

      const answer = resp.data.answer ?? JSON.stringify(resp.data);
      const botMsg = { role: "bot", text: answer, time: now() };
      setHistory((h) => [...h, botMsg]);
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || String(err);
      const botMsg = { role: "bot", text: `Error: ${detail}`, time: now() };
      setHistory((h) => [...h, botMsg]);
    } finally {
      setLoading(false);
    }
  }

  function clearHistory() {
    setHistory([]);
    localStorage.removeItem("esmael_ai_history");
  }

  function copyConversationJSON() {
    const payload = { conversation: history };
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    alert("Conversation JSON copied to clipboard.");
  }

  function downloadConversation() {
    const payload = { conversation: history };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "esmael_ai_conversation.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="logo">🤖</div>
          <div className="title">esmael ai</div>
        </div>

        <div className="controls">
          <button onClick={checkHealth}>Health: {status}</button>
          <button onClick={clearHistory}>Clear</button>
          <button onClick={copyConversationJSON}>Copy JSON</button>
          <button onClick={downloadConversation}>Download</button>
        </div>

        <div className="hint">
          <p>Tip: type a question and press Enter or click Send.</p>
        </div>
      </aside>

      <main className="chat-area">
        <header className="chat-header">
          <div className="hdr-left">
            <div className="hdr-title">esmael ai</div>
            <div className="hdr-sub">Ask questions about your indexed documents</div>
          </div>
        </header>

        <section className="messages">
          {history.length === 0 && <div className="start">Welcome — ask me anything.</div>}
          {history.map((m, idx) => (
            <Message key={idx} msg={m} />
          ))}
          {loading && (
            <div className="msg bot">
              <Avatar alt="esmael ai" emoji="🤖" />
              <div className="bubble">
                <div className="bubble-meta"><strong>esmael ai</strong> <span className="time">{now()}</span></div>
                <div className="bubble-text">Thinking…</div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </section>

        <form className="composer" onSubmit={sendQuestion}>
          <textarea
            ref={inputRef}
            className="input"
            placeholder="Ask a question..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={2}
          />
          <div className="composer-actions">
            <button type="submit" className="send" disabled={loading || !API_BASE && typeof window !== "undefined" && window.location.hostname !== "localhost"}>
              {loading ? "Sending…" : "Send"}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
