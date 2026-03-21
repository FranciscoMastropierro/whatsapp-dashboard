# Dashboard Streamlit (WhatsApp Chatbot)

Panel de lectura que consume el API del backend (`/api`) descrito en el brief del proyecto Chatbot.

## Requisitos

- Python 3.10+
- Backend FastAPI en ejecución (por defecto `http://127.0.0.1:8000`)

## Instalación

```bash
cd Dashboard_Whatsapp
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

## Configuración

1. **Variable de entorno:** `API_BASE_URL=http://127.0.0.1:8000`
2. O **Streamlit secrets:** copia `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` y ajusta `API_BASE_URL`.

En la barra lateral puedes sobrescribir la URL base sin reiniciar.

## Ejecución

```bash
streamlit run streamlit_app.py
```

## Pantallas

- **Resumen:** métricas (`/api/metrics/summary`) y serie temporal (`/api/metrics/users-over-time`).
- **Usuarios:** listado paginado con filtros (`/api/users`), detalle y mensajes (`/api/users/{id}`, `/api/users/{id}/messages`).
- **Feed:** mensajes del tenant (`/api/tenants/{tenant_id}/messages`).

### Tenant

- Un solo tenant en `GET /api/tenants`: se usa su `id` automáticamente (sin desplegable).
- Varios tenants: selectbox en la barra lateral.

Tema por defecto: [`.streamlit/config.toml`](.streamlit/config.toml) (oscuro).
