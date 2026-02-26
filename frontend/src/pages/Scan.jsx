import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, CheckCircle2, XCircle, FolderOpen, ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import useScanStore from '@/store/scanStore'
import useFileStore from '@/store/fileStore'
import { startScan, connectProgress } from '@/api/scan'

const STAGES = [
  { id: 1, label: '파일 목록 수집' },
  { id: 2, label: '메타데이터 분석' },
  { id: 3, label: '표지 탐지' },
  { id: 4, label: '본문 추출' },
  { id: 5, label: '분류 엔진 처리' },
  { id: 6, label: '유사도 계산' },
  { id: 7, label: '완료' },
]

export default function Scan() {
  const navigate = useNavigate()
  const esRef = useRef(null)

  const {
    selectedFolder,
    scanId,
    scanStatus,
    progress,
    setScanId,
    setScanStatus,
    setProgress,
    resetScan,
  } = useScanStore()

  const { reset: resetFiles } = useFileStore()

  // 페이지 진입 시 자동 스캔 시작
  useEffect(() => {
    if (!selectedFolder) {
      navigate('/')
      return
    }
    if (scanStatus === 'idle') {
      handleStartScan()
    }
    return () => {
      esRef.current?.close()
    }
  }, [])

  const handleStartScan = async () => {
    try {
      setScanStatus('scanning')
      resetFiles()

      const data = await startScan(selectedFolder)
      const newScanId = data.scan_id
      setScanId(newScanId)

      // SSE 연결
      esRef.current = connectProgress(
        newScanId,
        (data) => {
          setProgress({
            stage: data.stage,
            message: data.message,
            total: data.total,
            completed: data.completed,
            currentFile: data.current_file,
          })
        },
        () => {
          setScanStatus('completed')
        },
        () => {
          setScanStatus('error')
        }
      )
    } catch (err) {
      setScanStatus('error')
    }
  }

  const handleGoResult = () => {
    navigate('/result')
  }

  const handleRetry = () => {
    resetScan()
    handleStartScan()
  }

  const handleBack = () => {
    esRef.current?.close()
    resetScan()
    navigate('/')
  }

  const currentStage = progress.stage
  const isCompleted = scanStatus === 'completed'
  const isError = scanStatus === 'error'
  const isScanning = scanStatus === 'scanning'

  const progressPercent =
    progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-8">
      <div className="w-full max-w-2xl">
        {/* 헤더 */}
        <div className="flex items-center gap-3 mb-8">
          <button onClick={handleBack} className="text-gray-400 hover:text-gray-600 transition-colors">
            <ArrowLeft size={20} />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">폴더 스캔</h1>
            <div className="flex items-center gap-1.5 mt-0.5">
              <FolderOpen size={13} className="text-gray-400" />
              <span className="text-xs text-gray-500 truncate max-w-md">{selectedFolder}</span>
            </div>
          </div>
        </div>

        {/* 진행 상황 카드 */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 mb-6">
          {/* 전체 프로그레스 바 */}
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm font-medium text-gray-700">
                {isCompleted ? '스캔 완료' : isError ? '오류 발생' : progress.message || '준비 중...'}
              </span>
              <span className="text-sm text-gray-500">
                {progress.total > 0 && `${progress.completed} / ${progress.total}`}
              </span>
            </div>
            <div className="w-full bg-gray-100 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all duration-300 ${
                  isError ? 'bg-red-500' : isCompleted ? 'bg-green-500' : 'bg-blue-500'
                }`}
                style={{ width: `${isCompleted ? 100 : progressPercent}%` }}
              />
            </div>
            {progress.currentFile && (
              <p className="text-xs text-gray-400 mt-1.5 truncate">
                처리 중: {progress.currentFile}
              </p>
            )}
          </div>

          {/* 단계별 상태 */}
          <div className="space-y-3">
            {STAGES.map((stage) => {
              const isDone = currentStage > stage.id || isCompleted
              const isActive = currentStage === stage.id && isScanning
              const isPending = currentStage < stage.id && !isCompleted

              return (
                <div key={stage.id} className="flex items-center gap-3">
                  <div className="w-6 h-6 flex items-center justify-center shrink-0">
                    {isDone ? (
                      <CheckCircle2 size={20} className="text-green-500" />
                    ) : isActive ? (
                      <Loader2 size={20} className="text-blue-500 animate-spin" />
                    ) : isError && currentStage === stage.id ? (
                      <XCircle size={20} className="text-red-500" />
                    ) : (
                      <div className="w-5 h-5 rounded-full border-2 border-gray-200" />
                    )}
                  </div>
                  <span
                    className={`text-sm ${
                      isDone
                        ? 'text-gray-700 font-medium'
                        : isActive
                        ? 'text-blue-600 font-semibold'
                        : 'text-gray-400'
                    }`}
                  >
                    {stage.label}
                  </span>
                  {isActive && progress.total > 0 && (
                    <span className="ml-auto text-xs text-gray-400">
                      {progress.completed}/{progress.total}
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* 액션 버튼 */}
        {isCompleted && (
          <div className="flex gap-3">
            <Button variant="outline" onClick={handleBack} className="flex-1">
              처음으로
            </Button>
            <Button onClick={handleGoResult} className="flex-1">
              분류 결과 확인
            </Button>
          </div>
        )}

        {isError && (
          <div className="flex gap-3">
            <Button variant="outline" onClick={handleBack} className="flex-1">
              돌아가기
            </Button>
            <Button variant="destructive" onClick={handleRetry} className="flex-1">
              다시 시도
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
