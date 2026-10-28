// A fence around the analyst's report (C19 hotfix): if one of its charts throws while rendering, only
// that part of the Overview says so; the rest of the page keeps working. It tries again when the
// data it was given changes (`resetKey`), so a live match recovers on its next update.
import { Component, type ErrorInfo, type ReactNode } from "react";
import { useT } from "../../i18n";

type Props = { children: ReactNode; resetKey?: unknown };

export default class ReportBoundary extends Component<Props, { error: Error | null; key: unknown }> {
  state = { error: null as Error | null, key: this.props.resetKey };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  static getDerivedStateFromProps(props: Props, state: { error: Error | null; key: unknown }) {
    return props.resetKey !== state.key ? { error: null, key: props.resetKey } : null;
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Pivot report section failed", error, info.componentStack);
  }

  render() {
    return this.state.error ? <ReportFailed /> : this.props.children;
  }
}

function ReportFailed() {
  const t = useT();
  return <p className="rp-failed muted" role="status">{t("rp.failed")}</p>;
}
