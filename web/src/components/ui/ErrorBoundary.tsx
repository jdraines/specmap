import { Component } from 'react';
import type { ReactNode, ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div className="p-8 text-center">
            <p className="text-[var(--error-text)] text-sm font-semibold">Something went wrong</p>
            <p className="text-xs text-[var(--text-secondary)] mt-1">{this.state.error.message}</p>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
