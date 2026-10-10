import { defineConfig } from "orval";

export default defineConfig({
  compass: {
    input: {
      target: "../contracts/openapi.json",
    },
    output: {
      mode: "tags-split",
      target: "./src/lib/api/generated/index.ts",
      schemas: "./src/lib/api/generated/model",
      client: "react-query",
      httpClient: "fetch",
      clean: true,
      override: {
        mutator: {
          path: "./src/lib/api/client.ts",
          name: "compassFetch",
        },
        fetch: {
          includeHttpResponseReturnType: true,
          forceSuccessResponse: true,
          serializeResponseHeaders: true,
        },
      },
    },
  },
});
