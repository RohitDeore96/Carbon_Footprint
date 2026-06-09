/**
 * ChatCoach.test.tsx — Comprehensive tests for the ChatCoach conversational AI component.
 * Covers empty state, message sending, keyboard navigation, error state, and accessibility.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatCoach } from '../ChatCoach';
import type { ChatResponse, ApiResult, EmissionSummaryEntry } from '../../../services/apiClient';

// ---------------------------------------------------------------------------
// Mock apiClient
// ---------------------------------------------------------------------------

type PostChatRequestFn = (payload: unknown) => Promise<ApiResult<ChatResponse>>;

const { mockPostChatRequest } = vi.hoisted(() => ({
  mockPostChatRequest: vi.fn<PostChatRequestFn>(),
}));

vi.mock('../../../services/apiClient', () => ({
  apiClient: {
    postChatRequest: (...args: Parameters<PostChatRequestFn>) => mockPostChatRequest(...args),
    postFootprintLog: vi.fn(),
    postInsightsRequest: vi.fn(),
    getFootprintHistory: vi.fn(),
    getFootprintSummary: vi.fn(),
  },
}));

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  userId: 'test-user-001',
  totalCo2eKg: 15.5,
  periodDays: 7,
  emissionBreakdown: [
    { category: 'transport', total_co2e_kg: 10.5, entry_count: 1, description: 'Car commute' },
    { category: 'energy', total_co2e_kg: 5.0, entry_count: 1, description: 'Electricity' },
  ] as readonly EmissionSummaryEntry[],
};

const mockChatResponse: ChatResponse = {
  user_id: 'test-user-001',
  response: 'Your transport emissions are quite high. Consider using public transit.',
  suggestions: ['Try carpooling', 'Use a bicycle for short trips'],
  model_used: 'gemini-2.5-flash',
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ChatCoach', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPostChatRequest.mockReset();
    // Mock scrollIntoView since jsdom doesn't implement it
    Element.prototype.scrollIntoView = vi.fn();
  });

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  describe('rendering', () => {
    it('renders the chat coach container with correct aria-label', () => {
      render(<ChatCoach {...defaultProps} />);
      expect(screen.getByLabelText('Conversational AI Coach')).toBeInTheDocument();
    });

    it('renders the chat title', () => {
      render(<ChatCoach {...defaultProps} />);
      expect(screen.getByText('Ask the Coach')).toBeInTheDocument();
    });

    it('renders the chat subtitle', () => {
      render(<ChatCoach {...defaultProps} />);
      expect(screen.getByText(/Ask follow-up questions about your carbon footprint/)).toBeInTheDocument();
    });

    it('renders the chat input textarea', () => {
      render(<ChatCoach {...defaultProps} />);
      expect(screen.getByLabelText('Type your question')).toBeInTheDocument();
    });

    it('renders the send button', () => {
      render(<ChatCoach {...defaultProps} />);
      expect(screen.getByLabelText('Send message')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Empty state with starter suggestions
  // -------------------------------------------------------------------------

  describe('empty state', () => {
    it('shows empty state when no messages', () => {
      render(<ChatCoach {...defaultProps} />);
      expect(screen.getByText(/Ask me anything about your carbon footprint/)).toBeInTheDocument();
    });

    it('shows starter suggestion buttons', () => {
      render(<ChatCoach {...defaultProps} />);
      expect(screen.getByText('How can I reduce my transport emissions?')).toBeInTheDocument();
      expect(screen.getByText('What is the Paris Agreement target?')).toBeInTheDocument();
      expect(screen.getByText('Is my footprint above average?')).toBeInTheDocument();
    });

    it('clicking a starter suggestion populates the input', async () => {
      render(<ChatCoach {...defaultProps} />);
      const starterBtn = screen.getByText('How can I reduce my transport emissions?');
      await userEvent.click(starterBtn);
      const input = screen.getByLabelText('Type your question') as HTMLTextAreaElement;
      expect(input.value).toBe('How can I reduce my transport emissions?');
    });
  });

  // -------------------------------------------------------------------------
  // Sending a message
  // -------------------------------------------------------------------------

  describe('sending a message', () => {
    it('sends a message and displays the user message', async () => {
      mockPostChatRequest.mockResolvedValue({ success: true, data: mockChatResponse });
      render(<ChatCoach {...defaultProps} />);

      const input = screen.getByLabelText('Type your question');
      await userEvent.type(input, 'How can I reduce emissions?');
      const sendBtn = screen.getByLabelText('Send message');
      await userEvent.click(sendBtn);

      expect(screen.getByText('How can I reduce emissions?')).toBeInTheDocument();
    });

    it('displays AI response after successful send', async () => {
      mockPostChatRequest.mockResolvedValue({ success: true, data: mockChatResponse });
      render(<ChatCoach {...defaultProps} />);

      const input = screen.getByLabelText('Type your question');
      await userEvent.type(input, 'How can I reduce emissions?');
      const sendBtn = screen.getByLabelText('Send message');
      await userEvent.click(sendBtn);

      await waitFor(() => {
        expect(screen.getByText(mockChatResponse.response)).toBeInTheDocument();
      });
    });

    it('displays suggestion chips from AI response', async () => {
      mockPostChatRequest.mockResolvedValue({ success: true, data: mockChatResponse });
      render(<ChatCoach {...defaultProps} />);

      const input = screen.getByLabelText('Type your question');
      await userEvent.type(input, 'How can I reduce emissions?');
      const sendBtn = screen.getByLabelText('Send message');
      await userEvent.click(sendBtn);

      await waitFor(() => {
        expect(screen.getByText('Try carpooling')).toBeInTheDocument();
        expect(screen.getByText('Use a bicycle for short trips')).toBeInTheDocument();
      });
    });

    it('clears input after sending a message', async () => {
      mockPostChatRequest.mockResolvedValue({ success: true, data: mockChatResponse });
      render(<ChatCoach {...defaultProps} />);

      const input = screen.getByLabelText('Type your question') as HTMLTextAreaElement;
      await userEvent.type(input, 'How can I reduce emissions?');
      const sendBtn = screen.getByLabelText('Send message');
      await userEvent.click(sendBtn);

      expect(input.value).toBe('');
    });

    it('does not send empty message', async () => {
      render(<ChatCoach {...defaultProps} />);
      const sendBtn = screen.getByLabelText('Send message');
      expect(sendBtn).toBeDisabled();
    });

    it('does not send whitespace-only message', async () => {
      render(<ChatCoach {...defaultProps} />);
      const input = screen.getByLabelText('Type your question');
      await userEvent.type(input, '   ');
      const sendBtn = screen.getByLabelText('Send message');
      expect(sendBtn).toBeDisabled();
    });

    it('calls apiClient.postChatRequest with correct payload', async () => {
      mockPostChatRequest.mockResolvedValue({ success: true, data: mockChatResponse });
      render(<ChatCoach {...defaultProps} />);

      const input = screen.getByLabelText('Type your question');
      await userEvent.type(input, 'How can I reduce emissions?');
      const sendBtn = screen.getByLabelText('Send message');
      await userEvent.click(sendBtn);

      await waitFor(() => {
        expect(mockPostChatRequest).toHaveBeenCalledTimes(1);
      });

      const callArg = mockPostChatRequest.mock.calls[0][0] as Record<string, unknown>;
      expect(callArg.user_id).toBe('test-user-001');
      expect(callArg.message).toBe('How can I reduce emissions?');
      expect(callArg.total_co2e_kg).toBe(15.5);
      expect(callArg.period_days).toBe(7);
    });
  });

  // -------------------------------------------------------------------------
  // Keyboard navigation
  // -------------------------------------------------------------------------

  describe('keyboard navigation', () => {
    it('sends message on Enter key (without Shift)', async () => {
      mockPostChatRequest.mockResolvedValue({ success: true, data: mockChatResponse });
      render(<ChatCoach {...defaultProps} />);

      const input = screen.getByLabelText('Type your question');
      await userEvent.type(input, 'How can I reduce emissions?');
      await userEvent.keyboard('{Enter}');

      await waitFor(() => {
        expect(mockPostChatRequest).toHaveBeenCalledTimes(1);
      });
    });

    it('does not send message on Shift+Enter', async () => {
      render(<ChatCoach {...defaultProps} />);

      const input = screen.getByLabelText('Type your question');
      await userEvent.type(input, 'Test message');
      // Shift+Enter should add a newline, not send
      await userEvent.keyboard('{Shift>}{Enter}{/Shift}');

      expect(mockPostChatRequest).not.toHaveBeenCalled();
    });
  });

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------

  describe('loading state', () => {
    it('shows loading indicator while waiting for response', async () => {
      // Never resolve to keep loading state
      mockPostChatRequest.mockReturnValue(new Promise(() => {}));
      render(<ChatCoach {...defaultProps} />);

      const input = screen.getByLabelText('Type your question');
      await userEvent.type(input, 'Test question');
      const sendBtn = screen.getByLabelText('Send message');
      await userEvent.click(sendBtn);

      await waitFor(() => {
        expect(screen.getByText('Thinking...')).toBeInTheDocument();
      });
    });

    it('disables input while loading', async () => {
      mockPostChatRequest.mockReturnValue(new Promise(() => {}));
      render(<ChatCoach {...defaultProps} />);

      const input = screen.getByLabelText('Type your question');
      await userEvent.type(input, 'Test question');
      const sendBtn = screen.getByLabelText('Send message');
      await userEvent.click(sendBtn);

      await waitFor(() => {
        expect(input).toBeDisabled();
      });
    });

    it('loading indicator has role=status and aria-busy=true', async () => {
      mockPostChatRequest.mockReturnValue(new Promise(() => {}));
      render(<ChatCoach {...defaultProps} />);

      const input = screen.getByLabelText('Type your question');
      await userEvent.type(input, 'Test question');
      const sendBtn = screen.getByLabelText('Send message');
      await userEvent.click(sendBtn);

      await waitFor(() => {
        const loadingEl = screen.getByText('Thinking...');
        const parent = loadingEl.closest('[role="status"]');
        expect(parent).not.toBeNull();
        expect(parent).toHaveAttribute('aria-busy', 'true');
      });
    });
  });

  // -------------------------------------------------------------------------
  // Error state
  // -------------------------------------------------------------------------

  describe('error state', () => {
    it('shows error message when API call fails', async () => {
      mockPostChatRequest.mockResolvedValue({
        success: false,
        error: { code: 'network', message: 'Network error — backend unreachable' },
      });
      render(<ChatCoach {...defaultProps} />);

      const input = screen.getByLabelText('Type your question');
      await userEvent.type(input, 'Test question');
      const sendBtn = screen.getByLabelText('Send message');
      await userEvent.click(sendBtn);

      await waitFor(() => {
        expect(screen.getByText(/Failed to get response/)).toBeInTheDocument();
      });
    });

    it('shows error code in error message', async () => {
      mockPostChatRequest.mockResolvedValue({
        success: false,
        error: { code: 500, message: 'HTTP 500' },
      });
      render(<ChatCoach {...defaultProps} />);

      const input = screen.getByLabelText('Type your question');
      await userEvent.type(input, 'Test question');
      const sendBtn = screen.getByLabelText('Send message');
      await userEvent.click(sendBtn);

      await waitFor(() => {
        expect(screen.getByText(/Failed to get response \(500\)/)).toBeInTheDocument();
      });
    });

    it('error region has role=alert and aria-live=assertive', async () => {
      mockPostChatRequest.mockResolvedValue({
        success: false,
        error: { code: 'network', message: 'Network error' },
      });
      render(<ChatCoach {...defaultProps} />);

      const input = screen.getByLabelText('Type your question');
      await userEvent.type(input, 'Test question');
      const sendBtn = screen.getByLabelText('Send message');
      await userEvent.click(sendBtn);

      await waitFor(() => {
        const errorDiv = screen.getByRole('alert');
        expect(errorDiv).toHaveAttribute('aria-live', 'assertive');
      });
    });
  });

  // -------------------------------------------------------------------------
  // Accessibility
  // -------------------------------------------------------------------------

  describe('accessibility', () => {
    it('messages container has role=log and aria-live=polite', () => {
      render(<ChatCoach {...defaultProps} />);
      const messagesContainer = screen.getByLabelText('Conversation history');
      expect(messagesContainer).toHaveAttribute('role', 'log');
      expect(messagesContainer).toHaveAttribute('aria-live', 'polite');
    });

    it('send button has correct aria-label', () => {
      render(<ChatCoach {...defaultProps} />);
      expect(screen.getByLabelText('Send message')).toBeInTheDocument();
    });

    it('input has correct aria-label', () => {
      render(<ChatCoach {...defaultProps} />);
      expect(screen.getByLabelText('Type your question')).toBeInTheDocument();
    });

    it('user messages have role=presentation', async () => {
      mockPostChatRequest.mockResolvedValue({ success: true, data: mockChatResponse });
      render(<ChatCoach {...defaultProps} />);

      const input = screen.getByLabelText('Type your question');
      await userEvent.type(input, 'Test question');
      const sendBtn = screen.getByLabelText('Send message');
      await userEvent.click(sendBtn);

      await waitFor(() => {
        const userMessage = screen.getByText('Test question').closest('[role="presentation"]');
        expect(userMessage).not.toBeNull();
      });
    });

    it('AI messages have role=article and aria-label', async () => {
      mockPostChatRequest.mockResolvedValue({ success: true, data: mockChatResponse });
      render(<ChatCoach {...defaultProps} />);

      const input = screen.getByLabelText('Type your question');
      await userEvent.type(input, 'Test question');
      const sendBtn = screen.getByLabelText('Send message');
      await userEvent.click(sendBtn);

      await waitFor(() => {
        const aiMessage = screen.getByText(mockChatResponse.response).closest('[role="article"]');
        expect(aiMessage).not.toBeNull();
        expect(aiMessage).toHaveAttribute('aria-label', 'AI coach response');
      });
    });

    it('suggestions have aria-label for follow-up questions', async () => {
      mockPostChatRequest.mockResolvedValue({ success: true, data: mockChatResponse });
      render(<ChatCoach {...defaultProps} />);

      const input = screen.getByLabelText('Type your question');
      await userEvent.type(input, 'Test question');
      const sendBtn = screen.getByLabelText('Send message');
      await userEvent.click(sendBtn);

      await waitFor(() => {
        expect(screen.getByLabelText('Suggested follow-up questions')).toBeInTheDocument();
      });
    });
  });
});
