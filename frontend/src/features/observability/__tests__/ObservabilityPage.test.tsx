import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import MockAdapter from 'axios-mock-adapter';
import { beforeEach, expect, test } from 'vitest';

import { queryClient } from '@/app/queryClient';
import { ObservabilityPage } from '@/features/observability/ObservabilityPage';
import * as obsApi from '@/features/observability/api';
import { http } from '@/lib/api/http';

const mock = new MockAdapter(http);
beforeEach(() => {
  mock.reset();
  queryClient.clear();
});

test('shows a trace row', async () => {
  // Use regex to match /traces with or without query params
  mock.onGet(/\/api\/v1\/observability\/traces/).reply(200, {
    code: 0, message: 'ok',
    data: [{ id: 1, type: 'llm_call', status: 'ok', app_id: null, conversation_id: null,
             message_id: null, tokens_in: 8, tokens_out: 3,
             cost: '0.000900', latency_ms: 120, error: null, created_at: '2026-06-27T10:00:00Z' }],
  });
  mock.onGet('/api/v1/observability/usage').reply(200, { code: 0, message: 'ok', data: [] });
  render(
    <QueryClientProvider client={queryClient}>
      <ObservabilityPage />
    </QueryClientProvider>,
  );
  expect(await screen.findByText('llm_call')).toBeInTheDocument();
});

test('api module exports listTraces, listUsage, createAnnotation', () => {
  expect(typeof obsApi.listTraces).toBe('function');
  expect(typeof obsApi.listUsage).toBe('function');
  expect(typeof obsApi.createAnnotation).toBe('function');
});

test('createAnnotation posts to annotations endpoint', async () => {
  mock.onPost('/api/v1/observability/annotations').reply(200, {
    code: 0, message: 'ok',
    data: { id: 1, message_id: 42, rating: 1, comment: null, created_at: '2026-06-29T00:00:00Z' },
  });
  const result = await obsApi.createAnnotation({ message_id: 42, rating: 1 });
  expect(result.message_id).toBe(42);
  expect(result.rating).toBe(1);
});
