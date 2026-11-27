/** Lower case, no accents, Arabic letters unified (أ إ آ -> ا, ة -> ه, ى -> ي) and no diacritics: for the search in
 * the lists (crops, governorates) only. */
export function fold(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ًͯ-ٰٟ]/g, "")
    .replace(/[أإآٱ]/g, "ا")
    .replace(/ة/g, "ه")
    .replace(/ى/g, "ي")
    .trim();
}
