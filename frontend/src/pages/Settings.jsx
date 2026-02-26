import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Eye, EyeOff, Plus, X, Save, Key, ShieldAlert } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

// API Key는 보안상 localStorage 대신 Electron 메인 프로세스(암호화된 파일)에 저장
// 키워드는 민감 정보가 아니므로 localStorage 유지
const STORAGE_KEY_KEYWORDS = 'clasp_sensitive_keywords'

export default function Settings() {
  const navigate = useNavigate()
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [keywords, setKeywords] = useState([])
  const [newKeyword, setNewKeyword] = useState('')
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState('')

  useEffect(() => {
    // Electron 메인 프로세스에서 저장된 API Key 로드
    window.electronAPI?.getEnv?.('OPENAI_API_KEY').then((key) => {
      if (key) setApiKey(key)
    })
    const storedKeywords = JSON.parse(localStorage.getItem(STORAGE_KEY_KEYWORDS) || '[]')
    setKeywords(storedKeywords)
  }, [])

  const handleSave = async () => {
    setSaveError('')
    try {
      // Electron IPC → 메인 프로세스가 설정 파일 저장 + 백엔드 HTTP 전달
      const result = await window.electronAPI?.setEnv?.('OPENAI_API_KEY', apiKey)
      if (result && !result.success) {
        setSaveError('API Key 저장에 실패했습니다.')
        return
      }
    } catch (e) {
      setSaveError('백엔드 연결 실패: ' + e.message)
      return
    }
    localStorage.setItem(STORAGE_KEY_KEYWORDS, JSON.stringify(keywords))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleAddKeyword = (e) => {
    e.preventDefault()
    const kw = newKeyword.trim()
    if (!kw || keywords.includes(kw)) return
    setKeywords([...keywords, kw])
    setNewKeyword('')
  }

  const handleRemoveKeyword = (kw) => {
    setKeywords(keywords.filter((k) => k !== kw))
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-gray-600">
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-lg font-bold text-gray-900">설정</h1>
      </header>

      <div className="max-w-xl mx-auto px-6 py-6 space-y-6">

        {/* OpenAI API Key */}
        <section className="bg-white border border-gray-200 rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-1">
            <Key size={16} className="text-gray-400" />
            <h2 className="text-sm font-bold text-gray-800">OpenAI API Key</h2>
            <Badge variant="secondary" className="text-xs">Tier 3 선택사항</Badge>
          </div>
          <p className="text-xs text-gray-500 mb-4">
            API Key를 입력하면 신뢰도가 낮은 파일에 대해 GPT-4o-mini로 추가 분류를 수행합니다.
            파일 원문은 전송되지 않으며, 요약 텍스트만 사용됩니다.
          </p>
          <div className="relative">
            <input
              type={showKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
              className="w-full border border-gray-200 rounded-xl px-4 py-2.5 pr-10 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            <button
              type="button"
              onClick={() => setShowKey(!showKey)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          {apiKey && (
            <p className="text-xs text-green-600 mt-2">
              ✓ API Key가 입력되었습니다. 저장 후 적용됩니다.
            </p>
          )}
        </section>

        {/* 민감 파일 키워드 */}
        <section className="bg-white border border-gray-200 rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-1">
            <ShieldAlert size={16} className="text-gray-400" />
            <h2 className="text-sm font-bold text-gray-800">민감 파일 키워드</h2>
          </div>
          <p className="text-xs text-gray-500 mb-4">
            파일명에 아래 키워드가 포함된 파일은 내용 분석(Tier 2/3)에서 제외됩니다.
          </p>

          <form onSubmit={handleAddKeyword} className="flex gap-2 mb-4">
            <input
              type="text"
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
              placeholder="예: 개인정보, 비밀, secret"
              className="flex-1 border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
            <Button type="submit" size="sm" variant="outline">
              <Plus size={14} /> 추가
            </Button>
          </form>

          {keywords.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {keywords.map((kw) => (
                <span
                  key={kw}
                  className="flex items-center gap-1.5 bg-gray-100 text-gray-700 text-sm px-3 py-1 rounded-full"
                >
                  {kw}
                  <button onClick={() => handleRemoveKeyword(kw)} className="text-gray-400 hover:text-red-400">
                    <X size={12} />
                  </button>
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-400">등록된 키워드가 없습니다.</p>
          )}
        </section>

        {/* 저장 버튼 */}
        {saveError && (
          <p className="text-xs text-red-500 text-center">{saveError}</p>
        )}
        <Button onClick={handleSave} className="w-full" variant={saved ? 'outline' : 'default'}>
          <Save size={15} />
          {saved ? '저장됨 ✓' : '설정 저장'}
        </Button>
      </div>
    </div>
  )
}
