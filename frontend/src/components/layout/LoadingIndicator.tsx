import React from 'react';

interface LoadingIndicatorProps {
  readonly message?: string;
}

export function LoadingIndicator({ message = 'Loading content' }: LoadingIndicatorProps): React.JSX.Element {
  return (
    <div role="status" aria-busy="true" aria-label={message} className="loading-indicator">
      <span className="loading-spinner" aria-hidden="true" />
      <span className="loading-text">{message}</span>
    </div>
  );
}
