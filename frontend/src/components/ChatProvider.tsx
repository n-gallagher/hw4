import { useState, type ReactNode } from 'react'
import type { ProductSummary } from '../api'
import { ChatContext, type ChatResults } from './ChatContext'

export default function ChatProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const [results, setResults] = useState<ChatResults | null>(null)

  const openChat = (prefill?: string) => {
    if (prefill) setDraft(prefill)
    setIsOpen(true)
  }

  const showResults = (query: string, products: ProductSummary[]) =>
    setResults((prev) => ({ id: (prev?.id ?? 0) + 1, query, products }))

  return (
    <ChatContext.Provider
      value={{
        isOpen,
        draft,
        setDraft,
        openChat,
        closeChat: () => setIsOpen(false),
        results,
        showResults,
        clearResults: () => setResults(null),
      }}
    >
      {children}
    </ChatContext.Provider>
  )
}
