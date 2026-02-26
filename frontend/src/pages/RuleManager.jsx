import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors
} from '@dnd-kit/core'
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates,
  useSortable, verticalListSortingStrategy
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, Plus, Trash2, ArrowLeft, FolderTree } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import useRuleStore from '@/store/ruleStore'
import { getRules, createRule, updateRule, deleteRule } from '@/api/rules'

const TYPE_LABELS = { date: '날짜', content: '내용', extension: '확장자' }
const TYPE_COLORS = { date: 'default', content: 'warning', extension: 'secondary' }
const VALID_TYPES = ['date', 'content', 'extension']

function SortableRuleRow({ rule, onDelete }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: rule.id,
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-3 bg-white border border-gray-200 rounded-xl px-4 py-3 ${
        isDragging ? 'shadow-lg' : ''
      }`}
    >
      {/* 드래그 핸들 */}
      <button
        {...attributes}
        {...listeners}
        className="text-gray-300 hover:text-gray-500 cursor-grab active:cursor-grabbing"
      >
        <GripVertical size={18} />
      </button>

      {/* 우선순위 번호 */}
      <span className="w-6 h-6 bg-gray-100 rounded-full text-xs font-bold text-gray-500 flex items-center justify-center shrink-0">
        {rule.priority}
      </span>

      <Badge variant={TYPE_COLORS[rule.type] || 'secondary'}>
        {TYPE_LABELS[rule.type] || rule.type}
      </Badge>

      <div className="flex-1 min-w-0">
        <span className="text-sm font-medium text-gray-800">{rule.value}</span>
        <span className="text-gray-400 mx-2">→</span>
        <span className="text-sm text-gray-600">{rule.folder_name}</span>
      </div>

      <button
        onClick={() => onDelete(rule.id)}
        className="text-gray-300 hover:text-red-400 transition-colors"
      >
        <Trash2 size={15} />
      </button>
    </div>
  )
}

function AddRuleForm({ onAdd }) {
  const [type, setType] = useState('extension')
  const [value, setValue] = useState('')
  const [folderName, setFolderName] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!value.trim() || !folderName.trim()) {
      setError('값과 폴더명을 모두 입력해주세요')
      return
    }
    setError('')
    await onAdd({ type, value: value.trim(), folderName: folderName.trim() })
    setValue('')
    setFolderName('')
  }

  return (
    <form onSubmit={handleSubmit} className="bg-blue-50 border border-blue-200 rounded-xl p-4">
      <p className="text-sm font-semibold text-blue-800 mb-3">새 규칙 추가</p>
      <div className="flex gap-2 flex-wrap">
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          {VALID_TYPES.map((t) => (
            <option key={t} value={t}>{TYPE_LABELS[t]}</option>
          ))}
        </select>
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={type === 'date' ? '예: 2025' : type === 'extension' ? '예: pdf' : '예: 보안'}
          className="flex-1 min-w-28 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <input
          type="text"
          value={folderName}
          onChange={(e) => setFolderName(e.target.value)}
          placeholder="생성될 폴더명"
          className="flex-1 min-w-28 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <Button type="submit" size="sm">
          <Plus size={14} /> 추가
        </Button>
      </div>
      {error && <p className="text-xs text-red-500 mt-2">{error}</p>}
    </form>
  )
}

function FolderPreview({ rules }) {
  if (rules.length === 0) return null

  // 규칙 우선순위 순서로 폴더 구조 예시 생성
  const sorted = [...rules].sort((a, b) => a.priority - b.priority)
  const path = sorted.map((r) => r.folder_name).join(' / ')

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        <FolderTree size={15} className="text-gray-400" />
        <p className="text-xs font-semibold text-gray-500">폴더 구조 미리보기</p>
      </div>
      <p className="text-sm text-gray-700 font-mono">{path}</p>
      <p className="text-xs text-gray-400 mt-1">예: 파일이 이 경로로 분류됩니다</p>
    </div>
  )
}

export default function RuleManager() {
  const navigate = useNavigate()
  const { rules, setRules, addRule, removeRule, reorderRules } = useRuleStore()
  const [loading, setLoading] = useState(true)

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
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

  const handleAdd = async ({ type, value, folderName }) => {
    const nextPriority = rules.length > 0 ? Math.max(...rules.map((r) => r.priority)) + 1 : 1
    try {
      const newRule = await createRule({ priority: nextPriority, type, value, folderName })
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

  const handleDragEnd = async (event) => {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const oldIndex = rules.findIndex((r) => r.id === active.id)
    const newIndex = rules.findIndex((r) => r.id === over.id)
    const reordered = arrayMove(rules, oldIndex, newIndex).map((r, i) => ({
      ...r,
      priority: i + 1,
    }))

    reorderRules(reordered)

    // 변경된 우선순위 서버에 저장
    await Promise.all(
      reordered.map((r) => updateRule(r.id, { priority: r.priority }))
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 헤더 */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-gray-600">
          <ArrowLeft size={18} />
        </button>
        <div>
          <h1 className="text-lg font-bold text-gray-900">규칙 관리</h1>
          <p className="text-xs text-gray-500">드래그로 우선순위를 조정하세요</p>
        </div>
      </header>

      <div className="max-w-2xl mx-auto px-6 py-6 space-y-5">
        {/* 규칙 추가 폼 */}
        <AddRuleForm onAdd={handleAdd} />

        {/* 폴더 구조 미리보기 */}
        <FolderPreview rules={rules} />

        {/* 규칙 목록 */}
        {loading ? (
          <div className="text-center py-8 text-gray-400 text-sm">불러오는 중...</div>
        ) : rules.length === 0 ? (
          <div className="text-center py-12 text-gray-400 text-sm">
            등록된 규칙이 없습니다. 위에서 규칙을 추가하세요.
          </div>
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={rules.map((r) => r.id)}
              strategy={verticalListSortingStrategy}
            >
              <div className="space-y-2">
                {rules.map((rule) => (
                  <SortableRuleRow key={rule.id} rule={rule} onDelete={handleDelete} />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>
    </div>
  )
}
