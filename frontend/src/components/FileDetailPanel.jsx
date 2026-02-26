import { useState, useEffect } from 'react'
import { X, Save, FileText, Tag, BarChart2, Layers } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { updateFile } from '@/api/files'
import useFileStore from '@/store/fileStore'

const TIER_LABELS = { 1: 'Tier 1 규칙', 2: 'Tier 2 임베딩', 3: 'Tier 3 LLM' }
const TIER_COLORS = { 1: 'secondary', 2: 'default', 3: 'warning' }

function ConfidenceBar({ score }) {
  const pct = Math.round(score * 100)
  const color = score < 0.31 ? 'bg-red-400' : score < 0.5 ? 'bg-yellow-400' : 'bg-green-400'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-100 rounded-full h-1.5">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-medium text-gray-600 w-8 text-right">{pct}%</span>
    </div>
  )
}

export default function FileDetailPanel({ file, onClose }) {
  const { updateFile: updateStore } = useFileStore()
  const [category, setCategory] = useState(file?.category || '')
  const [tag, setTag] = useState(file?.tag || '')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    setCategory(file?.category || '')
    setTag(file?.tag || '')
    setSaved(false)
  }, [file?.id])

  if (!file) return null

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await updateFile(file.id, { category, tag })
      updateStore(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      alert('저장에 실패했습니다.')
    } finally {
      setSaving(false)
    }
  }

  const isDirty = category !== (file.category || '') || tag !== (file.tag || '')

  return (
    <div className="w-80 bg-white border-l border-gray-200 flex flex-col h-full shadow-lg">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
        <h3 className="font-semibold text-gray-800 text-sm truncate flex-1 mr-2">{file.filename}</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 shrink-0">
          <X size={18} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        {/* 파일 정보 */}
        <section>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">파일 정보</p>
          <div className="space-y-1.5 text-sm text-gray-600">
            <div className="flex items-start gap-2">
              <FileText size={14} className="text-gray-400 mt-0.5 shrink-0" />
              <span className="break-all text-xs">{file.path}</span>
            </div>
            <div className="flex gap-4 text-xs text-gray-500 mt-1">
              <span>{file.extension?.toUpperCase() || '-'}</span>
              <span>{file.size ? `${(file.size / 1024).toFixed(1)} KB` : '-'}</span>
            </div>
          </div>
        </section>

        {/* 분류 근거 */}
        <section>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">분류 근거</p>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Layers size={14} className="text-gray-400" />
              <Badge variant={TIER_COLORS[file.tier_used] || 'secondary'}>
                {TIER_LABELS[file.tier_used] || '-'}
              </Badge>
              {file.is_manual && <Badge variant="outline">수동</Badge>}
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">신뢰도</p>
              <ConfidenceBar score={file.confidence_score} />
            </div>
          </div>
        </section>

        {/* 수동 편집 */}
        <section>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">분류 수정</p>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">카테고리</label>
              <input
                type="text"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="카테고리 입력"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">태그</label>
              <div className="relative">
                <Tag size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  value={tag}
                  onChange={(e) => setTag(e.target.value)}
                  placeholder="태그 입력"
                  className="w-full border border-gray-200 rounded-lg pl-8 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
                />
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* 저장 버튼 */}
      <div className="px-5 py-4 border-t border-gray-100">
        <Button
          onClick={handleSave}
          disabled={!isDirty || saving}
          className="w-full"
          variant={saved ? 'outline' : 'default'}
        >
          {saving ? '저장 중...' : saved ? '저장됨 ✓' : '변경사항 저장'}
        </Button>
      </div>
    </div>
  )
}
