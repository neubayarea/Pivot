// Ax31: switching the language must change every word the page writes itself. Two guards:
// 1. No English typed straight into JSX (text, user-facing attributes, string children): it goes
//    through t() and the tables in messages/. Parsed with the TypeScript compiler, not a regex.
// 2. Every value the API sends as a code (event types, agents, verifier issues, step statuses) that
//    the page turns into words has a key, so a new one cannot slip through as raw English.
import ts from "typescript";
import { describe, expect, it } from "vitest";
import { en } from "./messages/en";

const sources = import.meta.glob<string>(["../**/*.tsx", "!../**/*.test.tsx", "!../fixtures/**"], {
  query: "?raw", import: "default", eager: true,
});
const schemaText = Object.values(import.meta.glob<string>("../../../../packages/contracts/schema/pivot.schema.json", {
  query: "?raw", import: "default", eager: true,
}))[0];

/** Attributes a viewer reads or hears. */
const SHOWN_ATTRS = new Set(["aria-label", "title", "placeholder", "alt", "label", "aria-description"]);
/** Words that are the same in every language: the product's name. */
// "ivot" is the wordmark after the p mark (Ax86).
const SAME_EVERYWHERE = new Set(["Pivot", "ivot"]);
/** Elements whose text is code, not words (the field a number came from: `stat_ref.xg`). */
const CODE_TAGS = new Set(["code", "pre"]);
const WORDS = /[A-Za-z]{2,}/;

/** "file:line  text" for each piece of English written into JSX. */
function hardcoded(file: string, code: string): string[] {
  const src = ts.createSourceFile(file, code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const found: string[] = [];
  const report = (node: ts.Node, text: string) => {
    const t = text.replace(/&\w+;/g, " ").trim();
    if (WORDS.test(t) && !SAME_EVERYWHERE.has(t)) {
      found.push(`${file}:${src.getLineAndCharacterOfPosition(node.getStart()).line + 1}  ${t}`);
    }
  };
  const isString = (e: ts.Node | undefined): e is ts.StringLiteral | ts.NoSubstitutionTemplateLiteral =>
    !!e && (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e));
  const visit = (node: ts.Node) => {
    if (ts.isJsxElement(node) && CODE_TAGS.has(node.openingElement.tagName.getText(src))) return;
    if (ts.isJsxText(node)) report(node, node.text);
    else if (ts.isJsxAttribute(node) && SHOWN_ATTRS.has(node.name.getText(src))) {
      const init = node.initializer;
      if (isString(init)) report(node, init.text);
      else if (init && ts.isJsxExpression(init) && isString(init.expression)) report(node, init.expression.text);
    } else if (ts.isJsxExpression(node) && !ts.isJsxAttribute(node.parent) && isString(node.expression)) {
      report(node, node.expression.text);
    }
    ts.forEachChild(node, visit);
  };
  visit(src);
  return found;
}

/** An enum from the contract schema, e.g. MatchEvent.type. */
function contractEnum(def: string, prop: string): string[] {
  const schema = JSON.parse(schemaText) as { $defs: Record<string, { properties: Record<string, { enum?: string[] }> }> };
  const values = schema.$defs[def].properties[prop].enum;
  if (!values) throw new Error(`${def}.${prop} is not an enum in the contract schema`);
  return values;
}

const missing = (prefix: string, values: string[]) => values.filter((v) => !(`${prefix}.${v}` in en));

describe("no English typed into the page", () => {
  it("finds the source files", () => {
    expect(Object.keys(sources).length).toBeGreaterThan(30);
  });

  it("catches what it is meant to catch", () => {
    const code = `const A = () => <p title="Open it" aria-label={"Close"}>Hello there {"Sir"} {t("ok")} Pivot&nbsp;<code>stat_ref.xg</code></p>;`;
    expect(hardcoded("x.tsx", code).map((l) => l.split("  ")[1])).toEqual(["Open it", "Close", "Hello there", "Sir"]);
  });

  it("every word in JSX goes through t()", () => {
    const found = Object.entries(sources).flatMap(([file, code]) => hardcoded(file.replace(/^\.\.\//, "src/"), code));
    expect(found, `Move these into i18n/messages/{en,zh,es}.ts and use t():\n${found.join("\n")}`).toEqual([]);
  });
});

describe("codes from the API have words in every language", () => {
  it("event types (the feed and the evidence chips)", () => {
    // EventFeed's describe() writes these itself; every other type is named from event.type.*.
    const own = new Set(["pass", "shot", "card", "substitution", "tactical_shift", "kickoff", "period_end"]);
    expect(missing("event.type", contractEnum("MatchEvent", "type").filter((v) => !own.has(v)))).toEqual([]);
  });

  it("agents, step statuses and verifier issues (the AI work log)", () => {
    expect(missing("trace.agent", contractEnum("AgentTrace", "agent"))).toEqual([]);
    expect(missing("trace.status", contractEnum("AgentTrace", "status"))).toEqual([]);
    expect(missing("trace.issue", contractEnum("VerifierIssue", "code"))).toEqual([]);
  });
});
