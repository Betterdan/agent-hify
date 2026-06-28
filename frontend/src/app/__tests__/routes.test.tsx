import { render, screen } from '@testing-library/react';
import { beforeEach, expect, test } from 'vitest';

import { App } from '@/app/App';
import { clearToken } from '@/lib/auth/token';

beforeEach(() => clearToken());

test('redirects to login when unauthenticated', async () => {
  window.history.pushState({}, '', '/models');
  render(<App />);
  expect(await screen.findByText('login')).toBeInTheDocument();
});
