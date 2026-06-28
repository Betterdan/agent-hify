import { type AxiosRequestConfig } from 'axios';

import { request } from '@/lib/api/http';

export function customRequest<T>(config: AxiosRequestConfig): Promise<T> {
  return request<T>(config);
}

export default customRequest;
