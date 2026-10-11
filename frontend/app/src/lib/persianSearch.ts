const PERSIAN_EQUIVALENTS: Record<string, string> = {
  "ي": "ی",
  "ى": "ی",
  "ك": "ک",
};

const IGNORED_FOR_SEARCH = /[\s\u064b-\u065f\u0670\u0640\u200b\u200c\u200e\u200f]/u;

function canonicalizeSearchCharacter(character: string): string {
  const persianCharacter = PERSIAN_EQUIVALENTS[character] ?? character;
  return persianCharacter
    .replace(/[٠-٩]/g, (digit) => String(digit.charCodeAt(0) - 0x0660))
    .replace(/[۰-۹]/g, (digit) => String(digit.charCodeAt(0) - 0x06f0))
    .toLowerCase();
}

/** Search-only normalization for Persian/Arabic OCR text; source text is unchanged. */
export function toPersianSearchKey(value: string): string {
  let key = "";
  for (const character of value) {
    if (!IGNORED_FOR_SEARCH.test(character)) key += canonicalizeSearchCharacter(character);
  }
  return key;
}

export type TextMatchRange = { start: number; end: number };

/** Finds ranges in the original string while comparing normalized search keys. */
export function findPersianSearchMatches(text: string, query: string): TextMatchRange[] {
  const needle = toPersianSearchKey(query);
  if (!needle) return [];

  let haystack = "";
  const sourceOffsets: number[] = [];
  let sourceOffset = 0;

  for (const character of text) {
    const start = sourceOffset;
    sourceOffset += character.length;
    if (IGNORED_FOR_SEARCH.test(character)) continue;

    const canonical = canonicalizeSearchCharacter(character);
    haystack += canonical;
    for (let index = 0; index < canonical.length; index += 1) sourceOffsets.push(start);
  }

  const ranges: TextMatchRange[] = [];
  let searchFrom = 0;
  while (searchFrom < haystack.length) {
    const matchAt = haystack.indexOf(needle, searchFrom);
    if (matchAt < 0) break;
    const start = sourceOffsets[matchAt];
    const lastCharacterStart = sourceOffsets[matchAt + needle.length - 1];
    const lastCodePoint = text.codePointAt(lastCharacterStart) ?? 0;
    ranges.push({ start, end: lastCharacterStart + (lastCodePoint > 0xffff ? 2 : 1) });
    searchFrom = matchAt + needle.length;
  }
  return ranges;
}
