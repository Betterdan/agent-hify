import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import MockAdapter from 'axios-mock-adapter';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, test } from 'vitest';

import { queryClient } from '@/app/queryClient';
import { ToolsPage } from '@/features/tools/ToolsPage';
import { http } from '@/lib/api/http';

const mock = new MockAdapter(http);
beforeEach(() => {
  mock.reset();
  queryClient.clear();
});

test('renders tool list from api', async () => {
  mock.onGet('/api/v1/tools').reply(200, {
    code: 0,
    message: 'ok',
    data: [
      {
        id: 1,
        workspace_id: 1,
        type: 'builtin',
        name: 'datetime',
        schema: {},
        config: {},
        enabled: true,
        created_at: '',
        updated_at: '',
      },
    ],
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ToolsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByText('datetime')).toBeInTheDocument();
});
