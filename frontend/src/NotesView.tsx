import { useEffect, useState } from 'react'
import { addNote, listNotes } from './api'

interface Note {
  id: string
  title: string
  summary?: string
  properties: Record<string, unknown>
}

export default function NotesView() {
  const [notes, setNotes] = useState<Note[]>([])
  const [content, setContent] = useState('')
  const [error, setError] = useState('')

  async function load() {
    try {
      setNotes(await listNotes())
    } catch (err) {
      setError((err as Error).message)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function onAdd() {
    if (!content.trim()) return
    try {
      await addNote(content.trim())
      setContent('')
      await load()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <div className="panel">
      <h2>Notes</h2>
      <p className="muted helper">Thoughts you save here become nodes in your graph.</p>
      <div className="row">
        <input
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="a thought to remember…"
          onKeyDown={(e) => e.key === 'Enter' && void onAdd()}
        />
        <button onClick={() => void onAdd()}>Save</button>
      </div>
      {error && <p className="error">{error}</p>}
      <ul className="results">
        {notes.map((note) => (
          <li key={note.id}>
            <span className="tag">note</span>
            <strong>{note.title}</strong>
            {note.summary && note.summary !== note.title && (
              <p className="muted">{note.summary}</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
