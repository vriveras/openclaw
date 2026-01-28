# State: Windows Skill Installation

## Position
- **Phase:** 1 of 4
- **Status:** Planning complete, ready to execute

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
- [ ] PLAN.md for Phase 1

## Notes
- winget path: `C:\Users\<user>\AppData\Local\Microsoft\WindowsApps\winget.exe`
- choco path: `C:\ProgramData\chocolatey\bin\choco.exe`
- Both need elevation for some installs (handled by the tools themselves)
