import { describe, expect, it } from "vitest";
import { safeHref } from "@/lib/safeHref";

describe("safeHref", () => {
  it("keeps web addresses", () => {
    expect(safeHref("https://doi.org/10.1/x")).toBe("https://doi.org/10.1/x");
    expect(safeHref("http://example.org/a")).toBe("http://example.org/a");
  });
  it.each([
    "javascript:alert(1)",
    "data:text/html,<script>1</script>",
    "vbscript:x",
    "//evil.example",
    "not a url",
    "",
    null,
    undefined,
    "file:///etc/passwd",
  ])("refuses %s", (u) => expect(safeHref(u as string | null | undefined)).toBeUndefined());
});
