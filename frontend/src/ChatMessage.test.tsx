import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChatMessage from '../ChatMessage';

describe('ChatMessage Component', () => {
  describe('User Messages', () => {
    it('renders user message text correctly', () => {
      render(<ChatMessage role="user" text="Hello, IGRIS!" />);
      expect(screen.getByText('Hello, IGRIS!')).toBeInTheDocument();
    });

    it('applies correct CSS class for user messages', () => {
      const { container } = render(<ChatMessage role="user" text="Test message" />);
      const messageRow = container.querySelector('.msg-row.user');
      expect(messageRow).toBeInTheDocument();
    });

    it('renders plain text without markdown processing for user messages', () => {
      render(<ChatMessage role="user" text="**Bold text**" />);
      // Should render literally, not as bold
      expect(screen.getByText('**Bold text**')).toBeInTheDocument();
    });
  });

  describe('Assistant Messages', () => {
    it('renders assistant message with markdown content', () => {
      render(<ChatMessage role="assistant" text="# Heading\nSome text" />);
      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toHaveTextContent('Heading');
    });

    it('applies correct CSS class for assistant messages', () => {
      const { container } = render(<ChatMessage role="assistant" text="Test" />);
      const messageRow = container.querySelector('.msg-row.assistant');
      expect(messageRow).toBeInTheDocument();
    });

    it('renders typing indicator when text is empty', () => {
      const { container } = render(<ChatMessage role="assistant" text="" />);
      const typingIndicator = container.querySelector('.typing-indicator');
      expect(typingIndicator).toBeInTheDocument();
    });

    it('renders markdown tables with GFM', () => {
      const table = `| Header 1 | Header 2 |
| --- | --- |
| Cell 1 | Cell 2 |`;
      const { container } = render(<ChatMessage role="assistant" text={table} />);
      expect(container.querySelector('table')).toBeInTheDocument();
    });

    it('opens links in new tab', () => {
      render(<ChatMessage role="assistant" text="[Click here](https://example.com)" />);
      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noreferrer noopener');
    });

    it('renders inline code with correct class', () => {
      render(<ChatMessage role="assistant" text="`const x = 1;`" />);
      const code = screen.getByText('const x = 1;');
      expect(code).toHaveClass('md-inline-code');
    });

    it('renders code blocks with correct class', () => {
      const { container } = render(
        <ChatMessage role="assistant" text="```javascript\nconst x = 1;\n```" />
      );
      const preElement = container.querySelector('pre.md-codeblock');
      expect(preElement).toBeInTheDocument();
    });
  });

  describe('Feedback System', () => {
    it('shows feedback buttons when pairUserText and onFeedback are provided', () => {
      const mockFeedback = vi.fn();
      render(
        <ChatMessage
          role="assistant"
          text="Response"
          pairUserText="Question"
          onFeedback={mockFeedback}
        />
      );
      const feedbackButtons = screen.getAllByRole('button', { type: 'button' });
      expect(feedbackButtons.length).toBeGreaterThan(0);
    });

    it('hides feedback buttons when pairUserText is not provided', () => {
      render(<ChatMessage role="assistant" text="Response" />);
      expect(screen.queryByLabelText('Train IGRIS')).not.toBeInTheDocument();
    });

    it('hides feedback buttons when assistant text is empty', () => {
      const mockFeedback = vi.fn();
      render(
        <ChatMessage
          role="assistant"
          text=""
          pairUserText="Question"
          onFeedback={mockFeedback}
        />
      );
      expect(screen.queryByLabelText('Train IGRIS')).not.toBeInTheDocument();
    });

    it('calls onFeedback with 1 when upvote button is clicked', async () => {
      const mockFeedback = vi.fn();
      const user = userEvent.setup();
      render(
        <ChatMessage
          role="assistant"
          text="Good response"
          pairUserText="Question"
          onFeedback={mockFeedback}
        />
      );
      const upvoteButton = screen.getByTitle('Good answer — reinforce');
      await user.click(upvoteButton);
      expect(mockFeedback).toHaveBeenCalledWith(1);
    });

    it('calls onFeedback with -1 when downvote button is clicked', async () => {
      const mockFeedback = vi.fn();
      const user = userEvent.setup();
      render(
        <ChatMessage
          role="assistant"
          text="Bad response"
          pairUserText="Question"
          onFeedback={mockFeedback}
        />
      );
      const downvoteButton = screen.getByTitle('Poor answer — discourage');
      await user.click(downvoteButton);
      expect(mockFeedback).toHaveBeenCalledWith(-1);
    });

    it('disables feedback buttons when feedbackDisabled is true', () => {
      const mockFeedback = vi.fn();
      render(
        <ChatMessage
          role="assistant"
          text="Response"
          pairUserText="Question"
          onFeedback={mockFeedback}
          feedbackDisabled={true}
        />
      );
      const buttons = screen.getAllByRole('button', { type: 'button' });
      buttons.forEach((btn) => {
        expect(btn).toBeDisabled();
      });
    });

    it('disables feedback buttons and shows "Saved" when feedbackSent is true', () => {
      const mockFeedback = vi.fn();
      render(
        <ChatMessage
          role="assistant"
          text="Response"
          pairUserText="Question"
          onFeedback={mockFeedback}
          feedbackSent={true}
        />
      );
      const buttons = screen.getAllByRole('button', { type: 'button' });
      buttons.forEach((btn) => {
        expect(btn).toBeDisabled();
      });
      expect(screen.getByText('Saved')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels for feedback section', () => {
      const mockFeedback = vi.fn();
      render(
        <ChatMessage
          role="assistant"
          text="Response"
          pairUserText="Question"
          onFeedback={mockFeedback}
        />
      );
      const feedbackDiv = screen.getByLabelText('Train IGRIS');
      expect(feedbackDiv).toBeInTheDocument();
    });
  });
});
