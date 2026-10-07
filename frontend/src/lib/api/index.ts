// Typed API layer — the only module pages should import backend/data access from.
// Domain modules (repos, reviews, chats) are added slice by slice.
export * from './types'
export * from './capabilities'
export { ApiError, API_BASE, isRateLimited, request, sendKeepalive, setAuthTokenProvider } from './http'
export type { ApiErrorKind } from './http'
export {
  parseRepoUrl, normalizeFingerprint, repoSummaryOf, fingerprintChips, typeHintsMeasured, typeHintsRepresentative, topLanguages,
  isAccountUserId, listRepos, analyzeRepo, startAnalyzeJob, getAnalyzeJob, isActiveAnalysis,
} from './repos'
export type { ParsedRepoUrl, AnalyzeResult, AnalyzeJobStatus } from './repos'
export {
  reviewCode, normalizeReview, normalizeFinding, parseLineHint, explainDegraded, formatMetricValue, REVIEW_LANGUAGES, AGENT_LABEL,
} from './reviews'
export type { RawReview, RawIssue, ReviewLanguage, ReviewProgress } from './reviews'
export { askQuestion, chatRepoUrl, groupChatsByRepo, historyFor, repoShortName } from './chats'
export type { Answer, ChatGroup, ChatMemory, HistoryTurn } from './chats'
export { fetchAllReviews, fetchRepoReviews, fetchRepoChats, fetchSavedReview, reviewFromRow, SAVED_CODE_LIMIT } from './history'
export { cleanupGuestOnUnload, cleanupGuestSession } from './guest'
