import { defineConfig } from 'orval';

export default defineConfig({
  agentHify: {
    input: './openapi.json',
    output: {
      mode: 'tags-split',
      target: 'src/lib/api/generated',
      client: 'react-query',
      override: {
        mutator: { path: 'src/lib/api/mutator.ts', name: 'customRequest' },
      },
    },
  },
});
