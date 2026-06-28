import MockAdapter from 'axios-mock-adapter';
import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, test } from 'vitest';

import { queryClient } from '@/app/queryClient';
import { ChatPage } from '@/features/chat/ChatPage';
import { http } from '@/lib/api/http';

const mock = new MockAdapter(http);
beforeEach(() => {
  mock.reset();
  queryClient.clear();
});

function renderChat() {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/apps/1/chat']}>
        <Routes>
          <Route path="/apps/:appId/chat" element={<ChatPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test('renders conversation list and opens messages', async () => {
  mock.onGet('/api/v1/apps/1/conversations').reply(200, {
    code: 0,
    message: 'ok',
    data: {
      items: [
        {
          id: 7,
          app_id: 1,
          title: '历史对话',
          created_at: '2026-06-29T00:00:00Z',
          updated_at: '2026-06-29T00:00:00Z',
        },
      ],
      next_cursor: null,
      has_more: false,
    },
  });
  mock.onGet('/api/v1/conversations/7/messages').reply(200, {
    code: 0,
    message: 'ok',
    data: {
      items: [
        {
          id: 1,
          conversation_id: 7,
          role: 'user',
          content: [{ type: 'text', text: '你好' }],
          created_at: '2026-06-29T00:00:00Z',
        },
        {
          id: 2,
          conversation_id: 7,
          role: 'assistant',
          content: [{ type: 'text', text: '你好，有什么可以帮你' }],
          created_at: '2026-06-29T00:00:01Z',
        },
      ],
      next_cursor: null,
      has_more: false,
    },
  });

  renderChat();
  const conv = await screen.findByText('历史对话');
  await userEvent.click(conv);
  expect(await screen.findByText('你好，有什么可以帮你')).toBeInTheDocument();
});
