import { useCallback, useEffect, useState } from 'react'
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Node,
  type Edge,
  type NodeProps,
  type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { detectGaps, fetchGraph, fetchNodeDetail, type GraphNode, type NodeDetail } from './api'

const TYPE_COLORS: Record<string, string> = {
  paper: '#8b5cf6',
  author: '#f59e0b',
  concept: '#10b981',
  hypothesis: '#ec4899',
  repo: '#3b82f6',
  file: '#06b6d4',
  chunk: '#94a3b8',
  note: '#14b8a6',
  claim: '#ef4444',
  action: '#9ca3af',
}

function ScireNode({ data, selected }: NodeProps) {
  const isHypothesis = data.type === 'hypothesis'
  return (
    <div
      style={{
        border: `2px ${isHypothesis ? 'dashed' : 'solid'} ${selected ? '#000' : String(data.color)}`,
        background: isHypothesis ? '#fdf2f8' : '#fff',
        borderRadius: 8,
        padding: '6px 10px',
        maxWidth: 220,
        fontSize: 12,
        color: '#111',
      }}
    >
      <div style={{ fontWeight: 600, color: String(data.color), textTransform: 'uppercase', fontSize: 10 }}>
        {String(data.type)}
      </div>
      <div>{String(data.label)}</div>
    </div>
  )
}

const nodeTypes: NodeTypes = { scire: ScireNode }

function layout(nodes: GraphNode[]): Node[] {
  return nodes.map((node, index) => ({
    id: node.id,
    type: 'scire',
    position: {
      x: 60 + (index % 6) * 260,
      y: 60 + Math.floor(index / 6) * 130,
    },
    data: { label: node.title, type: node.type, color: TYPE_COLORS[node.type] ?? '#999' },
  }))
}

function edgeStyle(type: string): { stroke: string; strokeDasharray?: string } {
  if (type === 'gap_in') {
    return { stroke: '#f43f5e', strokeDasharray: '6 4' }
  }
  return { stroke: '#94a3b8' }
}

export default function GraphView() {
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [detail, setDetail] = useState<NodeDetail | null>(null)
  const [gaps, setGaps] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const graph = await fetchGraph()
      setNodes(layout(graph.nodes))
      setEdges(
        graph.edges.map((edge) => ({
          id: edge.id,
          source: edge.source_id,
          target: edge.target_id,
          label: edge.type,
          style: edgeStyle(edge.type),
        })),
      )
      setGaps(graph.nodes.filter((n) => n.type === 'hypothesis').map((n) => n.title))
      setError('')
    } catch (err) {
      setError((err as Error).message)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const onDetectGaps = useCallback(async () => {
    setBusy(true)
    setError('')
    try {
      setGaps(await detectGaps())
      await load()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }, [load])

  const onNodeClick = useCallback(async (_: unknown, node: Node) => {
    try {
      setDetail(await fetchNodeDetail(node.id))
    } catch (err) {
      setError((err as Error).message)
    }
  }, [])

  return (
    <div className="graph-layout">
      <div style={{ height: 'calc(100vh - 120px)', flex: 1 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={onNodeClick}
          fitView
        >
          <Background />
          <Controls />
          <MiniMap nodeColor={(n) => (n.data?.color as string) ?? '#999'} />
        </ReactFlow>
      </div>
      <aside className="sidebar">
        <h3>Gaps &amp; hypotheses</h3>
        <button onClick={() => void onDetectGaps()} disabled={busy} className="wide">
          {busy ? 'detecting…' : 'Detect gaps'}
        </button>
        {gaps.length === 0 && !busy && <p className="muted">No hypotheses yet.</p>}
        <ul className="plain gaps">
          {gaps.map((gap) => (
            <li key={gap} className="gap">
              <span className="tag">hypothesis</span> {gap}
            </li>
          ))}
        </ul>

        <h3>Node details</h3>
        {detail ? (
          <>
            <p>
              <strong>{detail.title}</strong> <span className="tag">{detail.type}</span>
            </p>
            {detail.summary && <p className="muted">{detail.summary.slice(0, 400)}</p>}
            <h4>Neighbors</h4>
            <ul className="plain">
              {detail.neighbors.map((n) => (
                <li key={n.id}>
                  <span className="tag">{n.type}</span> {n.title}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="muted">Click a node to inspect it.</p>
        )}
        {error && <p className="error">{error}</p>}
      </aside>
    </div>
  )
}
