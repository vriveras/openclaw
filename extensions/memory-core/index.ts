import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import { emptyPluginConfigSchema } from "openclaw/plugin-sdk";

const memoryCorePlugin = {
  id: "memory-core",
  name: "Memory (Core)",
  description: "File-backed memory search tools and CLI",
  kind: "memory",
  configSchema: emptyPluginConfigSchema(),
  register(api: OpenClawPluginApi) {
    api.registerTool(
      (ctx) => {
        const memorySearchTool = api.runtime.tools.createMemorySearchTool({
          config: ctx.config,
          agentSessionKey: ctx.sessionKey,
        });
        const memoryGetTool = api.runtime.tools.createMemoryGetTool({
          config: ctx.config,
          agentSessionKey: ctx.sessionKey,
        });
        const memorySearchRefsTool = api.runtime.tools.createMemorySearchRefsTool({
          config: ctx.config,
          agentSessionKey: ctx.sessionKey,
        });
        const memoryExpandTool = api.runtime.tools.createMemoryExpandTool({
          config: ctx.config,
          agentSessionKey: ctx.sessionKey,
        });
        if (!memorySearchTool || !memoryGetTool) {
          return null;
        }
        return [
          memorySearchTool,
          memoryGetTool,
          ...(memorySearchRefsTool ? [memorySearchRefsTool] : []),
          ...(memoryExpandTool ? [memoryExpandTool] : []),
        ];
      },
      { names: ["memory_search", "memory_get", "memory_search_refs", "memory_expand"] },
    );

    api.registerCli(
      ({ program }) => {
        api.runtime.tools.registerMemoryCli(program);
      },
      { commands: ["memory"] },
    );
  },
};

export default memoryCorePlugin;
