import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Plus, X, Save, Cpu, ShieldAlert, FileType2, Trash2,
  Sun, Moon, Monitor, CheckCircle2, XCircle, Tags
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import useExtensionStore from '@/store/extensionStore'
import useThemeStore from '@/store/themeStore'
import {
  getLocalLlm, saveLocalLlm, testLocalLlm,
  getSensitiveKeywords, createSensitiveKeyword, deleteSensitiveKeyword,
} from '@/api/settings'

const THEME_OPTIONS = [
  { value: 'light', label: '라이트', icon: Sun },
  { value: 'dark', label: '다크', icon: Moon },
  { value: 'system', label: '시스템', icon: Monitor },
]

export default function Settings() {
  const navigate = useNavigate()
  const { mode, setTheme } = useThemeStore()
  const [llmEnabled, setLlmEnabled] = useState(false)
  const [llmBaseUrl, setLlmBaseUrl] = useState('')
  const [llmModel, setLlmModel] = useState('')
  const [llmModels, setLlmModels] = useState([])
  const [llmTest, setLlmTest] = useState(null)
  const [keywords, setKeywords] = useState([])
  const [newKeyword, setNewKeyword] = useState('')
  const [keywordError, setKeywordError] = useState('')
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState('')

  const [newExt, setNewExt] = useState('')
  const [newExtCategory, setNewExtCategory] = useState('')
  const [extError, setExtError] = useState('')

  const [newCatName, setNewCatName] = useState('')
  const [newCatKeywords, setNewCatKeywords] = useState('')
  const [catError, setCatError] = useState('')

  const {
    extensions, categories, customCategories,
    fetchExtensions, addExtension, removeExtension,
    fetchCategories, addCategory, removeCategory,
  } = useExtensionStore()

  useEffect(() => {
    getLocalLlm().then((config) => {
      setLlmEnabled(config.enabled)
      setLlmBaseUrl(config.base_url)
      setLlmModel(config.model)
    }).catch((e) => setSaveError(e.message))
    getSensitiveKeywords().then((data) => setKeywords(data.keywords)).catch((e) => setKeywordError(e.message))
    fetchExtensions()
    fetchCategories()
  }, [])

  const handleSave = async () => {
    setSaveError('')
    try {
      await saveLocalLlm({ enabled: llmEnabled, baseUrl: llmBaseUrl, model: llmModel })
    } catch (e) {
      setSaveError(e.message)
      return
    }
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleTestLlm = async () => {
    setLlmTest(null)
    try {
      const result = await testLocalLlm(llmBaseUrl)
      setLlmModels(result.models)
      setLlmTest(result.ok ? 'ok' : 'failed')
    } catch (e) {
      setLlmTest(e.message)
    }
  }

  const handleAddKeyword = async (e) => {
    e.preventDefault()
    setKeywordError('')
    const kw = newKeyword.trim()
    if (!kw) return
    try {
      const created = await createSensitiveKeyword(kw)
      setKeywords([...keywords, created])
      setNewKeyword('')
    } catch (err) {
      setKeywordError(err.message)
    }
  }

  const handleRemoveKeyword = async (id) => {
    await deleteSensitiveKeyword(id)
    setKeywords(keywords.filter((k) => k.id !== id))
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

        {/* 로컬 LLM */}
        <section className="glass-card p-6 space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <Cpu size={16} className="text-[hsl(var(--muted-foreground))]" />
            <h2 className="text-sm font-bold text-[hsl(var(--foreground))]">로컬 LLM</h2>
            <Badge variant="secondary" className="text-xs">Tier 3 선택사항</Badge>
          </div>
          <p className="text-xs text-[hsl(var(--muted-foreground))]">
            켜면 신뢰도가 낮은 파일의 파일명과 본문 앞부분을 이 컴퓨터의 LLM 서버로 보내 분류합니다.
            LM Studio, Ollama처럼 OpenAI 호환 API를 제공하는 서버를 쓸 수 있으며, 외부 주소는 사용할 수 없습니다.
          </p>

          <label className="flex items-center gap-2 text-sm text-[hsl(var(--foreground))]">
            <input
              type="checkbox"
              checked={llmEnabled}
              onChange={(e) => setLlmEnabled(e.target.checked)}
            />
            로컬 LLM 사용
          </label>

          <div>
            <p className="text-xs font-semibold text-[hsl(var(--foreground))] mb-2">서버 주소</p>
            <div className="flex gap-2">
              <input
                type="text"
                value={llmBaseUrl}
                onChange={(e) => setLlmBaseUrl(e.target.value)}
                placeholder="http://127.0.0.1:1234/v1"
                className="flex-1 glass-input px-4 py-2.5 text-sm font-mono"
              />
              <Button type="button" size="sm" variant="outline" onClick={handleTestLlm}>연결 시험</Button>
            </div>
            {llmTest === 'ok' && (
              <p className="flex items-center gap-1.5 text-xs text-emerald-500 mt-1.5">
                <CheckCircle2 size={13} /> 연결되었습니다. 모델 {llmModels.length}개를 찾았습니다.
              </p>
            )}
            {llmTest && llmTest !== 'ok' && (
              <p className="flex items-center gap-1.5 text-xs text-red-500 mt-1.5">
                <XCircle size={13} /> {llmTest === 'failed' ? '서버에 연결할 수 없습니다.' : llmTest}
              </p>
            )}
          </div>

          <div>
            <p className="text-xs font-semibold text-[hsl(var(--foreground))] mb-2">모델</p>
            <input
              type="text"
              list="local-llm-models"
              value={llmModel}
              onChange={(e) => setLlmModel(e.target.value)}
              placeholder="연결 시험 후 선택하거나 직접 입력"
              className="w-full glass-input px-4 py-2.5 text-sm font-mono"
            />
            <datalist id="local-llm-models">
              {llmModels.map((model) => <option key={model} value={model} />)}
            </datalist>
          </div>
        </section>

        {/* 민감 파일 키워드 */}
        <section className="glass-card p-6">
          <div className="flex items-center gap-2 mb-1">
            <ShieldAlert size={16} className="text-[hsl(var(--muted-foreground))]" />
            <h2 className="text-sm font-bold text-[hsl(var(--foreground))]">민감 파일 키워드</h2>
          </div>
          <p className="text-xs text-[hsl(var(--muted-foreground))] mb-4">
            파일명에 아래 키워드가 포함된 파일은 내용을 읽지 않고 파일명과 확장자로만 분류합니다. 이미 저장된 내용은 다음 스캔 때 지웁니다.
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
          {keywordError && <p className="text-xs text-red-500 mb-3">{keywordError}</p>}

          {keywords.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {keywords.map((kw) => (
                <span
                  key={kw.id}
                  className="flex items-center gap-1.5 bg-[var(--input-bg)] text-[hsl(var(--foreground)/0.8)] text-sm px-3 py-1 rounded-full border border-[var(--glass-border)]"
                >
                  {kw.keyword}
                  <button onClick={() => handleRemoveKeyword(kw.id)} className="text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--destructive))] transition-colors">
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

        {/* 카테고리 관리 */}
        <section className="glass-card p-6">
          <div className="flex items-center gap-2 mb-1">
            <Tags size={16} className="text-[hsl(var(--muted-foreground))]" />
            <h2 className="text-sm font-bold text-[hsl(var(--foreground))]">카테고리 관리</h2>
          </div>
          <p className="text-xs text-[hsl(var(--muted-foreground))] mb-4">
            기본 5개 카테고리 외에 사용자 정의 카테고리를 추가하면 Tier 2(임베딩) 및 Tier 3(LLM)에서 자동으로 인식합니다.
            키워드를 쉼표(,)로 구분하여 입력하면 분류 정확도가 높아집니다.
          </p>

          <form
            onSubmit={async (e) => {
              e.preventDefault()
              setCatError('')
              const name = newCatName.trim()
              if (!name) {
                setCatError('카테고리 이름을 입력해주세요')
                return
              }
              const keywords = newCatKeywords
                .split(',')
                .map((kw) => kw.trim())
                .filter(Boolean)
              try {
                await addCategory({ name, keywords })
                setNewCatName('')
                setNewCatKeywords('')
              } catch (err) {
                setCatError(err.message || '카테고리 추가 실패')
              }
            }}
            className="space-y-2 mb-4"
          >
            <div className="flex gap-2">
              <input
                type="text"
                value={newCatName}
                onChange={(e) => setNewCatName(e.target.value)}
                placeholder="카테고리 이름 (예: 디자인)"
                className="w-36 glass-input px-3 py-2 text-sm"
              />
              <input
                type="text"
                value={newCatKeywords}
                onChange={(e) => setNewCatKeywords(e.target.value)}
                placeholder="키워드 (예: UI, UX, 피그마, 와이어프레임)"
                className="flex-1 glass-input px-3 py-2 text-sm"
              />
              <Button type="submit" size="sm" variant="outline">
                <Plus size={14} /> 추가
              </Button>
            </div>
          </form>
          {catError && <p className="text-xs text-[hsl(var(--destructive))] mb-3">{catError}</p>}

          {/* 기본 카테고리 */}
          <div className="mb-4">
            <p className="text-xs font-semibold text-[hsl(var(--muted-foreground))] mb-2">기본 카테고리</p>
            <div className="flex flex-wrap gap-1.5">
              {customCategories.filter((c) => c.is_default).map((cat) => (
                <span
                  key={cat.name}
                  className="inline-flex items-center bg-[var(--input-bg)] text-[hsl(var(--foreground)/0.7)] text-xs px-2.5 py-1 rounded-full border border-[var(--glass-border)]"
                >
                  {cat.name}
                </span>
              ))}
            </div>
          </div>

          {/* 사용자 추가 카테고리 */}
          <div>
            <p className="text-xs font-semibold text-[hsl(var(--muted-foreground))] mb-2">사용자 추가 카테고리</p>
            {customCategories.filter((c) => !c.is_default).length > 0 ? (
              <div className="space-y-2">
                {customCategories.filter((c) => !c.is_default).map((cat) => (
                  <div
                    key={cat.id}
                    className="flex items-start gap-2 bg-[hsl(var(--primary)/0.08)] text-sm px-3 py-2 rounded-xl border border-[hsl(var(--primary)/0.2)]"
                  >
                    <div className="flex-1 min-w-0">
                      <span className="font-medium text-[hsl(var(--primary))]">{cat.name}</span>
                      {cat.keywords.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {cat.keywords.map((kw) => (
                            <span
                              key={kw}
                              className="text-xs bg-[var(--input-bg)] text-[hsl(var(--muted-foreground))] px-1.5 py-0.5 rounded"
                            >
                              {kw}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <button
                      onClick={async () => {
                        try {
                          await removeCategory(cat.id)
                        } catch (err) {
                          alert(err.message || '삭제 실패')
                        }
                      }}
                      className="text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--destructive))] transition-all shrink-0 mt-0.5"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[hsl(var(--muted-foreground))]">등록된 사용자 카테고리가 없습니다.</p>
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
