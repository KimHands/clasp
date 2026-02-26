import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  List, Network, Search, Filter, AlertTriangle,
  ArrowLeft, FolderOpen, Settings, ChevronDown
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import GraphView from '@/components/GraphView'
import FileDetailPanel from '@/components/FileDetailPanel'
import useScanStore from '@/store/scanStore'
import useFileStore from '@/store/fileStore'
import { getFiles } from '@/api/files'

const LAYOUT_OPTIONS = [
  { value: 'cluster', label: '클러스터 버블' },
  { value: 'tree', label: '트리' },
  { value: 'force', label: '포스 다이렉티드' },
]

const TIER_LABELS = { 1: 'T1', 2: 'T2', 3: 'T3' }
const TIER_COLORS = { 1: 'secondary', 2: 'default', 3: 'warning' }

function ConfidenceDot({ score }) {
  const color = score < 0.31 ? 'bg-red-400' : score < 0.5 ? 'bg-yellow-400' : 'bg-green-400'
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

  const [viewMode, setViewMode] = useState('list') // 'list' | 'graph'
  const [graphLayout, setGraphLayout] = useState('cluster')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [showLayoutMenu, setShowLayoutMenu] = useState(false)

  const fetchFiles = useCallback(async (overrides = {}) => {
    if (!scanId) return
    setLoading(true)
    try {
      const params = { scanId, page, pageSize, ...filters, ...overrides }
      const data = await getFiles(params)
      setFiles(data.items, data.total)
      // 미분류 파일 수 계산
      const unclassified = data.items.filter((f) => f.confidence_score < 0.31).length
      setUnclassifiedCount(unclassified)
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

  const handleSearch = (e) => {
    e.preventDefault()
    setFilters({ search })
    fetchFiles({ search, page: 1 })
    setPage(1)
  }

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
    <div className="h-screen bg-gray-50 flex flex-col overflow-hidden">
      {/* 상단 헤더 */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-4 shrink-0">
        <button onClick={() => navigate('/')} className="text-gray-400 hover:text-gray-600">
          <ArrowLeft size={18} />
        </button>
        <div className="flex items-center gap-1.5 text-sm text-gray-500 flex-1 min-w-0">
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
        <div className="bg-amber-50 border-b border-amber-200 px-6 py-2 flex items-center gap-2 shrink-0">
          <AlertTriangle size={15} className="text-amber-500" />
          <span className="text-sm text-amber-700">
            신뢰도 31% 미만 파일 <strong>{unclassifiedCount}개</strong>가 미분류 상태입니다. 정리 적용 시 자동 제외됩니다.
          </span>
        </div>
      )}

      {/* 툴바 */}
      <div className="bg-white border-b border-gray-100 px-6 py-2.5 flex items-center gap-3 shrink-0">
        {/* 검색 */}
        <form onSubmit={handleSearch} className="flex items-center gap-2 flex-1 max-w-sm">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="파일명 검색"
              className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </div>
          <Button type="submit" size="sm" variant="outline">검색</Button>
        </form>

        <div className="flex items-center gap-1 ml-auto">
          {/* 뷰 전환 */}
          <div className="flex bg-gray-100 rounded-lg p-0.5">
            <button
              onClick={() => setViewMode('list')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                viewMode === 'list' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <List size={13} /> 리스트
            </button>
            <button
              onClick={() => setViewMode('graph')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                viewMode === 'graph' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <Network size={13} /> 그래프
            </button>
          </div>

          {/* 그래프 레이아웃 선택 */}
          {viewMode === 'graph' && (
            <div className="relative">
              <button
                onClick={() => setShowLayoutMenu(!showLayoutMenu)}
                className="flex items-center gap-1 px-3 py-1.5 text-xs border border-gray-200 rounded-lg bg-white hover:bg-gray-50"
              >
                {LAYOUT_OPTIONS.find((o) => o.value === graphLayout)?.label}
                <ChevronDown size={12} />
              </button>
              {showLayoutMenu && (
                <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10 min-w-36">
                  {LAYOUT_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => { setGraphLayout(opt.value); setShowLayoutMenu(false) }}
                      className={`w-full text-left px-3 py-2 text-xs hover:bg-gray-50 ${
                        graphLayout === opt.value ? 'text-blue-600 font-medium' : 'text-gray-700'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <span className="text-xs text-gray-400 ml-2">총 {total}개</span>
        </div>
      </div>

      {/* 메인 콘텐츠 */}
      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 overflow-auto p-4">
          {loading ? (
            <div className="flex items-center justify-center h-full text-gray-400 text-sm">
              불러오는 중...
            </div>
          ) : viewMode === 'list' ? (
            /* 리스트 뷰 */
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-100">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">파일명</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">카테고리</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">태그</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">Tier</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500">신뢰도</th>
                  </tr>
                </thead>
                <tbody>
                  {files.map((file) => (
                    <tr
                      key={file.id}
                      onClick={() => handleRowClick(file)}
                      className={`border-b border-gray-50 cursor-pointer hover:bg-blue-50 transition-colors ${
                        selectedFile?.id === file.id ? 'bg-blue-50' : ''
                      } ${file.confidence_score < 0.31 ? 'bg-red-50 hover:bg-red-100' : ''}`}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <ConfidenceDot score={file.confidence_score} />
                          <span className="font-medium text-gray-800 truncate max-w-48">{file.filename}</span>
                          {file.is_manual && (
                            <Badge variant="outline" className="text-xs py-0 px-1.5">수동</Badge>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{file.category || <span className="text-gray-300">-</span>}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs">{file.tag || <span className="text-gray-300">-</span>}</td>
                      <td className="px-4 py-3">
                        <Badge variant={TIER_COLORS[file.tier_used] || 'secondary'} className="text-xs">
                          {TIER_LABELS[file.tier_used] || '-'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-16 bg-gray-100 rounded-full h-1.5">
                            <div
                              className={`h-1.5 rounded-full ${
                                file.confidence_score < 0.31 ? 'bg-red-400' :
                                file.confidence_score < 0.5 ? 'bg-yellow-400' : 'bg-green-400'
                              }`}
                              style={{ width: `${Math.round(file.confidence_score * 100)}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-500">
                            {Math.round(file.confidence_score * 100)}%
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {files.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-12 text-center text-gray-400 text-sm">
                        결과가 없습니다
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>

              {/* 페이지네이션 */}
              {total > pageSize && (
                <div className="flex items-center justify-center gap-2 py-3 border-t border-gray-100">
                  <Button
                    size="sm" variant="outline"
                    disabled={page === 1}
                    onClick={() => setPage(page - 1)}
                  >이전</Button>
                  <span className="text-xs text-gray-500">
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
                layout={graphLayout}
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
