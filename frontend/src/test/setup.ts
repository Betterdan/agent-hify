import '@testing-library/jest-dom';

// Fix for Node.js 22+: localStorage is experimentally defined but returns undefined without
// --localstorage-file, which shadows jsdom's own implementation. Provide a map-backed mock.
{
  const _store = new Map<string, string>();
  const _lsMock: Storage = {
    getItem: (k: string): string | null => _store.get(k) ?? null,
    setItem: (k: string, v: string): void => { _store.set(k, String(v)); },
    removeItem: (k: string): void => { _store.delete(k); },
    clear: (): void => { _store.clear(); },
    get length() { return _store.size; },
    key: (i: number): string | null => Array.from(_store.keys())[i] ?? null,
  };
  try {
    Object.defineProperty(globalThis, 'localStorage', {
      value: _lsMock, writable: true, configurable: true, enumerable: true,
    });
  } catch {
    (globalThis as Record<string, unknown>).localStorage = _lsMock;
  }
}

// Mock window.matchMedia for Ant Design's responsive observer (jsdom does not implement it).
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// Fix for Node.js 22+ + jsdom: jsdom's AbortSignal class differs from the one
// undici uses internally. react-router-dom's data router (createBrowserRouter)
// calls `new Request(url, { signal })` with a jsdom AbortSignal, which undici
// rejects with an instanceof mismatch. Stripping signal here is safe for
// route-rendering tests because we don't test request cancellation.
if (typeof globalThis.Request !== 'undefined') {
  const _OriginalRequest = globalThis.Request;
  class _PatchedRequest extends _OriginalRequest {
    constructor(input: RequestInfo | URL, init: RequestInit = {}) {
      const { signal: _omit, ...rest } = init;
      super(input, rest);
    }
  }
  globalThis.Request = _PatchedRequest;
}
