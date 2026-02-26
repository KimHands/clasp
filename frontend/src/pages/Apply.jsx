import { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft, FolderOpen, ChevronRight, ChevronDown,
  AlertTriangle, CheckCircle2, RotateCcw, Loader2, FileX
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import useScanStore from '@/store/scanStore'
import useApplyStore from '@/store/applyStore'
import { getApplyPreview, applyOrganize, undoApply } from '@/api/apply'

const RESOLUTION_OPTIONS = [
  { value: 'rename', label: '이름 변경', desc: '파일명에 번호를 추가합니다 (report_1.pdf)' },
  { value: 'overwrite', label: '덮어쓰기', desc: '기존 파일을 덮어씁니다' },
  { value: 'skip', label: '건너뛰기', desc: '충돌 파일은 이동하지 않습니다' },
]

function TreeNode({ node, depth = 0 }) {
  const [open, setOpen] = useState(depth === 0)
  const hasChildren = node.children && node.children.length > 0

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 w-full text-left py-1.5 hover:bg-[var(--input-bg)] rounded-lg px-2 transition-all duration-150"
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {hasChildren ? (
          open ? <ChevronDown size={13} className="text-[hsl(var(--muted-foreground))] shrink-0" /> : <ChevronRight size={13} className="text-[hsl(var(--muted-foreground))] shrink-0" />
        ) : (
          <span className="w-3 shrink-0" />
        )}
        {node.folder ? (
          <>
            <FolderOpen size={14} className="text-[hsl(var(--primary))] shrink-0" />
            <span className="text-sm font-medium text-[hsl(var(--foreground))]">{node.folder}</span>
            {hasChildren && (
              <span className="ml-1 text-xs text-[hsl(var(--muted-foreground))]">({node.children.length})</span>
            )}
          </>
        ) : (
          <span className="text-sm text-[hsl(var(--foreground)/0.7)] truncate">{node.file}</span>
        )}
      </button>
      {open && hasChildren && (
        <div>
          {node.children.map((child, i) => (
            <TreeNode key={i} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

function useModalKeyboard(onClose) {
  const ref = useRef(null)

  useEffect(() => {
    const el = ref.current
    if (el) el.focus()

    const handleKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  return ref
}

function ConflictModal({ conflicts, onConfirm, onCancel }) {
  const [resolution, setResolution] = useState('rename')
  const stableCancel = useCallback(() => onCancel(), [onCancel])
  const modalRef = useModalKeyboard(stableCancel)

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) onCancel()
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={handleBackdropClick}>
      <div ref={modalRef} role="dialog" aria-modal="true" aria-labelledby="conflict-title" tabIndex={-1} className="glass-heavy rounded-2xl w-full max-w-md overflow-hidden outline-none">
        <div className="px-6 py-5 border-b border-[var(--glass-border)]">
          <div className="flex items-center gap-2">
            <AlertTriangle size={18} className="text-amber-500" />
            <h2 id="conflict-title" className="text-base font-bold text-[hsl(var(--foreground))]">파일 충돌 감지</h2>
          </div>
          <p className="text-sm text-[hsl(var(--muted-foreground))] mt-1">
            {conflicts.length}개 파일이 대상 경로에 이미 존재합니다.
          </p>
        </div>

        <div className="px-6 py-4 max-h-40 overflow-y-auto">
          {conflicts.slice(0, 5).map((c, i) => (
            <div key={i} className="flex items-center gap-2 py-1.5 border-b border-[var(--glass-border)] last:border-0">
              <FileX size={13} className="text-red-400 shrink-0" />
              <span className="text-xs text-[hsl(var(--foreground)/0.7)] truncate">{c.filename}</span>
            </div>
          ))}
          {conflicts.length > 5 && (
            <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">외 {conflicts.length - 5}개...</p>
          )}
        </div>

        <div className="px-6 py-4 space-y-2">
          <p className="text-xs font-semibold text-[hsl(var(--muted-foreground))] mb-3">충돌 처리 방법 선택</p>
          {RESOLUTION_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all duration-200 ${
                resolution === opt.value
                  ? 'border-[hsl(var(--primary)/0.5)] bg-[hsl(var(--primary)/0.05)]'
                  : 'border-[var(--glass-border)] hover:bg-[var(--input-bg)]'
              }`}
            >
              <input
                type="radio"
                name="resolution"
                value={opt.value}
                checked={resolution === opt.value}
                onChange={() => setResolution(opt.value)}
                className="mt-0.5 accent-[hsl(var(--primary))]"
              />
              <div>
                <p className="text-sm font-medium text-[hsl(var(--foreground))]">{opt.label}</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">{opt.desc}</p>
              </div>
            </label>
          ))}
        </div>

        <div className="px-6 py-4 border-t border-[var(--glass-border)] flex gap-3">
          <Button variant="outline" onClick={onCancel} className="flex-1">취소</Button>
          <Button onClick={() => onConfirm(resolution)} className="flex-1">정리 적용</Button>
        </div>
      </div>
    </div>
  )
}

function ConfirmModal({ totalFiles, onConfirm, onCancel }) {
  const stableCancel = useCallback(() => onCancel(), [onCancel])
  const modalRef = useModalKeyboard(stableCancel)

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) onCancel()
  }

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={handleBackdropClick}>
      <div ref={modalRef} role="dialog" aria-modal="true" aria-labelledby="confirm-title" tabIndex={-1} className="glass-heavy rounded-2xl w-full max-w-sm p-6 outline-none">
        <h2 id="confirm-title" className="text-base font-bold text-[hsl(var(--foreground))] mb-2">정리를 적용할까요?</h2>
        <p className="text-sm text-[hsl(var(--muted-foreground))] mb-5">
          {totalFiles}개 파일이 이동됩니다. 이 작업은 되돌리기가 가능합니다.
        </p>
        <div className="flex gap-3">
          <Button variant="outline" onClick={onCancel} className="flex-1">취소</Button>
          <Button onClick={onConfirm} className="flex-1">확인</Button>
        </div>
      </div>
    </div>
  )
}

export default function Apply() {
  const navigate = useNavigate()
  const { scanId, selectedFolder } = useScanStore()
  const { preview, lastActionLogId, applyResult, undoResult,
    setPreview, setLastActionLogId, setApplyResult, setUndoResult, reset } = useApplyStore()

  const [loading, setLoading] = useState(false)
  const [applying, setApplying] = useState(false)
  const [undoing, setUndoing] = useState(false)
  const [showConflictModal, setShowConflictModal] = useState(false)
  const [showConfirmModal, setShowConfirmModal] = useState(false)

  useEffect(() => {
    if (!scanId) { navigate('/'); return }
    reset()
    loadPreview()
  }, [scanId])

  const loadPreview = async () => {
    setLoading(true)
    try {
      const data = await getApplyPreview(scanId)
      setPreview(data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const handleApplyClick = () => {
    if (!preview) return
    if (preview.conflicts.length > 0) {
      setShowConflictModal(true)
    } else {
      setShowConfirmModal(true)
    }
  }

  const handleConfirmApply = async (resolution = 'rename') => {
    setShowConflictModal(false)
    setShowConfirmModal(false)
    setApplying(true)
    try {
      const result = await applyOrganize({ scanId, conflictResolution: resolution })
      setApplyResult(result)
      setLastActionLogId(result.action_log_id)
    } catch (e) {
      alert('정리 적용에 실패했습니다.')
    } finally {
      setApplying(false)
    }
  }

  const handleUndo = async () => {
    if (!lastActionLogId) return
    setUndoing(true)
    try {
      const result = await undoApply({ actionLogId: lastActionLogId })
      setUndoResult(result)
      setApplyResult(null)
    } catch (e) {
      alert(e.message || '되돌리기에 실패했습니다.')
    } finally {
      setUndoing(false)
    }
  }

  return (
    <div className="min-h-screen mesh-gradient">
      {/* 헤더 */}
      <header className="glass-header px-6 py-4 flex items-center gap-3 sticky top-0 z-10">
        <button onClick={() => navigate('/result')} className="text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-bold text-[hsl(var(--foreground))]">정리 적용</h1>
          <div className="flex items-center gap-1.5 text-xs text-[hsl(var(--muted-foreground))] mt-0.5">
            <FolderOpen size={12} />
            <span className="truncate">{selectedFolder}</span>
          </div>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-6 py-6 space-y-5">

        {/* 적용 완료 결과 */}
        {applyResult && (
          <div className="glass-card p-5 border-emerald-500/20 bg-emerald-500/5">
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle2 size={18} className="text-emerald-500" />
              <h2 className="font-semibold text-emerald-600 dark:text-emerald-400">정리 완료</h2>
            </div>
            <div className="flex gap-6 text-sm">
              <div><span className="text-emerald-600 dark:text-emerald-400 font-bold text-lg">{applyResult.moved}</span><span className="text-emerald-600/70 dark:text-emerald-400/70 ml-1">이동됨</span></div>
              <div><span className="text-[hsl(var(--foreground))] font-bold text-lg">{applyResult.skipped}</span><span className="text-[hsl(var(--muted-foreground))] ml-1">건너뜀</span></div>
              {applyResult.failed > 0 && (
                <div><span className="text-red-500 font-bold text-lg">{applyResult.failed}</span><span className="text-red-500/70 ml-1">실패</span></div>
              )}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleUndo}
              disabled={undoing}
              className="mt-4"
            >
              {undoing ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
              되돌리기
            </Button>
          </div>
        )}

        {/* Undo 완료 결과 */}
        {undoResult && (
          <div className="glass-card p-5 border-[hsl(var(--primary)/0.2)] bg-[hsl(var(--primary)/0.04)]">
            <div className="flex items-center gap-2 mb-2">
              <RotateCcw size={16} className="text-[hsl(var(--primary))]" />
              <h2 className="font-semibold text-[hsl(var(--primary))]">되돌리기 완료</h2>
            </div>
            <p className="text-sm text-[hsl(var(--foreground)/0.8)]">{undoResult.restored}개 파일이 원래 위치로 복원되었습니다.</p>
            {undoResult.unrestorable?.length > 0 && (
              <div className="mt-3">
                <p className="text-xs font-semibold text-red-500 mb-1">복구 불가 항목</p>
                {undoResult.unrestorable.map((u, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-red-500">
                    <FileX size={12} />
                    <span>{u.filename}</span>
                    <span className="opacity-60">({u.reason})</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 미리보기 */}
        {!applyResult && !undoResult && (
          <>
            {loading ? (
              <div className="flex items-center justify-center py-16 text-[hsl(var(--muted-foreground))] gap-2">
                <Loader2 size={18} className="animate-spin" />
                <span className="text-sm">미리보기 생성 중...</span>
              </div>
            ) : preview ? (
              <>
                {/* 요약 카드 */}
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { label: '이동 대상', value: preview.total_files, color: 'text-[hsl(var(--primary))]' },
                    { label: '제외 (미분류)', value: preview.excluded_files, color: 'text-amber-500' },
                    { label: '생성 폴더', value: preview.folders_to_create, color: 'text-emerald-500' },
                  ].map((item) => (
                    <div key={item.label} className="glass-card p-4 text-center">
                      <p className={`text-2xl font-bold ${item.color}`}>{item.value}</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">{item.label}</p>
                    </div>
                  ))}
                </div>

                {/* 충돌 경고 */}
                {preview.conflicts.length > 0 && (
                  <div className="glass-card px-4 py-3 flex items-center gap-2 border-amber-500/20 bg-amber-500/5">
                    <AlertTriangle size={15} className="text-amber-500 shrink-0" />
                    <span className="text-sm text-amber-700 dark:text-amber-300">
                      {preview.conflicts.length}개 파일 충돌이 감지되었습니다. 적용 시 처리 방법을 선택합니다.
                    </span>
                  </div>
                )}

                {/* 폴더 트리 미리보기 */}
                <div className="glass-card overflow-hidden">
                  <div className="px-5 py-3 border-b border-[var(--glass-border)] flex items-center gap-2">
                    <FolderOpen size={15} className="text-[hsl(var(--muted-foreground))]" />
                    <h3 className="text-sm font-semibold text-[hsl(var(--foreground))]">폴더 구조 미리보기</h3>
                  </div>
                  <div className="px-3 py-3 max-h-72 overflow-y-auto">
                    {preview.preview_tree.length > 0 ? (
                      preview.preview_tree.map((node, i) => (
                        <TreeNode key={i} node={node} depth={0} />
                      ))
                    ) : (
                      <p className="text-sm text-[hsl(var(--muted-foreground))] text-center py-6">이동할 파일이 없습니다</p>
                    )}
                  </div>
                </div>

                {/* 적용 버튼 */}
                <div className="flex gap-3">
                  <Button variant="outline" onClick={() => navigate('/result')} className="flex-1">
                    취소
                  </Button>
                  <Button
                    onClick={handleApplyClick}
                    disabled={preview.total_files === 0 || applying}
                    className="flex-1"
                  >
                    {applying ? (
                      <><Loader2 size={14} className="animate-spin" /> 적용 중...</>
                    ) : (
                      `${preview.total_files}개 파일 정리 적용`
                    )}
                  </Button>
                </div>
              </>
            ) : null}
          </>
        )}
      </div>

      {/* 충돌 해결 모달 */}
      {showConflictModal && preview && (
        <ConflictModal
          conflicts={preview.conflicts}
          onConfirm={handleConfirmApply}
          onCancel={() => setShowConflictModal(false)}
        />
      )}

      {/* 충돌 없을 때 확인 모달 */}
      {showConfirmModal && preview && (
        <ConfirmModal
          totalFiles={preview.total_files}
          onConfirm={() => handleConfirmApply('rename')}
          onCancel={() => setShowConfirmModal(false)}
        />
      )}
    </div>
  )
}
