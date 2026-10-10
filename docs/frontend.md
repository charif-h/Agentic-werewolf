# Frontend

React 18 single-page app built with **Vite**, tested with **Vitest** and Testing Library, linted with ESLint.

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000, forwards /api and /ws to http://127.0.0.1:8000
npm test           # unit and component tests (no browser, no backend)
npm run lint       # zero warnings allowed
npm run build      # production build in frontend/dist
```

* The page always calls relative addresses (`/api/...`, `/ws/...`). In development the Vite dev server forwards them to the backend (`VITE_BACKEND_URL`, default `http://127.0.0.1:8000`); in Docker, nginx does (`nginx.conf`). So there is no CORS and no API address to configure. Set `VITE_API_URL` only when the backend is on a different host.
* No runtime dependency except React: the API client uses `fetch`.
* `package-lock.json` is committed; `npm ci` gives the same tree everywhere (CI uses Node 20).

## Dependency audit (issue #34)

| | Create React App (before) | Vite + Vitest (now) |
|---|---|---|
| Packages installed | 1,301 | 410 |
| `npm audit` | 99 vulnerabilities (63 high, 33 moderate, 3 low) | 5 (1 critical, 1 high, 3 moderate), all in development tools |
| Vulnerabilities in what ships to the browser (`npm audit --omit=dev`) | 99 | **0** |
| Runtime dependencies | react, react-dom, react-scripts, axios, socket.io-client, web-vitals | react, react-dom |

The five remaining advisories are in the **test runner and the dev server** (vitest/tinypool, vite/esbuild dev-server requests). They are not part of the production build. The fixed versions (Vite 8, Vitest 5) need Node 22 or newer; the project still supports Node 18 and 20, so they stay on Vite 5 and Vitest 3 until the minimum Node version is raised.

`axios`, `socket.io-client` (the backend speaks plain WebSocket, not Socket.IO) and `web-vitals` were removed.
