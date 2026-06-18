/**
 * ZoningChatPanel Component
 * =========================
 * Chat interface for the Zoning RAG Assistant.
 * Provides AI-powered zoning regulation guidance with parcel context.
 * 
 * @component
 * @example
 * ```tsx
 * <ZoningChatPanel
 *   selectedApn="123-456-789"
 *   selectedProps={{ ZONING_CODE: "R-1" }}
 *   autoQueryTrigger={1}
 * />
 * ```
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { apiClient } from '../../../utils/api';
import { Send, Bot, User, Loader2, MessageSquare, Tag } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { usePlannerSettings } from '../../../context/PlannerSettingsContext';
import './ZoningChatPanel.css';

/** Message data structure */
interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  ts: number;
}

/** Props for the ZoningChatPanel component */
interface ZoningChatPanelProps {
  /** Currently selected parcel APN */
  selectedApn: string | null;
  /** Parcel properties from GeoJSON */
  selectedProps: any | null;
  /** Trigger value for auto-querying on parcel selection */
  autoQueryTrigger?: number;
}

/**
 * ZoningChatPanel component.
 * Provides a chat interface for zoning regulation queries.
 */
export function ZoningChatPanel({
  selectedApn,
  selectedProps,
  autoQueryTrigger = 0,
}: ZoningChatPanelProps) {
  const { settings } = usePlannerSettings();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [parcelPending, setParcelPending] = useState<boolean>(false);
  const listRef = useRef<HTMLDivElement>(null);
  const hasAutoQueried = useRef<number>(0);

  // Auto-scroll on new message
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages.length]);

  /** Header text based on selected parcel */
  const header = useMemo(() => {
    return selectedApn ? `APN ${selectedApn}` : 'No parcel selected';
  }, [selectedApn]);

  // Track parcel context changes
  useEffect(() => {
    if (selectedApn) {
      setParcelPending(settings.regulatoryGuidance.includeParcelContext);
      // Reset session when parcel changes
      setSessionId(null);
    }
  }, [selectedApn, settings.regulatoryGuidance.includeParcelContext]);

  // Reset session if conversation continuity is disabled
  useEffect(() => {
    if (!settings.regulatoryGuidance.keepConversationContext) {
      setSessionId(null);
    }
  }, [settings.regulatoryGuidance.keepConversationContext]);

  /** Response style instruction based on settings */
  const responseStyleInstruction = useMemo(() => {
    const style = settings.regulatoryGuidance.responseStyle;
    if (style === 'concise') {
      return 'Keep the response concise with practical planning bullets.';
    }
    if (style === 'detailed') {
      return 'Provide a detailed response with clear planning implications and compliance notes.';
    }
    return '';
  }, [settings.regulatoryGuidance.responseStyle]);

  // Auto-query zoning agent when trigger changes
  useEffect(() => {
    if (
      autoQueryTrigger > 0 &&
      autoQueryTrigger !== hasAutoQueried.current &&
      selectedApn &&
      selectedProps
    ) {
      hasAutoQueried.current = autoQueryTrigger;
      const template = settings.regulatoryGuidance.defaultQuestionTemplate.trim();
      const autoQuestion =
        template.length > 0
          ? template
          : 'What are the zoning regulations and requirements for this parcel?';
      void sendAutoQuery(autoQuestion);
    }
  }, [
    autoQueryTrigger,
    selectedApn,
    selectedProps,
    settings.regulatoryGuidance.defaultQuestionTemplate,
  ]);

  /**
   * Send an automatic query to the zoning agent.
   * @param question - The question to ask
   */
  async function sendAutoQuery(question: string) {
    setLoading(true);

    // Add system message to show we're fetching
    const systemMsg: Message = {
      id: crypto.randomUUID(),
      role: 'system',
      content: `Fetching zoning information for parcel ${selectedApn}...`,
      ts: Date.now(),
    };
    setMessages((prev) => [...prev, systemMsg]);

    try {
      const payload: any = {
        question: responseStyleInstruction
          ? `${question}\n\n${responseStyleInstruction}`
          : question,
      };
      if (settings.regulatoryGuidance.keepConversationContext && sessionId) {
        payload.session_id = sessionId;
      }
      if (selectedApn && settings.regulatoryGuidance.includeParcelContext) {
        payload.apn = selectedApn;
        payload.context = selectedProps ?? {};
      }

      const res = await apiClient.zoningRagAsk(payload);
      const answer = (res as any)?.answer || 'No answer available.';
      const returnedSessionId = (res as any)?.session_id || null;

      if (
        settings.regulatoryGuidance.keepConversationContext &&
        returnedSessionId &&
        !sessionId
      ) {
        setSessionId(returnedSessionId);
      }

      if (parcelPending) setParcelPending(false);

      // Remove system message and add assistant response
      setMessages((prev) => {
        const filtered = prev.filter((m) => m.id !== systemMsg.id);
        return [
          ...filtered,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: answer,
            ts: Date.now(),
          },
        ];
      });
    } catch (err: any) {
      setMessages((prev) => {
        const filtered = prev.filter((m) => m.id !== systemMsg.id);
        return [
          ...filtered,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: `Unable to fetch zoning information. Error: ${err?.message || err}. Please try asking a question manually.`,
            ts: Date.now(),
          },
        ];
      });
    } finally {
      setLoading(false);
    }
  }

  /**
   * Send a user message to the zoning agent.
   */
  async function send() {
    const text = input.trim();
    if (!text) return;
    setInput('');

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      ts: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const payload: any = {
        question: responseStyleInstruction
          ? `${text}\n\n${responseStyleInstruction}`
          : text,
      };
      if (settings.regulatoryGuidance.keepConversationContext && sessionId) {
        payload.session_id = sessionId;
      }
      if (
        settings.regulatoryGuidance.includeParcelContext &&
        parcelPending &&
        selectedApn
      ) {
        payload.apn = selectedApn;
        payload.context = selectedProps ?? {};
      }

      const res = await apiClient.zoningRagAsk(payload);
      const answer = (res as any)?.answer || 'No answer available.';
      const returnedSessionId = (res as any)?.session_id || null;

      if (
        settings.regulatoryGuidance.keepConversationContext &&
        returnedSessionId &&
        !sessionId
      ) {
        setSessionId(returnedSessionId);
      }

      if (parcelPending) setParcelPending(false);

      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: answer,
        ts: Date.now(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `Backend not available yet. (Error: ${err?.message || err})`,
        ts: Date.now(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } finally {
      setLoading(false);
    }
  }

  /** Check if parcel is selected */
  const selectedParcelInfo = useMemo(() => {
    return !!(selectedApn && selectedProps);
  }, [selectedApn, selectedProps]);

  return (
    <div className="zoning-chat">
      {/* Header */}
      <header className="chat-header">
        <div className="chat-header__top">
          <div className="chat-header__brand">
            <div className="chat-header__icon-box">
              <MessageSquare className="chat-header__icon" />
            </div>
            <div>
              <h3 className="chat-header__title">Zoning RAG Assistant</h3>
              <p className="chat-header__subtitle">
                Ask questions about zoning regulations
              </p>
            </div>
          </div>
        </div>

        {/* Parcel Tag Badge */}
        {selectedApn && selectedProps && (
          <div className="parcel-tag__card">
            <div className="parcel-tag__row">
              <div className="parcel-tag__info">
                <div className="parcel-tag__icon-box">
                  <Tag className="parcel-tag__icon" />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="parcel-tag__label">
                    <span className="parcel-tag__label-text">Tagged Parcel</span>
                    <span className="parcel-tag__pulse" />
                  </div>
                  <div className="parcel-tag__apn">APN: {selectedApn}</div>
                  {selectedProps.ZONING_CODE && (
                    <div className="parcel-tag__meta">
                      Zone:{' '}
                      <span className="parcel-tag__meta-value">
                        {selectedProps.ZONING_CODE}
                      </span>
                      {selectedProps.JURISDICTION && (
                        <span> • {selectedProps.JURISDICTION}</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                {selectedProps.xgb_risk_score !== undefined && (
                  <div className="parcel-tag__stat-box">
                    <div className="parcel-tag__stat-label">Risk</div>
                    <div className="parcel-tag__stat-value">
                      {selectedProps.xgb_risk_score.toFixed(1)}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </header>

      {/* Messages Area */}
      <div
        ref={listRef}
        className={`messages-container ${messages.length === 0 ? '' : 'messages-container--with-space'}`}
      >
        {messages.length === 0 && (
          <div className="empty-chat">
            <div className="empty-chat__avatar">
              <div className="empty-chat__icon-box">
                <Bot className="empty-chat__icon" />
              </div>
              <div className="empty-chat__badge">
                <span className="empty-chat__badge-text">AI</span>
              </div>
            </div>
            <h4 className="empty-chat__title">
              {selectedParcelInfo
                ? `Ready to answer questions about parcel ${selectedApn}`
                : 'Zoning Information Assistant'}
            </h4>
            <p className="empty-chat__description">
              {selectedParcelInfo
                ? 'I have access to the selected parcel details. Ask me about zoning regulations, allowed uses, restrictions, or any other zoning-related questions.'
                : 'Select a parcel on the Map tab to get instant zoning information, or ask general zoning questions.'}
            </p>
            {selectedParcelInfo && (
              <div className="empty-chat__hint">
                <p className="empty-chat__hint-text">
                  Zoning information will be automatically fetched when you select a parcel
                </p>
              </div>
            )}
          </div>
        )}

        {messages.map((m) => {
          if (m.role === 'system') {
            return (
              <div key={m.id} className="system-message">
                <div className="system-message__box">
                  <div className="system-message__content">
                    <Loader2 className="system-message__spinner" />
                    <span className="system-message__text">{m.content}</span>
                  </div>
                </div>
              </div>
            );
          }

          return (
            <div
              key={m.id}
              className={`message ${m.role === 'user' ? 'message--user' : ''}`}
            >
              {/* Avatar */}
              <div
                className={`message__avatar ${
                  m.role === 'user' ? 'message__avatar--user' : 'message__avatar--assistant'
                }`}
              >
                {m.role === 'user' ? (
                  <User className="message__avatar-icon message__avatar-icon--user" />
                ) : (
                  <Bot className="message__avatar-icon message__avatar-icon--assistant" />
                )}
              </div>

              {/* Message Content */}
              <div className="message__content">
                <div
                  className={`message__bubble ${
                    m.role === 'user'
                      ? 'message__bubble--user'
                      : 'message__bubble--assistant'
                  }`}
                >
                  {m.role === 'assistant' ? (
                    <div className="message__markdown">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          h1: ({ node, ...props }) => <h1 {...props} />,
                          h2: ({ node, ...props }) => <h2 {...props} />,
                          h3: ({ node, ...props }) => <h3 {...props} />,
                          p: ({ node, ...props }) => <p {...props} />,
                          ul: ({ node, ...props }) => <ul {...props} />,
                          ol: ({ node, ...props }) => <ol {...props} />,
                          li: ({ node, ...props }) => <li {...props} />,
                          code: ({ node, inline, ...props }: any) =>
                            inline ? <code {...props} /> : <code {...props} />,
                          pre: ({ node, ...props }: any) => <pre {...props} />,
                          a: ({ node, ...props }) => <a {...props} />,
                          blockquote: ({ node, ...props }) => <blockquote {...props} />,
                          table: ({ node, ...props }) => <table {...props} />,
                          thead: ({ node, ...props }) => <thead {...props} />,
                          tbody: ({ node, ...props }) => <tbody {...props} />,
                          tr: ({ node, ...props }) => <tr {...props} />,
                          th: ({ node, ...props }) => <th {...props} />,
                          td: ({ node, ...props }) => <td {...props} />,
                          hr: ({ node, ...props }) => <hr {...props} />,
                          strong: ({ node, ...props }) => <strong {...props} />,
                          em: ({ node, ...props }) => <em {...props} />,
                        }}
                      >
                        {m.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <div className="message__text">{m.content}</div>
                  )}
                </div>
                <div
                  className={`message__timestamp ${
                    m.role === 'user' ? 'message__timestamp--user' : 'message__timestamp--assistant'
                  }`}
                >
                  {new Date(m.ts).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </div>
              </div>
            </div>
          );
        })}

        {loading && (
          <div className="thinking-indicator">
            <div className="thinking-indicator__avatar">
              <Bot className="thinking-indicator__avatar-icon" />
            </div>
            <div className="thinking-indicator__content">
              <div className="thinking-indicator__bubble">
                <div className="thinking-indicator__content-inner">
                  <Loader2 className="thinking-indicator__spinner" />
                  <span className="thinking-indicator__text">Thinking...</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="chat-input-area">
        <div className="chat-input-area__row">
          <div className="chat-input-area__field">
            <textarea
              className="chat-input"
              placeholder={
                selectedApn
                  ? `Ask about parcel ${selectedApn}...`
                  : 'Ask a zoning question...'
              }
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                const target = e.target;
                target.style.height = 'auto';
                target.style.height = `${Math.min(target.scrollHeight, 144)}px`;
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              disabled={loading}
              rows={1}
            />
            {input.trim() && (
              <div className="chat-input__hint">
                Press Enter to send, Shift+Enter for new line
              </div>
            )}
          </div>
          <button
            className={`send-btn ${
              loading || !input.trim() ? 'send-btn--disabled' : 'send-btn--enabled'
            }`}
            onClick={() => void send()}
            disabled={loading || !input.trim()}
            aria-label={loading ? 'Sending...' : 'Send message'}
          >
            {loading ? (
              <Loader2 className="send-btn__spinner" />
            ) : (
              <Send className="send-btn__icon" />
            )}
          </button>
        </div>
        {selectedParcelInfo && (
          <div className="context-hint">
            <span className="context-hint__dot" />
            <p className="context-hint__text">
              Parcel context will be included with your question
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
