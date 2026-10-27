// C13 (#316): ☆ Follow wherever a player appears; pressed when that player is the one followed.
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it } from "vitest";
import { PrefsProvider } from "../i18n";
import FollowButton from "./FollowButton";

const g = globalThis as { window?: { location: { search: string }; localStorage: Pick<Storage, "getItem" | "setItem" | "removeItem"> } };
const render = (search: string) => {
  const store = new Map<string, string>();
  g.window = { location: { search }, localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => void store.set(k, v), removeItem: (k) => void store.delete(k) } };
  return renderToStaticMarkup(<PrefsProvider><FollowButton playerId="h10" name="M. Miquingorini" /></PrefsProvider>);
};
afterEach(() => {
  delete g.window;
});

describe("follow button", () => {
  it("offers to follow a player nobody follows", () => {
    const html = render("?lang=en&player=none");
    expect(html).toContain('aria-pressed="false"');
    expect(html).toContain('aria-label="Follow M. Miquingorini"');
    expect(html).toContain("☆");
  });
  it("shows the followed player as followed, with a way to stop", () => {
    const html = render("?lang=en&player=h10");
    expect(html).toContain('aria-pressed="true"');
    expect(html).toContain('aria-label="Stop following M. Miquingorini"');
    expect(html).toContain("Following");
  });
  it("speaks Chinese", () => {
    expect(render("?lang=zh&player=none")).toContain("关注 M. Miquingorini");
  });
});
