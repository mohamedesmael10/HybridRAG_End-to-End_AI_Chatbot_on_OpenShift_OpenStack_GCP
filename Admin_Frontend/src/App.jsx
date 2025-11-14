


import { useState, useEffect } from "react";

const API_BASE = import.meta.env.VITE_API_URL || window.__RAG_API_URL__ || '/api'


function App() {
  const [text, setText] = useState("");
  const [jobId, setJobId] = useState("");
  const [status, setStatus] = useState("");
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(false);

  const submitText = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/submit_text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const data = await res.json();
      setJobId(data.job_id);
      setStatus(data.status);
      pollStatus(data.job_id);
    } catch (err) {
      alert("Failed to send text: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const pollStatus = async (id) => {
    const interval = setInterval(async () => {
      const res = await fetch(`${API_BASE}/status/${id}`);
      const data = await res.json();
      setStatus(data.status);
      setDetails(data.details);
      if (data.status === "done" || data.status === "failed") {
        clearInterval(interval);
      }
    }, 2000);
  };

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>🧠 AI Text Processing Frontend</h1>
      <textarea
        rows="6"
        cols="60"
        placeholder="Enter your text here..."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <br />
      <button onClick={submitText} disabled={!text || loading}>
        {loading ? "Submitting..." : "Submit"}
      </button>
      {jobId && (
        <div style={{ marginTop: "1rem" }}>
          <p><b>Job ID:</b> {jobId}</p>
          <p><b>Status:</b> {status}</p>
          {details && <pre>{JSON.stringify(details, null, 2)}</pre>}
        </div>
      )}
    </div>
  );
}

export default App;
