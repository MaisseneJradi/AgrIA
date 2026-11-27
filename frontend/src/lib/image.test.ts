import { describe, expect, it } from "vitest";
import { dataUrlBytes, dataUrlToBlob, fitWithin, preparePhoto, PhotoError } from "./image";

describe("photo preparation", () => {
  it("fits within 1280 px, keeps the ratio, never enlarges", () => {
    expect(fitWithin(4000, 3000)).toEqual({ width: 1280, height: 960 });
    expect(fitWithin(3000, 4000)).toEqual({ width: 960, height: 1280 });
    expect(fitWithin(800, 600)).toEqual({ width: 800, height: 600 });
  });

  it("the data URL becomes a JPEG file of the same bytes", async () => {
    const url = "data:image/jpeg;base64," + btoa("abcdef");
    const blob = dataUrlToBlob(url);
    expect(blob.type).toBe("image/jpeg");
    const text = await new Promise<string>((resolve) => {
      const r = new FileReader(); // (the Blob of jsdom has no .text())
      r.onload = () => resolve(String(r.result));
      r.readAsText(blob);
    });
    expect(text).toBe("abcdef");
    expect(dataUrlBytes(url)).toBe(6);
  });

  it("a file that is not an image is refused before any work", async () => {
    await expect(preparePhoto(new File(["x"], "notes.pdf", { type: "application/pdf" }))).rejects.toEqual(
      new PhotoError("notImage"),
    );
  });
});
