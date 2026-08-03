import { useState } from 'react'
import { addRepo, askRepo } from './api'

export default function RepoView() {
  const [ownerRepo, setOwnerRepo] = useState('')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState<'add' | 'ask' | null>(null)
  const [error, setError] = useState('')

  function split() {
    const [owner, repo] = ownerRepo.split('/')
    return { owner, repo }
  }

  async function onAdd() {
    const { owner, repo } = split()
    if (!owner || !repo) return
    setBusy('add')
    setError('')
    try {
      const counts = await addRepo(owner, repo, 200)
      setAnswer(`indexed ${owner}/${repo}: ${counts.files} files, ${counts.chunks} chunks`)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  async function onAsk() {
    const { owner, repo } = split()
    if (!owner || !repo || !question.trim()) return
    setBusy('ask')
    setError('')
    try {
      const result = await askRepo(owner, repo, question.trim())
      setAnswer(result.answer)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="panel">
      <h2>Repository analysis</h2>
      <p className="muted helper">
        Analyze any GitHub repo: index it first, then ask questions about its code.
      </p>

      <h3>1. Index a repo</h3>
      <p className="muted helper">
        Scire reads the repo and stores its files in your knowledge graph. Do this once per repo.
      </p>
      <div className="row">
        <input
          value={ownerRepo}
          onChange={(e) => setOwnerRepo(e.target.value)}
          placeholder="owner/repo, e.g. psf/requests"
        />
        <button onClick={() => void onAdd()} disabled={busy === 'add'}>
          {busy === 'add' ? 'indexing…' : 'Index repo'}
        </button>
      </div>

      <h3>2. Ask about the code</h3>
      <p className="muted helper">
        Once indexed, ask anything about how the repo works.
      </p>
      <div className="row">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="ask about the code, e.g. how does it handle redirects?"
          onKeyDown={(e) => e.key === 'Enter' && void onAsk()}
        />
        <button onClick={() => void onAsk()} disabled={busy === 'ask'}>
          {busy === 'ask' ? 'thinking…' : 'Ask'}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {answer && <pre className="answer">{answer}</pre>}
    </div>
  )
}
