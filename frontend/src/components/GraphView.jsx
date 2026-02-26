import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import {
  FileText, Presentation, Table2, Database, Code2,
  Image, Video, Music, Archive, HelpCircle, Tag,
  AlertTriangle, File, RotateCcw, Maximize2,
} from 'lucide-react'
import { buildMindmapTree } from '@/graph/cytoscapeConfig'

const ICON_MAP = {
  'file-text': FileText,
  'presentation': Presentation,
  'table': Table2,
  'database': Database,
  'code': Code2,
  'image': Image,
  'video': Video,
  'music': Music,
  'archive': Archive,
  'help-circle': HelpCircle,
  'tag': Tag,
  'alert': AlertTriangle,
  'file': File,
}

function NodeIcon({ name, size = 14, className = '' }) {
  const Icon = ICON_MAP[name] || File
  return <Icon size={size} className={className} />
}

const NODE_H = { root: 52, category: 48, tag: 42, file: 40 }
const NODE_GAP_Y = 12
const RANK_GAP_X = 80
const EXPAND_BTN_SPACE = 36

/**
 * 트리 레이아웃 계산 — 각 노드의 (x, y, width, height) 좌표 결정
 * 재귀적으로 서브트리 높이를 계산한 뒤 수직 중앙 정렬
 */
function layoutTree(node, collapsed, x = 0, depth = 0) {
  const h = NODE_H[node.type] || 36
  const w = getNodeWidth(node)
  const result = { ...node, x, y: 0, w, h, depth, childLayouts: [] }

  if (!node.children || node.children.length === 0 || collapsed.has(node.id)) {
    result.subtreeHeight = h
    return result
  }

  let childY = 0
  const childLayouts = []
  const childX = x + w + EXPAND_BTN_SPACE + RANK_GAP_X

  node.children.forEach((child, i) => {
    const childLayout = layoutTree(child, collapsed, childX, depth + 1)
    childLayout.y = childY
    childLayouts.push(childLayout)
    childY += childLayout.subtreeHeight + NODE_GAP_Y
  })

  const totalChildH = childY - NODE_GAP_Y
  result.subtreeHeight = Math.max(h, totalChildH)
  result.childLayouts = childLayouts
  result.y = 0

  childLayouts.forEach((cl) => {
    cl.y += (result.subtreeHeight - totalChildH) / 2
  })

  return result
}

function getNodeWidth(node) {
  if (node.type === 'root') return Math.min(Math.max(node.label.length * 12 + 48, 140), 240)
  if (node.type === 'category') return Math.min(Math.max(node.label.length * 11 + 80, 150), 220)
  if (node.type === 'tag') return Math.min(Math.max(node.label.length * 10 + 60, 120), 200)
  const name = node.label || ''
  return Math.min(Math.max(name.length * 8 + 52, 140), 280)
}

function flattenLayout(layout, offsetY = 0) {
  const nodes = []
  const edges = []
  const y = layout.y + offsetY
  const centerY = y + layout.h / 2

  nodes.push({ ...layout, y })

  if (layout.childLayouts && layout.childLayouts.length > 0) {
    layout.childLayouts.forEach((child) => {
      const childY = child.y + offsetY + layout.y
      const childCenterY = childY + child.h / 2

      edges.push({
        x1: layout.x + layout.w + EXPAND_BTN_SPACE / 2,
        y1: centerY,
        x2: child.x,
        y2: childCenterY,
        color: child.color || '#CBD5E1',
      })

      const sub = flattenLayout(child, offsetY + layout.y)
      nodes.push(...sub.nodes)
      edges.push(...sub.edges)
    })
  }

  return { nodes, edges }
}

function CurvePath({ x1, y1, x2, y2, color }) {
  const dx = x2 - x1
  const cp1x = x1 + dx * 0.4
  const cp2x = x2 - dx * 0.4
  const d = `M ${x1} ${y1} C ${cp1x} ${y1}, ${cp2x} ${y2}, ${x2} ${y2}`
  return (
    <path
      d={d}
      fill="none"
      stroke={color}
      strokeWidth={2}
      strokeOpacity={0.25}
      strokeLinecap="round"
    />
  )
}

function ExpandButton({ x, y, isCollapsed, onClick, size = 22 }) {
  const r = size / 2
  return (
    <g
      transform={`translate(${x}, ${y})`}
      onClick={(e) => { e.stopPropagation(); onClick() }}
      className="cursor-pointer"
    >
      <circle r={r} fill="white" stroke="#D1D5DB" strokeWidth={1} />
      <text
        x={0} y={1}
        textAnchor="middle" dominantBaseline="central"
        fill="#64748B" fontSize={12} fontWeight={500}
      >
        {isCollapsed ? '›' : '‹'}
      </text>
    </g>
  )
}

function MindmapNode({ node, collapsed, onToggle, onFileClick }) {
  const isCollapsed = collapsed.has(node.id)
  const hasChildren = node.children && node.children.length > 0 && node.type !== 'file'

  if (node.type === 'root') {
    return (
      <g transform={`translate(${node.x}, ${node.y})`}>
        <rect
          width={node.w} height={node.h}
          rx={14} ry={14}
          fill="#1E293B"
          filter="url(#cardShadow)"
        />
        <text
          x={node.w / 2} y={node.h / 2}
          textAnchor="middle" dominantBaseline="central"
          fill="white" fontSize={14} fontWeight={700}
          fontFamily="system-ui, -apple-system, sans-serif"
        >
          {node.label.length > 16 ? node.label.slice(0, 14) + '…' : node.label}
        </text>
        {hasChildren && (
          <ExpandButton
            x={node.w + 16} y={node.h / 2}
            isCollapsed={isCollapsed}
            onClick={() => onToggle(node.id)}
          />
        )}
      </g>
    )
  }

  if (node.type === 'category') {
    return (
      <g transform={`translate(${node.x}, ${node.y})`}>
        <rect
          width={node.w} height={node.h}
          rx={12} ry={12}
          fill="white"
          stroke="#E5E7EB" strokeWidth={1}
          filter="url(#cardShadow)"
        />
        {/* 왼쪽 컬러 바 */}
        <rect
          width={4} height={node.h - 16}
          x={6} y={8}
          rx={2} ry={2}
          fill={node.color}
        />
        {/* 아이콘 */}
        <foreignObject x={18} y={0} width={22} height={node.h}>
          <div xmlns="http://www.w3.org/1999/xhtml" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <NodeIcon name={node.icon} size={16} />
          </div>
        </foreignObject>
        {/* 라벨 */}
        <text
          x={44} y={node.h / 2}
          dominantBaseline="central"
          fill="#1E293B" fontSize={13} fontWeight={600}
          fontFamily="system-ui, -apple-system, sans-serif"
        >
          {node.label}
        </text>
        {/* 파일 수 */}
        <text
          x={node.w - (hasChildren ? 28 : 12)} y={node.h / 2}
          textAnchor="end" dominantBaseline="central"
          fill="#94A3B8" fontSize={11}
          fontFamily="system-ui, -apple-system, sans-serif"
        >
          {node.count}
        </text>
        {/* 접기/펼치기 */}
        {hasChildren && (
          <ExpandButton
            x={node.w + 16} y={node.h / 2}
            isCollapsed={isCollapsed}
            onClick={() => onToggle(node.id)}
          />
        )}
      </g>
    )
  }

  if (node.type === 'tag') {
    return (
      <g transform={`translate(${node.x}, ${node.y})`}>
        <rect
          width={node.w} height={node.h}
          rx={10} ry={10}
          fill="white"
          stroke="#E5E7EB" strokeWidth={1}
          filter="url(#cardShadow)"
        />
        {/* 왼쪽 컬러 바 */}
        <rect
          width={3} height={node.h - 14}
          x={6} y={7}
          rx={1.5} ry={1.5}
          fill={node.color}
          opacity={0.5}
        />
        {/* 태그 아이콘 */}
        <foreignObject x={16} y={0} width={20} height={node.h}>
          <div xmlns="http://www.w3.org/1999/xhtml" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <Tag size={13} style={{ color: node.color, opacity: 0.7 }} />
          </div>
        </foreignObject>
        {/* 라벨 */}
        <text
          x={40} y={node.h / 2}
          dominantBaseline="central"
          fill="#475569" fontSize={12}
          fontFamily="system-ui, -apple-system, sans-serif"
        >
          {node.label.length > 16 ? node.label.slice(0, 14) + '…' : node.label}
        </text>
        {/* 접기/펼치기 */}
        {node.children && node.children.length > 0 && (
          <ExpandButton
            x={node.w + 14} y={node.h / 2}
            isCollapsed={isCollapsed}
            onClick={() => onToggle(node.id)}
            size={18}
          />
        )}
      </g>
    )
  }

  const borderColor = node.unclassified ? '#FCA5A5' : node.lowConfidence ? '#FCD34D' : '#E5E7EB'
  const bgColor = node.unclassified ? '#FEF2F2' : node.lowConfidence ? '#FFFBEB' : 'white'

  return (
    <g
      transform={`translate(${node.x}, ${node.y})`}
      onClick={() => onFileClick?.(node.fileId)}
      className="cursor-pointer"
    >
      <rect
        width={node.w} height={node.h}
        rx={9} ry={9}
        fill={bgColor}
        stroke={borderColor} strokeWidth={1}
        filter="url(#cardShadow)"
      />
      {/* 파일 아이콘 */}
      <foreignObject x={10} y={0} width={20} height={node.h}>
        <div xmlns="http://www.w3.org/1999/xhtml" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
          <NodeIcon name={node.unclassified ? 'alert' : 'file-text'} size={14} />
        </div>
      </foreignObject>
      {/* 파일명 */}
      <text
        x={34} y={node.h / 2}
        dominantBaseline="central"
        fill="#374151" fontSize={11}
        fontFamily="system-ui, -apple-system, sans-serif"
      >
        {node.label.length > 24 ? node.label.slice(0, 22) + '…' : node.label}
      </text>
    </g>
  )
}

export default function GraphView({ files, folderName, onNodeClick }) {
  const containerRef = useRef(null)
  const [collapsed, setCollapsed] = useState(new Set())
  const [pan, setPan] = useState({ x: 40, y: 40 })
  const [zoom, setZoom] = useState(1)
  const [dragging, setDragging] = useState(false)
  const dragStart = useRef(null)

  const tree = useMemo(
    () => buildMindmapTree(files, folderName || '스캔 결과'),
    [files, folderName]
  )

  const layout = useMemo(() => layoutTree(tree, collapsed), [tree, collapsed])
  const { nodes, edges } = useMemo(() => flattenLayout(layout), [layout])

  const totalWidth = useMemo(() => {
    let max = 0
    nodes.forEach((n) => { if (n.x + n.w > max) max = n.x + n.w })
    return max + 80
  }, [nodes])

  const totalHeight = useMemo(() => {
    let max = 0
    nodes.forEach((n) => { if (n.y + n.h > max) max = n.y + n.h })
    return max + 80
  }, [nodes])

  const handleToggle = useCallback((nodeId) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(nodeId)) next.delete(nodeId)
      else next.add(nodeId)
      return next
    })
  }, [])

  const collapseAll = useCallback(() => {
    const ids = new Set()
    const walk = (node) => {
      if (node.type === 'category' || node.type === 'tag') ids.add(node.id)
      node.children?.forEach(walk)
    }
    walk(tree)
    setCollapsed(ids)
  }, [tree])

  const expandAll = useCallback(() => setCollapsed(new Set()), [])

  const fitView = useCallback(() => {
    if (!containerRef.current) return
    const cw = containerRef.current.clientWidth
    const ch = containerRef.current.clientHeight
    const scaleX = (cw - 60) / totalWidth
    const scaleY = (ch - 60) / totalHeight
    const s = Math.min(scaleX, scaleY, 1.2)
    setZoom(Math.max(0.3, Math.min(s, 2)))
    setPan({ x: 30, y: 30 })
  }, [totalWidth, totalHeight])

  useEffect(() => {
    fitView()
  }, [files])

  const handleWheel = useCallback((e) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? 0.92 : 1.08
    setZoom((z) => Math.max(0.2, Math.min(z * delta, 3)))
  }, [])

  const handlePointerDown = useCallback((e) => {
    if (e.target.closest('[data-interactive]')) return
    setDragging(true)
    dragStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y }
  }, [pan])

  const handlePointerMove = useCallback((e) => {
    if (!dragging || !dragStart.current) return
    setPan({ x: e.clientX - dragStart.current.x, y: e.clientY - dragStart.current.y })
  }, [dragging])

  const handlePointerUp = useCallback(() => {
    setDragging(false)
    dragStart.current = null
  }, [])

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full rounded-xl bg-gradient-to-br from-slate-50/80 via-white to-blue-50/20 border border-gray-200 overflow-hidden select-none"
      style={{ minHeight: 480 }}
      onWheel={handleWheel}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerLeave={handlePointerUp}
    >
      {/* 컨트롤 */}
      <div className="absolute top-3 right-3 z-10 flex items-center gap-1.5">
        <button
          data-interactive
          onClick={collapseAll}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-white/95 backdrop-blur border border-gray-200 rounded-lg text-xs text-gray-600 hover:bg-gray-50 shadow-sm transition-colors"
        >
          <RotateCcw size={12} />
          모두 접기
        </button>
        <button
          data-interactive
          onClick={expandAll}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-white/95 backdrop-blur border border-gray-200 rounded-lg text-xs text-gray-600 hover:bg-gray-50 shadow-sm transition-colors"
        >
          <Maximize2 size={12} />
          모두 펼치기
        </button>
        <button
          data-interactive
          onClick={fitView}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-white/95 backdrop-blur border border-gray-200 rounded-lg text-xs text-gray-600 hover:bg-gray-50 shadow-sm transition-colors"
        >
          <Maximize2 size={12} />
          맞춤
        </button>
      </div>

      {/* SVG 마인드맵 */}
      <svg
        width="100%"
        height="100%"
        style={{ cursor: dragging ? 'grabbing' : 'grab' }}
      >
        <defs>
          <filter id="cardShadow" x="-8%" y="-12%" width="116%" height="132%">
            <feDropShadow dx="0" dy="2" stdDeviation="4" floodColor="#64748B" floodOpacity="0.08" />
          </filter>
        </defs>
        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* 엣지 (커브) */}
          {edges.map((edge, i) => (
            <CurvePath key={i} {...edge} />
          ))}
          {/* 노드 */}
          {nodes.map((node) => (
            <MindmapNode
              key={node.id}
              node={node}
              collapsed={collapsed}
              onToggle={handleToggle}
              onFileClick={onNodeClick}
            />
          ))}
        </g>
      </svg>

      {/* 범례 */}
      <div className="absolute bottom-3 left-3 z-10 flex items-center gap-3 px-3 py-2 bg-white/90 backdrop-blur border border-gray-200 rounded-lg shadow-sm">
        <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
          <span className="w-2.5 h-2.5 rounded-full bg-green-400" /> 높은 신뢰도
        </span>
        <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
          <span className="w-2.5 h-2.5 rounded-full bg-yellow-400" /> 낮은 신뢰도
        </span>
        <span className="flex items-center gap-1.5 text-[10px] text-gray-500">
          <span className="w-2.5 h-2.5 rounded-full bg-red-400" /> 미분류
        </span>
      </div>
    </div>
  )
}
