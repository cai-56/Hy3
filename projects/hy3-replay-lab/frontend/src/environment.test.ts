import { describe, expect, it } from "vitest";

import { clearedHy3EnvironmentValues } from "./environment";

describe("clearedHy3EnvironmentValues", () => {
  it("overrides every case-insensitive HY3 value without copying unrelated data", () => {
    expect(
      clearedHy3EnvironmentValues({
        PATH: "C:/tools",
        HY3_API_KEY: "unit-test-key",
        hy3_base_url: "https://provider.invalid/v1",
        Hy3_Model: "hy3-preview",
      }),
    ).toEqual({
      HY3_API_KEY: "",
      hy3_base_url: "",
      Hy3_Model: "",
    });
  });
});
