import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import MockAdapter from 'axios-mock-adapter';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, test } from 'vitest';

import { queryClient } from '@/app/queryClient';
import { KnowledgePage } from '@/features/knowledge/KnowledgePage';
import { http } from '@/lib/api/http';

const mock = new MockAdapter(http);
beforeEach(() => {
  mock.reset();
  queryClient.clear();
});

test('renders kb list from api', async () => {
  mock.onGet('/api/v1/knowledge_bases').reply(200, {
    code: 0,
    message: 'ok',
    data: {
      items: [
        {
          id: 1,
          workspace_id: 1,
          name: '产品手册',
          embedding_model_id: 2,
          config: {},
          created_at: '2026-06-29T00:00:00Z',
          updated_at: '2026-06-29T00:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    },
  });
  mock.onGet('/api/v1/models').reply(200, { code: 0, message: 'ok', data: [] });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <KnowledgePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByText('产品手册')).toBeInTheDocument();
});
