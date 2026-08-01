import { useRef, useState } from 'react'
import { ingestPdf, type IngestCounts } from './api'

export default function IngestView() {
  const [title, setTitle] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [counts, setCounts] = useState<IngestCounts | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  async function onUpload() {
    if (!file) return
    setBusy(true)
    setError('')
    setCounts(null)
    try {
      setCounts(await ingestPdf(file, title))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel">
      <h2>PDF ingestion</h2>
      <div className="row">
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <button onClick={() => inputRef.current?.click()}>Choose file</button>
      </div>
      <p className="muted">
        {file ? file.name : 'No file selected'}
      </p>
      <div className="row">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Paper title (optional)"
        />
        <button onClick={() => void onUpload()} disabled={!file || busy}>
          {busy ? 'ingesting…' : 'Ingest'}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {counts && (
        <pre className="answer">
          {`paper: ${counts.paper_id}
chunks: ${counts.chunks}
authors: ${counts.authors}
concepts: ${counts.concepts}
claims: ${counts.claims}`}
        </pre>
      )}
    </div>
  )
}
