import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MockAdapter from 'axios-mock-adapter';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, test } from 'vitest';

import { LoginPage } from '@/features/auth/LoginPage';
import { http } from '@/lib/api/http';
import { getToken } from '@/lib/auth/token';

const mock = new MockAdapter(http);
beforeEach(() => mock.reset());

test('logs in and stores token', async () => {
  mock.onPost('/api/v1/auth/login').reply(200, {
    code: 0, message: 'ok', data: { access_token: 'tok-123', token_type: 'bearer' },
  });
  render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );
  await userEvent.type(screen.getByLabelText('邮箱'), 'admin@agent-hify.local');
  await userEvent.type(screen.getByLabelText('密码'), 'admin123');
  await userEvent.click(screen.getByRole('button', { name: '登录' }));
  await waitFor(() => expect(getToken()).toBe('tok-123'));
});
