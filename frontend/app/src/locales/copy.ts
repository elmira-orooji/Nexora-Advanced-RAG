import type { TFunction } from "i18next";

export function sectionCopy(t: TFunction, section: string, keys: readonly string[]) {
  return Object.fromEntries(keys.map((key) => [key, t(`${section}.${key}`)])) as Record<string, string>;
}
