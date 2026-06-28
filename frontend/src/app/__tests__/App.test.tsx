/// <reference types="vitest" />
import { render, screen } from '@testing-library/react';

import { App } from '@/app/App';

test('renders app name', () => {
  render(<App />);
  expect(screen.getByText('agent-hify')).toBeInTheDocument();
});
