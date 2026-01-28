<plan phase="3" name="Skill Manifest Updates">

<task id="3.1" type="auto">
  <name>Add winget specs to cross-platform skills</name>
  <files>
    skills/github/SKILL.md
    skills/himalaya/SKILL.md
    skills/nano-banana-pro/SKILL.md
    skills/openai-image-gen/SKILL.md
    skills/1password/SKILL.md
  </files>
  <action>
    Add winget install specs to skills with Windows equivalents:
    
    | Skill | Brew Formula | Winget ID |
    |-------|--------------|-----------|
    | github | gh | GitHub.cli |
    | nano-banana-pro | uv | astral-sh.uv |
    | openai-image-gen | python | Python.Python.3.12 |
    | 1password | 1password-cli | AgileBits.1Password.CLI |
    
    For himalaya: use download kind with GitHub release URL for Windows binary.
    
    Update the JSON metadata in each SKILL.md frontmatter to add:
    {"id":"winget","kind":"winget","wingetId":"...","bins":["..."],"label":"Install ... (winget)"}
  </action>
  <verify>grep for wingetId in each file</verify>
  <done>5 skills updated with Windows install specs</done>
</task>

<task id="3.2" type="auto">
  <name>Mark macOS-only skills with platforms field</name>
  <files>
    skills/apple-notes/SKILL.md
    skills/apple-reminders/SKILL.md
    skills/imsg/SKILL.md
    skills/camsnap/SKILL.md
    skills/bird/SKILL.md
    skills/peekaboo/SKILL.md
    skills/sag/SKILL.md
  </files>
  <action>
    These skills use macOS-only tools (steipete/tap/*) and have no Windows equivalent.
    Add "os": ["macos"] to their metadata to indicate they're macOS-only.
    
    This will allow the installer to skip them on Windows with a clear message.
  </action>
  <verify>grep for "os.*macos" in each file</verify>
  <done>macOS-only skills marked</done>
</task>

<task id="3.3" type="auto">
  <name>Add download-based installs for CLI tools</name>
  <files>
    skills/himalaya/SKILL.md
    skills/gifgrep/SKILL.md
  </files>
  <action>
    For tools that don't have winget packages but do have Windows binaries on GitHub,
    add download-based install specs:
    
    {"id":"download-windows","kind":"download","url":"https://github.com/.../releases/latest/download/...-windows.zip","platforms":["windows"],"extract":true,"bins":["..."]}
  </action>
  <verify>Test download URLs are valid</verify>
  <done>Download-based Windows installs added</done>
</task>

</plan>
