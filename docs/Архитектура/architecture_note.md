```plain
                  ┌──────────────────┐
                  │    Keycloak      │
                  │                  │
                  │ tiu-media-hub    │
                  │                  │
                  │ users            │
                  │ login            │
                  │ JWT              │
                  └────────┬─────────┘
                           │
                           │ OIDC
                           │
            ┌──────────────┴──────────────┐
            │                             │
            ▼                             ▼
        Frontend                       FastAPI
        web client                     resource server
            │                             │
            │ Bearer JWT                  │
            └─────────────────────────────┘
                                          │
                                          ▼
                                   PostgreSQL
                                          │
                                  collection_members
                                          │
                              ┌───────────┼───────────┐
                              ▼           ▼           ▼
                           OWNER     CONTRIBUTOR    VIEWER
```