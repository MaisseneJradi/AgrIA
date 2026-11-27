import { Fragment, type ReactNode } from "react";

const URL_RE = /(https?:\/\/[^\s)]+)/g;

/** The text of the answer, line by line, links clickable (left to right inside Arabic text). Nothing is added,
 * removed or reordered: this is the text the Vérificateur checked. */
export function AnswerText({ text, lang }: { text: string; lang: "fr" | "ar" }) {
  return (
    <div
      lang={lang}
      dir={lang === "ar" ? "rtl" : "ltr"}
      className="whitespace-pre-wrap break-words leading-relaxed"
    >
      {text.split(URL_RE).map((part, i) =>
        /^https?:\/\//.test(part) ? (
          <a
            key={i}
            href={part}
            target="_blank"
            rel="noopener noreferrer"
            dir="ltr"
            className="break-all font-medium text-text underline underline-offset-2"
          >
            {part}
          </a>
        ) : lang === "ar" ? (
          <Fragment key={i}>{isolateLatin(part)}</Fragment>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </div>
  );
}

// a run of French or Latin text inside Arabic (product names, doses, "Alternariose (brûlure alternarienne)"): starts
// with a Latin letter or a digit, ends with one (or a closing bracket, a % or a unit dot)
const LATIN_RUN = /([A-Za-zÀ-ÖØ-öø-ÿŒœ0-9][A-Za-zÀ-ÖØ-öø-ÿŒœ0-9 .,;:/%()+'’-]*[A-Za-zÀ-ÖØ-öø-ÿŒœ0-9)%.])/g;

/** In an Arabic answer, each Latin run is isolated left to right (<bdi dir="ltr">), so that its brackets and numbers
 * stay in place. Display only: the characters are the same (tested). */
function isolateLatin(text: string) {
  const out: ReactNode[] = [];
  text.split(LATIN_RUN).forEach((part, i) => {
    if (i % 2 === 0) {
      out.push(part);
      return;
    }
    // a closing bracket of the Arabic sentence around the run stays outside it
    let run = part;
    let tail = "";
    while (run.endsWith(")") && count(run, ")") > count(run, "(")) {
      tail = ")" + tail;
      run = run.slice(0, -1);
    }
    out.push(
      <bdi key={i} dir="ltr">
        {run}
      </bdi>,
      tail,
    );
  });
  return out;
}

function count(s: string, ch: string): number {
  return s.split(ch).length - 1;
}
