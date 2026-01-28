# State: Windows Skill Installation

## Position
- **Phase:** 2 of 4
- **Status:** Phase 1 complete, ready for Phase 2

## Decisions
- **Primary PM:** winget (built into Windows 10+)
- **Fallback PM:** chocolatey (wider package coverage)
- **Detection order:** winget → choco → error
- **Manifest format:** Add `winget`/`choco` fields to existing `install` array

## Blockers
None

## Done
- [x] PROJECT.md created
- [x] ROADMAP.md created
- [x] STATE.md created
- [x] PLAN.md for Phase 1
- [x] **Phase 1: Package Manager Infrastructure**
  - [x] Task 1.1: winget.ts created
  - [x] Task 1.2: 18 tests added
  - [x] Task 1.3: SkillInstallSpec updated with winget/choco
  - [x] Task 1.4: buildInstallCommand handles winget/choco

## Commits
- d642d54c5 feat: add winget/choco support for Windows skill installation

## Notes
- winget path: `C:\Users\<user>\AppData\Local\Microsoft\WindowsApps\winget.exe`
- choco path: `C:\ProgramData\chocolatey\bin\choco.exe`
- Both need elevation for some installs (handled by the tools themselves)
