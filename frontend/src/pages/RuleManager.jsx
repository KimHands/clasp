import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors,
  DragOverlay, useDroppable
} from '@dnd-kit/core'
import { useDraggable } from '@dnd-kit/core'
import {
  GripVertical, Plus, Trash2, ArrowLeft, FolderTree,
  ChevronRight, ChevronDown, ArrowDown
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import useRuleStore from '@/store/ruleStore'
import useExtensionStore from '@/store/extensionStore'
import { getRules, createRule, updateRule, deleteRule } from '@/api/rules'

const TYPE_LABELS = { date: '날짜', content: '내용', extension: '확장자' }
const TYPE_COLORS = { date: 'default', content: 'warning', extension: 'secondary' }
const VALID_TYPES = ['date', 'content', 'extension']

const DEFAULT_EXTENSIONS = {
  '문서': ['pdf', 'docx', 'doc', 'txt', 'md', 'hwp', 'rtf'],
  '프레젠테이션': ['pptx', 'ppt', 'key'],
  '스프레드시트': ['xlsx', 'xls', 'csv'],
  '데이터': ['json', 'xml', 'yaml', 'sql'],
  '코드': ['py', 'js', 'ts', 'jsx', 'tsx', 'java', 'cpp', 'c', 'h', 'go', 'rs', 'html', 'css'],
  '이미지': ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp'],
  '영상': ['mp4', 'mov', 'avi', 'mkv', 'webm'],
  '오디오': ['mp3', 'wav', 'flac', 'aac', 'ogg'],
  '압축': ['zip', 'tar', 'gz', 'rar', '7z'],
}

function DraggableRuleCard({ rule, onDelete }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `rule-${rule.id}`,
    data: { type: 'rule', rule },
  })

  const style = transform
    ? { transform: `translate(${transform.x}px, ${transform.y}px)` }
    : {}

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-2 glass-card px-3 py-2.5 min-w-0 shrink-0 transition-all duration-200 ${
        isDragging ? 'shadow-lg border-[hsl(var(--primary)/0.5)] opacity-50 z-50' : 'hover:shadow-md'
      }`}
    >
      <button
        {...attributes}
        {...listeners}
        className="text-[hsl(var(--muted-foreground)/0.4)] hover:text-[hsl(var(--muted-foreground))] cursor-grab active:cursor-grabbing shrink-0"
      >
        <GripVertical size={16} />
      </button>

      <Badge variant={TYPE_COLORS[rule.type] || 'secondary'} className="shrink-0 text-xs">
        {TYPE_LABELS[rule.type] || rule.type}
      </Badge>

      <div className="flex items-center gap-1.5 min-w-0">
        <span className="text-sm font-medium text-[hsl(var(--foreground))] truncate">{rule.value}</span>
        <span className="text-[hsl(var(--muted-foreground)/0.4)]">→</span>
        <span className="text-sm text-[hsl(var(--foreground)/0.7)] truncate">{rule.folder_name}</span>
      </div>

      <button
        onClick={() => onDelete(rule.id)}
        className="text-[hsl(var(--muted-foreground)/0.3)] hover:text-[hsl(var(--destructive))] transition-colors shrink-0 ml-auto"
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}

function NestDropZone({ ruleId, children }) {
  const { setNodeRef, isOver } = useDroppable({
    id: `nest-${ruleId}`,
    data: { type: 'nest', targetRuleId: ruleId },
  })

  return (
    <div
      ref={setNodeRef}
      className={`relative rounded-xl transition-all ${
        isOver ? 'ring-2 ring-[hsl(var(--primary))] ring-offset-1 bg-[hsl(var(--primary)/0.05)]' : ''
      }`}
    >
      {children}
      {isOver && (
        <div className="absolute -bottom-1 left-4 right-4 flex items-center gap-1 text-[hsl(var(--primary))]">
          <ArrowDown size={10} />
          <span className="text-[10px] font-medium">하위 중첩</span>
        </div>
      )}
    </div>
  )
}

function FlatDropZone({ parentId, position }) {
  const { setNodeRef, isOver } = useDroppable({
    id: `flat-${parentId ?? 'root'}-${position}`,
    data: { type: 'flat', parentId, position },
  })

  return (
    <div
      ref={setNodeRef}
      className={`flex items-center justify-center transition-all shrink-0 ${
        isOver
          ? 'w-16 h-full min-h-[44px] border-2 border-dashed border-[hsl(var(--primary))] rounded-xl bg-[hsl(var(--primary)/0.05)]'
          : 'w-3 h-full min-h-[44px] rounded opacity-0 hover:opacity-100 hover:bg-[var(--input-bg)]'
      }`}
    >
      {isOver && <Plus size={14} className="text-[hsl(var(--primary))]" />}
    </div>
  )
}

function RuleTreeLevel({ nodes, parentId, onDelete, depth = 0 }) {
  if (!nodes || nodes.length === 0) return null

  return (
    <div className={depth > 0 ? 'mt-2' : ''}>
      {depth > 0 && (
        <div className="flex items-center gap-1 mb-1.5 ml-1">
          <ChevronDown size={12} className="text-[hsl(var(--muted-foreground)/0.4)]" />
          <span className="text-[10px] text-[hsl(var(--muted-foreground))] uppercase tracking-wider">하위 규칙</span>
        </div>
      )}
      <div className="flex items-start gap-1 flex-wrap">
        <FlatDropZone parentId={parentId} position={0} />
        {nodes.map((node, i) => (
          <div key={node.id} className="flex items-start gap-1">
            <div className="flex flex-col">
              <NestDropZone ruleId={node.id}>
                <DraggableRuleCard rule={node} onDelete={onDelete} />
              </NestDropZone>
              {node.children && node.children.length > 0 && (
                <div className="ml-4 pl-3 border-l-2 border-[hsl(var(--border))]">
                  <RuleTreeLevel
                    nodes={node.children}
                    parentId={node.id}
                    onDelete={onDelete}
                    depth={depth + 1}
                  />
                </div>
              )}
            </div>
            <FlatDropZone parentId={parentId} position={i + 1} />
          </div>
        ))}
      </div>
    </div>
  )
}

function AddRuleForm({ onAdd, rules }) {
  const [type, setType] = useState('extension')
  const [value, setValue] = useState('')
  const [folderName, setFolderName] = useState('')
  const [parentId, setParentId] = useState('')
  const [error, setError] = useState('')
  const [useCustomInput, setUseCustomInput] = useState(false)

  const { extensions, fetchExtensions } = useExtensionStore()

  useEffect(() => {
    fetchExtensions()
  }, [])

  const extensionsByCategory = (() => {
    const grouped = {}
    for (const [cat, exts] of Object.entries(DEFAULT_EXTENSIONS)) {
      grouped[cat] = [...exts]
    }
    const customExts = extensions.filter((e) => !e.is_default)
    for (const ext of customExts) {
      if (!grouped[ext.category]) grouped[ext.category] = []
      if (!grouped[ext.category].includes(ext.extension)) {
        grouped[ext.category].push(ext.extension)
      }
    }
    return grouped
  })()

  const handleTypeChange = (newType) => {
    setType(newType)
    setValue('')
    setUseCustomInput(false)
  }

  const handleExtensionSelect = (ext) => {
    if (ext === '__custom__') {
      setUseCustomInput(true)
      setValue('')
    } else {
      setUseCustomInput(false)
      setValue(ext)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!value.trim() || !folderName.trim()) {
      setError('값과 폴더명을 모두 입력해주세요')
      return
    }
    setError('')
    await onAdd({
      type,
      value: value.trim(),
      folderName: folderName.trim(),
      parentId: parentId ? Number(parentId) : null,
    })
    setValue('')
    setFolderName('')
    setParentId('')
    setUseCustomInput(false)
  }

  return (
    <form onSubmit={handleSubmit} className="glass-card p-4 border-[hsl(var(--primary)/0.2)] bg-[hsl(var(--primary)/0.04)]">
      <p className="text-sm font-semibold text-[hsl(var(--primary))] mb-3">새 규칙 추가</p>
      <div className="flex gap-2 flex-wrap">
        <select
          value={type}
          onChange={(e) => handleTypeChange(e.target.value)}
          className="glass-input px-3 py-2 text-sm bg-[var(--glass-bg)]"
        >
          {VALID_TYPES.map((t) => (
            <option key={t} value={t}>{TYPE_LABELS[t]}</option>
          ))}
        </select>

        {type === 'extension' && !useCustomInput ? (
          <select
            value={value}
            onChange={(e) => handleExtensionSelect(e.target.value)}
            className="flex-1 min-w-36 glass-input px-3 py-2 text-sm bg-[var(--glass-bg)]"
          >
            <option value="">확장자 선택...</option>
            {Object.entries(extensionsByCategory).map(([category, exts]) => (
              <optgroup key={category} label={category}>
                {exts.map((ext) => (
                  <option key={ext} value={ext}>.{ext}</option>
                ))}
              </optgroup>
            ))}
            <optgroup label="기타">
              <option value="__custom__">직접 입력...</option>
            </optgroup>
          </select>
        ) : (
          <div className="flex items-center gap-1 flex-1 min-w-28">
            <input
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder={type === 'date' ? '예: 2025' : type === 'extension' ? '예: hwp' : '예: 보안'}
              className="flex-1 glass-input px-3 py-2 text-sm"
            />
            {type === 'extension' && useCustomInput && (
              <button
                type="button"
                onClick={() => { setUseCustomInput(false); setValue('') }}
                className="text-xs text-[hsl(var(--primary))] hover:brightness-110 whitespace-nowrap"
              >
                목록으로
              </button>
            )}
          </div>
        )}

        <input
          type="text"
          value={folderName}
          onChange={(e) => setFolderName(e.target.value)}
          placeholder="생성될 폴더명"
          className="flex-1 min-w-28 glass-input px-3 py-2 text-sm"
        />
        <select
          value={parentId}
          onChange={(e) => setParentId(e.target.value)}
          className="glass-input px-3 py-2 text-sm bg-[var(--glass-bg)]"
        >
          <option value="">루트 (최상위)</option>
          {rules.map((r) => (
            <option key={r.id} value={r.id}>
              ↳ {r.folder_name} ({TYPE_LABELS[r.type]}: {r.value})
            </option>
          ))}
        </select>
        <Button type="submit" size="sm">
          <Plus size={14} /> 추가
        </Button>
      </div>
      {error && <p className="text-xs text-[hsl(var(--destructive))] mt-2">{error}</p>}
    </form>
  )
}

function buildPathFromTree(node, parentPath = '') {
  const current = parentPath ? `${parentPath} / ${node.folder_name}` : node.folder_name
  const paths = [current]
  if (node.children) {
    for (const child of node.children) {
      paths.push(...buildPathFromTree(child, current))
    }
  }
  return paths
}

function FolderPreview({ tree }) {
  if (tree.length === 0) return null

  const allPaths = []
  for (const root of tree) {
    allPaths.push(...buildPathFromTree(root))
  }

  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <FolderTree size={15} className="text-[hsl(var(--muted-foreground))]" />
        <p className="text-xs font-semibold text-[hsl(var(--muted-foreground))]">폴더 구조 미리보기</p>
      </div>
      <div className="space-y-1">
        {allPaths.map((p, i) => {
          const segments = p.split(' / ')
          const depth = segments.length - 1
          return (
            <div key={i} className="flex items-center gap-1.5" style={{ paddingLeft: depth * 16 }}>
              {depth > 0 && <ChevronRight size={12} className="text-[hsl(var(--muted-foreground)/0.4)]" />}
              <span className="text-sm text-[hsl(var(--foreground)/0.8)] font-mono">{segments[segments.length - 1]}</span>
            </div>
          )
        })}
      </div>
      <p className="text-xs text-[hsl(var(--muted-foreground))] mt-2">
        가로 나란히 = 동일 레벨 · 세로 아래 = 하위 중첩
      </p>
    </div>
  )
}

export default function RuleManager() {
  const navigate = useNavigate()
  const { rules, tree, setRules, addRule, removeRule } = useRuleStore()
  const [loading, setLoading] = useState(true)
  const [activeRule, setActiveRule] = useState(null)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  )

  useEffect(() => {
    loadRules()
  }, [])

  const loadRules = async () => {
    setLoading(true)
    try {
      const data = await getRules()
      setRules(data.rules)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = async ({ type, value, folderName, parentId }) => {
    const nextPriority = rules.length > 0 ? Math.max(...rules.map((r) => r.priority)) + 1 : 1
    try {
      const newRule = await createRule({
        priority: nextPriority, type, value, folderName, parentId,
      })
      addRule(newRule)
    } catch (e) {
      alert(e.message || '규칙 추가에 실패했습니다')
    }
  }

  const handleDelete = async (ruleId) => {
    try {
      await deleteRule(ruleId)
      removeRule(ruleId)
    } catch (e) {
      alert('규칙 삭제에 실패했습니다')
    }
  }

  const sortedRules = [...rules].sort((a, b) => a.priority - b.priority)

  const handleDragStart = (event) => {
    const data = event.active.data.current
    if (data?.type === 'rule') {
      setActiveRule(data.rule)
    }
  }

  const isDescendant = (ruleId, potentialAncestorId, ruleMap) => {
    let cursor = ruleMap[ruleId]
    const visited = new Set()
    while (cursor) {
      if (cursor.id === potentialAncestorId) return true
      if (visited.has(cursor.id)) return false
      visited.add(cursor.id)
      cursor = cursor.parent_id ? ruleMap[cursor.parent_id] : null
    }
    return false
  }

  const handleDragEnd = async (event) => {
    const { active, over } = event
    setActiveRule(null)
    if (!over) return

    const dragData = active.data.current
    const dropData = over.data.current
    if (!dragData || dragData.type !== 'rule') return

    const draggedRule = dragData.rule
    const ruleMap = Object.fromEntries(rules.map((r) => [r.id, r]))
    let newParentId

    if (dropData.type === 'nest') {
      newParentId = dropData.targetRuleId
      if (newParentId === draggedRule.id) return
      if (isDescendant(newParentId, draggedRule.id, ruleMap)) return
    } else if (dropData.type === 'flat') {
      newParentId = dropData.parentId ?? null
      if (newParentId === draggedRule.id) return
      if (newParentId && isDescendant(newParentId, draggedRule.id, ruleMap)) return
    } else {
      return
    }

    if (draggedRule.parent_id === newParentId) return

    const updates = rules.map((r) =>
      r.id === draggedRule.id ? { ...r, parent_id: newParentId } : r
    )
    setRules(updates)

    try {
      await updateRule(draggedRule.id, { parentId: newParentId })
    } catch (e) {
      console.error('규칙 업데이트 실패:', e)
      loadRules()
    }
  }

  return (
    <div className="min-h-screen mesh-gradient">
      <header className="glass-header px-6 py-4 flex items-center gap-3 sticky top-0 z-10">
        <button onClick={() => navigate(-1)} className="text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors">
          <ArrowLeft size={18} />
        </button>
        <div>
          <h1 className="text-lg font-bold text-[hsl(var(--foreground))]">규칙 관리</h1>
          <p className="text-xs text-[hsl(var(--muted-foreground))]">
            규칙 위에 드롭 = 하위 중첩 · 규칙 사이에 드롭 = 같은 레벨
          </p>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-6 space-y-5">
        <AddRuleForm onAdd={handleAdd} rules={sortedRules} />

        <FolderPreview tree={tree} />

        {/* 드래그 안내 */}
        {sortedRules.length > 0 && (
          <div className="flex gap-4 flex-wrap text-xs text-[hsl(var(--muted-foreground))] glass-card px-3 py-2">
            <span className="flex items-center gap-1.5">
              <span className="w-5 h-5 rounded bg-[hsl(var(--primary)/0.08)] border-2 border-dashed border-[hsl(var(--primary)/0.3)] flex items-center justify-center">
                <Plus size={8} className="text-[hsl(var(--primary))]" />
              </span>
              사이에 드롭 = 같은 레벨 (flat)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-5 h-5 rounded bg-[hsl(var(--primary)/0.08)] border-2 border-[hsl(var(--primary)/0.3)] flex items-center justify-center">
                <ArrowDown size={8} className="text-[hsl(var(--primary))]" />
              </span>
              규칙 위에 드롭 = 하위 중첩 (nested)
            </span>
          </div>
        )}

        {loading ? (
          <div className="text-center py-8 text-[hsl(var(--muted-foreground))] text-sm">불러오는 중...</div>
        ) : sortedRules.length === 0 ? (
          <div className="text-center py-12 text-[hsl(var(--muted-foreground))] text-sm">
            등록된 규칙이 없습니다. 위에서 규칙을 추가하세요.
          </div>
        ) : (
          <DndContext
            sensors={sensors}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <div className="glass-card p-4">
              <RuleTreeLevel
                nodes={tree}
                parentId={null}
                onDelete={handleDelete}
              />
            </div>

            <DragOverlay>
              {activeRule ? (
                <div className="flex items-center gap-2 glass-heavy rounded-xl px-3 py-2.5 shadow-xl border-[hsl(var(--primary)/0.3)]">
                  <GripVertical size={16} className="text-[hsl(var(--primary)/0.5)]" />
                  <Badge variant={TYPE_COLORS[activeRule.type] || 'secondary'} className="text-xs">
                    {TYPE_LABELS[activeRule.type]}
                  </Badge>
                  <span className="text-sm font-medium text-[hsl(var(--foreground))]">{activeRule.value}</span>
                  <span className="text-[hsl(var(--muted-foreground)/0.4)]">→</span>
                  <span className="text-sm text-[hsl(var(--foreground)/0.7)]">{activeRule.folder_name}</span>
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>
        )}
      </div>
    </div>
  )
}
