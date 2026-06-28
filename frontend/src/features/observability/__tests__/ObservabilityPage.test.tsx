import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import MockAdapter from 'axios-mock-adapter';
import { beforeEach, expect, test } from 'vitest';

import { queryClient } from '@/app/queryClient';
import { ObservabilityPage } from '@/features/observability/ObservabilityPage';
import { http } from '@/lib/api/http';

const mock = new MockAdapter(http);
beforeEach(() => {
  mock.reset();
  queryClient.clear();
});

test('shows a trace row', async () => {
  mock.onGet('/api/v1/observability/traces').reply(200, {
    code: 0, message: 'ok',
    data: [{ id: 1, type: 'llm_call', status: 'ok', tokens_in: 8, tokens_out: 3,
             cost: '0.000900', latency_ms: 120, created_at: '2026-06-27T10:00:00Z' }],
  });
  mock.onGet('/api/v1/observability/usage').reply(200, { code: 0, message: 'ok', data: [] });
  render(
    <QueryClientProvider client={queryClient}>
      <ObservabilityPage />
    </QueryClientProvider>,
  );
  expect(await screen.findByText('llm_call')).toBeInTheDocument();
});
