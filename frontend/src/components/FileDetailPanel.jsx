import { useState, useEffect } from 'react'
import { X, FileText, Tag, Layers, AlignLeft, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { updateFile } from '@/api/files'
import useFileStore from '@/store/fileStore'

const TIER_LABELS = { 1: 'Tier 1 규칙', 2: 'Tier 2 임베딩', 3: 'Tier 3 LLM' }
const TIER_COLORS = { 1: 'secondary', 2: 'default', 3: 'warning' }

function ConfidenceBar({ score }) {
  const pct = Math.round(score * 100)
  const color = score < 0.31 ? 'bg-red-400' : score < 0.5 ? 'bg-amber-400' : 'bg-emerald-400'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-[var(--input-bg)] rounded-full h-1.5 overflow-hidden">
        <div className={`h-1.5 rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-medium text-[hsl(var(--foreground)/0.7)] w-8 text-right">{pct}%</span>
    </div>
  )
}

export default function FileDetailPanel({ file, onClose }) {
  const { updateFile: updateStore } = useFileStore()
  const [category, setCategory] = useState(file?.category || '')
  const [tag, setTag] = useState(file?.tag || '')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [summaryExpanded, setSummaryExpanded] = useState(false)

  useEffect(() => {
    setCategory(file?.category || '')
    setTag(file?.tag || '')
    setSaved(false)
    setSummaryExpanded(false)
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
    <div className="w-80 glass-heavy flex flex-col h-full border-l border-[var(--glass-border)]">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--glass-border)]">
        <h3 className="font-semibold text-[hsl(var(--foreground))] text-sm truncate flex-1 mr-2">{file.filename}</h3>
        <button onClick={onClose} className="text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] shrink-0 transition-colors">
          <X size={18} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        {/* 파일 정보 */}
        <section>
          <p className="text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wide mb-2">파일 정보</p>
          <div className="space-y-1.5 text-sm text-[hsl(var(--foreground)/0.7)]">
            <div className="flex items-start gap-2">
              <FileText size={14} className="text-[hsl(var(--muted-foreground))] mt-0.5 shrink-0" />
              <span className="break-all text-xs">{file.path}</span>
            </div>
            <div className="flex gap-4 text-xs text-[hsl(var(--muted-foreground))] mt-1">
              <span>{file.extension?.toUpperCase() || '-'}</span>
              <span>{file.size ? `${(file.size / 1024).toFixed(1)} KB` : '-'}</span>
            </div>
          </div>
        </section>

        {/* 분류 근거 */}
        <section>
          <p className="text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wide mb-2">분류 근거</p>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Layers size={14} className="text-[hsl(var(--muted-foreground))]" />
              <Badge variant={TIER_COLORS[file.tier_used] || 'secondary'}>
                {TIER_LABELS[file.tier_used] || '-'}
              </Badge>
              {file.is_manual && <Badge variant="outline">수동</Badge>}
            </div>
            <div>
              <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">신뢰도</p>
              <ConfidenceBar score={file.confidence_score} />
            </div>
          </div>
        </section>

        {/* 파일 내용 요약 */}
        {file.extracted_text_summary && (
          <section>
            <button
              onClick={() => setSummaryExpanded((v) => !v)}
              className="w-full flex items-center justify-between text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wide mb-2 hover:text-[hsl(var(--foreground))] transition-colors"
            >
              <span className="flex items-center gap-1.5">
                <AlignLeft size={12} />
                내용 요약
              </span>
              {summaryExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            </button>
            {summaryExpanded && (
              <div className="glass rounded-xl px-3 py-2.5 text-xs text-[hsl(var(--foreground)/0.7)] leading-relaxed whitespace-pre-wrap break-words max-h-48 overflow-y-auto">
                {file.extracted_text_summary}
              </div>
            )}
          </section>
        )}

        {/* 수동 편집 */}
        <section>
          <p className="text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wide mb-2">분류 수정</p>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">카테고리</label>
              <input
                type="text"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="카테고리 입력"
                className="w-full glass-input px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-[hsl(var(--muted-foreground))] mb-1 block">태그</label>
              <div className="relative">
                <Tag size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[hsl(var(--muted-foreground))]" />
                <input
                  type="text"
                  value={tag}
                  onChange={(e) => setTag(e.target.value)}
                  placeholder="태그 입력"
                  className="w-full glass-input pl-8 pr-3 py-2 text-sm"
                />
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* 저장 버튼 */}
      <div className="px-5 py-4 border-t border-[var(--glass-border)]">
        <Button
          onClick={handleSave}
          disabled={!isDirty || saving}
          className="w-full"
          variant={saved ? 'outline' : 'default'}
        >
          {saving ? '저장 중...' : saved ? '저장됨' : '변경사항 저장'}
        </Button>
      </div>
    </div>
  )
}
