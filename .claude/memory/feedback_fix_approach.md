---
name: feedback-fix-approach
description: Rule for how to approach issue fixes — always clean up unnecessary/dead code alongside the targeted fix.
metadata:
  type: feedback
---

When resolving any issue (GATE compliance or otherwise), also remove unnecessary, dead, or redundant code in the same files touched by the fix.

**Why:** Fixing a bug while leaving surrounding dead code creates confusion and technical debt. For example, fixing ISSUE-10 (activating SL_TIMEFRAME_MAP) means the old structural SL path that is now bypassed should also be removed, not left as a dormant fallback.

**How to apply:** After making the targeted change for an issue:
1. Scan the same function/file for unreachable branches, unused variables, or legacy fallbacks made obsolete by the fix.
2. Remove them in the same edit pass — do not create a separate cleanup task.
3. Verify the function is cleaner and shorter after the fix, not longer.
4. Do not remove code that is a legitimate fallback or reused elsewhere — only remove what the fix made truly dead.
