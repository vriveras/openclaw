# Roadmap: Windows Skill Installation

## Phase 1: Package Manager Infrastructure
**Goal:** Add Windows package manager detection and execution utilities

- Create `src/infra/winget.ts` with winget/choco detection
- Add `resolveWingetExecutable()` and `resolveChocoExecutable()`
- Add `getWindowsPackageManager()` to pick best available
- Unit tests for detection logic

## Phase 2: Skill Installer Integration
**Goal:** Update skill installer to support Windows package managers

- Add `winget` and `choco` to `SkillInstallSpec` type
- Update `buildInstallCommand()` to handle Windows installers
- Add platform detection to choose brew vs winget/choco
- Handle "not available on Windows" gracefully

## Phase 3: Skill Manifest Updates
**Goal:** Add Windows install specs to existing skills

- Audit skills that use brew
- Add `winget` alternatives where available
- Mark skills as Windows-incompatible where no alternative exists
- Update skill documentation

## Phase 4: Testing & Polish
**Goal:** Verify everything works end-to-end on Windows

- Test `moltbot onboard` on Windows
- Test individual skill installs
- Add CI workflow for Windows skill tests
- Update docs with Windows installation guide
