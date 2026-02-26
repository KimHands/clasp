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

// 드래그 가능한 규칙 카드
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
      className={`flex items-center gap-2 bg-white border rounded-xl px-3 py-2.5 min-w-0 shrink-0 transition-shadow ${
        isDragging ? 'shadow-lg border-blue-300 opacity-50 z-50' : 'border-gray-200 hover:border-gray-300'
      }`}
    >
      <button
        {...attributes}
        {...listeners}
        className="text-gray-300 hover:text-gray-500 cursor-grab active:cursor-grabbing shrink-0"
      >
        <GripVertical size={16} />
      </button>

      <Badge variant={TYPE_COLORS[rule.type] || 'secondary'} className="shrink-0 text-xs">
        {TYPE_LABELS[rule.type] || rule.type}
      </Badge>

      <div className="flex items-center gap-1.5 min-w-0">
        <span className="text-sm font-medium text-gray-800 truncate">{rule.value}</span>
        <span className="text-gray-300">→</span>
        <span className="text-sm text-gray-600 truncate">{rule.folder_name}</span>
      </div>

      <button
        onClick={() => onDelete(rule.id)}
        className="text-gray-300 hover:text-red-400 transition-colors shrink-0 ml-auto"
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}

// 규칙 위에 드롭 → 해당 규칙의 자식(중첩)으로
function NestDropZone({ ruleId, children }) {
  const { setNodeRef, isOver } = useDroppable({
    id: `nest-${ruleId}`,
    data: { type: 'nest', targetRuleId: ruleId },
  })

  return (
    <div
      ref={setNodeRef}
      className={`relative rounded-xl transition-all ${
        isOver ? 'ring-2 ring-blue-400 ring-offset-1 bg-blue-50/50' : ''
      }`}
    >
      {children}
      {isOver && (
        <div className="absolute -bottom-1 left-4 right-4 flex items-center gap-1 text-blue-500">
          <ArrowDown size={10} />
          <span className="text-[10px] font-medium">하위 중첩</span>
        </div>
      )}
    </div>
  )
}

// 같은 레벨 드롭존 (규칙 그룹 사이의 가로 삽입 지점)
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
          ? 'w-16 h-full min-h-[44px] border-2 border-dashed border-blue-400 rounded-xl bg-blue-50'
          : 'w-3 h-full min-h-[44px] rounded opacity-0 hover:opacity-100 hover:bg-gray-100'
      }`}
    >
      {isOver && <Plus size={14} className="text-blue-400" />}
    </div>
  )
}

// 트리 노드 렌더링: 같은 부모의 자식들은 가로 배치
function RuleTreeLevel({ nodes, parentId, onDelete, depth = 0 }) {
  if (!nodes || nodes.length === 0) return null

  return (
    <div className={depth > 0 ? 'mt-2' : ''}>
      {depth > 0 && (
        <div className="flex items-center gap-1 mb-1.5 ml-1">
          <ChevronDown size={12} className="text-gray-300" />
          <span className="text-[10px] text-gray-400 uppercase tracking-wider">하위 규칙</span>
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
                <div className="ml-4 pl-3 border-l-2 border-gray-200">
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
    <form onSubmit={handleSubmit} className="bg-blue-50 border border-blue-200 rounded-xl p-4">
      <p className="text-sm font-semibold text-blue-800 mb-3">새 규칙 추가</p>
      <div className="flex gap-2 flex-wrap">
        <select
          value={type}
          onChange={(e) => handleTypeChange(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          {VALID_TYPES.map((t) => (
            <option key={t} value={t}>{TYPE_LABELS[t]}</option>
          ))}
        </select>

        {type === 'extension' && !useCustomInput ? (
          <select
            value={value}
            onChange={(e) => handleExtensionSelect(e.target.value)}
            className="flex-1 min-w-36 border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
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
              className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            {type === 'extension' && useCustomInput && (
              <button
                type="button"
                onClick={() => { setUseCustomInput(false); setValue('') }}
                className="text-xs text-blue-500 hover:text-blue-700 whitespace-nowrap"
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
          className="flex-1 min-w-28 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <select
          value={parentId}
          onChange={(e) => setParentId(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
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
      {error && <p className="text-xs text-red-500 mt-2">{error}</p>}
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
    <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <FolderTree size={15} className="text-gray-400" />
        <p className="text-xs font-semibold text-gray-500">폴더 구조 미리보기</p>
      </div>
      <div className="space-y-1">
        {allPaths.map((p, i) => {
          const segments = p.split(' / ')
          const depth = segments.length - 1
          return (
            <div key={i} className="flex items-center gap-1.5" style={{ paddingLeft: depth * 16 }}>
              {depth > 0 && <ChevronRight size={12} className="text-gray-300" />}
              <span className="text-sm text-gray-700 font-mono">{segments[segments.length - 1]}</span>
            </div>
          )
        })}
      </div>
      <p className="text-xs text-gray-400 mt-2">
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
      // 규칙 위에 드롭 → 해당 규칙의 자식
      newParentId = dropData.targetRuleId
      if (newParentId === draggedRule.id) return
      if (isDescendant(newParentId, draggedRule.id, ruleMap)) return
    } else if (dropData.type === 'flat') {
      // 드롭존에 드롭 → 해당 부모의 같은 레벨
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
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-gray-600">
          <ArrowLeft size={18} />
        </button>
        <div>
          <h1 className="text-lg font-bold text-gray-900">규칙 관리</h1>
          <p className="text-xs text-gray-500">
            규칙 위에 드롭 = 하위 중첩 · 규칙 사이에 드롭 = 같은 레벨
          </p>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-6 space-y-5">
        <AddRuleForm onAdd={handleAdd} rules={sortedRules} />

        <FolderPreview tree={tree} />

        {/* 드래그 안내 */}
        {sortedRules.length > 0 && (
          <div className="flex gap-4 flex-wrap text-xs text-gray-400 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
            <span className="flex items-center gap-1.5">
              <span className="w-5 h-5 rounded bg-blue-50 border-2 border-dashed border-blue-300 flex items-center justify-center">
                <Plus size={8} className="text-blue-400" />
              </span>
              사이에 드롭 = 같은 레벨 (flat)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-5 h-5 rounded bg-blue-50 border-2 border-blue-300 flex items-center justify-center">
                <ArrowDown size={8} className="text-blue-400" />
              </span>
              규칙 위에 드롭 = 하위 중첩 (nested)
            </span>
          </div>
        )}

        {loading ? (
          <div className="text-center py-8 text-gray-400 text-sm">불러오는 중...</div>
        ) : sortedRules.length === 0 ? (
          <div className="text-center py-12 text-gray-400 text-sm">
            등록된 규칙이 없습니다. 위에서 규칙을 추가하세요.
          </div>
        ) : (
          <DndContext
            sensors={sensors}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <div className="bg-white border border-gray-200 rounded-2xl p-4">
              <RuleTreeLevel
                nodes={tree}
                parentId={null}
                onDelete={handleDelete}
              />
            </div>

            <DragOverlay>
              {activeRule ? (
                <div className="flex items-center gap-2 bg-white border-2 border-blue-300 rounded-xl px-3 py-2.5 shadow-xl">
                  <GripVertical size={16} className="text-blue-300" />
                  <Badge variant={TYPE_COLORS[activeRule.type] || 'secondary'} className="text-xs">
                    {TYPE_LABELS[activeRule.type]}
                  </Badge>
                  <span className="text-sm font-medium text-gray-800">{activeRule.value}</span>
                  <span className="text-gray-300">→</span>
                  <span className="text-sm text-gray-600">{activeRule.folder_name}</span>
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>
        )}
      </div>
    </div>
  )
}
