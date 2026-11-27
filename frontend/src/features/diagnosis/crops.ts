import {
  Apple,
  Cherry,
  Citrus,
  Grape,
  Sprout,
  TreeDeciduous,
  TreePalm,
  Wheat,
  type LucideIcon,
} from "lucide-react";
import type { Culture } from "@/api/client";
import type { Lang } from "@/lib/i18n";

/** An icon per crop of /cultures (display only; the label is the crop name). */
const ICONS: Record<string, LucideIcon> = {
  apple: Apple,
  peach: Apple,
  cherry: Cherry,
  citrus: Citrus,
  grape: Grape,
  wheat: Wheat,
  corn: Wheat,
  datepalm: TreePalm,
  olive: TreeDeciduous,
};

export function cropIcon(code: string): LucideIcon {
  return ICONS[code] ?? Sprout;
}

export function cropName(
  code: string | null | undefined,
  cultures: Culture[] | undefined,
  lang: Lang,
): string {
  const c = cultures?.find((x) => x.code === code);
  return c ? c[lang] : (code ?? "");
}
