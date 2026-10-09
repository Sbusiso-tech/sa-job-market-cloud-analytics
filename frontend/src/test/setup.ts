import '@testing-library/jest-dom/vitest';
import { cleanup, configure } from '@testing-library/react';
import { afterEach } from 'vitest';

// Pages are lazy-loaded; the first import of a chart-heavy page can take over a second.
configure({ asyncUtilTimeout: 5000 });

// jsdom has no layout engine; Recharts' ResponsiveContainer only needs the API to exist.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
});
