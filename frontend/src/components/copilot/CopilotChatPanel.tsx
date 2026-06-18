import React, { useEffect, useRef, useState } from 'react';
import { Send, RotateCcw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CopilotMessage } from '../../types';
import './CopilotStyles.css';

interface CopilotChatPanelProps {
  messages: CopilotMessage[];
  isStreaming: boolean;
  error: string | null;
  onSend: (query: string) => void;
  onReset: () => void;
}

const SUGGESTED_QUERIES = [
  'Analyze environmental risk for selected parcels',
  'What zoning regulations apply here?',
  'Generate an optimized land-use plan',
  'Explain the main risk factors',
];

export function CopilotChatPanel({
  messages,
  isStreaming,
  error,
  onSend,
  onReset,
}: CopilotChatPanelProps) {
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    const q = input.trim();
    if (!q || isStreaming) return;
    setInput('');
    onSend(q);
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="copilot-chat-panel">
      {/* Header */}
      <div className="copilot-header">
        <div>
          <div className="copilot-header-title">Planner's Copilot</div>
          <div className="copilot-header-subtitle">
            Ask anything about your parcels
          </div>
        </div>
        {messages.length > 0 && (
          <button className="copilot-reset-btn" onClick={onReset} title="New conversation">
            <RotateCcw size={14} />
            <span style={{ fontSize: 12 }}>Reset</span>
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="copilot-messages">
        {messages.length === 0 && (
          <div className="copilot-empty-state">
            <div className="copilot-empty-text">
              Select parcels on the map, then ask a question
            </div>
            <div className="copilot-suggestions">
              {SUGGESTED_QUERIES.map(q => (
                <button key={q} className="copilot-suggestion-btn" onClick={() => onSend(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <ChatBubble key={idx} message={msg} />
        ))}

        {error && (
          <div className="copilot-error">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="copilot-input-container">
        <div className="copilot-input-wrapper">
          <textarea
            className="copilot-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask about your parcels…"
            disabled={isStreaming}
            rows={1}
          />
          <button
            className={`copilot-send-btn ${input.trim() && !isStreaming ? 'enabled' : 'disabled'}`}
            onClick={handleSend}
            disabled={isStreaming || !input.trim()}
          >
            <Send size={16} color={input.trim() && !isStreaming ? '#0A1630' : '#4FFFA7'} />
          </button>
        </div>
        <div className="copilot-input-hint">
          Enter to send · Shift+Enter for new line
        </div>
      </div>
    </div>
  );
}

function ChatBubble({ message }: { message: CopilotMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={`copilot-chat-bubble-wrapper ${message.role}`}>
      <div className={`copilot-chat-bubble ${message.role}`}>
        {!message.content && message.isStreaming ? (
          <span className="thinking">Thinking…</span>
        ) : (
          <>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => <p>{children}</p>,
                strong: ({ children }) => <strong>{children}</strong>,
                em: ({ children }) => <em>{children}</em>,
                ul: ({ children }) => <ul>{children}</ul>,
                li: ({ children }) => <li>{children}</li>,
                code: ({ children }) => <code>{children}</code>,
              }}
            >
              {message.content}
            </ReactMarkdown>
            {message.isStreaming && (
              <span className="cursor" />
            )}
          </>
        )}
      </div>
    </div>
  );
}
