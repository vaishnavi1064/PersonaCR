// Typed API layer — the only module pages should import backend/data access from.
// Domain modules (repos, reviews, chats) are added slice by slice.
export * from './types'
export * from './capabilities'
export { ApiError, API_BASE, request, setAuthTokenProvider } from './http'
export type { ApiErrorKind } from './http'
