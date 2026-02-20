import { createInternalHookEvent, triggerInternalHook } from "../hooks/internal-hooks.js";

type SessionTranscriptUpdate = {
  sessionFile: string;
};

type SessionTranscriptListener = (update: SessionTranscriptUpdate) => void;

const SESSION_TRANSCRIPT_LISTENERS = new Set<SessionTranscriptListener>();

export function onSessionTranscriptUpdate(listener: SessionTranscriptListener): () => void {
  SESSION_TRANSCRIPT_LISTENERS.add(listener);
  return () => {
    SESSION_TRANSCRIPT_LISTENERS.delete(listener);
  };
}

export async function emitSessionTranscriptUpdate(sessionFile: string): Promise<void> {
  const trimmed = sessionFile.trim();
  if (!trimmed) {
    return;
  }
  const update = { sessionFile: trimmed };

  // Notify legacy listeners
  for (const listener of SESSION_TRANSCRIPT_LISTENERS) {
    listener(update);
  }

  // Dispatch hook event for manifest-based hooks
  // Extract sessionKey from file path if possible (sessionFile format: /path/to/<sessionId>.jsonl)
  // For now, use empty sessionKey - hooks can extract from sessionFile
  const hookEvent = createInternalHookEvent(
    "session",
    "transcript:update",
    "", // sessionKey - hooks can derive from sessionFile
    { sessionFile: trimmed },
  );
  await triggerInternalHook(hookEvent);
}
