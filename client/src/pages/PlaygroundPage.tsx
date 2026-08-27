import { useState, useRef, useEffect, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Link } from 'react-router-dom'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { PageHeader } from '@/components/page-header'
import { Markdown } from '@/components/markdown'
import { Trash2, History, Clock, Search, Zap } from 'lucide-react'

interface FallbackEntry {
  modelDbId: number
  priority: number
  enabled: boolean
  platform: string
  modelId: string
  displayName: string
  sizeLabel: string
  keyCount: number
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  meta?: {
    platform?: string
    model?: string
    latency?: number
    fallbackAttempts?: number
    inputTokens?: number
    outputTokens?: number
    rpmRemaining?: number | null
    tpmRemaining?: number | null
  }
}

interface HistoryEntry {
  id: string
  createdAt: number
  model: string
  messages: ChatMessage[]
  firstUserMessage: string
  totalTokens?: number
}

const PLAYGROUND_HISTORY = '/api/playground/history'
const RATE_LIMITS_MODEL = '/api/rate-limits/model'

function truncate(text: string, maxLen: number = 70): string {
  return text.length <= maxLen ? text : text.slice(0, maxLen) + '…'
}

function formatTime(ts: number): string {
  const diffMin = Math.floor((Date.now() - ts) / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH}h ago`
  return new Date(ts).toLocaleDateString()
}

export default function PlaygroundPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedModel, setSelectedModel] = useState<string>('auto')
  const [showHistory, setShowHistory] = useState(false)
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const queryClient = useQueryClient()

  const { data: keyData } = useQuery<{ apiKey: string }>({
    queryKey: ['unified-key'],
    queryFn: () => apiFetch('/api/settings/api-key'),
  })

  const { data: fallbackEntries = [] } = useQuery<FallbackEntry[]>({
    queryKey: ['fallback'],
    queryFn: () => apiFetch('/api/fallback'),
  })

  const { data: history = [] } = useQuery<HistoryEntry[]>({
    queryKey: ['playground-history'],
    queryFn: () => apiFetch(PLAYGROUND_HISTORY),
  })

  const availableModels = fallbackEntries.filter(e => e.keyCount > 0 && e.enabled)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (!currentId) return
    const entry = history.find(h => h.id === currentId)
    if (entry) {
      setMessages(entry.messages.map(m => ({ ...m, id: m.id ?? crypto.randomUUID() })))
      setSelectedModel(entry.model)
    }
  }, [currentId, history])

  const invalidateHistory = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['playground-history'] })
  }, [queryClient])

  // Fetch rate-limit info for a model
  const fetchRateLimit = useCallback(async (platform: string, modelId: string) => {
    try {
      return await apiFetch<{ remaining?: { rpmRemaining?: number | null; tpmRemaining?: number | null } }>(`${RATE_LIMITS_MODEL}/${platform}/${modelId}`)
    } catch {
      return null
    }
  }, [])

  // Pre-fetch rate limit info for visible messages
  useEffect(() => {
    const lastMsg = messages[messages.length - 1]
    if (lastMsg?.meta?.platform && lastMsg?.meta?.model && !lastMsg.meta.rpmRemaining && !loading) {
      fetchRateLimit(lastMsg.meta.platform, lastMsg.meta.model).then(info => {
        if (info) {
          setMessages(prev => {
            const updated = [...prev]
            const m = updated[updated.length - 1]
            if (m && m.meta) {
              m.meta.rpmRemaining = info.remaining?.rpmRemaining ?? null
              m.meta.tpmRemaining = info.remaining?.tpmRemaining ?? null
            }
            return updated
          })
        }
      })
    }
  }, [messages, loading, fetchRateLimit])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return

    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: text }
    const newMessages = [...messages, userMsg]
    setMessages(newMessages)
    setInput('')
    setLoading(true)
    inputRef.current?.focus()

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (keyData?.apiKey) headers['Authorization'] = `Bearer ${keyData.apiKey}`

      const body: any = { messages: newMessages.map(m => ({ role: m.role, content: m.content })) }
      if (selectedModel !== 'auto') body.model = selectedModel

      const base = import.meta.env.BASE_URL.replace(/\/$/, '')
      const start = Date.now()
      const res = await fetch(`${base}/v1/chat/completions`, { method: 'POST', headers, body: JSON.stringify(body) })

      const latency = Date.now() - start
      const routedVia = res.headers.get('X-Routed-Via')
      const fallbackAttempts = res.headers.get('X-Fallback-Attempts')

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: { message: `HTTP ${res.status}` } }))
        setMessages([...newMessages, { id: crypto.randomUUID(), role: 'assistant', content: `Error: ${err.error?.message ?? 'Unknown error'}` }])
        return
      }

      const data = await res.json()
      const content = data.choices?.[0]?.message?.content ?? JSON.stringify(data, null, 2)
      const via = data._routed_via ?? (routedVia ? { platform: routedVia.split('/')[0], model: routedVia.split('/').slice(1).join('/') } : undefined)
      const usage = data.usage ?? {}

      const finalMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content,
        meta: {
          platform: via?.platform,
          model: via?.model,
          latency,
          fallbackAttempts: fallbackAttempts ? parseInt(fallbackAttempts) : undefined,
          inputTokens: usage.prompt_tokens,
          outputTokens: usage.completion_tokens,
        },
      }
      setMessages([...newMessages, finalMsg])

      const entryId = currentId || crypto.randomUUID()
      const isNew = !currentId
      const entry: HistoryEntry = {
        id: entryId,
        createdAt: Date.now(),
        model: selectedModel,
        messages: [...newMessages, finalMsg],
        firstUserMessage: text,
        totalTokens: usage.total_tokens,
      }
      await apiFetch(PLAYGROUND_HISTORY, { method: 'POST', body: JSON.stringify(entry) })
      if (isNew) setCurrentId(entryId)
      invalidateHistory()
    } catch (err: any) {
      setMessages([...newMessages, { id: crypto.randomUUID(), role: 'assistant', content: `Error: ${err.message}` }])
    } finally {
      setLoading(false)
      setTimeout(() => inputRef.current?.focus(), 0)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const handleClear = () => { setMessages([]); setCurrentId(null); setSelectedModel('auto'); inputRef.current?.focus() }
  const handleLoadHistory = (entry: HistoryEntry) => { setMessages(entry.messages); setSelectedModel(entry.model); setCurrentId(entry.id); setShowHistory(false); setSearchQuery('') }
  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    await apiFetch(`${PLAYGROUND_HISTORY}/${id}`, { method: 'DELETE' })
    invalidateHistory()
    if (currentId === id) { setMessages([]); setCurrentId(null) }
  }
  const handleClearAll = async () => {
    await apiFetch(PLAYGROUND_HISTORY, { method: 'DELETE' })
    invalidateHistory()
    if (currentId) { setMessages([]); setCurrentId(null) }
  }

  // Filter history by search query
  const filteredHistory = searchQuery
    ? history.filter(h => h.firstUserMessage.toLowerCase().includes(searchQuery.toLowerCase()))
    : history

  const activeModelLabel = selectedModel === 'auto'
    ? 'Auto (fallback chain)'
    : availableModels.find(m => m.modelId === selectedModel)?.displayName ?? selectedModel

  // Compute total tokens for current session
  const totalSessionTokens = messages.reduce((sum, m) => sum + (m.meta?.inputTokens ?? 0) + (m.meta?.outputTokens ?? 0), 0)

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <PageHeader
          title="Playground"
          description="Send a chat completion through the router and see which provider serves it."
          actions={
            <>
              <Select value={selectedModel} onValueChange={(v) => setSelectedModel(v ?? 'auto')}>
                <SelectTrigger className="w-[260px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">Auto (fallback chain)</SelectItem>
                  {availableModels.map(m => (
                    <SelectItem key={m.modelDbId} value={m.modelId}>
                      <span className="flex items-center gap-2">
                        <span>{m.displayName}</span>
                        <span className="text-xs text-muted-foreground">{m.platform}</span>
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Link to="/debate" target="_blank">
                  <Button variant="outline" size="sm">
                    🎭 Debate AI
                  </Button>
                </Link>
                {messages.length > 0 && (
                <Button variant="outline" size="sm" onClick={handleClear}>New Chat</Button>
              )}
            </>
          }
        />
      </div>

      <div className="flex-1 flex gap-4 min-h-0">
        {/* History sidebar */}
        <div className={`flex flex-col border rounded-2xl bg-card overflow-hidden transition-all duration-200 ${showHistory ? 'w-72 shrink-0' : 'w-0 opacity-0'}`}>
          <div className="flex items-center justify-between px-4 py-3 border-b bg-muted/30">
            <span className="text-sm font-medium flex items-center gap-2"><History className="size-3.5" /> History</span>
            {history.length > 0 && (
              <Button variant="ghost" size="icon-xs" onClick={handleClearAll} title="Clear all history"><Trash2 className="size-3.5 text-destructive" /></Button>
            )}
          </div>

          {/* Search input */}
          <div className="px-3 py-2 border-b">
            <div className="relative">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 size-3 text-muted-foreground" />
              <input
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Search conversations…"
                className="w-full rounded-md border bg-background pl-7 pr-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {filteredHistory.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-6">
                {searchQuery ? 'No matches found' : 'No conversations yet'}
              </p>
            ) : (
              filteredHistory.map(entry => (
                <div
                  key={entry.id}
                  onClick={() => handleLoadHistory(entry)}
                  className={`group relative p-3 rounded-lg cursor-pointer transition-colors ${currentId === entry.id ? 'bg-accent' : 'hover:bg-muted'}`}
                >
                  <p className="text-sm font-medium truncate pr-6">{truncate(entry.firstUserMessage)}</p>
                  <div className="flex items-center gap-1 mt-1 text-[11px] text-muted-foreground flex-wrap">
                    <Clock className="size-3 shrink-0" /><span className="shrink-0">{formatTime(entry.createdAt)}</span>
                    <span>·</span>
                    <span className="font-mono truncate max-w-[70px]">{entry.model}</span>
                    <span>·</span>
                    <span className="shrink-0">{entry.messages.filter(m => m.role === 'user').length} turns</span>
                    {entry.totalTokens != null && (
                      <>
                        <span>·</span>
                        <Zap className="size-3 shrink-0 text-yellow-500" />
                        <span className="shrink-0">{entry.totalTokens.toLocaleString()} toks</span>
                      </>
                    )}
                  </div>
                  <button
                    onClick={(e) => handleDelete(e, entry.id)}
                    className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-destructive/20"
                    title="Delete"
                  >
                    <Trash2 className="size-3 text-destructive" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Main chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex-1 flex flex-col rounded-3xl border bg-card overflow-hidden min-h-0">
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {messages.length === 0 ? (
                <div className="flex items-center justify-center h-full text-center">
                  <div className="space-y-2 max-w-sm">
                    <p className="text-base font-medium">Send a message to get started.</p>
                    <p className="text-sm text-muted-foreground">
                      Using <span className="text-foreground">{activeModelLabel}</span>. Switch models above.
                    </p>
                    {totalSessionTokens > 0 && (
                      <p className="text-xs text-muted-foreground flex items-center justify-center gap-1">
                        <Zap className="size-3 text-yellow-500" /> Session: {totalSessionTokens.toLocaleString()} tokens
                      </p>
                    )}
                  </div>
                </div>
              ) : (
                <>
                  {messages.map((msg) => (
                    <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[78%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
                        {msg.role === 'assistant' ? <Markdown>{msg.content}</Markdown> : <div className="whitespace-pre-wrap">{msg.content}</div>}
                        {msg.meta && (
                          <div className="flex items-center gap-2 mt-2 flex-wrap text-[11px] opacity-70 tabular-nums">
                            {msg.meta.platform && <span>{msg.meta.platform}</span>}
                            {msg.meta.model && <span className="font-mono">· {msg.meta.model}</span>}
                            {msg.meta.latency != null && <span>· {msg.meta.latency} ms</span>}
                            {msg.meta.inputTokens != null && (
                              <><Zap className="size-3" /><span>· {msg.meta.inputTokens.toLocaleString()}↑/{msg.meta.outputTokens?.toLocaleString()}↓</span></>
                            )}
                            {msg.meta.fallbackAttempts != null && msg.meta.fallbackAttempts > 0 && <span>· {msg.meta.fallbackAttempts} fallback{msg.meta.fallbackAttempts > 1 ? 's' : ''}</span>}
                            {(msg.meta.rpmRemaining != null || msg.meta.tpmRemaining != null) && (
                              <span className="text-green-600 dark:text-green-400">
                                · RPM: {msg.meta.rpmRemaining ?? '?'} left
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  {loading && (
                    <div className="flex justify-start">
                      <div className="bg-muted rounded-2xl px-4 py-3">
                        <div className="flex gap-1">
                          <span className="size-1.5 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: '0ms' }} />
                          <span className="size-1.5 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: '150ms' }} />
                          <span className="size-1.5 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: '300ms' }} />
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            <div className="border-t bg-background/50 p-3">
              <div className="flex gap-2 items-end">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Type a message… (⏎ to send, ⇧⏎ for newline)"
                  rows={1}
                  className="flex-1 resize-none rounded-lg border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/50 min-h-[40px] max-h-[160px]"
                  style={{ height: 'auto', overflow: 'hidden' }}
                  onInput={e => { const el = e.target as HTMLTextAreaElement; el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 160) + 'px' }}
                />
                <Button onClick={handleSend} disabled={loading || !input.trim()} size="default">
                  {loading ? 'Sending…' : 'Send'}
                </Button>
                <Button variant="outline" size="icon" onClick={() => setShowHistory(v => !v)} title="Toggle history">
                  <History className="size-4" />
                </Button>
              </div>
              {totalSessionTokens > 0 && (
                <div className="mt-2 text-[11px] text-muted-foreground flex items-center gap-1 justify-end">
                  <Zap className="size-3 text-yellow-500" />
                  Session total: {totalSessionTokens.toLocaleString()} tokens
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
