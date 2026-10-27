// Scrolling that follows the viewer's "reduce motion" setting (C11): a jump instead of a glide.
export const scrollBehavior = (): ScrollBehavior =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
