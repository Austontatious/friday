import { useEffect, useMemo, useRef, useState } from "react";
import { Button, Textarea, useColorMode, useToast } from "@chakra-ui/react";
import { MoonIcon, SunIcon } from "@chakra-ui/icons";
import { useNavigate } from "react-router-dom";
import type { ChatMode } from "./services/api";
import { confirmMemory, getStoredChatMode, sendPrompt, setStoredChatMode } from "./services/api";
import { isSketchMathEnabled } from "./services/sketchmath";
import type { ModelResponse } from "./types";

type Message = {
  sender: "user" | "ai";
  content: string;
};

type SystemEvent = {
  id: string;
  level: "info" | "success" | "warning" | "danger";
  title: string;
  detail: string;
  timestamp: string;
};

type RouteEntry = {
  label: string;
  detail: string;
  timestamp: string;
};

type ArtifactEntry = {
  label: string;
  detail: string;
};

const shellVersion = "2026-06-18-command-center-shell-v1";

const nowLabel = () =>
  new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date());

const makeEvent = (
  level: SystemEvent["level"],
  title: string,
  detail: string,
): SystemEvent => ({
  id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  level,
  title,
  detail,
  timestamp: nowLabel(),
});

const extractRouteLabel = (response: ModelResponse, mode: ChatMode): string => {
  const meta = response.meta || {};
  const route = meta.route || meta.router || meta.routing_path || meta.profile || meta.alias;
  const model = meta.model || meta.model_name || meta.route_model || meta.provider_model;
  return [route, model].filter(Boolean).join(" / ") || (mode === "direct_friday" ? "Direct Friday / default" : "Legacy route");
};

const extractContextUsage = (response: ModelResponse): string => {
  const meta = response.meta || {};
  const usage = meta.context_usage || meta.token_usage || meta.usage || meta.tokens;
  if (!usage) return "Context unavailable";
  if (typeof usage === "string") return usage;
  if (typeof usage === "number") return `${usage} tokens`;
  const used = usage.used || usage.prompt_tokens || usage.input_tokens || usage.total_tokens;
  const limit = usage.limit || usage.max || usage.context_limit;
  return used && limit ? `${used}/${limit}` : used ? `${used} tokens` : "Context reported";
};

const extractArtifacts = (response: ModelResponse): ArtifactEntry[] => {
  const metaArtifacts = response.meta?.artifacts;
  if (!Array.isArray(metaArtifacts)) return [];
  return metaArtifacts.slice(0, 6).map((artifact, index) => {
    if (typeof artifact === "string") {
      return { label: `Artifact ${index + 1}`, detail: artifact };
    }
    return {
      label: String(artifact.name || artifact.label || artifact.type || `Artifact ${index + 1}`),
      detail: String(artifact.path || artifact.url || artifact.detail || artifact.id || "Attached to response"),
    };
  });
};

const renderInlineMarkdown = (text: string) => {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g);
  return parts.map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (linkMatch) {
      return (
        <a key={index} href={linkMatch[2]} target="_blank" rel="noreferrer">
          {linkMatch[1]}
        </a>
      );
    }
    return part;
  });
};

const MarkdownDocument = ({ content }: { content: string }) => {
  const blocks = content.split(/\n{2,}/).map((block) => block.trim()).filter(Boolean);
  let inCodeFence = false;

  return (
    <div className="friday-markdown">
      {blocks.map((block, index) => {
        if (block.startsWith("```")) {
          inCodeFence = !inCodeFence;
          const code = block.replace(/^```[a-zA-Z0-9_-]*\n?/, "").replace(/```$/, "");
          return <pre key={index}><code>{code}</code></pre>;
        }
        if (inCodeFence) {
          return <pre key={index}><code>{block}</code></pre>;
        }
        if (block.startsWith("### ")) {
          return <h3 key={index}>{renderInlineMarkdown(block.slice(4))}</h3>;
        }
        if (block.startsWith("## ")) {
          return <h2 key={index}>{renderInlineMarkdown(block.slice(3))}</h2>;
        }
        if (block.startsWith("# ")) {
          return <h1 key={index}>{renderInlineMarkdown(block.slice(2))}</h1>;
        }
        const lines = block.split("\n");
        if (lines.every((line) => /^>\s?/.test(line))) {
          return (
            <blockquote key={index}>
              {lines.map((line, lineIndex) => (
                <p key={lineIndex}>{renderInlineMarkdown(line.replace(/^>\s?/, ""))}</p>
              ))}
            </blockquote>
          );
        }
        if (lines.every((line) => /^[-*]\s+/.test(line))) {
          return (
            <ul key={index}>
              {lines.map((line, lineIndex) => (
                <li key={lineIndex}>{renderInlineMarkdown(line.replace(/^[-*]\s+/, ""))}</li>
              ))}
            </ul>
          );
        }
        if (lines.every((line) => /^\d+\.\s+/.test(line))) {
          return (
            <ol key={index}>
              {lines.map((line, lineIndex) => (
                <li key={lineIndex}>{renderInlineMarkdown(line.replace(/^\d+\.\s+/, ""))}</li>
              ))}
            </ol>
          );
        }
        return <p key={index}>{renderInlineMarkdown(block)}</p>;
      })}
    </div>
  );
};

const App = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  const navigate = useNavigate();
  const toast = useToast();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [mode, setMode] = useState<ChatMode>(() => getStoredChatMode());
  const [pendingIds, setPendingIds] = useState<string[]>([]);
  const [confirming, setConfirming] = useState(false);
  const [systemEvents, setSystemEvents] = useState<SystemEvent[]>([
    makeEvent("success", "Shell ready", "Direct Friday workspace initialized."),
  ]);
  const [routeHistory, setRouteHistory] = useState<RouteEntry[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactEntry[]>([]);
  const [contextUsage, setContextUsage] = useState("Awaiting response");
  const [healthLabel, setHealthLabel] = useState("Idle");
  const [sessionMapOpen, setSessionMapOpen] = useState(true);
  const sketchMathEnabled = isSketchMathEnabled();
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    document.documentElement.dataset.fridayTheme = colorMode;
  }, [colorMode]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const assistantMessages = useMemo(
    () => messages.filter((message) => message.sender === "ai"),
    [messages],
  );
  const recentDecisions = assistantMessages.slice(-3).map((message) => {
    const firstLine = message.content.split("\n").find(Boolean) || "Assistant response";
    return firstLine.replace(/^#+\s*/, "").slice(0, 96);
  });

  const appendEvent = (event: SystemEvent) => {
    setSystemEvents((previous) => [event, ...previous].slice(0, 12));
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const currentInput = input;
    setInput("");
    setMessages((prev) => [...prev, { sender: "user", content: currentInput }]);
    setHealthLabel("Requesting");
    appendEvent(makeEvent("info", "Prompt sent", `Direct Friday request queued: ${currentInput.slice(0, 90)}`));

    try {
      const response = await sendPrompt({ prompt: currentInput }, mode);
      const cleaned = response.assistant_text || response.text || "FRIDAY gave no valid reply.";
      const routeLabel = extractRouteLabel(response, mode);

      setMessages((prev) => [...prev, { sender: "ai", content: cleaned }]);
      setContextUsage(extractContextUsage(response));
      setHealthLabel("Healthy");
      setRouteHistory((previous) => [
        { label: routeLabel, detail: response.meta?.fallback ? `Fallback: ${String(response.meta.fallback)}` : "Primary path", timestamp: nowLabel() },
        ...previous,
      ].slice(0, 8));
      setArtifacts((previous) => [...extractArtifacts(response), ...previous].slice(0, 8));

      const responsePending = Array.isArray(response.memory?.pending_ids)
        ? response.memory?.pending_ids ?? []
        : [];
      setPendingIds(responsePending);
      appendEvent(makeEvent("success", "Assistant response", `${routeLabel}; ${responsePending.length} memory confirmations pending.`));

      if (Array.isArray(response.tools) && response.tools.length > 0) {
        appendEvent(makeEvent("info", "Tool calls", `${response.tools.length} tool call${response.tools.length === 1 ? "" : "s"} reported by response.`));
      }
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Unknown request failure";
      setHealthLabel("Degraded");
      appendEvent(makeEvent("danger", "Request failed", detail));
    }

    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  };

  const handleConfirm = async (decision: "accept" | "reject") => {
    if (!pendingIds.length || confirming) return;

    setConfirming(true);
    try {
      await confirmMemory({ pending_ids: pendingIds, decision });
      appendEvent(makeEvent("success", decision === "accept" ? "Memory saved" : "Memory discarded", `${pendingIds.length} pending item${pendingIds.length === 1 ? "" : "s"} processed.`));
      setPendingIds([]);
      toast({
        title: decision === "accept" ? "Saved" : "Discarded",
        status: "success",
        duration: 2400,
        isClosable: true,
      });
    } catch (err) {
      const detail = err instanceof Error ? err.message : "Memory confirmation failed";
      appendEvent(makeEvent("danger", "Memory confirmation failed", detail));
      toast({
        title: "Memory confirmation failed",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setConfirming(false);
    }
  };

  const setActiveMode = (nextMode: ChatMode) => {
    setMode(nextMode);
    setStoredChatMode(nextMode);
    appendEvent(makeEvent("info", "Workspace changed", "Direct Friday mode selected."));
  };

  return (
    <main
      className="friday-command-shell"
      data-friday-shell-ui-version={shellVersion}
      data-testid="friday-command-shell"
    >
      <aside className="friday-mode-rail" aria-label="Friday workspaces">
        <div className="friday-brand-mark">F</div>
        <button
          type="button"
          className="friday-rail-item friday-rail-item-active"
          onClick={() => setActiveMode("direct_friday")}
          aria-label="Direct Friday"
        >
          <span>FR</span>
          <strong>Direct</strong>
        </button>
        {sketchMathEnabled ? (
          <button
            type="button"
            className="friday-rail-item"
            onClick={() => navigate("/tools/sketchmath")}
            aria-label="SketchMath"
          >
            <span>SM</span>
            <strong>Sketch</strong>
          </button>
        ) : null}
      </aside>

      <section className="friday-shell-frame">
        <header className="friday-status-bar">
          <div>
            <p className="friday-kicker">FRIDAY</p>
            <h1>Command Center</h1>
          </div>
          <div className="friday-status-grid" aria-label="Runtime status">
            <span><b>Mode</b> Direct Friday</span>
            <span><b>Route / Model</b> {routeHistory[0]?.label || "Direct Friday standby"}</span>
            <span><b>Context</b> {contextUsage}</span>
            <span className={`friday-health friday-health-${healthLabel.toLowerCase().replace(/\s+/g, "-")}`}><b>Health</b> {healthLabel}</span>
          </div>
          <Button size="sm" variant="ghost" onClick={toggleColorMode} aria-label="Toggle color mode" className="friday-icon-button">
            {colorMode === "light" ? <MoonIcon /> : <SunIcon />}
          </Button>
        </header>

        <div className="friday-workbench">
          <section className="friday-workspace-pane" aria-label="Direct Friday chat workspace">
            <div className="friday-chat-history" data-testid="friday-chat-history">
              {messages.length === 0 ? (
                <div className="friday-empty-state">
                  <span className="friday-empty-eyebrow">Ready workspace</span>
                  <h2>Direct Friday</h2>
                  <p>Ask for planning, coding support, operational checks, or a concise readout. Assistant replies render as clean documents; transport and tool failures stay in the sidecar.</p>
                  <div className="friday-empty-hints" aria-label="Direct Friday empty state capabilities">
                    <span>Markdown output</span>
                    <span>Event-aware failures</span>
                    <span>Quiet telemetry</span>
                  </div>
                </div>
              ) : (
                messages.map((message, index) => (
                  <article
                    key={`${message.sender}-${index}`}
                    className={`friday-message friday-message-${message.sender}`}
                  >
                    <div className="friday-message-label">{message.sender === "user" ? "You" : "FRIDAY"}</div>
                    {message.sender === "ai" ? (
                      <MarkdownDocument content={message.content} />
                    ) : (
                      <p>{message.content}</p>
                    )}
                  </article>
                ))
              )}
              <div ref={scrollRef} />
            </div>

            {pendingIds.length > 0 ? (
              <div className="friday-memory-confirmation">
                <span>{pendingIds.length} memories need confirmation</span>
                <div>
                  <Button size="sm" onClick={() => handleConfirm("accept")} isLoading={confirming}>
                    Accept all
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handleConfirm("reject")} isLoading={confirming}>
                    Reject all
                  </Button>
                </div>
              </div>
            ) : null}

            <div className="friday-composer">
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask FRIDAY something..."
                className="friday-composer-input"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void handleSend();
                  }
                }}
              />
              <Button onClick={() => void handleSend()} className="friday-send-button">
                SUBMIT
              </Button>
            </div>
          </section>

          <aside className="friday-telemetry-sidecar" data-testid="friday-telemetry-panel" aria-label="Telemetry sidecar">
            <button
              type="button"
              className="friday-session-toggle"
              onClick={() => setSessionMapOpen((open) => !open)}
              aria-expanded={sessionMapOpen}
            >
              Session Map
              <span>{sessionMapOpen ? "Collapse" : "Expand"}</span>
            </button>
            {sessionMapOpen ? (
              <section className="friday-session-map" data-testid="friday-session-map">
                <dl>
                  <div><dt>Objective</dt><dd>{messages[0]?.content || "No active objective yet"}</dd></div>
                  <div><dt>Workspace</dt><dd>Direct Friday chat</dd></div>
                  <div><dt>Recent decisions</dt><dd>{recentDecisions.length ? recentDecisions.join(" / ") : "No assistant decisions captured"}</dd></div>
                  <div><dt>Attached context</dt><dd>{pendingIds.length ? `${pendingIds.length} memory confirmations pending` : "No pending context attachments"}</dd></div>
                  <div><dt>Artifacts</dt><dd>{artifacts.length ? `${artifacts.length} tracked` : "No response artifacts"}</dd></div>
                </dl>
              </section>
            ) : null}

            <section>
              <h2>System Events</h2>
              <div className="friday-event-list">
                {systemEvents.map((event) => (
                  <article key={event.id} className={`friday-event friday-event-${event.level}`}>
                    <span>{event.timestamp}</span>
                    <strong>{event.title}</strong>
                    <p>{event.detail}</p>
                  </article>
                ))}
              </div>
            </section>

            <section>
              <h2>Route History</h2>
              <div className="friday-telemetry-list">
                {routeHistory.length ? routeHistory.map((entry) => (
                  <article key={`${entry.timestamp}-${entry.label}`}>
                    <strong>{entry.label}</strong>
                    <span>{entry.detail}</span>
                  </article>
                )) : <p className="friday-quiet-empty">No route decisions yet. The active model path will appear after the first response.</p>}
              </div>
            </section>

            <section>
              <h2>Artifacts</h2>
              <div className="friday-telemetry-list">
                {artifacts.length ? artifacts.map((artifact, index) => (
                  <article key={`${artifact.label}-${index}`}>
                    <strong>{artifact.label}</strong>
                    <span>{artifact.detail}</span>
                  </article>
                )) : <p className="friday-quiet-empty">No generated artifacts for this session.</p>}
              </div>
            </section>
          </aside>
        </div>
      </section>
    </main>
  );
};

export default App;
