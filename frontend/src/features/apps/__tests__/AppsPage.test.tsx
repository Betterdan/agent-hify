import MockAdapter from 'axios-mock-adapter';
import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, test } from 'vitest';

import { queryClient } from '@/app/queryClient';
import { AppsPage } from '@/features/apps/AppsPage';
import { http } from '@/lib/api/http';

const mock = new MockAdapter(http);
beforeEach(() => {
  mock.reset();
  queryClient.clear();
});

test('renders app list from api', async () => {
  mock.onGet('/api/v1/apps').reply(200, {
    code: 0,
    message: 'ok',
    data: [
      {
        id: 1,
        type: 'chat',
        name: '客服助手',
        config: { model_id: 1 },
        status: 'draft',
        created_at: '2026-06-29T00:00:00Z',
        updated_at: '2026-06-29T00:00:00Z',
      },
    ],
  });
  mock.onGet('/api/v1/models').reply(200, { code: 0, message: 'ok', data: [] });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AppsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByText('客服助手')).toBeInTheDocument();
});
