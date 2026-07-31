import { useEffect, useState } from 'react'
import { getSupabaseClient } from '../lib/supabase'
import { ApiError, searchDecisions, type SearchResponse } from '../lib/api'

/**
 * Fire-and-forget: logs a completed search to search_history via the
 * search-history Edge Function so it shows up in Settings > Search. Never
 * blocks or fails the actual search — a logging problem shouldn't stop the
 * user from seeing their answer. Respects the user's saveHistory
 * preference server side (the function no-ops if they've turned it off).
 */
function recordSearchHistory(query: string, resultCount: number) {
  void getSupabaseClient()
    .functions.invoke('search-history', {
      body: { action: 'record', query, result_count: resultCount },
    })
    .catch(() => {
      // Best-effort only.
    })
}

const SUGGESTIONS = [
  'What does our org already know about the Q3 timeline?',
  'What context do we have on the onboarding flow?',
]

type RecentSearch = { query: string; at: number }

function firstName(email: string | null | undefined, displayName: string | null | undefined) {
  if (displayName) return displayName.split(/\s+/)[0]
  if (!email) return 'there'
  return email.split('@')[0].split(/[._-]+/)[0].replace(/^\w/, (c) => c.toUpperCase())
}

function timeAgo(at: number, now = Date.now()) {
  const minutes = Math.max(1, Math.floor((now - at) / 60_000))
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export function DashboardSearch() {
  const [greetingName, setGreetingName] = useState('there')
  const [question, setQuestion] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  const [result, setResult] = useState<SearchResponse | null>(null)
  const [error, setError] = useState('')
  const [recentSearches, setRecentSearches] = useState<RecentSearch[]>([])

  useEffect(() => {
    const supabase = getSupabaseClient()
    void supabase.auth.getSession().then(({ data }) => {
      const user = data.session?.user
      const displayName =
        (user?.user_metadata.full_name as string | undefined) ??
        (user?.user_metadata.name as string | undefined) ??
        null
      setGreetingName(firstName(user?.email, displayName))
    })
  }, [])

  const runSearch = async (submittedQuestion: string) => {
    const trimmed = submittedQuestion.trim()
    if (!trimmed || isSearching) return

    setIsSearching(true)
    setError('')
    setResult(null)

    try {
      const response = await searchDecisions(trimmed)
      setResult(response)
      setRecentSearches((current) => [{ query: trimmed, at: Date.now() }, ...current].slice(0, 5))
      recordSearchHistory(trimmed, response.citations.length)
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        const wait = err.retryAfterSeconds ? ` Try again in ${err.retryAfterSeconds}s.` : ''
        setError(`You're searching too quickly.${wait}`)
      } else {
        setError(err instanceof ApiError ? err.message : 'Search failed, try again.')
      }
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <section className="mb-8">
      <h1 className="mb-5 text-[32px] font-bold leading-tight tracking-[-0.02em] text-[#111827]">
        Good morning, {greetingName}
      </h1>

      <form
        className="relative mb-3.5"
        onSubmit={(event) => {
          event.preventDefault()
          void runSearch(question)
        }}
      >
        <div className="flex h-[52px] items-center rounded-xl border border-[#E5E7EB] bg-white px-4 shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
          <svg
            className="mr-3 shrink-0 text-[#9CA3AF]"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
            <path
              d="M20 20l-3.5-3.5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
          <input
            type="text"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask anything your organization already knows."
            className="h-full w-full bg-transparent text-[15px] text-[#111827] outline-none placeholder:text-[#9CA3AF]"
          />
          <button
            type="submit"
            disabled={isSearching || !question.trim()}
            className="ml-3 shrink-0 rounded-lg bg-[#5A45FF] px-5 py-2 text-[14px] font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSearching ? 'Asking...' : 'Ask'}
          </button>
        </div>
      </form>

      <div className="mb-7 flex flex-wrap gap-2.5">
        {SUGGESTIONS.map((text, i) => (
          <button
            key={`${text}-${i}`}
            type="button"
            onClick={() => {
              setQuestion(text)
              void runSearch(text)
            }}
            className="rounded-full border border-[#E5E7EB] bg-white px-4 py-2 text-[13px] font-medium text-[#374151] transition-colors hover:bg-[#F9FAFB]"
          >
            {text}
          </button>
        ))}
      </div>

      {error ? (
        <div className="mb-6 rounded-xl border border-[#F3D6D6] bg-[#FFF7F7] px-4 py-3 text-[14px] text-[#B4232C]">
          {error}
        </div>
      ) : null}

      {result ? (
        <div className="mb-7 rounded-xl border border-[#E8E8ED] bg-white p-5 shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
          <p className="text-[15px] leading-6 whitespace-pre-wrap text-[#111827]">
            {result.answer}
          </p>
          {result.citations.length > 0 ? (
            <ul className="mt-4 flex flex-col gap-2 border-t border-[#F0F0F4] pt-4">
              {result.citations.map((citation) => (
                <li key={citation.decision_id} className="text-[13px] text-[#6B7280]">
                  <span className="font-semibold text-[#5A45FF]">
                    [{citation.decision_number}]
                  </span>{' '}
                  {citation.decision_statement}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {recentSearches.length > 0 ? (
        <div>
          <h2 className="mb-3 text-[11px] font-semibold tracking-[0.08em] text-[#9CA3AF] uppercase">
            Recent Search
          </h2>
          <ul className="overflow-hidden rounded-xl border border-[#E8E8ED] bg-white">
            {recentSearches.map((item, i) => (
              <li
                key={`${item.query}-${item.at}`}
                className={`flex items-center justify-between px-4 py-3.5 ${
                  i < recentSearches.length - 1 ? 'border-b border-[#F0F0F4]' : ''
                }`}
              >
                <button
                  type="button"
                  onClick={() => {
                    setQuestion(item.query)
                    void runSearch(item.query)
                  }}
                  className="truncate text-left text-[14px] text-[#374151] hover:text-[#5A45FF]"
                >
                  {item.query}
                </button>
                <span className="ml-4 shrink-0 text-[13px] text-[#9CA3AF]">
                  {timeAgo(item.at)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}
