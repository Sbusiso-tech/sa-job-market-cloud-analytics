import { createContext, useContext, type ReactNode } from 'react';
import type { ApiClient } from './api/client';
import type { AppConfig } from './config';

export interface Services {
  api: ApiClient;
  config: AppConfig;
}

const ServicesContext = createContext<Services | null>(null);

export function ServicesProvider({ value, children }: { value: Services; children: ReactNode }) {
  return <ServicesContext.Provider value={value}>{children}</ServicesContext.Provider>;
}

export function useServices(): Services {
  const ctx = useContext(ServicesContext);
  if (!ctx) throw new Error('useServices must be used inside <ServicesProvider>');
  return ctx;
}

export function useApi(): ApiClient {
  return useServices().api;
}
