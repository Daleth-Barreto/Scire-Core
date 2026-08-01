import { useState } from 'react'
import { fetchPaper, runWebSearch, type Candidate } from './api'

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

  async function onSearch() {
    if (!query.trim()) return
    setBusy(true)
    setError('')
    try {
      setResults(await runWebSearch(query.trim(), limit, persist))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
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
      <h2>Web search</h2>
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
        persist results into the graph
      </label>

      {error && <p className="error">{error}</p>}

      <h3>Fetch paper by ID</h3>
      <div className="row">
        <input
          value={externalId}
          onChange={(e) => setExternalId(e.target.value)}
          placeholder="arxiv:2301.00000 or ss:... (persists into the graph)"
          onKeyDown={(e) => e.key === 'Enter' && void onFetch()}
        />
        <button onClick={() => void onFetch()} disabled={fetchBusy}>
          {fetchBusy ? 'fetching…' : 'Fetch'}
        </button>
      </div>
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
