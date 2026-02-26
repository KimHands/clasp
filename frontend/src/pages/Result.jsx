import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  List, Network, Search, AlertTriangle,
  ArrowLeft, FolderOpen, Settings, X
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import GraphView from '@/components/GraphView'
import FileDetailPanel from '@/components/FileDetailPanel'
import useScanStore from '@/store/scanStore'
import useFileStore from '@/store/fileStore'
import { getFiles } from '@/api/files'

const TIER_LABELS = { 1: 'T1', 2: 'T2', 3: 'T3' }
const TIER_COLORS = { 1: 'secondary', 2: 'default', 3: 'warning' }

function HighlightText({ text, query }) {
  if (!query || !text) return <>{text}</>
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const parts = text.split(new RegExp(`(${escaped})`, 'gi'))
  return (
    <>
      {parts.map((part, i) =>
        part.toLowerCase() === query.toLowerCase()
          ? <mark key={i} className="bg-amber-500/20 text-amber-700 dark:text-amber-300 rounded-sm px-0.5">{part}</mark>
          : part
      )}
    </>
  )
}

function ConfidenceDot({ score }) {
  const color = score < 0.31 ? 'bg-red-400' : score < 0.5 ? 'bg-amber-400' : 'bg-emerald-400'
  return <span className={`inline-block w-2 h-2 rounded-full ${color}`} />
}

export default function Result() {
  const navigate = useNavigate()
  const { scanId, selectedFolder } = useScanStore()
  const {
    files, total, page, pageSize, filters,
    selectedFile, unclassifiedCount,
    setFiles, setPage, setFilters, setSelectedFile, setUnclassifiedCount,
  } = useFileStore()

  const [viewMode, setViewMode] = useState('list')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const debounceRef = useRef(null)
  const inputRef = useRef(null)

  const fetchFiles = useCallback(async (overrides = {}) => {
    if (!scanId) return
    setLoading(true)
    try {
      const params = { scanId, page, pageSize, ...filters, ...overrides }
      const data = await getFiles(params)
      setFiles(data.items, data.total)
      if (data.unclassified_count != null) {
        setUnclassifiedCount(data.unclassified_count)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [scanId, page, pageSize, filters])

  useEffect(() => {
    if (!scanId) {
      navigate('/')
      return
    }
    fetchFiles()
  }, [scanId, page, fetchFiles, navigate])

  const handleSearchChange = (value) => {
    setSearch(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setPage(1)
      setFilters({ search: value })
    }, 300)
  }

  const clearSearch = () => {
    setSearch('')
    if (debounceRef.current) clearTimeout(debounceRef.current)
    setPage(1)
    setFilters({ search: '' })
    inputRef.current?.focus()
  }

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  const handleNodeClick = (fileId) => {
    if (!fileId) {
      setSelectedFile(null)
      return
    }
    const file = files.find((f) => f.id === fileId)
    setSelectedFile(file || null)
  }

  const handleRowClick = (file) => {
    setSelectedFile(selectedFile?.id === file.id ? null : file)
  }

  return (
    <div className="h-screen mesh-gradient flex flex-col overflow-hidden">
      {/* 상단 헤더 */}
      <header className="glass-header px-6 py-3 flex items-center gap-4 shrink-0">
        <button onClick={() => navigate('/')} className="text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors">
          <ArrowLeft size={18} />
        </button>
        <div className="flex items-center gap-1.5 text-sm text-[hsl(var(--muted-foreground))] flex-1 min-w-0">
          <FolderOpen size={14} />
          <span className="truncate">{selectedFolder}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button variant="ghost" size="sm" onClick={() => navigate('/settings')}>
            <Settings size={14} />
          </Button>
          <Button variant="outline" size="sm" onClick={() => navigate('/rules')}>
            규칙 관리
          </Button>
          <Button size="sm" onClick={() => navigate('/apply')}>
            정리 적용
          </Button>
        </div>
      </header>

      {/* 미분류 배너 */}
      {unclassifiedCount > 0 && (
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-6 py-2 flex items-center gap-2 shrink-0">
          <AlertTriangle size={15} className="text-amber-500" />
          <span className="text-sm text-amber-700 dark:text-amber-300">
            신뢰도 31% 미만 파일 <strong>{unclassifiedCount}개</strong>가 미분류 상태입니다. 정리 적용 시 자동 제외됩니다.
          </span>
        </div>
      )}

      {/* 툴바 */}
      <div className="glass-header px-6 py-2.5 flex items-center gap-3 shrink-0 !border-b !border-t-0">
        {/* 검색 */}
        <div className="flex items-center gap-2 flex-1 max-w-md">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[hsl(var(--muted-foreground))]" />
            <input
              ref={inputRef}
              type="text"
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="파일명, 경로, 카테고리, 태그 검색"
              className="w-full pl-8 pr-8 py-1.5 text-sm glass-input"
            />
            {search && (
              <button
                onClick={clearSearch}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[hsl(var(--muted-foreground)/0.5)] hover:text-[hsl(var(--foreground))] transition-colors"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1 ml-auto">
          {/* 뷰 전환 */}
          <div className="flex glass rounded-xl p-0.5">
            <button
              onClick={() => setViewMode('list')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
                viewMode === 'list'
                  ? 'bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] shadow-sm'
                  : 'text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]'
              }`}
            >
              <List size={13} /> 리스트
            </button>
            <button
              onClick={() => setViewMode('graph')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
                viewMode === 'graph'
                  ? 'bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] shadow-sm'
                  : 'text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]'
              }`}
            >
              <Network size={13} /> 마인드맵
            </button>
          </div>

          <span className="text-xs text-[hsl(var(--muted-foreground))] ml-2">총 {total}개</span>
        </div>
      </div>

      {/* 메인 콘텐츠 */}
      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 overflow-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center h-full text-[hsl(var(--muted-foreground))] text-sm">
              불러오는 중...
            </div>
          ) : viewMode === 'list' ? (
            /* 리스트 뷰 */
            <div className="glass-card overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--glass-border)]">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-[hsl(var(--muted-foreground))]">파일명</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-[hsl(var(--muted-foreground))]">카테고리</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-[hsl(var(--muted-foreground))]">태그</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-[hsl(var(--muted-foreground))]">Tier</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-[hsl(var(--muted-foreground))]">신뢰도</th>
                  </tr>
                </thead>
                <tbody>
                  {files.map((file) => (
                    <tr
                      key={file.id}
                      onClick={() => handleRowClick(file)}
                      className={`border-b border-[var(--glass-border)] cursor-pointer transition-all duration-150 ${
                        selectedFile?.id === file.id
                          ? 'bg-[hsl(var(--primary)/0.08)]'
                          : file.confidence_score < 0.31
                          ? 'bg-red-500/5 hover:bg-red-500/10'
                          : 'hover:bg-[var(--input-bg)]'
                      }`}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <ConfidenceDot score={file.confidence_score} />
                          <span className="font-medium text-[hsl(var(--foreground))] truncate max-w-48">
                            <HighlightText text={file.filename} query={search} />
                          </span>
                          {file.is_manual && (
                            <Badge variant="outline" className="text-xs py-0 px-1.5">수동</Badge>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-[hsl(var(--foreground)/0.7)]">
                        {file.category
                          ? <HighlightText text={file.category} query={search} />
                          : <span className="text-[hsl(var(--muted-foreground)/0.4)]">-</span>}
                      </td>
                      <td className="px-4 py-3 text-[hsl(var(--muted-foreground))] text-xs">
                        {file.tag
                          ? <HighlightText text={file.tag} query={search} />
                          : <span className="text-[hsl(var(--muted-foreground)/0.4)]">-</span>}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={TIER_COLORS[file.tier_used] || 'secondary'} className="text-xs">
                          {TIER_LABELS[file.tier_used] || '-'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-16 bg-[var(--input-bg)] rounded-full h-1.5 overflow-hidden">
                            <div
                              className={`h-1.5 rounded-full transition-all ${
                                file.confidence_score < 0.31 ? 'bg-red-400' :
                                file.confidence_score < 0.5 ? 'bg-amber-400' : 'bg-emerald-400'
                              }`}
                              style={{ width: `${Math.round(file.confidence_score * 100)}%` }}
                            />
                          </div>
                          <span className="text-xs text-[hsl(var(--muted-foreground))]">
                            {Math.round(file.confidence_score * 100)}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {files.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-12 text-center text-[hsl(var(--muted-foreground))] text-sm">
                        결과가 없습니다
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>

              {/* 페이지네이션 */}
              {total > pageSize && (
                <div className="flex items-center justify-center gap-2 py-3 border-t border-[var(--glass-border)]">
                  <Button
                    size="sm" variant="outline"
                    disabled={page === 1}
                    onClick={() => setPage(page - 1)}
                  >이전</Button>
                  <span className="text-xs text-[hsl(var(--muted-foreground))]">
                    {page} / {Math.ceil(total / pageSize)}
                  </span>
                  <Button
                    size="sm" variant="outline"
                    disabled={page >= Math.ceil(total / pageSize)}
                    onClick={() => setPage(page + 1)}
                  >다음</Button>
                </div>
              )}
            </div>
          ) : (
            /* 그래프 뷰 */
            <div className="h-full" style={{ minHeight: 480 }}>
              <GraphView
                files={files}
                folderName={selectedFolder?.split('/').pop() || '스캔 결과'}
                onNodeClick={handleNodeClick}
              />
            </div>
          )}
        </div>

        {/* 우측 슬라이드 패널 */}
        {selectedFile && (
          <FileDetailPanel
            file={selectedFile}
            onClose={() => setSelectedFile(null)}
          />
        )}
      </div>
    </div>
  )
}
