import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, X, Loader2 } from 'lucide-react'
import { getUserAnalyzedRepos } from '../../lib/db'
import type { AnalyzedRepo } from '../../lib/db'
import { analyzeRepo } from '../../lib/api'

interface Props {
  userId: string
  selectedUrls: string[]
  onSelectionChange: (urls: string[]) => void
  /** Derived review target — selectedUrls[0]. Kept for call-site clarity. */
  primaryUrl?: string | null
  /** Promote a URL to review target (reorder to index 0). */
  onPrimaryChange?: (url: string | null) => void
}

const chipEasing: [number, number, number, number] = [0.22, 1, 0.36, 1]

export default function RepoSelector({
  userId,
  selectedUrls,
  onSelectionChange,
  primaryUrl: primaryUrlProp,
  onPrimaryChange,
}: Props) {
  const [repos, setRepos] = useState<AnalyzedRepo[]>([])
  const [showInput, setShowInput] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

  // Single-slice contract: index 0 is always the review target
  const primaryUrl = primaryUrlProp ?? selectedUrls[0] ?? null

  // Load user's analyzed repos
  useEffect(() => {
    if (userId === 'anonymous') return
    getUserAnalyzedRepos(userId).then(setRepos)
  }, [userId])

  const promotePrimary = useCallback((url: string) => {
    if (onPrimaryChange) {
      onPrimaryChange(url)
      return
    }
    if (!selectedUrls.includes(url) || selectedUrls[0] === url) return
    onSelectionChange([url, ...selectedUrls.filter((u) => u !== url)])
  }, [selectedUrls, onSelectionChange, onPrimaryChange])

  const toggleRepo = useCallback((url: string) => {
    const isSelected = selectedUrls.includes(url)
    const next = isSelected
      ? selectedUrls.filter((u) => u !== url)
      : [...selectedUrls, url]
    // Order alone encodes primary — no separate primary store write
    onSelectionChange(next)
  }, [selectedUrls, onSelectionChange])

  const handleAddRepo = useCallback(async () => {
    const url = inputValue.trim()
    if (!url) return

    setAdding(true)
    setAddError(null)

    try {
      const result = await analyzeRepo(url, userId)
      const repoName = result.repo_name ?? url.split('/').slice(-2).join('/')
      const cleanUrl = url.replace(/\/$/, '')

      // Add to local repos list if not already present
      setRepos((prev) => {
        if (prev.some((r) => r.repo_url === cleanUrl)) return prev
        return [{ repo_url: cleanUrl, repo_name: repoName, languages: [] }, ...prev]
      })

      // Auto-select the new repo (becomes primary if it is the only selection)
      if (!selectedUrls.includes(cleanUrl)) {
        onSelectionChange([...selectedUrls, cleanUrl])
      }

      setInputValue('')
      setShowInput(false)
    } catch (err) {
      setAddError(err instanceof Error ? err.message : 'Failed to analyze repo')
    } finally {
      setAdding(false)
    }
  }, [inputValue, userId, selectedUrls, onSelectionChange])

  const repoDisplayName = (repo: AnalyzedRepo) => {
    if (repo.repo_name) return repo.repo_name
    const parts = repo.repo_url.replace(/\/$/, '').split('/')
    return parts.slice(-2).join('/')
  }

  return (
    <div style={{
      padding: '12px 0 8px',
      borderBottom: '0.5px solid var(--border)',
      flexShrink: 0,
    }}>
      <p style={{
        fontFamily: 'var(--font-body)',
        fontSize: 12,
        color: 'var(--text-tertiary)',
        marginBottom: 8,
      }}>
        Repos in this conversation
      </p>

      {repos.length === 0 && !showInput ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <p style={{
            fontFamily: 'var(--font-body)',
            fontSize: 13,
            color: 'var(--text-tertiary)',
          }}>
            Add a repo to get started
          </p>
          <button
            type="button"
            onClick={() => setShowInput(true)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              fontFamily: 'var(--font-body)',
              fontSize: 13,
              fontWeight: 500,
              color: 'var(--accent)',
              background: 'var(--accent-surface)',
              border: '0.5px solid var(--accent)',
              borderRadius: 8,
              padding: '5px 12px',
              cursor: 'pointer',
              transition: 'filter 0.15s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.filter = 'brightness(1.1)')}
            onMouseLeave={(e) => (e.currentTarget.style.filter = 'brightness(1)')}
          >
            <Plus size={13} />
            Add repo
          </button>
        </div>
      ) : (
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 6,
          alignItems: 'center',
        }}>
          <AnimatePresence mode="popLayout">
            {repos.map((repo) => {
              const isSelected = selectedUrls.includes(repo.repo_url)
              return (
                <motion.button
                  key={repo.repo_url}
                  type="button"
                  onClick={() => toggleRepo(repo.repo_url)}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  transition={{ duration: 0.25, ease: chipEasing }}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    fontFamily: 'var(--font-body)',
                    fontSize: 13,
                    color: isSelected ? 'var(--accent)' : 'var(--text-secondary)',
                    background: isSelected ? 'var(--accent-surface)' : 'transparent',
                    border: `0.5px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`,
                    borderRadius: 8,
                    padding: '5px 12px',
                    cursor: 'pointer',
                    transition: 'background 0.15s, border-color 0.15s, color 0.15s',
                    maxWidth: 200,
                  }}
                  title={repo.repo_url}
                >
                  {isSelected && (
                    <span
                      onClick={(e) => {
                        e.stopPropagation()
                        promotePrimary(repo.repo_url)
                      }}
                      title={primaryUrl === repo.repo_url ? "Code reviews use this repo's fingerprint" : "Click the dot to make this the review target"}
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        background: primaryUrl === repo.repo_url ? 'var(--accent)' : 'transparent',
                        border: `1px solid ${primaryUrl === repo.repo_url ? 'var(--accent)' : 'var(--text-tertiary)'}`,
                        flexShrink: 0,
                        cursor: 'pointer',
                      }}
                    />
                  )}
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {repoDisplayName(repo)}
                  </span>
                </motion.button>
              )
            })}
          </AnimatePresence>

          {/* Add repo button */}
          {!showInput && (
            <button
              type="button"
              onClick={() => setShowInput(true)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                fontFamily: 'var(--font-body)',
                fontSize: 12,
                color: 'var(--text-tertiary)',
                background: 'transparent',
                border: '0.5px solid var(--border)',
                borderRadius: 8,
                padding: '5px 10px',
                cursor: 'pointer',
                transition: 'border-color 0.15s, color 0.15s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--border-hover)'
                e.currentTarget.style.color = 'var(--text-secondary)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border)'
                e.currentTarget.style.color = 'var(--text-tertiary)'
              }}
            >
              <Plus size={12} />
              Add
            </button>
          )}
        </div>
      )}

      {/* Inline add-repo input */}
      <AnimatePresence>
        {showInput && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: chipEasing }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{
              display: 'flex',
              gap: 8,
              marginTop: 8,
              alignItems: 'center',
            }}>
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleAddRepo()
                  if (e.key === 'Escape') { setShowInput(false); setAddError(null) }
                }}
                placeholder="https://github.com/owner/repo"
                disabled={adding}
                autoFocus
                style={{
                  flex: 1,
                  fontFamily: 'var(--font-body)',
                  fontSize: 13,
                  color: 'var(--text-primary)',
                  background: 'var(--bg-secondary)',
                  border: '0.5px solid var(--border)',
                  borderRadius: 8,
                  padding: '6px 12px',
                  outline: 'none',
                }}
              />
              <button
                type="button"
                onClick={handleAddRepo}
                disabled={adding || !inputValue.trim()}
                style={{
                  fontFamily: 'var(--font-body)',
                  fontSize: 13,
                  fontWeight: 500,
                  color: 'white',
                  background: adding || !inputValue.trim() ? 'var(--bg-tertiary)' : 'var(--accent)',
                  border: 'none',
                  borderRadius: 8,
                  padding: '6px 14px',
                  cursor: adding || !inputValue.trim() ? 'default' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                {adding ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> : null}
                {adding ? 'Analyzing…' : 'Add'}
              </button>
              <button
                type="button"
                onClick={() => { setShowInput(false); setAddError(null) }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 28,
                  height: 28,
                  borderRadius: 6,
                  border: '0.5px solid var(--border)',
                  background: 'transparent',
                  color: 'var(--text-tertiary)',
                  cursor: 'pointer',
                }}
              >
                <X size={13} />
              </button>
            </div>
            {addError && (
              <p style={{
                fontFamily: 'var(--font-body)',
                fontSize: 12,
                color: 'var(--error)',
                marginTop: 4,
              }}>
                {addError}
              </p>
            )}
            <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
