import { Component, type ErrorInfo, type ReactNode } from "react";
import { useT } from "../i18n";
import Wordmark from "./Wordmark";
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
  const t = useT();
  return (
    <>
      <header className="top">
        <Wordmark />
      </header>
      <main className="page">
        <StateCard title={t("error.title")} tone="error" actions={<>
          <button type="button" className="btn pri" onClick={() => window.location.reload()}>{t("error.reload")}</button>
          <a className="btn" href="/">{t("error.back")}</a>
        </>}>
          <p>{t("error.body")}</p>
          <p className="muted state-detail">{error.message}</p>
        </StateCard>
      </main>
    </>
  );
}
