import { describe, expect, it } from 'vitest'
import type { ChatMeta } from '../db'
import { chatRepoUrl, groupChatsByRepo } from './chats'

const chat = (id: string, updated_at: string, repos: Partial<ChatMeta> = {}): ChatMeta => ({
  id, title: id, starred: false, last_repo_url: null, primary_repo_url: null, selected_repos: [], updated_at, ...repos,
})

describe('chatRepoUrl', () => {
  it('uses the first selected repo, then primary, then last', () => {
    expect(chatRepoUrl(chat('a', 't', { selected_repos: ['r1', 'r2'], primary_repo_url: 'p' }))).toBe('r1')
    expect(chatRepoUrl(chat('a', 't', { primary_repo_url: 'p', last_repo_url: 'l' }))).toBe('p')
    expect(chatRepoUrl(chat('a', 't', { last_repo_url: 'l' }))).toBe('l')
    expect(chatRepoUrl(chat('a', 't'))).toBeNull()
  })
})

describe('groupChatsByRepo', () => {
  it('groups by repo, newest group first, "no repo" last', () => {
    const groups = groupChatsByRepo([
      chat('old-api', '2026-10-01', { selected_repos: ['api'] }),
      chat('none', '2026-10-05'),
      chat('web', '2026-10-03', { selected_repos: ['web'] }),
      chat('new-api', '2026-10-04', { selected_repos: ['api'] }),
    ])
    expect(groups.map((g) => g.repoUrl)).toEqual(['api', 'web', null])
    expect(groups[0].chats.map((c) => c.id)).toEqual(['new-api', 'old-api'])
  })
})
