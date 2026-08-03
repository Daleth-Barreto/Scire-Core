import { useState } from 'react'
import { addRepo, askRepo, auditPaper, type AuditReport } from './api'

export default function RepoView() {
  const [ownerRepo, setOwnerRepo] = useState('')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState<'add' | 'ask' | 'audit' | null>(null)
  const [error, setError] = useState('')
  const [paperTitle, setPaperTitle] = useState('')
  const [audit, setAudit] = useState<AuditReport | null>(null)

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

  async function onAudit() {
    const { owner, repo } = split()
    if (!owner || !repo || !paperTitle.trim()) return
    setBusy('audit')
    setError('')
    try {
      setAudit(await auditPaper(paperTitle.trim(), owner, repo))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const verdictClass = (verdict: string) => {
    if (verdict === 'supported') return 'ok'
    if (verdict === 'refuted') return 'error'
    return 'muted'
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
      <h3>3. Audit a paper against this repo</h3>
      <p className="muted helper">
        Checks the claims of a paper you have ingested against this repo's code, and reports which
        are supported, refuted, or missing evidence.
      </p>
      <div className="row">
        <input
          value={paperTitle}
          onChange={(e) => setPaperTitle(e.target.value)}
          placeholder="paper title from your graph, e.g. Attention Is All You Need"
          onKeyDown={(e) => e.key === 'Enter' && void onAudit()}
        />
        <button onClick={() => void onAudit()} disabled={busy === 'audit'}>
          {busy === 'audit' ? 'auditing…' : 'Audit'}
        </button>
      </div>
      {audit && (
        <div className="audit">
          <h4>{audit.paper_title}</h4>
          <p className="muted helper">
            Supported {audit.summary.supported ?? 0} · Refuted {audit.summary.refuted ?? 0} · Not
            evidenced {audit.summary['not-evidenced'] ?? 0}
          </p>
          <ul className="plain">
            {audit.verdicts.map((verdict, i) => (
              <li key={i} className={`gap ${verdictClass(verdict.verdict)}`}>
                <span className="tag">{verdict.verdict}</span> {verdict.claim}
                {verdict.evidence && <div className="muted">evidence: {verdict.evidence}</div>}
                {verdict.reason && <div className="muted">{verdict.reason}</div>}
              </li>
            ))}
          </ul>
        </div>
      )}
      {error && <p className="error">{error}</p>}
      {answer && <pre className="answer">{answer}</pre>}
    </div>
  )
}
