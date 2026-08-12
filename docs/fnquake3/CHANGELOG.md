# Changelog

This is the pending release-note queue for the next FnQuake3 release.

Keep short user-facing bullets under `Unreleased` as changes land. During release publishing, the workflow asks GitHub Copilot to dedupe and categorize the notes for the GitHub release details, then clears this section for the next cycle.

## [Unreleased]

### Highlights
- _None yet._

### Compatibility
- _None yet._

### Rendering and Display
- _None yet._

### Audio
- _None yet._

### Builds and Packaging
- _None yet._

### Fixes
- `sv_playdemo` now holds on the first demo frame until a real client is ready to watch, and repeated playback no longer exhausts hunk memory and crashes the server.
- Fixed a dedicated-server crash (`VM_Call with NULL vm`) triggered by typing any unrecognized console command while `sv_playdemo` demo cinema playback was active. Also added a new read-only `sv_playingDemo` cvar (visible locally and to remote `getinfo`/`getstatus` queries) so it's now possible to tell whether a server is currently replaying a demo.
- `sv_playdemo` now checks that the demo's map is actually present on the server before starting cinema playback, instead of starting anyway and leaving every connecting client to discover the missing map on its own and disconnect.

### Documentation and Tooling
- _None yet._
