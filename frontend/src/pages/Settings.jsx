import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Eye, EyeOff, Plus, X, Save, Key, ShieldAlert, FileType2, Trash2,
  Sun, Moon, Monitor
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import useExtensionStore from '@/store/extensionStore'
import useThemeStore from '@/store/themeStore'

const STORAGE_KEY_KEYWORDS = 'clasp_sensitive_keywords'

const THEME_OPTIONS = [
  { value: 'light', label: '라이트', icon: Sun },
  { value: 'dark', label: '다크', icon: Moon },
  { value: 'system', label: '시스템', icon: Monitor },
]

export default function Settings() {
  const navigate = useNavigate()
  const { mode, setTheme } = useThemeStore()
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [keywords, setKeywords] = useState([])
  const [newKeyword, setNewKeyword] = useState('')
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState('')

  const [newExt, setNewExt] = useState('')
  const [newExtCategory, setNewExtCategory] = useState('')
  const [extError, setExtError] = useState('')

  const { extensions, categories, fetchExtensions, addExtension, removeExtension } = useExtensionStore()

  useEffect(() => {
    window.electronAPI?.getEnv?.('OPENAI_API_KEY').then((key) => {
      if (key) setApiKey(key)
    })
    const storedKeywords = JSON.parse(localStorage.getItem(STORAGE_KEY_KEYWORDS) || '[]')
    setKeywords(storedKeywords)
    fetchExtensions()
  }, [])

  const handleSave = async () => {
    setSaveError('')
    try {
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
    <div className="min-h-screen mesh-gradient">
      <header className="glass-header px-6 py-4 flex items-center gap-3 sticky top-0 z-10">
        <button onClick={() => navigate(-1)} className="text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors">
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-lg font-bold text-[hsl(var(--foreground))]">설정</h1>
      </header>

      <div className="max-w-xl mx-auto px-6 py-6 space-y-6">

        {/* 테마 설정 */}
        <section className="glass-card p-6">
          <div className="flex items-center gap-2 mb-1">
            <Sun size={16} className="text-[hsl(var(--muted-foreground))]" />
            <h2 className="text-sm font-bold text-[hsl(var(--foreground))]">테마</h2>
          </div>
          <p className="text-xs text-[hsl(var(--muted-foreground))] mb-4">
            앱의 외관을 설정합니다. 시스템 설정을 따르거나 직접 선택할 수 있습니다.
          </p>
          <div className="flex gap-2">
            {THEME_OPTIONS.map((opt) => {
              const Icon = opt.icon
              const isActive = mode === opt.value
              return (
                <button
                  key={opt.value}
                  onClick={() => setTheme(opt.value)}
                  className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 ${
                    isActive
                      ? 'bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))] shadow-sm'
                      : 'glass-input text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]'
                  }`}
                >
                  <Icon size={16} />
                  {opt.label}
                </button>
              )
            })}
          </div>
        </section>

        {/* OpenAI API Key */}
        <section className="glass-card p-6">
          <div className="flex items-center gap-2 mb-1">
            <Key size={16} className="text-[hsl(var(--muted-foreground))]" />
            <h2 className="text-sm font-bold text-[hsl(var(--foreground))]">OpenAI API Key</h2>
            <Badge variant="secondary" className="text-xs">Tier 3 선택사항</Badge>
          </div>
          <p className="text-xs text-[hsl(var(--muted-foreground))] mb-4">
            API Key를 입력하면 신뢰도가 낮은 파일에 대해 GPT-4o-mini로 추가 분류를 수행합니다.
            파일 원문은 전송되지 않으며, 요약 텍스트만 사용됩니다.
          </p>
          <div className="relative">
            <input
              type={showKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
              className="w-full glass-input px-4 py-2.5 pr-10 text-sm font-mono"
            />
            <button
              type="button"
              onClick={() => setShowKey(!showKey)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors"
            >
              {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          {apiKey && (
            <p className="text-xs text-emerald-500 mt-2">
              API Key가 입력되었습니다. 저장 후 적용됩니다.
            </p>
          )}
        </section>

        {/* 민감 파일 키워드 */}
        <section className="glass-card p-6">
          <div className="flex items-center gap-2 mb-1">
            <ShieldAlert size={16} className="text-[hsl(var(--muted-foreground))]" />
            <h2 className="text-sm font-bold text-[hsl(var(--foreground))]">민감 파일 키워드</h2>
          </div>
          <p className="text-xs text-[hsl(var(--muted-foreground))] mb-4">
            파일명에 아래 키워드가 포함된 파일은 내용 분석(Tier 2/3)에서 제외됩니다.
          </p>

          <form onSubmit={handleAddKeyword} className="flex gap-2 mb-4">
            <input
              type="text"
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
              placeholder="예: 개인정보, 비밀, secret"
              className="flex-1 glass-input px-3 py-2 text-sm"
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
                  className="flex items-center gap-1.5 bg-[var(--input-bg)] text-[hsl(var(--foreground)/0.8)] text-sm px-3 py-1 rounded-full border border-[var(--glass-border)]"
                >
                  {kw}
                  <button onClick={() => handleRemoveKeyword(kw)} className="text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--destructive))] transition-colors">
                    <X size={12} />
                  </button>
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-[hsl(var(--muted-foreground))]">등록된 키워드가 없습니다.</p>
          )}
        </section>

        {/* 확장자 관리 */}
        <section className="glass-card p-6">
          <div className="flex items-center gap-2 mb-1">
            <FileType2 size={16} className="text-[hsl(var(--muted-foreground))]" />
            <h2 className="text-sm font-bold text-[hsl(var(--foreground))]">확장자 관리</h2>
          </div>
          <p className="text-xs text-[hsl(var(--muted-foreground))] mb-4">
            기본 확장자 외에 추가 확장자를 등록하면 규칙 추가 시 드롭다운에 표시됩니다.
            분류 엔진(Tier 1)에서도 자동으로 인식합니다.
          </p>

          <form
            onSubmit={async (e) => {
              e.preventDefault()
              setExtError('')
              const ext = newExt.trim().replace(/^\./, '').toLowerCase()
              const cat = newExtCategory.trim()
              if (!ext || !cat) {
                setExtError('확장자와 카테고리를 모두 입력해주세요')
                return
              }
              try {
                await addExtension({ extension: ext, category: cat })
                setNewExt('')
                setNewExtCategory('')
              } catch (err) {
                setExtError(err.message || '확장자 추가 실패')
              }
            }}
            className="flex gap-2 mb-4 flex-wrap"
          >
            <input
              type="text"
              value={newExt}
              onChange={(e) => setNewExt(e.target.value)}
              placeholder="확장자 (예: hwp)"
              className="w-28 glass-input px-3 py-2 text-sm"
            />
            <div className="flex-1 min-w-32 relative">
              <input
                type="text"
                list="category-suggestions"
                value={newExtCategory}
                onChange={(e) => setNewExtCategory(e.target.value)}
                placeholder="카테고리 (예: 문서)"
                className="w-full glass-input px-3 py-2 text-sm"
              />
              <datalist id="category-suggestions">
                {categories.map((cat) => (
                  <option key={cat} value={cat} />
                ))}
              </datalist>
            </div>
            <Button type="submit" size="sm" variant="outline">
              <Plus size={14} /> 추가
            </Button>
          </form>
          {extError && <p className="text-xs text-[hsl(var(--destructive))] mb-3">{extError}</p>}

          {/* 기본 확장자 목록 */}
          <div className="mb-4">
            <p className="text-xs font-semibold text-[hsl(var(--muted-foreground))] mb-2">기본 확장자</p>
            <div className="flex flex-wrap gap-1.5">
              {extensions.filter((e) => e.is_default).map((ext) => (
                <span
                  key={ext.extension}
                  className="inline-flex items-center gap-1 bg-[var(--input-bg)] text-[hsl(var(--foreground)/0.7)] text-xs px-2.5 py-1 rounded-full border border-[var(--glass-border)]"
                >
                  .{ext.extension}
                  <span className="text-[hsl(var(--muted-foreground))]">({ext.category})</span>
                </span>
              ))}
            </div>
          </div>

          {/* 사용자 추가 확장자 */}
          <div>
            <p className="text-xs font-semibold text-[hsl(var(--muted-foreground))] mb-2">사용자 추가 확장자</p>
            {extensions.filter((e) => !e.is_default).length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {extensions.filter((e) => !e.is_default).map((ext) => (
                  <span
                    key={ext.id}
                    className="inline-flex items-center gap-1.5 bg-[hsl(var(--primary)/0.08)] text-[hsl(var(--primary))] text-sm px-3 py-1 rounded-full border border-[hsl(var(--primary)/0.2)]"
                  >
                    .{ext.extension}
                    <span className="opacity-60 text-xs">({ext.category})</span>
                    <button
                      onClick={async () => {
                        try {
                          await removeExtension(ext.id)
                        } catch (err) {
                          alert(err.message || '삭제 실패')
                        }
                      }}
                      className="opacity-50 hover:text-[hsl(var(--destructive))] hover:opacity-100 transition-all"
                    >
                      <Trash2 size={12} />
                    </button>
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[hsl(var(--muted-foreground))]">등록된 사용자 확장자가 없습니다.</p>
            )}
          </div>
        </section>

        {/* 저장 버튼 */}
        {saveError && (
          <p className="text-xs text-[hsl(var(--destructive))] text-center">{saveError}</p>
        )}
        <Button onClick={handleSave} className="w-full" variant={saved ? 'outline' : 'default'}>
          <Save size={15} />
          {saved ? '저장됨' : '설정 저장'}
        </Button>
      </div>
    </div>
  )
}
