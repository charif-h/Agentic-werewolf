import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// The page loads data with fetch; the answer arrives between two steps of a test, outside of
// the window React Testing Library wraps in act(). The tests wait for the final state with
// findBy/waitFor, so this warning is noise: hide it, keep every other console.error.
const consoleError = console.error;
vi.spyOn(console, 'error').mockImplementation((...args) => {
  if (typeof args[0] === 'string' && args[0].includes('not wrapped in act')) return;
  consoleError(...args);
});
