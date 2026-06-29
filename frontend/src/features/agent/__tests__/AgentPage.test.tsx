import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { expect, test, vi } from 'vitest';

import { AgentPage } from '@/features/agent/AgentPage';
import * as agentApi from '@/features/agent/api';

test('renders input field', () => {
  vi.spyOn(agentApi, 'runAgent').mockResolvedValue(undefined);
  render(
    <MemoryRouter initialEntries={['/apps/1/run']}>
      <Routes>
        <Route path="/apps/:appId/run" element={<AgentPage />} />
      </Routes>
    </MemoryRouter>,
  );
  expect(screen.getByPlaceholderText(/输入消息/)).toBeInTheDocument();
});
