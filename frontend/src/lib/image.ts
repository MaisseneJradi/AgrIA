// Photo prepared on the phone before it is sent: turned upright (EXIF orientation), reduced to MAX_SIDE pixels on
// its longest side, saved as JPEG. A 12 MP photo of 4 MB becomes ~200 KB: much faster on 3G, and the models work on
// 224-300 px images anyway. The photo stays on the device until the farmer sends it.
export const MAX_SIDE = 1280;
export const QUALITY = 0.8;

export interface PreparedPhoto {
  dataUrl: string;
  width: number;
  height: number;
  bytes: number;
}

export class PhotoError extends Error {
  constructor(public readonly kind: "notImage" | "unsupported") {
    super(kind);
    this.name = "PhotoError";
  }
}

/** Size that fits within max x max, ratio kept, never enlarged. */
export function fitWithin(width: number, height: number, max = MAX_SIDE): { width: number; height: number } {
  const scale = Math.min(1, max / Math.max(width, height));
  return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

async function decode(file: Blob): Promise<CanvasImageSource & { width: number; height: number }> {
  if (typeof createImageBitmap === "function") {
    try {
      // imageOrientation "from-image": the EXIF rotation of phone photos is applied
      return await createImageBitmap(file, { imageOrientation: "from-image" });
    } catch {
      /* older browser or format: try an <img> (which also applies EXIF in current browsers) */
    }
  }
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.decoding = "async";
    img.src = url;
    await img.decode();
    return Object.assign(img, { width: img.naturalWidth, height: img.naturalHeight });
  } catch {
    throw new PhotoError("unsupported");
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function preparePhoto(file: File): Promise<PreparedPhoto> {
  if (!file.type.startsWith("image/")) throw new PhotoError("notImage");
  const source = await decode(file);
  const { width, height } = fitWithin(source.width, source.height);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new PhotoError("unsupported");
  ctx.drawImage(source, 0, 0, width, height);
  if ("close" in source && typeof source.close === "function") source.close();
  const dataUrl = canvas.toDataURL("image/jpeg", QUALITY);
  return { dataUrl, width, height, bytes: dataUrlBytes(dataUrl) };
}

export function dataUrlBytes(dataUrl: string): number {
  const b64 = dataUrl.slice(dataUrl.indexOf(",") + 1);
  return Math.floor((b64.length * 3) / 4) - (b64.endsWith("==") ? 2 : b64.endsWith("=") ? 1 : 0);
}

/** The prepared photo as a file to upload (kept as a data URL so that a reload of the page does not lose it). */
export function dataUrlToBlob(dataUrl: string): Blob {
  const [head, b64 = ""] = dataUrl.split(",");
  const type = /data:([^;]+)/.exec(head ?? "")?.[1] ?? "image/jpeg";
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type });
}
