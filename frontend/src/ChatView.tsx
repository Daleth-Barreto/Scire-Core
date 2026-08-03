import { useEffect, useRef, useState } from 'react'
import { sendChat, type ChatMessage as ChatMsg } from './api'

export default function ChatView() {
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy])

  async function onSend() {
    const text = input.trim()
    if (!text || busy) return
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setInput('')
    setError('')
    setBusy(true)
    try {
      const answer = await sendChat(text)
      setMessages((prev) => [...prev, { role: 'assistant', content: answer }])
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel chat">
      <h2>Chat</h2>
      <p className="muted helper">
        Ask anything — your LLM answers with your configured provider. The conversation is not yet
        persisted to the graph; use Notes to save insights.
      </p>
      <div className="chat-log">
        {messages.length === 0 && !busy && (
          <p className="muted">No messages yet — ask about your research topic.</p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`bubble ${msg.role}`}>
            {msg.content}
          </div>
        ))}
        {busy && <div className="bubble assistant muted">thinking…</div>}
        <div ref={endRef} />
      </div>
      {error && <p className="error">{error}</p>}
      <div className="row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="ask anything…"
          onKeyDown={(e) => e.key === 'Enter' && void onSend()}
          disabled={busy}
        />
        <button onClick={() => void onSend()} disabled={busy || !input.trim()}>
          {busy ? '…' : 'Send'}
        </button>
      </div>
    </div>
  )
}
