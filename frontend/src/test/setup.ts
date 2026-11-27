import "@testing-library/jest-dom/vitest";
import "fake-indexeddb/auto"; // IndexedDB of the history and the queue
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import "@/lib/i18n";
import { sentForms, server } from "./server";

// Node 25 has its own global localStorage (without --localstorage-file it has no methods) which hides the one of
// jsdom: a Storage in memory, like the browser's.
class MemoryStorage implements Storage {
  private data = new Map<string, string>();
  get length() {
    return this.data.size;
  }
  clear() {
    this.data.clear();
  }
  getItem(key: string) {
    return this.data.get(key) ?? null;
  }
  key(i: number) {
    return Array.from(this.data.keys())[i] ?? null;
  }
  removeItem(key: string) {
    this.data.delete(key);
  }
  setItem(key: string, value: string) {
    this.data.set(key, String(value));
  }
}
for (const name of ["localStorage", "sessionStorage"] as const) {
  Object.defineProperty(globalThis, name, { value: new MemoryStorage(), configurable: true, writable: true });
}

// The data router of react-router builds a Request with an AbortSignal of jsdom, which the Request of Node refuses: the
// navigation then fails silently. The signal is left out (no navigation is cancelled in these tests).
const NodeRequest = globalThis.Request;
globalThis.Request = class extends NodeRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    super(input, init ? { ...init, signal: undefined } : init);
  }
} as typeof Request;

// jsdom has no matchMedia (theme "system")
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
  // jsdom objects that the Request of Node (built by MSW) does not take: the AbortSignal is left out (the timeouts of
  // src/api/client.ts are not tested here, MSW answers at once) and a FormData body is recorded in `sentForms` for
  // the tests to read (Node cannot serialise the FormData of jsdom).
  const mswFetch = globalThis.fetch;
  globalThis.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (init?.body instanceof FormData) {
      sentForms.push({ path: new URL(url, "http://localhost").pathname, form: init.body });
      return mswFetch(input, { ...init, body: undefined, signal: undefined });
    }
    return mswFetch(input, { ...init, signal: undefined });
  };
});
afterEach(() => {
  cleanup();
  sentForms.length = 0;
  server.resetHandlers();
  localStorage.clear();
  document.documentElement.classList.remove("dark");
});
afterAll(() => server.close());
