# Packaging strategy note

`agent_praxis` currently re-exposes `framework/` and `environments/` through
package mirrors so repository commands and tests can import from stable paths.

For v0.1, this was a pragmatic local workaround for an import-layout issue
caught in this session. The mirrors are functional but should be revisited
before release. Preferred next step: consolidate the canonical code under
`agent_praxis/` directly and remove the mirror layer, or document the intended
layout explicitly and keep one source of truth.
