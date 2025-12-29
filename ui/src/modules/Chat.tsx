import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { QueryResponse } from "../services/api";
import { useSafeQuery } from "./useSafeQuery";
import { ChatIcon } from "../components/Icons";

/**
 * Post-process LLM output to improve formatting:
 * - Convert ASCII formulas to LaTeX
 * - Normalize excessive line breaks
 */
function processContent(content: string): string {
  let processed = content;

  // Normalize multiple consecutive newlines to single newline
  processed = processed.replace(/\n{3,}/g, "\n\n");

  // Convert common ASCII formula patterns to LaTeX
  // Pattern: P(X = k) = (e^(-λ) * (λ^k)) / k!
  processed = processed.replace(
    /P\s*\(\s*[Xx]\s*=\s*k\s*\)\s*=\s*\(\s*e\s*\^\s*\(\s*-\s*[λλ]\s*\)\s*\*\s*\(\s*[λλ]\s*\^\s*k\s*\)\s*\)\s*\/\s*k\s*!/gi,
    "$P(X=k) = \\frac{e^{-\\lambda} \\lambda^k}{k!}$"
  );

  // Pattern: P(x) = (e^(-μ) * (μ^x)) / x!
  processed = processed.replace(
    /P\s*\(\s*x\s*\)\s*=\s*\(\s*e\s*\^\s*\(\s*-\s*[μµ]\s*\)\s*\*\s*\(\s*[μµ]\s*\^\s*x\s*\)\s*\)\s*\/\s*x\s*!/gi,
    "$P(x) = \\frac{e^{-\\mu} \\mu^x}{x!}$"
  );

  // Generic exponential patterns: e^(-x) -> $e^{-x}$
  processed = processed.replace(
    /\be\s*\^\s*\(\s*-\s*([^)]+)\s*\)/g,
    "$e^{-$1}$"
  );

  // Factorial: x! when standalone
  processed = processed.replace(/(\d+)!/g, "$$$1!$$");

  return processed;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata?: {
    citations?: QueryResponse["citations"];
    max_pii_sensitivity?: QueryResponse["max_pii_sensitivity"];
  };
}

interface ChatProps {
  subjectId?: string | null;
  contextType?: string | null;
  messages: ChatMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
}

export const Chat: React.FC<ChatProps> = ({
  subjectId = null,
  contextType = null,
  messages,
  setMessages,
}) => {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState<string>("");
  const { ask, askStream } = useSafeQuery();
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change or streaming content updates
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  const generateId = () =>
    `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    setError(null);
    const userMsg: ChatMessage = {
      id: generateId(),
      role: "user",
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setStreamingContent("");

    const assistantId = generateId();

    try {
      let fullContent = "";
      let streamWorked = false;

      // Try streaming first
      try {
        await askStream(
          text,
          { subjectId, contextType },
          (token) => {
            fullContent += token;
            setStreamingContent(fullContent);
          },
          () => {
            // On done - finalize the message
            streamWorked = true;
          },
          (errorMsg) => {
            setError(errorMsg);
          }
        );
      } catch (streamErr: any) {
        // Streaming failed, will fallback
        console.log("Streaming not available, falling back to regular query");
      }

      if (streamWorked && fullContent.trim()) {
        // Add the streamed response as a complete message
        const assistantMsg: ChatMessage = {
          id: assistantId,
          role: "assistant",
          content: fullContent.trim(),
          metadata: {},
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } else {
        // Fallback to regular (non-streaming) query
        const resp = await ask(text, { subjectId, contextType });
        const assistantMsg: ChatMessage = {
          id: assistantId,
          role: "assistant",
          content: resp.answer,
          metadata: {
            citations: resp.citations,
            max_pii_sensitivity: resp.max_pii_sensitivity,
          },
        };
        setMessages((prev) => [...prev, assistantMsg]);
      }
    } catch (e: any) {
      setError(e?.message || "Error inesperado al consultar el backend.");
    } finally {
      setLoading(false);
      setStreamingContent("");
    }
  };

  const handleKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (
    e
  ) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  return (
    <main className="chat-main">
      <section className="chat-history" aria-label="Historial de conversacion">
        {messages.length === 0 && !streamingContent && !loading && (
          <div className="chat-empty empty-state">
            <span className="empty-state-icon" aria-hidden="true">
              <ChatIcon size={48} />
            </span>
            <p className="empty-state-title">Inicia una conversacion</p>
            <p className="empty-state-description">
              Escribe una pregunta para comenzar. Algunos ejemplos:
            </p>
            <ul className="chat-empty-examples">
              <li>
                <strong>Consulta personal:</strong> "Que informacion tengo
                asociada a mi cuenta?"
              </li>
              <li>
                <strong>Analisis de contexto:</strong> "Resume los datos
                relevantes de este perfil."
              </li>
              <li>
                <strong>Documentacion:</strong> "Como se gestiona este tipo de
                caso segun los procedimientos internos?"
              </li>
            </ul>
          </div>
        )}
        {/* LLM Initialization indicator for first query */}
        {loading && messages.length === 1 && !streamingContent && (
          <div className="llm-initializing">
            <div className="llm-initializing-spinner" aria-hidden="true"></div>
            <div className="llm-initializing-text">
              <p className="llm-initializing-title">
                Inicializando asistente...
              </p>
              <p className="llm-initializing-subtitle">
                La primera consulta puede tomar unos segundos mientras el modelo
                se carga en memoria.
              </p>
            </div>
          </div>
        )}
        {messages.map((m) => (
          <article key={m.id} className={`chat-message chat-${m.role}`}>
            <header className="chat-message-header">
              <span className="chat-role">
                {m.role === "user" ? "Tu" : "Cortex"}
              </span>
            </header>
            <div className="chat-content">
              {m.role === "assistant" ? (
                <ReactMarkdown
                  remarkPlugins={[remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                >
                  {processContent(m.content)}
                </ReactMarkdown>
              ) : (
                m.content
              )}
            </div>
            {m.role === "assistant" && m.metadata && (
              <footer className="chat-meta">
                {m.metadata.max_pii_sensitivity && (
                  <span className="badge">
                    Sensibilidad PII: {m.metadata.max_pii_sensitivity}
                  </span>
                )}
                {m.metadata.citations && m.metadata.citations.length > 0 && (
                  <details>
                    <summary>
                      Citas de contexto ({m.metadata.citations.length})
                    </summary>
                    <ul>
                      {m.metadata.citations.map((c, i) => (
                        <li key={`${c.id}-${i}`}>
                          <code>{c.id}</code> - fuente:{" "}
                          <strong>{c.source}</strong>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </footer>
            )}
          </article>
        ))}
        {/* Show streaming content as it arrives */}
        {streamingContent && (
          <article className="chat-message chat-assistant chat-streaming">
            <header className="chat-message-header">
              <span className="chat-role">Cortex</span>
              <span className="streaming-indicator">●</span>
            </header>
            <div className="chat-content">
              <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[rehypeKatex]}
              >
                {processContent(streamingContent)}
              </ReactMarkdown>
            </div>
          </article>
        )}
        <div ref={chatEndRef} />
      </section>
      <section className="chat-input-section">
        {error && <div className="chat-error">{error}</div>}
        <label className="chat-input-label">
          Escribe tu pregunta
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={3}
            placeholder="Haz una pregunta sobre tus datos o la documentacion interna"
          />
        </label>
        <button
          className="chat-send-button"
          onClick={() => void handleSend()}
          disabled={loading || !input.trim()}
        >
          {loading ? "Generando..." : "Enviar"}
        </button>
      </section>
    </main>
  );
};
