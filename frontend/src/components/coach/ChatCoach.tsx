/**
 * ChatCoach — Multi-turn conversational AI interface for follow-up questions.
 * Enables users to ask the Sustainability Coach about their carbon data.
 * Accessible: aria-live, role attributes, keyboard navigation.
 */

import React, { useState, useRef, useEffect } from 'react';
import { apiClient, type EmissionSummaryEntry, type ApiError } from '../../services/apiClient';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChatCoachProps {
  readonly userId: string;
  readonly totalCo2eKg: number;
  readonly periodDays: number;
  readonly emissionBreakdown: readonly EmissionSummaryEntry[];
}

interface ChatMessage {
  readonly role: 'user' | 'model';
  readonly content: string;
  readonly suggestions?: readonly string[];
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ChatMessageBubble({ message, onSuggestionClick }: { readonly message: ChatMessage; readonly onSuggestionClick: (suggestion: string) => void }): React.JSX.Element {
  const isUser = message.role === 'user';
  return (
    <div
      className={`chat-message ${isUser ? 'chat-message--user' : 'chat-message--model'}`}
      role={isUser ? 'presentation' : 'article'}
      aria-label={isUser ? undefined : 'AI coach response'}
    >
      <span className="chat-message-avatar" aria-hidden="true">
        {isUser ? '👤' : '✦'}
      </span>
      <div className="chat-message-content">
        <p className="chat-message-text">{message.content}</p>
        {message.suggestions && message.suggestions.length > 0 && (
          <div className="chat-suggestions" aria-label="Suggested follow-up questions">
            {message.suggestions.map((suggestion, i) => (
              <button
                key={`suggestion-${i}`}
                type="button"
                className="chat-suggestion-chip"
                onClick={() => onSuggestionClick(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main ChatCoach component
// ---------------------------------------------------------------------------

export function ChatCoach({
  userId,
  totalCo2eKg,
  periodDays,
  emissionBreakdown,
}: ChatCoachProps): React.JSX.Element {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (): Promise<void> => {
    const trimmed = inputValue.trim();
    if (trimmed === '' || isLoading) return;

    // Abort any previous in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const userMessage: ChatMessage = { role: 'user', content: trimmed };
    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    setError(null);

    // Build conversation history from existing messages (last 10 for context)
    const conversationHistory = messages.slice(-10).map((msg) => ({
      role: msg.role,
      content: msg.content,
    }));

    const result = await apiClient.postChatRequest({
      user_id: userId,
      message: trimmed,
      total_co2e_kg: totalCo2eKg,
      period_days: periodDays,
      emission_breakdown: emissionBreakdown,
      conversation_history: conversationHistory,
    }, controller.signal);

    // Ignore result if request was aborted (reset loading to avoid stuck spinner)
    if (controller.signal.aborted) {
      setIsLoading(false);
      return;
    }

    setIsLoading(false);
    if (result.success) {
      const modelMessage: ChatMessage = {
        role: 'model',
        content: result.data.response,
        suggestions: result.data.suggestions,
      };
      setMessages((prev) => [...prev, modelMessage]);
    } else {
      setError(result.error);
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleSuggestionClick = (suggestion: string): void => {
    setInputValue(suggestion);
  };

  return (
    <div className="chat-coach" aria-label="Conversational AI Coach" id="chat-coach">
      <header className="chat-coach-header">
        <h4 className="chat-coach-title">
          <span aria-hidden="true">💬</span> Ask the Coach
        </h4>
        <p className="chat-coach-subtitle">
          Ask follow-up questions about your carbon footprint
        </p>
      </header>

      <div
        className="chat-messages"
        role="log"
        aria-live="polite"
        aria-label="Conversation history"
        id="chat-messages"
      >
        {messages.length === 0 && (
          <div className="chat-empty" id="chat-empty-state">
            <p className="chat-empty-text">
              Ask me anything about your carbon footprint! Try:
            </p>
            <div className="chat-starter-suggestions">
              {[
                'How can I reduce my transport emissions?',
                'What is the Paris Agreement target?',
                'Is my footprint above average?',
              ].map((starter) => (
                <button
                  key={starter}
                  type="button"
                  className="chat-starter-btn"
                  onClick={() => handleSuggestionClick(starter)}
                >
                  {starter}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <ChatMessageBubble key={`msg-${i}`} message={msg} onSuggestionClick={handleSuggestionClick} />
        ))}
        {isLoading && (
          <div className="chat-loading" role="status" aria-busy="true">
            <span className="loading-spinner chat-spinner" aria-hidden="true" />
            <span className="chat-loading-text">Thinking...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {error !== null && (
        <div className="chat-error" role="alert" aria-live="assertive">
          <p>Failed to get response ({error.code}). Please try again.</p>
        </div>
      )}

      <div className="chat-input-area">
        <textarea
          className="chat-input"
          id="chat-input"
          placeholder="Ask about your carbon footprint..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          aria-label="Type your question"
          rows={1}
          maxLength={2000}
        />
        <button
          type="button"
          className="chat-send-btn"
          onClick={sendMessage}
          disabled={isLoading || inputValue.trim() === ''}
          aria-label="Send message"
        >
          {isLoading ? '...' : '→'}
        </button>
      </div>
    </div>
  );
}
