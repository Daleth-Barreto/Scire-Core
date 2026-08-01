import { useState } from 'react'
import GraphView from './GraphView'
import SearchView from './SearchView'
import RepoView from './RepoView'
import NotesView from './NotesView'
import IngestView from './IngestView'
import SettingsView from './SettingsView'
import './App.css'

type Tab = 'graph' | 'search' | 'repo' | 'notes' | 'ingest' | 'settings'

const TABS: { id: Tab; label: string }[] = [
  { id: 'graph', label: 'Graph' },
  { id: 'search', label: 'Search' },
  { id: 'repo', label: 'Repo' },
  { id: 'notes', label: 'Notes' },
  { id: 'ingest', label: 'Ingest' },
  { id: 'settings', label: 'Settings' },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('graph')

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">scire</span>
        <nav>
          {TABS.map((t) => (
            <button
              key={t.id}
              className={tab === t.id ? 'active' : ''}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main>
        {tab === 'graph' && <GraphView />}
        {tab === 'search' && <SearchView />}
        {tab === 'repo' && <RepoView />}
        {tab === 'notes' && <NotesView />}
        {tab === 'ingest' && <IngestView />}
        {tab === 'settings' && <SettingsView />}
      </main>
    </div>
  )
}
