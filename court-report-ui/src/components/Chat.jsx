import { useState, useRef, useEffect } from 'react'

const API = 'http://localhost:8000'

function ChevronUp() {
  return (
    <svg width="13" height="8" viewBox="0 0 13 8" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M1.5 6.5L6.5 1.5L11.5 6.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

function ChevronDown() {
  return (
    <svg width="13" height="8" viewBox="0 0 13 8" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M1.5 1.5L6.5 6.5L11.5 1.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

function ChevronRight() {
  return (
    <svg width="8" height="13" viewBox="0 0 8 13" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M1.5 1.5L6.5 6.5L1.5 11.5" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

export default function Chat() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const msgsRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (msgsRef.current) msgsRef.current.scrollTop = msgsRef.current.scrollHeight
  }, [messages])

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 350)
  }, [open])

  async function send() {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    setMessages(m => [...m, { role: 'user', text: q }])
    setLoading(true)
    try {
      const res = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, session_id: 'default' }),
      })
      const data = await res.json()
      setMessages(m => [...m, { role: 'assistant', text: data.answer || data.response || JSON.stringify(data) }])
    } catch {
      setMessages(m => [...m, { role: 'assistant', text: 'Could not reach the server. Make sure the API is running.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-bar">
      <div className="chat-bar-inner">
        <div className="chat-trigger" onClick={() => setOpen(o => !o)}>
          <div className="c-dot"></div>
          <div className="chat-trigger-lbl">Ask Court Report</div>
          <button className="chat-trigger-btn" aria-label={open ? 'Close chat' : 'Open chat'}>
            {open ? <ChevronDown /> : <ChevronUp />}
          </button>
        </div>
        <div className={`chat-panel${open ? ' open' : ''}`}>
          <div className="chat-msgs" ref={msgsRef}>
            {messages.length === 0 && (
              <div className="c-empty">Ask anything about last night's games...</div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`bub ${m.role === 'user' ? 'u' : 'a'}`}>{m.text}</div>
            ))}
            {loading && <div className="bub a">Thinking...</div>}
          </div>
          <div className="chat-foot">
            <input
              ref={inputRef}
              className="c-inp"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && send()}
              placeholder="How did Wemby compare to his average?"
            />
            <button className="c-send" onClick={send}>
              Ask <ChevronRight />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
