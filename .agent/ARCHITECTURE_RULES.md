# Architecture Rules

- Frontend and backend must be completely decoupled.
- The backend serves as an API (JSON) provider.
- The frontend acts as a single-page application consuming the APIs.
- Do NOT intertwine frontend logic into the Django templates.
- Strict modularity for Django apps: independent functionality where possible.
