import { useNavigate } from 'react-router-dom'
import { FolderOpen, Clock, ArrowRight, Sun, Moon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import useScanStore from '@/store/scanStore'
import useThemeStore from '@/store/themeStore'

export default function Home() {
  const navigate = useNavigate()
  const { selectedFolder, recentFolders, setSelectedFolder } = useScanStore()
  const { resolvedTheme, toggleTheme } = useThemeStore()

  const handleSelectFolder = async () => {
    // Electron IPC로 폴더 선택 다이얼로그 호출
    const folderPath = await window.electronAPI?.openFolderDialog()
    if (!folderPath) return
    setSelectedFolder(folderPath)
  }

  const handleStartScan = () => {
    if (!selectedFolder) return
    useScanStore.getState().resetScan()
    navigate('/scan')
  }

  const handleRecentFolder = (path) => {
    setSelectedFolder(path)
  }

  return (
    <div className="min-h-screen mesh-gradient flex flex-col items-center justify-center p-8 relative">
      {/* 테마 토글 */}
      <button
        onClick={toggleTheme}
        className="absolute top-5 right-5 w-10 h-10 rounded-full glass flex items-center justify-center text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors"
      >
        {resolvedTheme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
      </button>

      <div className="w-full max-w-2xl">
        {/* 헤더 */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-[hsl(var(--foreground))] mb-3 tracking-tight">Clasp</h1>
          <p className="text-[hsl(var(--muted-foreground))] text-lg">파일을 자동으로 분류하고 시각화합니다</p>
        </div>

        {/* 폴더 선택 카드 */}
        <div className="glass-card p-8 mb-6">
          <h2 className="text-lg font-semibold text-[hsl(var(--foreground))] mb-4">정리할 폴더 선택</h2>

          {selectedFolder ? (
            <div className="flex items-center gap-3 bg-[hsl(var(--primary)/0.08)] border border-[hsl(var(--primary)/0.2)] rounded-xl px-4 py-3 mb-4">
              <FolderOpen className="text-[hsl(var(--primary))] shrink-0" size={20} />
              <span className="text-sm text-[hsl(var(--foreground))] truncate flex-1">{selectedFolder}</span>
              <button
                onClick={handleSelectFolder}
                className="text-xs text-[hsl(var(--primary))] hover:brightness-110 shrink-0"
              >
                변경
              </button>
            </div>
          ) : (
            <div
              onClick={handleSelectFolder}
              className="border-2 border-dashed border-[hsl(var(--border))] rounded-xl px-6 py-10 text-center cursor-pointer hover:border-[hsl(var(--primary)/0.5)] hover:bg-[hsl(var(--primary)/0.04)] transition-all duration-200 mb-4"
            >
              <FolderOpen className="mx-auto text-[hsl(var(--muted-foreground))] mb-3" size={36} />
              <p className="text-[hsl(var(--muted-foreground))] text-sm">클릭하여 폴더를 선택하세요</p>
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
          <div className="glass-card p-6">
            <div className="flex items-center gap-2 mb-4">
              <Clock size={16} className="text-[hsl(var(--muted-foreground))]" />
              <h3 className="text-sm font-medium text-[hsl(var(--muted-foreground))]">최근 작업</h3>
            </div>
            <ul className="space-y-1">
              {recentFolders.map((folder) => (
                <li key={folder}>
                  <button
                    onClick={() => handleRecentFolder(folder)}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-[var(--input-bg)] text-left transition-all duration-200"
                  >
                    <FolderOpen size={15} className="text-[hsl(var(--muted-foreground))] shrink-0" />
                    <span className="text-sm text-[hsl(var(--foreground)/0.8)] truncate">{folder}</span>
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
