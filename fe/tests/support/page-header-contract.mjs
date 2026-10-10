import ts from "typescript";
import path from "node:path";

// Read actual JSX call sites with TypeScript's symbol resolver, including import aliases, re-exports,
// arbitrary wrapper names, forwarded props and action components that never import PageAction.
// This is a structural guard, not a substitute for browser/accessibility or workflow tests.
export function inspectHeaderContracts(program, root) {
  const checker = program.getTypeChecker();
  const files = program.getSourceFiles().filter((s) => s.fileName.startsWith(root) && !s.fileName.includes("/generated/"));
  const issues = [];
  const compositions = [];
  const wrappers = new Map();
  const slots = new Map([["actions", "actions"], ["back", "back"], ["help", "help"], ["meta", "meta"]]);
  const visit = (node, fn) => { fn(node); ts.forEachChild(node, (child) => visit(child, fn)); };
  const opening = (n) => ts.isJsxElement(n) ? n.openingElement : n;
  const jsx = (n) => ts.isJsxSelfClosingElement(n) || ts.isJsxOpeningElement(n);
  const attr = (n, name) => opening(n).attributes.properties.find((p) => ts.isJsxAttribute(p) && p.name.text === name);
  const value = (a) => a?.initializer && (ts.isJsxExpression(a.initializer) ? a.initializer.expression : a.initializer);
  const unparen = (n) => n && (ts.isParenthesizedExpression(n) || ts.isAsExpression(n) || ts.isNonNullExpression(n)) ? unparen(n.expression) : n;
  function declaration(n) {
    let symbol = checker.getSymbolAtLocation(n);
    if (symbol?.flags & ts.SymbolFlags.Alias) symbol = checker.getAliasedSymbol(symbol);
    return symbol?.valueDeclaration ?? symbol?.declarations?.[0];
  }
  function component(n) {
    const d = declaration(opening(n).tagName);
    return d && ts.isVariableDeclaration(d) ? unparen(d.initializer) : d;
  }
  function named(n, file, name) {
    const d = declaration(opening(n).tagName);
    return d?.getSourceFile().fileName.endsWith(file) && d.name?.getText() === name;
  }
  const header = (n) => named(n, "/components/ui/page-header.tsx", "PageHeader");
  function owner(n) {
    for (let p = n.parent; p; p = p.parent) if (ts.isFunctionLike(p)) return p;
  }
  function prop(n) {
    n = unparen(n);
    if (!n) return;
    if (ts.isIdentifier(n)) {
      const d = declaration(n);
      if (d && ts.isBindingElement(d) && ts.isParameter(d.parent.parent)) return { fn: d.parent.parent.parent, name: (d.propertyName ?? d.name).getText() };
      if (d && ts.isVariableDeclaration(d)) return prop(d.initializer);
    }
    if (ts.isPropertyAccessExpression(n) && ts.isIdentifier(n.expression)) {
      const d = declaration(n.expression);
      if (d && ts.isParameter(d)) return { fn: d.parent, name: n.name.text };
    }
  }
  function schema(n) { return header(n) ? slots : wrappers.get(component(n)); }
  // Discover forwarding wrappers to a fixed point; no naming convention or file allowlist.
  let changed = true;
  while (changed) {
    changed = false;
    for (const s of files) visit(s, (n) => {
      if (!jsx(n) || !schema(n)) return;
      for (const [name, role] of schema(n)) {
        const expr = value(attr(n, name));
        if (!expr) continue;
        function forwarding(part) {
          part = unparen(part);
          if (!part) return;
          if (ts.isConditionalExpression(part)) { forwarding(part.whenTrue); forwarding(part.whenFalse); return; }
          if (ts.isBinaryExpression(part)) { if (part.operatorToken.kind !== ts.SyntaxKind.AmpersandAmpersandToken) forwarding(part.left); forwarding(part.right); return; }
          if (ts.isJsxExpression(part)) { forwarding(part.expression); return; }
          if (ts.isJsxFragment(part)) { part.children.forEach(forwarding); return; }
          if (ts.isJsxElement(part)) {
            // Only rendered slot content forwards slots. Conditions, link destinations and
            // component configuration are data, not ReactNode action/back/help props.
            if (part.openingElement.tagName.getText() === "div") part.children.forEach(forwarding);
            return;
          }
          const p = prop(part);
          if (!p || p.fn === component(n)) return;
          const map = wrappers.get(p.fn) ?? new Map();
          if (!map.has(p.name)) { map.set(p.name, role); wrappers.set(p.fn, map); changed = true; }
        }
        forwarding(expr);
      }
    });
  }
  function fail(n, message) {
    const s = n.getSourceFile();
    issues.push(`${path.relative(root, s.fileName)}:${s.getLineAndCharacterOfPosition(n.getStart()).line + 1}: ${message}`);
  }
  function literal(n) { n = unparen(n); return n && (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) ? n.text : undefined; }
  function returns(fn) {
    const result = [];
    if (!fn?.body) return result;
    if (!ts.isBlock(fn.body)) return [fn.body];
    function walk(n) {
      if (n !== fn.body && ts.isFunctionLike(n)) return;
      if (ts.isReturnStatement(n) && n.expression) result.push(n.expression);
      else ts.forEachChild(n, walk);
    }
    walk(fn.body);
    return result;
  }
  function examine(expr, role, seen = new Set()) {
    expr = unparen(expr);
    if (!expr || seen.has(expr)) return;
    seen = new Set(seen).add(expr);
    if (expr.kind === ts.SyntaxKind.NullKeyword || expr.kind === ts.SyntaxKind.FalseKeyword || ts.isIdentifier(expr) && expr.text === "undefined") return;
    if (ts.isConditionalExpression(expr)) { examine(expr.whenTrue, role, seen); examine(expr.whenFalse, role, seen); return; }
    if (ts.isBinaryExpression(expr)) {
      if (expr.operatorToken.kind !== ts.SyntaxKind.AmpersandAmpersandToken) examine(expr.left, role, seen);
      examine(expr.right, role, seen); return;
    }
    if (ts.isJsxExpression(expr)) { examine(expr.expression, role, seen); return; }
    if (ts.isJsxFragment(expr)) { expr.children.forEach((c) => examine(c, role, seen)); return; }
    if (ts.isJsxText(expr)) { if (expr.text.trim() && role === "actions") fail(expr, "metadata/text belongs outside actions"); return; }
    if (ts.isIdentifier(expr) || ts.isPropertyAccessExpression(expr)) {
      const p = prop(expr);
      if (p && wrappers.get(p.fn)?.get(p.name) === role) return; // Validated at every caller.
      const d = declaration(expr);
      if (d && ts.isVariableDeclaration(d) && d.initializer) { examine(d.initializer, role, seen); return; }
      if (role === "actions" || role === "back" || role === "help") fail(expr, `unresolved ${role} content: ${expr.getText()}`); return;
    }
    if (ts.isJsxElement(expr) || ts.isJsxSelfClosingElement(expr)) {
      const node = opening(expr);
      const tag = node.tagName.getText();
      const children = ts.isJsxElement(expr) ? expr.children : [];
      if (named(node, "/components/ui/page-action.tsx", "PageAction") || named(node, "/components/ui/page-action.tsx", "PageActionLink")) {
        if (role !== "actions") fail(node, `page command misplaced in ${role}`);
        const label = value(attr(node, "label"));
        function emptyLabel(n) {
          n = unparen(n);
          if (!n) return true;
          if (ts.isConditionalExpression(n)) return emptyLabel(n.whenTrue) || emptyLabel(n.whenFalse);
          return literal(n)?.trim() === "";
        }
        if (emptyLabel(label)) fail(node, "page action requires a visible label");
        if (!attr(node, "icon")) fail(node, "page action requires its icon surface");
        const renderer = value(attr(node, "as"));
        if (renderer) {
          const d = declaration(renderer);
          if (!d?.getSourceFile().fileName.endsWith("/features/form-safety/guarded-portal-link.tsx") && !d?.getSourceFile().fileName.includes("next/dist/client/link")) fail(node, "page action link renderer must preserve shared navigation");
        }
        const className = literal(value(attr(node, "className")));
        if (className && /(?:^|\s)(?:\S+:)?(?:hidden|sr-only)(?:\s|$)/.test(className)) fail(node, "page action label cannot be hidden");
        return;
      }
      // Portalled confirmation/dialog content is a separate interaction context; its triggers are
      // checked through children when asChild is used, never the confirmation's ordinary Buttons.
      if (named(node, "/components/ui/dialog.tsx", "DialogTrigger")) { children.forEach((c) => examine(c, role, seen)); return; }
      if (named(node, "/components/ui/dialog.tsx", "Dialog") || named(node, "/components/ui/consequential-action-dialog.tsx", "ConsequentialActionDialog") || named(node, "/features/content/content-shared.tsx", "ContentConfirmDialog")) return;
      // The only audited live-workspace exception: a named view preset selector, not a record command.
      if (named(node, "/features/ecounseling/session-layout.tsx", "LayoutPresetControl")) return;
      if (role === "actions") {
        if (["div", "section"].includes(tag) || named(node, "/components/ui/page-action.tsx", "PageActionGroup")) { children.forEach((c) => examine(c, role, seen)); return; }
        if (["p", "span"].includes(tag) && literal(value(attr(node, "role"))) === "alert") {
          let container = expr.parent;
          while (container && !ts.isJsxElement(container)) container = container.parent;
          let commandFeedback = false;
          if (container) visit(container, (part) => { if (jsx(part) && (named(part, "/components/ui/page-action.tsx", "PageAction") || named(part, "/components/ui/page-action.tsx", "PageActionLink"))) commandFeedback = true; });
          if (!commandFeedback) fail(node, "action feedback must accompany a labeled command");
          return;
        }
        if (/^[a-z]/.test(tag)) { fail(node, `noncanonical ${tag} in actions`); return; }
        const fn = component(node);
        if (fn && ts.isFunctionLike(fn)) { const rendered = returns(fn); if (!rendered.length) fail(node, `unresolved action component ${tag}`); rendered.forEach((e) => examine(e, role, seen)); return; }
        fail(node, `noncanonical action component ${tag}`); return;
      }
      if (role === "back") {
        if (tag === "div") { children.forEach((c) => examine(c, role, seen)); return; }
        const d = declaration(node.tagName);
        const link = tag === "a" || d?.getSourceFile().fileName.includes("next/dist/client/link") || named(node, "/features/form-safety/guarded-portal-link.tsx", "GuardedPortalLink");
        if (link) {
          const style = value(attr(node, "className"));
          let shared = false;
          if (style) visit(style, (part) => {
            if (!ts.isIdentifier(part)) return;
            const d = declaration(part);
            if (d?.getSourceFile().fileName.endsWith("/components/ui/page-header.tsx") && d.name?.getText() === "pageBackLinkClass") shared = true;
          });
          if (!shared) fail(node, "back link must use shared text-link styling");
          if (children.some((c) => ts.isJsxText(c) && /[←→]/.test(c.text))) fail(node, "back arrow must be decoration, not text");
          const firstText = children.find((c) => ts.isJsxText(c) && c.text.trim());
          if (firstText && !firstText.text.trim().startsWith("Back to")) fail(node, "standard back label starts with Back to");
          return;
        }
        const fn = component(node); if (fn && ts.isFunctionLike(fn)) { returns(fn).forEach((e) => examine(e, role, seen)); return; }
        fail(node, `non-navigation ${tag} in back`); return;
      }
      if (role === "help") {
        if (named(node, "/components/ui/context-help.tsx", "ContextHelp")) return;
        const fn = component(node); if (fn && ts.isFunctionLike(fn)) { returns(fn).forEach((e) => examine(e, role, seen)); return; }
        fail(node, `non-help ${tag} in help`); return;
      }
      // Metadata may contain domain badges and record facts, but not commands.
      if (role === "meta") {
        if (["button"].includes(tag) || named(node, "/components/ui/button.tsx", "Button") || named(node, "/components/ui/icon-action.tsx", "IconAction")) fail(node, "command misplaced in metadata");
        const fn = component(node);
        if (fn && ts.isFunctionLike(fn)) returns(fn).forEach((e) => examine(e, role, seen));
        else children.forEach((c) => examine(c, role, seen));
      }
      return;
    }
    if (role === "actions") fail(expr, `unresolved action expression: ${expr.getText()}`);
  }
  for (const s of files) {
    if (s.fileName.endsWith("/components/ui/page-header.tsx")) continue;
    visit(s, (n) => {
      if (!jsx(n)) return;
      const map = schema(n);
      if (map) {
        compositions.push(n);
        for (const [name, role] of map) examine(value(attr(n, name)), role);
        if (n.attributes.properties.some(ts.isJsxSpreadAttribute)) fail(n, "header slots must be explicit for structural review");
      }
      // Validate every canonical action too, even outside a discovered header.
      if (named(n, "/components/ui/page-action.tsx", "PageAction") || named(n, "/components/ui/page-action.tsx", "PageActionLink")) examine(ts.isJsxOpeningElement(n) ? n.parent : n, "actions");
      if (named(n, "/components/ui/panel.tsx", "PanelHeader")) {
        const title = literal(value(attr(n, "title")));
        if (!title) return;
        const fn = owner(n);
        if (fn) visit(fn, (h) => { if (jsx(h) && schema(h) && literal(value(attr(h, "title"))) === title) fail(n, `panel repeats page title ${title}`); });
      }
    });
  }
  return { issues: [...new Set(issues)], compositions: compositions.length, wrappers: wrappers.size };
}
