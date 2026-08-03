export interface GraphNode {
  id: string
  type: string
  title: string
  summary?: string
  properties: Record<string, unknown>
}

export interface GraphEdge {
  id: string
  source_id: string
  target_id: string
  type: string
}

export interface Graph {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface Candidate {
  title: string
  authors: string[]
  url: string
  source: string
  external_id: string
  summary: string
  published?: string
}

export interface SearchResult {
  id: string
  type: string
  title: string
  summary?: string
  distance: number
}

export interface ConfigInfo {
  provider: string
  embed_model: string | null
  api_key: string
  github_token: string
  encrypted: boolean
}

export interface NodeDetail {
  id: string
  type: string
  title: string
  summary?: string
  properties: Record<string, unknown>
  neighbors: { id: string; type: string; title: string }[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const base = import.meta.env.DEV ? '' : 'http://127.0.0.1:8000'
  let response: Response
  try {
    response = await fetch(`${base}${path}`, init)
  } catch (err) {
    if (err instanceof TypeError) {
      throw new Error(
        `${(err as Error).message} (is the backend running? try: uv run uvicorn backend.api.main:app)`,
      )
    }
    throw err
  }
  if (!response.ok) {
    let detail = response.statusText
    try {
      detail = (await response.json()).detail ?? detail
    } catch {
      // keep statusText
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export function fetchGraph(): Promise<Graph> {
  return request<Graph>('/api/graph')
}

export function fetchNodeDetail(id: string): Promise<NodeDetail> {
  return request<NodeDetail>(`/api/graph/nodes/${encodeURIComponent(id)}`)
}

export function searchGraph(q: string): Promise<SearchResult[]> {
  return request<SearchResult[]>(`/api/graph/search?q=${encodeURIComponent(q)}`)
}

export function runWebSearch(query: string, limit: number, persist: boolean): Promise<Candidate[]> {
  return request<Candidate[]>('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, limit, persist }),
  })
}

export function fetchPaper(externalId: string, persist: boolean): Promise<Candidate> {
  return request<Candidate>('/api/papers/fetch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ external_id: externalId, persist }),
  })
}

export function addRepo(owner: string, repo: string, limitFiles: number): Promise<{ files: number; chunks: number; skipped: number; repo_id: string }> {
  return request('/api/repos/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ owner, repo, limit_files: limitFiles }),
  })
}

export function askRepo(owner: string, repo: string, question: string): Promise<{ answer: string }> {
  return request('/api/repos/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ owner, repo, question }),
  })
}

export function listNotes(): Promise<{ id: string; title: string; summary?: string; properties: Record<string, unknown> }[]> {
  return request('/api/notes')
}

export function addNote(content: string): Promise<{ id: string; title: string }> {
  return request('/api/notes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
}

export function fetchConfig(): Promise<ConfigInfo> {
  return request<ConfigInfo>('/api/config')
}

export function saveConfigKeys(
  passphrase: string,
  keys: Record<string, string>,
): Promise<{ status: string; path: string; keys: string[] }> {
  return request('/api/config/keys', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ passphrase, keys }),
  })
}

export function unlockConfig(passphrase: string): Promise<{ status: string; keys: string[] }> {
  return request('/api/config/unlock', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ passphrase }),
  })
}

export function lockConfig(): Promise<{ status: string }> {
  return request('/api/config/lock', { method: 'POST' })
}

export function detectGaps(): Promise<string[]> {
  return request<string[]>('/api/graph/gaps', { method: 'POST' })
}

export interface IngestCounts {
  authors: number
  concepts: number
  claims: number
  chunks: number
  paper_id: string
}

export function ingestPdf(file: File, title: string): Promise<IngestCounts> {
  const form = new FormData()
  form.append('file', file)
  if (title.trim()) form.append('title', title.trim())
  return request<IngestCounts>('/api/ingest/pdf', { method: 'POST', body: form })
}
