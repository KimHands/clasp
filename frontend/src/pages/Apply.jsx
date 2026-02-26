import { useEffect, useState } from 'react'
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

// 충돌 해결 옵션
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
        className="flex items-center gap-1.5 w-full text-left py-1 hover:bg-gray-50 rounded px-2 transition-colors"
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {hasChildren ? (
          open ? <ChevronDown size={13} className="text-gray-400 shrink-0" /> : <ChevronRight size={13} className="text-gray-400 shrink-0" />
        ) : (
          <span className="w-3 shrink-0" />
        )}
        {node.folder ? (
          <>
            <FolderOpen size={14} className="text-blue-400 shrink-0" />
            <span className="text-sm font-medium text-gray-700">{node.folder}</span>
            {hasChildren && (
              <span className="ml-1 text-xs text-gray-400">({node.children.length})</span>
            )}
          </>
        ) : (
          <span className="text-sm text-gray-600 truncate">{node.file}</span>
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

function ConflictModal({ conflicts, onConfirm, onCancel }) {
  const [resolution, setResolution] = useState('rename')

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="px-6 py-5 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <AlertTriangle size={18} className="text-amber-500" />
            <h2 className="text-base font-bold text-gray-900">파일 충돌 감지</h2>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {conflicts.length}개 파일이 대상 경로에 이미 존재합니다.
          </p>
        </div>

        <div className="px-6 py-4 max-h-40 overflow-y-auto">
          {conflicts.slice(0, 5).map((c, i) => (
            <div key={i} className="flex items-center gap-2 py-1.5 border-b border-gray-50 last:border-0">
              <FileX size={13} className="text-red-400 shrink-0" />
              <span className="text-xs text-gray-600 truncate">{c.filename}</span>
            </div>
          ))}
          {conflicts.length > 5 && (
            <p className="text-xs text-gray-400 mt-1">외 {conflicts.length - 5}개...</p>
          )}
        </div>

        <div className="px-6 py-4 space-y-2">
          <p className="text-xs font-semibold text-gray-500 mb-3">충돌 처리 방법 선택</p>
          {RESOLUTION_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                resolution === opt.value
                  ? 'border-blue-400 bg-blue-50'
                  : 'border-gray-200 hover:bg-gray-50'
              }`}
            >
              <input
                type="radio"
                name="resolution"
                value={opt.value}
                checked={resolution === opt.value}
                onChange={() => setResolution(opt.value)}
                className="mt-0.5"
              />
              <div>
                <p className="text-sm font-medium text-gray-800">{opt.label}</p>
                <p className="text-xs text-gray-500">{opt.desc}</p>
              </div>
            </label>
          ))}
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex gap-3">
          <Button variant="outline" onClick={onCancel} className="flex-1">취소</Button>
          <Button onClick={() => onConfirm(resolution)} className="flex-1">정리 적용</Button>
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
    <div className="min-h-screen bg-gray-50">
      {/* 헤더 */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3">
        <button onClick={() => navigate('/result')} className="text-gray-400 hover:text-gray-600">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-bold text-gray-900">정리 적용</h1>
          <div className="flex items-center gap-1.5 text-xs text-gray-500 mt-0.5">
            <FolderOpen size={12} />
            <span className="truncate">{selectedFolder}</span>
          </div>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-6 py-6 space-y-5">

        {/* 적용 완료 결과 */}
        {applyResult && (
          <div className="bg-green-50 border border-green-200 rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle2 size={18} className="text-green-500" />
              <h2 className="font-semibold text-green-800">정리 완료</h2>
            </div>
            <div className="flex gap-6 text-sm">
              <div><span className="text-green-700 font-bold text-lg">{applyResult.moved}</span><span className="text-green-600 ml-1">이동됨</span></div>
              <div><span className="text-gray-600 font-bold text-lg">{applyResult.skipped}</span><span className="text-gray-500 ml-1">건너뜀</span></div>
              {applyResult.failed > 0 && (
                <div><span className="text-red-600 font-bold text-lg">{applyResult.failed}</span><span className="text-red-500 ml-1">실패</span></div>
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
          <div className="bg-blue-50 border border-blue-200 rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-2">
              <RotateCcw size={16} className="text-blue-500" />
              <h2 className="font-semibold text-blue-800">되돌리기 완료</h2>
            </div>
            <p className="text-sm text-blue-700">{undoResult.restored}개 파일이 원래 위치로 복원되었습니다.</p>
            {undoResult.unrestorable?.length > 0 && (
              <div className="mt-3">
                <p className="text-xs font-semibold text-red-500 mb-1">복구 불가 항목</p>
                {undoResult.unrestorable.map((u, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-red-600">
                    <FileX size={12} />
                    <span>{u.filename}</span>
                    <span className="text-red-400">({u.reason})</span>
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
              <div className="flex items-center justify-center py-16 text-gray-400 gap-2">
                <Loader2 size={18} className="animate-spin" />
                <span className="text-sm">미리보기 생성 중...</span>
              </div>
            ) : preview ? (
              <>
                {/* 요약 카드 */}
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { label: '이동 대상', value: preview.total_files, color: 'text-blue-600' },
                    { label: '제외 (미분류)', value: preview.excluded_files, color: 'text-amber-600' },
                    { label: '생성 폴더', value: preview.folders_to_create, color: 'text-green-600' },
                  ].map((item) => (
                    <div key={item.label} className="bg-white border border-gray-200 rounded-xl p-4 text-center">
                      <p className={`text-2xl font-bold ${item.color}`}>{item.value}</p>
                      <p className="text-xs text-gray-500 mt-1">{item.label}</p>
                    </div>
                  ))}
                </div>

                {/* 충돌 경고 */}
                {preview.conflicts.length > 0 && (
                  <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex items-center gap-2">
                    <AlertTriangle size={15} className="text-amber-500 shrink-0" />
                    <span className="text-sm text-amber-700">
                      {preview.conflicts.length}개 파일 충돌이 감지되었습니다. 적용 시 처리 방법을 선택합니다.
                    </span>
                  </div>
                )}

                {/* 폴더 트리 미리보기 */}
                <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
                  <div className="px-5 py-3 border-b border-gray-100 flex items-center gap-2">
                    <FolderOpen size={15} className="text-gray-400" />
                    <h3 className="text-sm font-semibold text-gray-700">폴더 구조 미리보기</h3>
                  </div>
                  <div className="px-3 py-3 max-h-72 overflow-y-auto">
                    {preview.preview_tree.length > 0 ? (
                      preview.preview_tree.map((node, i) => (
                        <TreeNode key={i} node={node} depth={0} />
                      ))
                    ) : (
                      <p className="text-sm text-gray-400 text-center py-6">이동할 파일이 없습니다</p>
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
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
            <h2 className="text-base font-bold text-gray-900 mb-2">정리를 적용할까요?</h2>
            <p className="text-sm text-gray-500 mb-5">
              {preview.total_files}개 파일이 이동됩니다. 이 작업은 되돌리기가 가능합니다.
            </p>
            <div className="flex gap-3">
              <Button variant="outline" onClick={() => setShowConfirmModal(false)} className="flex-1">취소</Button>
              <Button onClick={() => handleConfirmApply('rename')} className="flex-1">확인</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
