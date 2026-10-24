import { Component, type ErrorInfo, type ReactNode } from "react";
import StateCard from "./StateCard";

/** Last line of defence: a render error shows a message and a way back instead of a blank page. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Pivot page crashed", error, info.componentStack);
  }

  render() {
    return this.state.error ? <ErrorScreen error={this.state.error} /> : this.props.children;
  }
}

export function ErrorScreen({ error }: { error: Error }) {
  return (
    <>
      <header className="top">
        <span className="brand">Pivot</span>
      </header>
      <main className="page">
        <StateCard title="Something went wrong" tone="error" actions={<>
          <button type="button" className="btn pri" onClick={() => window.location.reload()}>Reload the page</button>
          <a className="btn" href="/">Back to the live board</a>
        </>}>
          <p>This page hit an unexpected error and stopped. Reloading usually fixes it.</p>
          <p className="muted state-detail">{error.message}</p>
        </StateCard>
      </main>
    </>
  );
}
