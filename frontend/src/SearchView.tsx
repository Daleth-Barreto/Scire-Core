import { useState } from 'react'
import { deepResearch, fetchPaper, runWebSearch, type Candidate, type ResearchBrief } from './api'

export default function SearchView() {
  const [query, setQuery] = useState('')
  const [limit, setLimit] = useState(8)
  const [persist, setPersist] = useState(false)
  const [results, setResults] = useState<Candidate[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [externalId, setExternalId] = useState('arxiv:')
  const [fetched, setFetched] = useState<Candidate | null>(null)
  const [fetchBusy, setFetchBusy] = useState(false)
  const [brief, setBrief] = useState<ResearchBrief | null>(null)
  const [deepBusy, setDeepBusy] = useState(false)

  async function onSearch() {
    if (!query.trim()) return
    setBusy(true)
    setError('')
    setBrief(null)
    try {
      setResults(await runWebSearch(query.trim(), limit, persist))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function onDeep() {
    if (!query.trim()) return
    setDeepBusy(true)
    setError('')
    try {
      setBrief(await deepResearch(query.trim(), 5))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setDeepBusy(false)
    }
  }

  async function onFetch() {
    if (!externalId.trim()) return
    setFetchBusy(true)
    setError('')
    try {
      setFetched(await fetchPaper(externalId.trim(), true))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setFetchBusy(false)
    }
  }

  return (
    <div className="panel">
      <h2>Search</h2>
      <p className="muted helper">
        Find papers on a topic, or add a specific paper to your graph by its ID.
      </p>

      <h3>Search the web &amp; academia</h3>
      <p className="muted helper">
        Look for papers across academic sources and the web. Checking the box saves the results to
        your knowledge graph as you go.
      </p>
      <div className="row">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="topic, e.g. retrieval augmented generation"
          onKeyDown={(e) => e.key === 'Enter' && void onSearch()}
        />
        <input
          type="number"
          min={1}
          max={50}
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          style={{ width: 70 }}
        />
        <button onClick={() => void onSearch()} disabled={busy}>
          {busy ? 'searching…' : 'Search'}
        </button>
      </div>
      <label className="row">
        <input type="checkbox" checked={persist} onChange={(e) => setPersist(e.target.checked)} />
        save results to my knowledge graph
      </label>

      <button onClick={() => void onDeep()} disabled={deepBusy || !query.trim()} className="wide">
        {deepBusy ? 'researching… this takes a minute' : 'Deep research this topic'}
      </button>
      <p className="muted helper">
        Runs a full research pipeline: gathers sources, writes a cited brief, and verifies each
        claim against them.
      </p>

      {error && <p className="error">{error}</p>}

      {brief && (
        <div className="brief">
          <h3>Research brief: {brief.topic}</h3>
          {brief.verified ? (
            <p className="ok">Verified — every claim is backed by a source.</p>
          ) : (
            <p className="error">Not fully verified — review the flagged issues below.</p>
          )}
          {brief.issues.length > 0 && (
            <ul className="plain">
              {brief.issues.map((issue) => (
                <li key={issue} className="muted">
                  {issue}
                </li>
              ))}
            </ul>
          )}
          <pre className="answer">{brief.markdown}</pre>
          <h4>Sources</h4>
          <ul className="plain">
            {brief.sources.map((source, i) => (
              <li key={`${source.source}-${i}`}>
                <span className="tag">{source.source}</span> [{i + 1}] {source.title} —{' '}
                <a href={source.url} target="_blank" rel="noreferrer">
                  {source.url}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      <h3>Fetch a specific paper by ID</h3>
      <p className="muted helper">
        If you already know the paper you want, fetch it by ID — it is saved to your knowledge
        graph automatically.
      </p>
      <div className="row">
        <input
          value={externalId}
          onChange={(e) => setExternalId(e.target.value)}
          placeholder="paper ID, e.g. arxiv:2301.00000"
          onKeyDown={(e) => e.key === 'Enter' && void onFetch()}
        />
        <button onClick={() => void onFetch()} disabled={fetchBusy}>
          {fetchBusy ? 'fetching…' : 'Fetch'}
        </button>
      </div>
      <p className="muted helper">Accepted prefixes: arxiv:, epmc:, ss:, oa:</p>
      {fetched && (
        <li className="result-item">
          <span className="tag">{fetched.source}</span>
          <strong>{fetched.title}</strong>
          {fetched.authors.length > 0 && (
            <div className="muted">{fetched.authors.slice(0, 5).join(', ')}</div>
          )}
          {fetched.summary && <p className="muted">{fetched.summary.slice(0, 240)}</p>}
          {fetched.url && (
            <a href={fetched.url} target="_blank" rel="noreferrer">
              {fetched.url}
            </a>
          )}
        </li>
      )}

      {results && (
        <ul className="results">
          {results.map((candidate, i) => (
            <li key={`${candidate.source}-${candidate.external_id}-${i}`}>
              <span className="tag">{candidate.source}</span>
              <strong>{candidate.title}</strong>
              {candidate.authors.length > 0 && (
                <div className="muted">{candidate.authors.slice(0, 5).join(', ')}</div>
              )}
              {candidate.summary && <p className="muted">{candidate.summary.slice(0, 240)}</p>}
              {candidate.url && (
                <a href={candidate.url} target="_blank" rel="noreferrer">
                  {candidate.url}
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
