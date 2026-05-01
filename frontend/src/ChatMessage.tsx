import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

type Props = {
  role: 'user' | 'assistant';
  text: string;
  /** User message that prompted this assistant reply (for learning feedback). */
  pairUserText?: string;
  feedbackDisabled?: boolean;
  feedbackSent?: boolean;
  onFeedback?: (rating: -1 | 1) => void;
};

/**
 * Renders a chat message. User messages are plain text (safer — no markdown
 * injection from the user side). Assistant messages get full markdown +
 * GFM (tables, strikethrough, task lists).
 */
export default function ChatMessage({
  role,
  text,
  pairUserText,
  feedbackDisabled,
  feedbackSent,
  onFeedback,
}: Props) {
  if (role === 'user') {
    return (
      <div className="msg-row user">
        <div className="msg user">
          <span className="msg-text">{text}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="msg-row assistant">
      <div className="msg assistant">
        <div className="msg-markdown">
          {text ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: (props) => (
                  <a {...props} target="_blank" rel="noreferrer noopener" />
                ),
                code: ({ inline, className, children, ...props }: any) =>
                  inline ? (
                    <code className="md-inline-code" {...props}>
                      {children}
                    </code>
                  ) : (
                    <pre className={`md-codeblock ${className || ''}`}>
                      <code {...props}>{children}</code>
                    </pre>
                  ),
              }}
            >
              {text}
            </ReactMarkdown>
          ) : (
            <span className="typing-indicator">
              <i /> <i /> <i />
            </span>
          )}
        </div>
        {pairUserText && text.trim().length > 0 && onFeedback ? (
          <div className="msg-feedback" aria-label="Train IGRIS">
            <button
              type="button"
              className="msg-feedback-btn"
              title="Good answer — reinforce"
              disabled={feedbackDisabled || feedbackSent}
              onClick={() => onFeedback(1)}
            >
              ↑
            </button>
            <button
              type="button"
              className="msg-feedback-btn danger"
              title="Poor answer — discourage"
              disabled={feedbackDisabled || feedbackSent}
              onClick={() => onFeedback(-1)}
            >
              ↓
            </button>
            {feedbackSent ? <span className="msg-feedback-note">Saved</span> : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
