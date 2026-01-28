<plan phase="1" name="Package Manager Infrastructure">

<task id="1.1" type="auto">
  <name>Create Windows package manager utilities</name>
  <files>src/infra/winget.ts</files>
  <action>
    Create src/infra/winget.ts with:
    
    1. `resolveWingetExecutable()` - Find winget.exe
       - Check common paths: %LOCALAPPDATA%\Microsoft\WindowsApps\winget.exe
       - Also check if `winget` is in PATH via `where winget`
       - Return path or undefined
    
    2. `resolveChocoExecutable()` - Find choco.exe
       - Check: C:\ProgramData\chocolatey\bin\choco.exe
       - Also check PATH via `where choco`
       - Return path or undefined
    
    3. `getWindowsPackageManager()` - Pick best available
       - Returns { manager: 'winget' | 'choco' | null, path: string | null }
       - Prefer winget over choco
    
    4. `isWindowsPlatform()` - Simple platform check
    
    Use similar patterns to src/infra/brew.ts for consistency.
  </action>
  <verify>
    - File exists and exports all functions
    - Type-checks with tsc
  </verify>
  <done>winget.ts created with all 4 functions</done>
</task>

<task id="1.2" type="auto">
  <name>Add unit tests for Windows package manager detection</name>
  <files>src/infra/winget.test.ts</files>
  <action>
    Create src/infra/winget.test.ts with tests:
    
    1. isWindowsPlatform() returns boolean
    2. resolveWingetExecutable() returns string or undefined
    3. resolveChocoExecutable() returns string or undefined  
    4. getWindowsPackageManager() prefers winget over choco
    5. getWindowsPackageManager() falls back to choco when winget unavailable
    6. getWindowsPackageManager() returns null when neither available
    
    Mock filesystem/PATH checks for cross-platform testing.
    Follow patterns from brew.test.ts.
  </action>
  <verify>pnpm vitest run src/infra/winget.test.ts passes</verify>
  <done>All tests pass</done>
</task>

<task id="1.3" type="auto">
  <name>Update SkillInstallSpec type for Windows</name>
  <files>src/agents/skills.ts</files>
  <action>
    Update the SkillInstallSpec type to add:
    
    1. Add 'winget' and 'choco' to the `kind` union type
    2. Add optional `wingetId?: string` field (e.g., "GitHub.cli")
    3. Add optional `chocoPackage?: string` field (e.g., "gh")
    4. Add optional `windowsOnly?: boolean` field
    5. Add optional `platforms?: ('windows' | 'macos' | 'linux')[]` field
    
    This allows skills to specify:
    ```yaml
    install:
      - kind: brew
        formula: gh
      - kind: winget
        wingetId: GitHub.cli
    ```
  </action>
  <verify>tsc passes with no type errors</verify>
  <done>SkillInstallSpec updated with Windows fields</done>
</task>

<task id="1.4" type="auto">
  <name>Integrate Windows installers into buildInstallCommand</name>
  <files>src/agents/skills-install.ts</files>
  <action>
    Update buildInstallCommand() to handle winget and choco:
    
    1. Add case for 'winget':
       - Check spec.wingetId exists
       - Return ['winget', 'install', '--id', spec.wingetId, '-e', '--accept-source-agreements', '--accept-package-agreements']
    
    2. Add case for 'choco':
       - Check spec.chocoPackage exists
       - Return ['choco', 'install', spec.chocoPackage, '-y']
    
    3. Add platform-aware installer selection:
       - If on Windows and spec.kind === 'brew', check if there's a winget/choco alternative
       - If no alternative, return error "not available on Windows"
    
    Import getWindowsPackageManager from winget.ts.
  </action>
  <verify>
    - tsc passes
    - Existing tests still pass
  </verify>
  <done>buildInstallCommand handles winget and choco</done>
</task>

</plan>
