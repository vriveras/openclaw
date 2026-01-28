# Windows Skill Installation Support

## Vision

Enable Moltbot skills to install their dependencies on Windows using native package managers (`winget`, `choco`) instead of failing with "brew not installed" errors.

## Goals (MVP)

- [ ] Detect Windows and use appropriate package manager
- [ ] Add `winget` installer kind (Windows 10+ built-in)
- [ ] Add `choco` installer kind (fallback for older Windows)
- [ ] Update skill manifests with Windows alternatives
- [ ] Graceful fallback when no Windows equivalent exists
- [ ] No breaking changes for macOS/Linux users

## Constraints

- Language: TypeScript
- Platform: Windows 10+, Node.js 22+
- Package managers: winget (preferred), chocolatey (fallback)
- Must maintain backward compatibility with existing brew/node/go/uv installers

## Out of Scope (v1)

- Automatic winget→brew mapping (manual mapping per skill)
- Scoop package manager support
- WSL-based fallback for unavailable packages
- GUI installer prompts

## Key Files

| File | Purpose |
|------|---------|
| `src/infra/winget.ts` | Windows package manager detection + helpers |
| `src/agents/skills-install.ts` | Add winget/choco to `buildInstallCommand` |
| `src/agents/skills.ts` | Update `SkillInstallSpec` type |
| `skills/*/SKILL.md` | Add Windows install alternatives |

## Package Manager Mapping

| Brew Formula | Winget ID | Choco Package |
|--------------|-----------|---------------|
| gh | GitHub.cli | gh |
| jq | jqlang.jq | jq |
| fzf | junegunn.fzf | fzf |
| ripgrep | BurntSushi.ripgrep.MSVC | ripgrep |
| ffmpeg | Gyan.FFmpeg | ffmpeg |
| yt-dlp | yt-dlp.yt-dlp | yt-dlp |
| imagemagick | ImageMagick.ImageMagick | imagemagick |

## Success Criteria

1. `moltbot onboard` completes on Windows without brew errors
2. Skills with Windows equivalents install successfully
3. Skills without Windows equivalents show clear "not available on Windows" message
4. All existing macOS/Linux functionality unchanged
