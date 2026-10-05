// Typed API layer — the only module pages should import backend/data access from.
// Domain modules (repos, reviews, chats) are added slice by slice.
export * from './types'
export * from './capabilities'
export { ApiError, API_BASE, request, setAuthTokenProvider } from './http'
export type { ApiErrorKind } from './http'
export {
  parseRepoUrl, normalizeFingerprint, fingerprintChips, topLanguages,
  isAccountUserId, listRepos, analyzeRepo,
} from './repos'
export type { ParsedRepoUrl, AnalyzeResult } from './repos'
export {
  reviewCode, normalizeReview, normalizeFinding, parseLineHint, REVIEW_LANGUAGES, AGENT_LABEL,
} from './reviews'
export type { RawReview, RawIssue, ReviewLanguage } from './reviews'
export { askQuestion, chatRepoUrl, groupChatsByRepo, repoShortName } from './chats'
export type { Answer, ChatGroup } from './chats'
