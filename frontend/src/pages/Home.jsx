import { useNavigate } from 'react-router-dom'
import { FolderOpen, Clock, ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import useScanStore from '@/store/scanStore'

export default function Home() {
  const navigate = useNavigate()
  const { selectedFolder, recentFolders, setSelectedFolder } = useScanStore()

  const handleSelectFolder = async () => {
    // Electron IPC로 폴더 선택 다이얼로그 호출
    const folderPath = await window.electronAPI?.openFolderDialog()
    if (!folderPath) return
    setSelectedFolder(folderPath)
  }

  const handleStartScan = () => {
    if (!selectedFolder) return
    navigate('/scan')
  }

  const handleRecentFolder = (path) => {
    setSelectedFolder(path)
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-8">
      <div className="w-full max-w-2xl">
        {/* 헤더 */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-3">Clasp</h1>
          <p className="text-gray-500 text-lg">파일을 자동으로 분류하고 시각화합니다</p>
        </div>

        {/* 폴더 선택 카드 */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 mb-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">정리할 폴더 선택</h2>

          {/* 선택된 폴더 표시 */}
          {selectedFolder ? (
            <div className="flex items-center gap-3 bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 mb-4">
              <FolderOpen className="text-blue-500 shrink-0" size={20} />
              <span className="text-sm text-blue-800 truncate flex-1">{selectedFolder}</span>
              <button
                onClick={handleSelectFolder}
                className="text-xs text-blue-500 hover:text-blue-700 shrink-0"
              >
                변경
              </button>
            </div>
          ) : (
            <div
              onClick={handleSelectFolder}
              className="border-2 border-dashed border-gray-300 rounded-lg px-6 py-10 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors mb-4"
            >
              <FolderOpen className="mx-auto text-gray-400 mb-3" size={36} />
              <p className="text-gray-500 text-sm">클릭하여 폴더를 선택하세요</p>
            </div>
          )}

          <div className="flex gap-3">
            <Button variant="outline" onClick={handleSelectFolder} className="flex-1">
              <FolderOpen size={16} />
              폴더 선택
            </Button>
            <Button
              onClick={handleStartScan}
              disabled={!selectedFolder}
              className="flex-1"
            >
              스캔 시작
              <ArrowRight size={16} />
            </Button>
          </div>
        </div>

        {/* 최근 작업 목록 */}
        {recentFolders.length > 0 && (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center gap-2 mb-4">
              <Clock size={16} className="text-gray-400" />
              <h3 className="text-sm font-medium text-gray-600">최근 작업</h3>
            </div>
            <ul className="space-y-2">
              {recentFolders.map((folder) => (
                <li key={folder}>
                  <button
                    onClick={() => handleRecentFolder(folder)}
                    className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-50 text-left transition-colors"
                  >
                    <FolderOpen size={15} className="text-gray-400 shrink-0" />
                    <span className="text-sm text-gray-700 truncate">{folder}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
