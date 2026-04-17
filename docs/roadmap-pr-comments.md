# PR Comments: Fetch, Display, and Post from GitHub/GitLab

## Context

Specmap displays AI-generated annotations on PR diffs but has no awareness of human PR comments. Users must switch to GitHub/GitLab to read or write review comments. Adding comment support makes specmap a more complete review tool. Since specmap has no webhook infrastructure, the UI will poll for updates. The user specifically wants conflict detection when posting: if the thread changed since last refresh, block the submit, show what changed, and preserve the draft.

## Scope

- **In scope**: Fetch and display line-level review comments and general PR comments, threading (replies), reactions (display-only), posting new comments and replies, 60s polling, conflict detection on submit
- **Out of scope for v1**: Adding reactions, editing/deleting comments, resolving threads, review submission (APPROVE/REQUEST_CHANGES)

---

## 1. Normalized Data Model

GitHub has issue comments (general) + review comments (line-level, threaded via `in_reply_to_id`). GitLab has MR discussions (threaded, with optional `position` for line-level). Normalize to a unified model at the backend.

### Backend (Python dicts returned by forge providers)

```python
# Single comment
{
    "id": str,                    # Forge-native ID as string
    "author_login": str,
    "author_avatar": str,
    "body": str,                  # Markdown
    "created_at": str,            # ISO 8601
    "updated_at": str,
    "reactions": [{"emoji": str, "count": int}, ...],  # Aggregated
}

# Thread (group of comments)
{
    "thread_id": str,             # GitHub: root comment ID; GitLab: discussion ID
    "path": str | None,           # File path (None for general comments)
    "line": int | None,           # New-file line number
    "side": "LEFT" | "RIGHT" | None,
    "is_resolved": bool,
    "is_outdated": bool,          # GitHub: position no longer valid
    "comments": [comment, ...],   # Ordered by created_at
    "comment_count": int,
    "latest_updated_at": str,     # For conflict detection
}

# Full response
{
    "threads": [thread, ...],           # Line-level threads
    "general_comments": [thread, ...],  # PR-level threads (path=None)
}
```

### Frontend (TypeScript)

Add to `web/src/api/types.ts`:

```typescript
interface CommentAuthor { login: string; avatar_url: string; }
interface CommentReaction { emoji: string; count: number; }
interface Comment {
  id: string;
  author: CommentAuthor;
  body: string;
  created_at: string;
  updated_at: string;
  reactions: CommentReaction[];
}
interface CommentThread {
  thread_id: string;
  path: string | null;
  line: number | null;
  side: 'LEFT' | 'RIGHT' | null;
  is_resolved: boolean;
  is_outdated: boolean;
  comments: Comment[];
  comment_count: number;
  latest_updated_at: string;
}
interface CommentsResponse {
  threads: CommentThread[];
  general_comments: CommentThread[];
}
```

---

## 2. Forge Provider Methods

**File**: `src/specmap/server/forge.py`

Add to `ForgeProvider` protocol:

```python
async def list_pull_comments(
    self, client: httpx.AsyncClient, token: str,
    owner: str, repo: str, number: int,
) -> dict:
    """Return {threads: [...], general_comments: [...]}."""

async def post_pull_comment(
    self, client: httpx.AsyncClient, token: str,
    owner: str, repo: str, number: int,
    body: str, *,
    thread_id: str | None = None,
    path: str | None = None,
    line: int | None = None,
    side: str | None = None,
    head_sha: str | None = None,
) -> dict:
    """Post comment. Returns normalized comment dict."""
```

### GitHub Implementation (`src/specmap/server/github.py`)

**`list_pull_comments`**:
1. Fetch in parallel:
   - `GET /repos/{o}/{r}/issues/{n}/comments?per_page=100` (general)
   - `GET /repos/{o}/{r}/pulls/{n}/comments?per_page=100` (review/line-level)
2. Both paginated via Link header (reuse existing `_next_link()`)
3. Review comments: build threads by walking `in_reply_to_id` chains — the root comment (no `in_reply_to_id`) defines the `thread_id`. Group all comments sharing the same root.
4. Issue comments: each is a single-comment thread with `path=None`
5. Reactions: GitHub returns `reactions` object on comments (with `+1`, `-1`, `laugh`, etc. counts). Extract inline — no separate API call needed for counts.

**`post_pull_comment`**:
- Reply to review thread: `POST /repos/{o}/{r}/pulls/{n}/comments` with `{"body", "in_reply_to_id": thread_id}`
- New line-level: `POST /repos/{o}/{r}/pulls/{n}/comments` with `{"body", "commit_id": head_sha, "path", "line", "side"}`
- General: `POST /repos/{o}/{r}/issues/{n}/comments` with `{"body"}`

### GitLab Implementation (`src/specmap/server/gitlab.py`)

**`list_pull_comments`**:
1. `GET /projects/{id}/merge_requests/{iid}/discussions?per_page=100`
2. Each discussion is a thread. `discussion.notes[]` are the comments.
3. If any note has `position` with `new_line` → line-level thread; else general.
4. Reactions: GitLab doesn't include them inline. For v1, return `reactions: []`. Can add lazy-fetch later via `GET /projects/{id}/merge_requests/{iid}/notes/{note_id}/award_emoji`.

**`post_pull_comment`**:
- Reply: `POST /projects/{id}/merge_requests/{iid}/discussions/{thread_id}/notes` with `{"body"}`
- New line-level: `POST /projects/{id}/merge_requests/{iid}/discussions` with `{"body", "position": {"position_type": "text", "base_sha", "head_sha", "start_sha", "new_path": path, "new_line": line}}`
- General: `POST /projects/{id}/merge_requests/{iid}/notes` with `{"body"}`

**GitLab `diff_refs`**: Creating line-level comments requires `base_sha`, `head_sha`, `start_sha`. These come from the MR's `diff_refs` field. Options:
- **Option A**: Extend `_normalize_pull()` to include `diff_refs` — adds a field to the normalized pull dict
- **Option B**: Fetch MR details in `post_pull_comment` when creating a new thread

Recommend **Option A** — add `diff_refs` to `_normalize_pull()` since `get_pull` is already called during `_handle_get_pull`. The backend comment handler can access the PR data from the DB or refetch.

---

## 3. Backend Routes

**File**: `src/specmap/server/app.py`

Two new handlers:

```python
async def _handle_list_comments(request, owner, repo, number):
    """GET .../pulls/{number}/comments"""
    claims = _get_current_user(request)
    token = _get_forge_token(request, claims)
    provider = _provider(request)
    return await provider.list_pull_comments(_http(request), token, owner, repo, number)

async def _handle_post_comment(request, owner, repo, number):
    """POST .../pulls/{number}/comments"""
    claims = _get_current_user(request)
    token = _get_forge_token(request, claims)
    provider = _provider(request)
    data = await request.json()

    body = data.get("body", "").strip()
    if not body:
        raise HTTPError(400, "Comment body required")

    thread_id = data.get("thread_id")
    path = data.get("path")
    line = data.get("line")
    side = data.get("side")

    # For new line-level comments, need head_sha (and diff_refs for GitLab)
    head_sha = None
    if path and not thread_id:
        p = await provider.get_pull(_http(request), token, owner, repo, number)
        head_sha = p["head_sha"]

    result = await provider.post_pull_comment(
        _http(request), token, owner, repo, number,
        body, thread_id=thread_id, path=path, line=line,
        side=side, head_sha=head_sha,
    )
    return result
```

Add to dispatcher:
```python
if action == "comments" and method == "GET":
    return await _handle_list_comments(...)
if action == "comments" and method == "POST":
    return await _handle_post_comment(...)
```

---

## 4. Frontend API Endpoints

**File**: `web/src/api/endpoints.ts`

```typescript
export const comments = {
  list: (fullName: string, number: number) =>
    apiFetch<CommentsResponse>(`/api/v1/repos/${fullName}/pulls/${number}/comments`),
  post: (fullName: string, number: number, data: PostCommentRequest) =>
    apiFetch<Comment>(`/api/v1/repos/${fullName}/pulls/${number}/comments`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};
```

---

## 5. Comment Store (new file)

**File**: `web/src/stores/commentStore.ts`

Zustand store managing comment state, polling, drafts, and conflict detection.

### State shape

```typescript
interface CommentState {
  // Data
  threads: CommentThread[];
  generalComments: CommentThread[];
  threadsByFile: Map<string, CommentThread[]>;
  loading: boolean;
  error: string | null;

  // Polling
  pollTimer: ReturnType<typeof setInterval> | null;

  // Drafts: keyed by thread_id (reply) or "new:{path}:{line}" (new thread)
  drafts: Map<string, string>;

  // Conflict detection
  conflicts: Map<string, { stale: CommentThread; fresh: CommentThread }>;

  // Actions
  fetchComments(fullName: string, number: number): Promise<void>;
  startPolling(fullName: string, number: number): void;
  stopPolling(): void;
  postComment(fullName: string, number: number, req: PostCommentRequest): Promise<boolean>;
  setDraft(key: string, text: string): void;
  clearConflict(threadId: string): void;
}
```

### Conflict detection flow

When `postComment()` is called:
1. Set submitting state
2. Call `comments.list()` to get fresh state from forge
3. Find the target thread in the fresh response
4. Compare `comment_count` and `latest_updated_at` with the locally cached version
5. **If changed**: Store the conflict (`conflicts.set(threadId, { stale, fresh })`), update all thread state with fresh data, return `false`
6. **If unchanged**: Call `comments.post()`, then `fetchComments()` to refresh, return `true`
7. For **new threads** (no `thread_id`): skip conflict check, just post

### Polling

`startPolling(fullName, number)` sets a 60s `setInterval` calling `fetchComments`. The fetch merges new data into state. Polling stops on `stopPolling()` (called on page unmount).

Polling should be smart: compare the new response with current state before triggering a React re-render. Simple approach: compare `JSON.stringify` of thread IDs + comment counts + latest timestamps.

---

## 6. UI Components

### 6a. `CommentThread.tsx` (new)

**File**: `web/src/components/comments/CommentThread.tsx`

Renders a single thread: all comments in order.

- Each comment: avatar (16px) + `author.login` + relative timestamp + markdown body + reaction pills
- If > 3 comments: collapsed by default, showing root + "N more replies" + latest reply. Expand to see all.
- Reply form at the bottom (textarea + Submit button)
- Conflict banner when `conflicts.has(thread_id)`: warning text, shows fresh comments, preserves draft

### 6b. `InlineCommentWidget.tsx` (new)

**File**: `web/src/components/comments/InlineCommentWidget.tsx`

Wrapper for `CommentThread` styled for inline diff placement. Visually distinct from annotations — different border/background color (e.g., `--comment-border: #a78bfa` purple vs annotation blue). Placed as a widget in the diff table, same mechanism as `AnnotationWidget`.

### 6c. `ConversationPanel.tsx` (new)

**File**: `web/src/components/comments/ConversationPanel.tsx`

Collapsible section at the top of `PRReviewPage`, above the diff. Shows general (non-line) PR comments. "Conversation (N)" header. Contains `CommentThread` components and a form for posting new general comments.

### 6d. "Add comment" button on diff lines

**File**: `web/src/components/diff/DiffFile.tsx` (modify)

On hover over a gutter cell, show a small "+" icon button. Clicking opens an inline reply form for a new thread at that line. The button is rendered via CSS `:hover` on the gutter + an absolutely positioned element, or as a React hover state.

The new-thread form is an `InlineCommentWidget` with an empty thread and the draft input focused. On submit, posts via `commentStore.postComment()` with `{ body, path: file.filename, line }`.

---

## 7. Integration: DiffViewer + DiffFile

### DiffViewer.tsx (modify)

- Import `useCommentStore` and read `threadsByFile`
- Pass `commentThreads={threadsByFile.get(file.filename) ?? []}` to each `DiffFile`

### DiffFile.tsx (modify)

- Accept new prop `commentThreads: CommentThread[]`
- In the widget-building `useMemo`, after placing annotation widgets, also place comment widgets:
  - For each thread, find the change key for `thread.line` using the existing `findChangeForLine()`
  - Place `<InlineCommentWidget>` at that key
  - Comments and annotations at the same line stack (annotations first, then comments)
- The "+" button on gutter hover opens a new-thread form at that line

### Side mode

For v1, comments render inline only (in the diff table as widgets), not in the side annotation panel. This keeps comments visually separate from AI annotations and avoids complicating the positioning hooks. The side panel remains annotation-only.

---

## 8. PRReviewPage Integration

**File**: `web/src/pages/PRReviewPage.tsx` (modify)

- Import `useCommentStore`
- In the mount effect, call `fetchComments(fullName, prNumber)` and `startPolling(fullName, prNumber)`
- Return `stopPolling()` from cleanup
- Render `<ConversationPanel>` between the toolbar and `<DiffViewer>`

---

## 9. CSS Tokens

**File**: `web/src/index.css` (modify)

Add comment-specific tokens to distinguish from annotations:

```css
/* Light */
--comment-bg: #f5f3ff;
--comment-border: #a78bfa;

/* Dark */
--comment-bg: #1e1533;
--comment-border: #8b5cf6;
```

---

## Files Modified

| File | Change |
|------|--------|
| `src/specmap/server/forge.py` | Add `list_pull_comments`, `post_pull_comment` to protocol |
| `src/specmap/server/github.py` | Implement GitHub comment methods with thread reconstruction |
| `src/specmap/server/gitlab.py` | Implement GitLab comment methods via discussions API; extend `_normalize_pull` for `diff_refs` |
| `src/specmap/server/app.py` | Add `_handle_list_comments`, `_handle_post_comment` handlers + dispatcher |
| `web/src/api/types.ts` | Add `Comment`, `CommentThread`, `CommentsResponse`, `PostCommentRequest` types |
| `web/src/api/endpoints.ts` | Add `comments.list()`, `comments.post()` |
| `web/src/stores/commentStore.ts` | **New**: Zustand store with polling, conflict detection, drafts |
| `web/src/components/comments/CommentThread.tsx` | **New**: Thread renderer |
| `web/src/components/comments/InlineCommentWidget.tsx` | **New**: Diff widget wrapper |
| `web/src/components/comments/ConversationPanel.tsx` | **New**: General comments section |
| `web/src/components/diff/DiffFile.tsx` | Add comment widget placement + gutter "+" button |
| `web/src/components/diff/DiffViewer.tsx` | Pass `commentThreads` to `DiffFile` |
| `web/src/pages/PRReviewPage.tsx` | Wire up comment store, polling, `ConversationPanel` |
| `web/src/index.css` | Comment color tokens |

---

## Edge Cases

- **No comments on PR**: `threads` and `general_comments` are empty arrays — UI renders nothing extra
- **Outdated review comments** (code changed since comment): `is_outdated: true` — render with a visual indicator (muted/strikethrough). Don't hide them.
- **Resolved threads**: `is_resolved: true` — render collapsed with "(resolved)" label. Still visible.
- **GitHub reactions counts**: Inline on the comment response (`reactions.+1`, etc.) — extract without extra API calls
- **GitLab reactions**: Not included in discussions API. Return `reactions: []` for v1. Lazy-fetch is a follow-up.
- **Large PRs with many comments**: Pagination. Use existing `_next_link` (GitHub) / `_gitlab_next_url` (GitLab) helpers.
- **Binary/deleted files with comments**: Thread has `path` but file may not be in the diff. Render thread in ConversationPanel as a fallback.
- **Comment on a line that isn't visible in the diff**: Similar to annotation auto-expand. For v1, render in a "Comments outside visible hunks" section (same pattern as the existing annotation warning). Auto-expand as a follow-up.
- **Conflict on new thread**: Not applicable — new threads have no prior state to conflict with
- **Polling overlap**: If a poll fetch is in-flight when the user triggers a manual fetch (via submit conflict check), don't double-fetch. Use an `AbortController` or a fetch-in-progress flag.

---

## Verification

1. **Backend**: Add unit tests for `_normalize_comment()` and thread reconstruction in GitHub provider. Test GitLab discussion → thread mapping.
2. **Manual test (GitHub)**: `specmap serve` against a GitHub repo with PR comments → verify comments appear inline in diff at correct lines, general comments in ConversationPanel
3. **Manual test (GitLab)**: Same with a GitLab MR
4. **Polling**: Leave page open, add a comment on GitHub/GitLab directly → appears in specmap within 60s
5. **Conflict detection**: Open two tabs. In tab A, start typing a reply. In tab B, post a reply. In tab A, click submit → should show conflict warning with tab B's comment, draft preserved
6. **Post comment**: Reply to existing thread → appears on GitHub/GitLab. New line-level comment → creates thread at correct line on forge.
7. **Reactions**: Comments with reactions on GitHub show emoji pills with counts
