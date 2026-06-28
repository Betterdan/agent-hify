import '@testing-library/jest-dom';

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
