import { useState } from 'react'
import GraphView from './GraphView'
import SearchView from './SearchView'
import RepoView from './RepoView'
import NotesView from './NotesView'
import IngestView from './IngestView'
import SettingsView from './SettingsView'
import './App.css'

type Tab = 'graph' | 'search' | 'repo' | 'notes' | 'ingest' | 'settings'

const TABS: { id: Tab; label: string; hint: string }[] = [
  { id: 'graph', label: 'Graph', hint: 'Explore your knowledge graph of papers, authors, and concepts' },
  { id: 'search', label: 'Search', hint: 'Find papers on the web or fetch a paper by its ID' },
  { id: 'repo', label: 'Repo', hint: 'Index a GitHub repo, then ask questions about its code' },
  { id: 'notes', label: 'Notes', hint: 'Save thoughts that become nodes in your graph' },
  { id: 'ingest', label: 'Ingest', hint: 'Upload a PDF to add its contents to your graph' },
  { id: 'settings', label: 'Settings', hint: 'Choose your LLM provider and manage API keys' },
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
              title={t.hint}
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
