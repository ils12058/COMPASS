// Gives components that read next/navigation (usePathname, useSearchParams, useRouter) the
// router contexts the App Router normally provides, so they can render under node:test.
import { createRequire } from "node:module";

import { createElement } from "react";

const require = createRequire(import.meta.url);
const { AppRouterContext } = require("next/dist/shared/lib/app-router-context.shared-runtime.js");
const { PathnameContext, SearchParamsContext, PathParamsContext } = require(
  "next/dist/shared/lib/hooks-client-context.shared-runtime.js",
);

export function withNextRouter(element, { pathname = "/", search = "", params = {}, navigations = [] } = {}) {
  const record = (method) => (href) => navigations.push({ method, href });
  const router = {
    back() {},
    forward() {},
    refresh() {},
    hmrRefresh() {},
    prefetch() {},
    push: record("push"),
    replace: record("replace"),
  };
  return createElement(
    AppRouterContext.Provider,
    { value: router },
    createElement(
      PathnameContext.Provider,
      { value: pathname },
      createElement(SearchParamsContext.Provider, { value: new URLSearchParams(search) }, createElement(PathParamsContext.Provider, { value: params }, element)),
    ),
  );
}
