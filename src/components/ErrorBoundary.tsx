import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an unhandled error:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[300px] flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-white border-2 border-red-300 rounded-lg p-6 shadow-xl text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-red-100 text-red-600 flex items-center justify-center mx-auto">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-bold text-navy-900">
                {this.props.fallbackTitle || 'Component Error Encountered'}
              </h3>
              <p className="text-xs text-gov-muted mt-1">
                {this.state.error?.message || 'An unexpected rendering error occurred in this section.'}
              </p>
            </div>
            <button
              onClick={this.handleReset}
              className="inline-flex items-center space-x-2 px-4 py-2 bg-navy-800 hover:bg-navy-900 text-white text-xs font-bold rounded shadow transition-colors cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Reload Interface</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
