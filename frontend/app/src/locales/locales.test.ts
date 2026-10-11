import { describe, expect, it } from "vitest";
import { en } from "./en";
import { fa } from "./fa";

function keys(value: object, prefix = ""): string[] {
  return Object.entries(value).flatMap(([key, item]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return item && typeof item === "object" ? keys(item, path) : [path];
  }).sort();
}

describe("translation resources", () => {
  it("keeps English and Persian key sets identical", () => {
    expect(keys(fa)).toEqual(keys(en));
  });
});
