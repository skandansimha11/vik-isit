import React from "react";

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Dashboard crashed:", error, info);
  }

  handleReset = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      if (this.props.compact) {
        return (
          <div className="rounded-xl border border-negative/30 bg-base-850 p-5 text-center">
            <p className="text-sm text-negative">
              {this.state.error.message || "This card failed to render."}
            </p>
            <button
              onClick={this.handleReset}
              className="mt-3 rounded-lg bg-orange-500 px-3 py-1.5 text-xs font-medium text-black hover:bg-orange-400"
            >
              Try again
            </button>
          </div>
        );
      }

      return (
        <div className="flex min-h-screen items-center justify-center bg-base-900 px-4">
          <div className="max-w-md rounded-xl border border-base-700 bg-base-850 p-6 text-center">
            <h1 className="text-lg font-semibold text-white">Something went wrong</h1>
            <p className="mt-2 text-sm text-base-400">
              {this.state.error.message || "An unexpected error occurred."}
            </p>
            <button
              onClick={this.handleReset}
              className="mt-4 rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-black hover:bg-orange-400"
            >
              Try again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
