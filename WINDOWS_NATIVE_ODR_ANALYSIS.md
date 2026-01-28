# Windows Native Support & ODR Integration Analysis
**Date:** 2026-01-28  
**Project:** Moltbot/Clawdbot  
**Objective:** Enable native Windows execution with ODR (On-Demand Remote) integration

---

## Executive Summary

Moltbot currently works on Windows **only via WSL** (Windows Subsystem for Linux). The codebase has minimal Windows-native support, defaulting to Unix-style shells and paths. To enable **native Windows execution with ODR integration**, significant architectural changes are required across the exec tool, shell handling, and security model.

**Key Finding:** The WLXC project (WSL→Windows CLI Sandbox) being built in parallel provides the **exact foundation needed** for ODR integration. Instead of reimplementing container/policy controls, Moltbot should integrate with WLXC as its Windows execution backend.

---

## Current State: Windows Support

### What Works Today (WSL Only)

| Feature | Status | Implementation |
|---------|--------|----------------|
| Shell execution | ✅ WSL | Uses `/bin/sh` via Node.js child_process |
| Environment loading | ✅ WSL | Loads `$SHELL` login env |
| PTY support | ✅ WSL | node-pty works in WSL |
| File access | ✅ WSL | Unix paths work normally |
| Networking | ✅ WSL | Linux network stack |

### What Doesn't Work (Native Windows)

| Feature | Status | Reason |
|---------|--------|--------|
| Native exec | ❌ | Shell defaults to `/bin/sh` |
| PowerShell | ❌ | Only `cmd.exe` supported (basic) |
| Windows paths | ❌ | Path normalization expects Unix |
| Environment vars | ❌ | Shell env loading skipped on win32 |
| PTY on Windows | ⚠️ | node-pty works but limited testing |
| Process isolation | ❌ | No container/sandbox support |

---

## Code Analysis: Key Files

### 1. Shell Execution (`src/infra/shell-env.ts`)

**Current behavior on Windows:**
```typescript
if (process.platform === "win32") {
  cachedShellPath = null;  // Skips shell PATH loading
  return cachedShellPath;
}
```

**Issue:** Windows is explicitly excluded from shell environment loading. This means:
- No `$PATH` from user profile
- No environment variables from login shell
- Limited to system-wide `%PATH%`

### 2. Shell Command Building (`src/infra/node-shell.ts`)

**Current implementation:**
```typescript
if (normalized.startsWith("win")) {
  return ["cmd.exe", "/d", "/s", "/c", command];  // Basic cmd.exe
}
return ["/bin/sh", "-lc", command];  // Unix default
```

**Limitations:**
- Only `cmd.exe` support (no PowerShell)
- No PTY/interactive mode consideration
- No profile/environment loading
- Basic command string execution only

### 3. Exec Tool (`src/agents/bash-tools.exec.ts`)

**Architecture:**
- Direct Node.js `child_process` spawn
- Optional PTY mode (node-pty)
- Approval system for dangerous commands
- Session registry for background processes

**Missing for Windows:**
- Process isolation/sandboxing
- Policy-based execution controls
- Container/silo support
- Audit logging for compliance

### 4. Exec Approvals (`src/infra/exec-approvals.ts`)

**Windows-specific code:**
```typescript
// Path handling on Windows
const hasExtension = process.platform === "win32" && path.extname(expanded).length > 0;
if (process.platform === "win32" && !hasWildcard) {
  // Special handling for .exe/.bat/.cmd
}
```

**Current approach:**
- Basic allowlist/denylist
- File-based approvals
- No policy engine
- No runtime enforcement beyond string matching

---

## ODR Integration Requirements

### What is ODR?

**On-Demand Remote (ODR)** is Microsoft's enterprise execution framework for:
- **Sandboxed execution** of untrusted workloads
- **Policy-based controls** (allow/deny, resource limits, network restrictions)
- **Audit logging** for compliance
- **Container/VM isolation** (HCS, Hyper-V, or process silos)

**Use case:** Agents/automation running tools in customer environments need to comply with enterprise security policies.

### ODR Integration Needs

| Requirement | Description | Priority |
|-------------|-------------|----------|
| **Policy enforcement** | Every exec must pass policy check | 🔴 Critical |
| **Container isolation** | Tools run in sandboxed containers | 🔴 Critical |
| **Audit trail** | Immutable logs of all executions | 🔴 Critical |
| **Resource limits** | CPU/memory/timeout caps | 🟡 High |
| **Network control** | Allowlist/denylist for outbound | 🟡 High |
| **Mount restrictions** | RO/RW file access controls | 🟡 High |
| **Identity propagation** | Caller context (user/agent/session) | 🟢 Medium |

---

## Architecture Gap Analysis

### Current: Direct Execution Model

```
Moltbot Agent
  ↓
bash-tools.exec.ts
  ↓
Node.js child_process.spawn()
  ↓
cmd.exe / /bin/sh
  ↓
Tool runs with HOST PRIVILEGES (no isolation)
```

**Problems:**
- No policy layer
- No sandboxing
- No audit trail
- No resource limits
- Full host access

### Target: ODR-Integrated Model

```
Moltbot Agent
  ↓
bash-tools.exec.ts (new ODR path)
  ↓
WLXC / ODR Adapter
  ↓
Policy Evaluation (allow/deny + mutations)
  ↓
Container Creation (HCS/Hyper-V)
  ↓
Tool runs in ISOLATED CONTAINER
  ↓
Audit Log + Artifacts Stored
```

**Benefits:**
- ✅ Policy-first enforcement
- ✅ Process/VM isolation
- ✅ Full audit trail
- ✅ Resource limits enforced
- ✅ Default-deny file/network access

---

## Recommended Solution: WLXC Integration

### Why WLXC?

**WLXC (WSL→Windows CLI Sandbox)** is being built in parallel and provides:
- **Policy engine** (JSON rules, moving to OPA/Rego)
- **HCS adapter** for Windows container primitives
- **Audit system** with immutable logs
- **Mount controls** (RO/RW, allowlist/denylist)
- **Network restrictions** (none/outbound_allowlist/full)
- **Resource limits** (CPU/memory/timeout)

**Perfect fit:** WLXC is **exactly** what Moltbot needs for ODR compliance.

### Integration Plan

#### Phase 1: WLXC as Exec Backend (Windows Only)

**Changes to Moltbot:**

1. **New exec mode:** `host=wlxc` (alongside `sandbox`, `gateway`, `node`)
   ```typescript
   // src/agents/bash-tools.exec.ts
   if (params.host === "wlxc") {
     return await executeViaWLXC(params);
   }
   ```

2. **WLXC adapter module:** `src/infra/wlxc-adapter.ts`
   - Converts Moltbot exec params → WLXC RunRequest
   - Invokes `wlxc.exe run` via child_process
   - Parses stdout/stderr and exit code
   - Handles policy denials and errors

3. **Config schema updates:** `src/config/types.tools.ts`
   ```json
   {
     "tools": {
       "exec": {
         "host": "wlxc",
         "wlxc": {
           "exePath": "C:\\wlxc\\wlxc.exe",
           "defaultPolicy": "strict",
           "auditPath": "C:\\ProgramData\\wlxc\\runs"
         }
       }
     }
   }
   ```

4. **Policy passthrough:** Moltbot's approval system → WLXC policy
   - Map allowlist/denylist to WLXC policy JSON
   - Propagate caller context (agent/session)
   - Set resource limits from config

#### Phase 2: PowerShell & Enhanced Windows Support

**Changes:**

1. **PowerShell detection:**
   ```typescript
   // src/infra/node-shell.ts
   if (normalized.startsWith("win")) {
     if (hasPowerShell()) {
       return ["powershell.exe", "-NoProfile", "-Command", command];
     }
     return ["cmd.exe", "/d", "/s", "/c", command];
   }
   ```

2. **Windows environment loading:**
   ```typescript
   // src/infra/shell-env.ts
   if (process.platform === "win32") {
     return loadPowerShellEnvironment();  // New function
   }
   ```

3. **Path normalization:**
   - Convert WSL paths (`/mnt/c/...`) → Windows paths (`C:\...`)
   - Handle UNC paths, drive letters, environment vars

#### Phase 3: Cross-Platform Policy Engine

**Goal:** Unified policy model for Linux (Docker/podman) and Windows (WLXC/ODR)

**Architecture:**
```typescript
interface ExecutionPolicy {
  mode: "direct" | "sandboxed" | "container";
  isolation: "none" | "process" | "vm";
  allowlist: string[];
  denylist: string[];
  mounts: Mount[];
  network: NetworkPolicy;
  resources: ResourceLimits;
}
```

**Backends:**
- Linux: Docker/podman (existing sandbox support)
- Windows: WLXC (new ODR integration)
- macOS: Future (sandboxd/App Sandbox)

---

## Implementation Roadmap

### Milestone 1: WLXC Foundation (Q1 2026)

**Dependencies:**
- [x] WLXC v1.0 complete (in progress)
  - Rust CLI + policy engine
  - HCS adapter for process isolation
  - Audit logging + artifact storage

**Deliverables:**
1. WLXC adapter module in Moltbot
2. Config schema for `host=wlxc`
3. Basic integration tests
4. Documentation for setup

**Timeline:** 2-3 weeks after WLXC v1.0 ships

### Milestone 2: Windows Native Support (Q2 2026)

**Deliverables:**
1. PowerShell as primary shell on Windows
2. Windows environment variable loading
3. Path normalization (WSL ↔ Windows)
4. PTY mode testing on Windows

**Timeline:** 3-4 weeks

### Milestone 3: Unified Policy Engine (Q2 2026)

**Deliverables:**
1. Abstract policy interface
2. WLXC policy backend (Windows)
3. Docker policy backend (Linux)
4. Policy migration guide

**Timeline:** 4-5 weeks

### Milestone 4: Production Hardening (Q3 2026)

**Deliverables:**
1. Full audit log integration
2. ODR compliance documentation
3. Performance optimization
4. Security audit + pen testing

**Timeline:** 4-6 weeks

---

## Technical Decisions & Trade-offs

### Decision 1: WLXC vs. Native ODR SDK

**Options:**
1. ✅ **Use WLXC** as abstraction layer
   - Pro: Clean separation, WLXC handles HCS complexity
   - Pro: WLXC can evolve independently
   - Pro: Easier testing (mock WLXC CLI)
   - Con: Extra process hop (Moltbot → WLXC → HCS)

2. ❌ **Direct HCS integration** (C++/Rust bindings)
   - Pro: Lower latency
   - Con: Complex Windows API surface
   - Con: Hard to test/mock
   - Con: Duplication of WLXC policy engine

**Recommendation:** **Use WLXC.** The abstraction benefits outweigh the minor latency cost.

### Decision 2: Execution Mode Strategy

**Options:**
1. ✅ **Explicit opt-in** (`host=wlxc`)
   - Pro: No breaking changes
   - Pro: Gradual rollout
   - Pro: Easy fallback to direct exec
   - Con: Users must configure

2. ❌ **Auto-detect + auto-enable**
   - Pro: Seamless for users
   - Con: Breaking changes on Windows
   - Con: Harder to debug failures
   - Con: Policy mismatches

**Recommendation:** **Explicit opt-in.** Safer for production rollout.

### Decision 3: Policy Source of Truth

**Options:**
1. ✅ **WLXC owns policy**
   - Pro: Single source of truth
   - Pro: Policy enforced at exec boundary
   - Pro: Audit logs match policy version
   - Con: Moltbot allowlist becomes advisory

2. ❌ **Moltbot owns policy**
   - Pro: Consistent with current model
   - Con: Duplication with WLXC
   - Con: Policy drift between layers
   - Con: Weaker security boundary

**Recommendation:** **WLXC owns policy.** Moltbot's approval system becomes a UX layer on top.

---

## Security Considerations

### Threat Model Changes

**Before (WSL/Direct Exec):**
- Threat: Malicious agent executes arbitrary commands
- Mitigation: Approval prompts, allowlist/denylist
- Weakness: User can approve anything, full host access

**After (WLXC/ODR):**
- Threat: Same
- Mitigation: Policy-enforced denial, process isolation, audit trail
- Strength: Even approved commands are sandboxed and logged

### Attack Surface

**New risks:**
- WLXC.exe vulnerability could escalate privileges
- Policy misconfiguration could block legitimate tools
- Audit log tampering (mitigated by immutable logs)

**Mitigations:**
- WLXC security audit before production
- Default-deny policy with explicit allowlist
- Audit log integrity checks (hashes, append-only)

---

## Testing Strategy

### Unit Tests

**Moltbot side:**
- WLXC adapter: request building, response parsing
- Config validation: schema enforcement
- Error handling: WLXC denials, failures

**WLXC side:**
- Policy evaluation: allowlist/denylist logic
- Container lifecycle: create/exec/destroy
- Audit logging: record completeness

### Integration Tests

**End-to-end:**
1. Moltbot agent sends exec request
2. WLXC evaluates policy → allowed
3. Tool runs in container
4. stdout/stderr captured
5. Exit code propagated
6. Audit log written

**Failure modes:**
1. Policy denial → error returned to agent
2. Container creation fails → graceful error
3. Tool timeout → container killed
4. WLXC.exe not found → fallback or error

### Manual Testing

**Windows environments:**
- Windows 10/11 Pro (HCS available)
- Windows Server 2019/2022
- WSL 1 vs. WSL 2 vs. native Windows

**Tools to test:**
- git.exe, powershell.exe, python.exe
- curl.exe, node.exe, npm.exe
- Custom binaries (signed vs. unsigned)

---

## Migration Guide (for Users)

### Before: WSL-Only Setup

```bash
# Run Moltbot in WSL
cd /mnt/c/Users/me/moltbot
npm start
```

**Exec behavior:** Direct `/bin/sh` execution, no isolation

### After: Windows Native + ODR

1. **Install WLXC:**
   ```powershell
   # Download wlxc.exe to C:\wlxc\
   # Verify: wlxc version
   ```

2. **Configure Moltbot:**
   ```json
   {
     "tools": {
       "exec": {
         "host": "wlxc",
         "wlxc": {
           "exePath": "C:\\wlxc\\wlxc.exe",
           "defaultPolicy": "dev"
         }
       }
     }
   }
   ```

3. **Run Moltbot natively:**
   ```powershell
   cd C:\Users\me\moltbot
   npm start
   ```

**Exec behavior:** WLXC-sandboxed execution, policy-enforced, audited

### Compatibility

**Breaking changes:**
- None if `host=wlxc` is opt-in
- Default behavior (WSL) unchanged

**Upgrade path:**
1. Test with WLXC in dev environment
2. Migrate policies from Moltbot → WLXC
3. Enable `host=wlxc` in prod config
4. Monitor audit logs for denials

---

## Open Questions

1. **WLXC availability:**  
   Q: When will WLXC v1.0 be production-ready?  
   A: Estimated 2-4 weeks (Phase 1 of WLXC build in progress)

2. **Policy migration:**  
   Q: How do existing Moltbot allowlists map to WLXC policies?  
   A: Need converter script: `moltbot-policy.json` → `wlxc-policy.json`

3. **Performance:**  
   Q: Latency overhead of WLXC vs. direct exec?  
   A: Estimated +50-100ms (policy eval + container create/destroy)  
   **Mitigation:** Container pooling (WLXC v2 roadmap)

4. **Fallback behavior:**  
   Q: If WLXC fails, should Moltbot fall back to direct exec?  
   A: **No** (security policy violation). Fail-safe: deny execution.

5. **Cross-platform:**  
   Q: Should Linux also use WLXC-style policies?  
   A: **Yes** (Milestone 3: unified policy engine)

---

## Next Steps

### Immediate (Week 1-2)

1. ✅ Complete this analysis document
2. ⏳ Review with Vicente (you!)
3. ⏳ Finalize WLXC integration architecture
4. ⏳ Create GitHub issue: "Windows native exec via WLXC"

### Short-term (Week 3-6)

1. ⏳ Wait for WLXC v1.0 completion
2. ⏳ Build WLXC adapter module
3. ⏳ Write integration tests
4. ⏳ Create PR: "feat: Windows native exec with ODR support"

### Long-term (Q2-Q3 2026)

1. ⏳ PowerShell support
2. ⏳ Unified policy engine
3. ⏳ Production hardening
4. ⏳ ODR compliance certification

---

## Appendix A: Files to Modify

### New Files (to create)

| Path | Purpose |
|------|---------|
| `src/infra/wlxc-adapter.ts` | WLXC CLI adapter + request builder |
| `src/infra/wlxc-adapter.test.ts` | Unit tests for adapter |
| `src/infra/wlxc-types.ts` | TypeScript types for WLXC data contracts |
| `src/infra/windows-env.ts` | PowerShell environment loading |
| `src/infra/windows-paths.ts` | Path conversion (WSL ↔ Windows) |
| `docs/windows-native.md` | User guide for Windows setup |
| `docs/odr-integration.md` | ODR compliance documentation |

### Existing Files (to modify)

| Path | Changes |
|------|---------|
| `src/agents/bash-tools.exec.ts` | Add `host=wlxc` execution path |
| `src/infra/node-shell.ts` | Add PowerShell detection + support |
| `src/infra/shell-env.ts` | Enable Windows environment loading |
| `src/config/types.tools.ts` | Add WLXC config schema |
| `src/config/config-schema.yaml` | Add WLXC properties |
| `README.md` | Update with Windows native support |

### Configuration Examples (to add)

| File | Content |
|------|---------|
| `.env.example` | WLXC path, policy defaults |
| `config-examples/windows-native.json` | Full Windows config |
| `config-examples/odr-enterprise.json` | ODR compliance config |

---

## Appendix B: WLXC CLI Examples

### Plan a command (dry-run)

```powershell
wlxc plan -- git.exe status
```

**Output:**
```
ALLOWED: git.exe status
Policy: dev (hash: abc123...)
Mounts:
  - C:\Users\me\repo → /work (ro)
  - C:\ProgramData\wlxc\runs\run-xyz → /out (rw)
Network: none
Resources: cpu=50%, mem=2048MB, timeout=5m
Toolbox: toolbox-wincli:2026.01
```

### Run a command

```powershell
wlxc run -- git.exe status
```

**Output:** (same as native `git status`, but sandboxed)

### Check audit logs

```powershell
wlxc logs run-xyz
```

**Output:**
```json
{
  "runId": "run-xyz",
  "timestamp": "2026-01-28T10:15:30Z",
  "caller": { "wslUser": "me", "agentId": "moltbot-123" },
  "tool": { "exe": "git.exe", "args": ["status"] },
  "policy": { "hash": "abc123...", "decision": "allow" },
  "result": { "exitCode": 0, "durationMs": 150 }
}
```

---

## Conclusion

**TL;DR:**
- Moltbot works on Windows today **only via WSL**
- Native Windows exec needs **PowerShell support** + **path normalization**
- ODR integration requires **WLXC** for policy/sandboxing/audit
- **Recommended path:** Wait for WLXC v1.0, then integrate as exec backend
- **Timeline:** 2-3 weeks for WLXC integration, 6-8 weeks for full Windows native support

**Key insight:** WLXC solves the exact problem Moltbot needs for ODR. Integrate, don't duplicate.

**Next decision point:** Approve WLXC integration architecture → start implementation.

---

**Questions? Concerns? Ready to move forward?** 🚀
