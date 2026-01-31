import {
  ApplicationConfig,
  provideBrowserGlobalErrorListeners,
  provideZoneChangeDetection,
  isDevMode,
  inject,
} from '@angular/core';
import { provideRouter } from '@angular/router';

import { routes } from './app.routes';
import { provideStore } from '@ngrx/store';
import { provideEffects } from '@ngrx/effects';
import { provideStoreDevtools } from '@ngrx/store-devtools';
import { reducers } from './state/app/app.reducers';
import { appEffects } from './state/app/app.effects';
import {
  providePersistStore,
  localStorageStrategy,
} from '@ngrx-addons/persist-state';
import { BeforeAppInit } from '@ngrx-addons/common';
import { PROJECT_FEATURE_KEY } from './state/project/project.reducer';
import { provideHttpClient } from '@angular/common/http';
import { provideApollo } from 'apollo-angular';
import { HttpLink } from 'apollo-angular/http';
import { ApolloLink, InMemoryCache } from '@apollo/client';
import { GraphQLWsLink } from '@apollo/client/link/subscriptions';
import { getMainDefinition } from '@apollo/client/utilities';
import { createClient } from 'graphql-ws';
import { CHAT_FEATURE_KEY } from './state/chat/chat.reducer';
import { OPERATIONS_FEATURE_KEY } from './state/operations/operations.reducer';
import { LOG_FEATURE_KEY } from './state/logs/logs.reducer';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideStore(reducers),
    provideEffects(appEffects),
    providePersistStore({
      states: [
        { key: PROJECT_FEATURE_KEY, storage: localStorageStrategy },
        { key: CHAT_FEATURE_KEY, storage: localStorageStrategy },
        { key: OPERATIONS_FEATURE_KEY, storage: localStorageStrategy },
        { key: LOG_FEATURE_KEY, storage: localStorageStrategy },
      ],
      strategy: BeforeAppInit,
    }),
    provideStoreDevtools({ maxAge: 25, logOnly: !isDevMode() }),
    provideHttpClient(),
    provideHttpClient(),
    provideApollo(() => {
      const httpLink = inject(HttpLink);
      const http = httpLink.create({ uri: 'http://localhost:8000/graphql' });

      const ws = new GraphQLWsLink(
        createClient({
          url: 'ws://localhost:8020/graphql',
          on: {
            connected: () => console.log('✅ WebSocket connected'),
            closed: () => console.log('🔌 WebSocket closed'),
            error: (error) => console.error('❌ WebSocket error:', error),
          },
          retryAttempts: 5,
          shouldRetry: () => true,
        })
      );

      // Updated split logic using ApolloLink.split
      const link = ApolloLink.split(
        ({ query }) => {
          const definition = getMainDefinition(query);
          return (
            definition.kind === 'OperationDefinition' &&
            definition.operation === 'subscription'
          );
        },
        ws,
        http
      );

      return {
        link,
        cache: new InMemoryCache(),
        defaultOptions: {
          watchQuery: {
            fetchPolicy: 'network-only',
          },
        },
      };
    }),
  ],
};
