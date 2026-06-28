import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import MockAdapter from 'axios-mock-adapter';
import { beforeEach, expect, test } from 'vitest';

import { queryClient } from '@/app/queryClient';
import { ModelsPage } from '@/features/models/ModelsPage';
import { http } from '@/lib/api/http';

const mock = new MockAdapter(http);
beforeEach(() => {
  mock.reset();
  queryClient.clear();
});

test('renders model list from api', async () => {
  mock.onGet('/api/v1/models').reply(200, {
    code: 0, message: 'ok',
    data: [{ id: 1, provider_id: 1, model_key: 'gpt-4o-mini', type: 'llm',
             capabilities: [], embedding_dim: null, enabled: true }],
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ModelsPage />
    </QueryClientProvider>,
  );
  expect(await screen.findByText('gpt-4o-mini')).toBeInTheDocument();
});
