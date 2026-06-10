"use client";
import { Component, type ReactNode } from "react";
import { PageError } from "./PageError";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    if (process.env.NODE_ENV !== "production") {
      console.error("[ErrorBoundary]", error, info.componentStack);
    }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <PageError
          message="Something went wrong"
          detail={process.env.NODE_ENV !== "production" ? this.state.error?.message : undefined}
          onRetry={() => this.setState({ hasError: false, error: undefined })}
        />
      );
    }
    return this.props.children;
  }
}

export function withErrorBoundary<T extends object>(
  WrappedComponent: React.ComponentType<T>,
  fallback?: ReactNode
) {
  return function ComponentWithBoundary(props: T) {
    return (
      <ErrorBoundary fallback={fallback}>
        <WrappedComponent {...props} />
      </ErrorBoundary>
    );
  };
}
