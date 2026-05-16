"""
Streamlit dashboard for the WhatsApp chatbot backend (/api).
Run: streamlit run streamlit_app.py
"""

from __future__ import annotations

from datetime import date
from html import escape

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.api_client import (
    AuthenticationError,
    allow_api_base_url_override,
    get_json,
    health_ok,
    patch_json,
    post_json,
    resolve_base_url,
)

st.set_page_config(page_title="Dashboard Chatbot", layout="wide", initial_sidebar_state="expanded")

_DASHBOARD_CSS = """
<style>
/* KPI cards */
div[data-testid="stMetric"] {
    background: linear-gradient(145deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 0.85rem 1rem 0.75rem 1rem;
}
div[data-testid="stMetric"] label {
    font-size: 0.8rem !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    opacity: 0.85;
}
.summary-card {
    background: linear-gradient(145deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%);
    border: 1px solid rgba(255,255,255,0.08);
    border-left: 4px solid rgba(255,255,255,0.18);
    border-radius: 12px;
    padding: 0.85rem 1rem 0.75rem 1rem;
    min-height: 118px;
}
.summary-card--pending {
    background: linear-gradient(145deg, rgba(245, 158, 11, 0.13) 0%, rgba(255,255,255,0.02) 100%);
    border-left-color: #f59e0b;
}
.summary-card--rejected {
    background: linear-gradient(145deg, rgba(248, 113, 113, 0.12) 0%, rgba(255,255,255,0.02) 100%);
    border-left-color: #f87171;
}
.summary-card__label {
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    opacity: 0.85;
    margin-bottom: 0.35rem;
}
.summary-card__value {
    font-size: 2rem;
    font-weight: 600;
    line-height: 1.2;
}
.summary-card__description {
    font-size: 0.82rem;
    opacity: 0.72;
    margin-top: 0.35rem;
}
/* Page title */
.dashboard-title {
    font-size: 1.75rem;
    font-weight: 650;
    letter-spacing: -0.02em;
    margin-bottom: 0.25rem;
}
.dashboard-sub {
    color: rgba(240,246,252,0.55);
    font-size: 0.9rem;
    margin-bottom: 1.25rem;
}
/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background: rgba(255,255,255,0.03);
    padding: 6px;
    border-radius: 10px;
}
</style>
"""

_AUTH_TOKEN_KEY = "auth_token"
_AUTH_USER_KEY = "auth_user"


def _is_dark_theme() -> bool:
    try:
        t = st.context.theme.type
        if t == "light":
            return False
        if t == "dark":
            return True
    except (AttributeError, RuntimeError):
        pass
    return True


def _inject_styles() -> None:
    st.markdown(_DASHBOARD_CSS, unsafe_allow_html=True)


def _auth_token() -> str | None:
    token = st.session_state.get(_AUTH_TOKEN_KEY)
    return str(token) if token else None


def _auth_user_label() -> str:
    user = st.session_state.get(_AUTH_USER_KEY) or {}
    if isinstance(user, dict):
        return str(user.get("username") or user.get("name") or "usuario")
    return "usuario"


def _clear_auth_session() -> None:
    st.session_state.pop(_AUTH_TOKEN_KEY, None)
    st.session_state.pop(_AUTH_USER_KEY, None)


def _store_auth_session(auth_data: dict, fallback_username: str) -> bool:
    token = auth_data.get("access_token") or auth_data.get("token")
    if not token:
        st.error("El backend no devolvió un token de acceso.")
        return False
    st.session_state[_AUTH_TOKEN_KEY] = str(token)
    st.session_state[_AUTH_USER_KEY] = auth_data.get("user") or {"username": fallback_username}
    return True


def _render_login(base: str) -> bool:
    if _auth_token():
        return True

    st.markdown('<p class="dashboard-title">Acceso al dashboard</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="dashboard-sub">Iniciá sesión para ver métricas, usuarios y mensajes.</p>',
        unsafe_allow_html=True,
    )
    with st.form("dashboard_login"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar", type="primary")

    if not submitted:
        return False
    if not username.strip() or not password:
        st.error("Ingresá usuario y contraseña.")
        return False

    try:
        auth_data = post_json(
            "/api/auth/login",
            {"username": username.strip(), "password": password},
            base_url=base,
        )
        if not _store_auth_session(auth_data, username.strip()):
            return False
        st.session_state[_AUTH_USER_KEY] = get_json("/api/auth/me", base_url=base, auth_token=_auth_token())
    except AuthenticationError:
        _clear_auth_session()
        st.error("Usuario o contraseña inválidos.")
        return False
    except (httpx.HTTPError, ValueError) as e:
        _clear_auth_session()
        st.error(f"No se pudo iniciar sesión: {e}")
        return False

    st.rerun()


def _render_session_controls() -> None:
    st.sidebar.caption(f"Sesión: **{_auth_user_label()}**")
    if st.sidebar.button("Cerrar sesión"):
        _clear_auth_session()
        st.rerun()


def _init_session() -> None:
    default = resolve_base_url()
    if "api_base_url" not in st.session_state:
        st.session_state.api_base_url = default


def _sidebar_base_url() -> str:
    _init_session()
    st.sidebar.markdown("**Conexión**")
    resolved = resolve_base_url()
    if allow_api_base_url_override():
        url = st.sidebar.text_input(
            "URL base del API",
            value=st.session_state.api_base_url,
            help="Prioridad: este campo → secrets.toml → API_BASE_URL → http://127.0.0.1:8000",
        )
        if url != st.session_state.api_base_url:
            st.session_state.api_base_url = url.strip() or resolved
        base = st.session_state.api_base_url.strip() or resolved
    else:
        st.session_state.api_base_url = resolved
        base = resolved
        st.sidebar.caption("URL base del API definida por configuración.")
    ok = health_ok(base_url=base)
    st.sidebar.caption("Estado API: **OK**" if ok else "Estado API: **sin respuesta** (`/health`)")
    return base


def _load_tenants(base: str, auth_token: str) -> list[dict]:
    data = get_json("/api/tenants", base_url=base, auth_token=auth_token)
    return list(data.get("items") or [])


def _resolve_tenant_id(base: str, auth_token: str) -> str | None:
    """
    Un solo tenant: se usa su id automáticamente (sin selectbox).
    Varios: selectbox en sidebar.
    Cero: aviso y None.
    """
    tenants = _load_tenants(base, auth_token)
    if not tenants:
        st.sidebar.warning("No hay tenants en el API.")
        return None
    if len(tenants) == 1:
        t = tenants[0]
        name = t.get("name") or "—"
        st.sidebar.caption(f"Tenant · **{name}**")
        return str(t["id"])
    labels = [f"{t.get('name', '(sin nombre)')} · `{str(t.get('id', ''))[:8]}…`" for t in tenants]
    ids = [str(t["id"]) for t in tenants]
    idx = st.sidebar.selectbox("Tenant", range(len(ids)), format_func=lambda i: labels[i])
    return ids[idx]


def _plotly_template() -> str:
    return "plotly_dark" if _is_dark_theme() else "plotly_white"


def _summary_value(summary: dict, key: str, default: int = 0) -> object:
    value = summary.get(key)
    return default if value is None else value


def _render_summary_card(title: str, value: object, description: str, tone: str) -> None:
    st.markdown(
        f"""
        <div class="summary-card summary-card--{escape(tone)}">
            <div class="summary-card__label">{escape(title)}</div>
            <div class="summary-card__value">{escape(str(value))}</div>
            <div class="summary-card__description">{escape(description)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def tab_overview(base: str, tenant_id: str | None, auth_token: str) -> None:
    st.markdown('<p class="dashboard-title">Resumen</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="dashboard-sub">Métricas globales y altas de usuarios en el período.</p>',
        unsafe_allow_html=True,
    )
    params = {"tenant_id": tenant_id} if tenant_id else {}
    try:
        summary = get_json("/api/metrics/summary", params, base_url=base, auth_token=auth_token)
    except AuthenticationError:
        raise
    except (httpx.HTTPError, ValueError) as e:
        st.error(f"No se pudo cargar métricas: {e}")
        return

    r1 = st.columns(4)
    metrics_row1 = [
        ("Usuarios totales", summary.get("total_users", "—")),
        ("Mensajes totales", summary.get("total_messages", "—")),
        ("Usuarios (7 días)", summary.get("users_last_7_days", "—")),
        ("Mensajes (7 días)", summary.get("messages_last_7_days", "—")),
    ]
    for col, (label, val) in zip(r1, metrics_row1):
        col.metric(label, val)

    r2 = st.columns(3)
    metrics_row2 = [
        ("Calif. pendiente", summary.get("qualification_pending", "—")),
        ("Calif. aprobados", summary.get("qualification_passed", "—")),
        ("Calif. rechazados", summary.get("qualification_rejected", "—")),
    ]
    for col, (label, val) in zip(r2, metrics_row2):
        col.metric(label, val)

    r3 = st.columns(2)
    with r3[0]:
        _render_summary_card(
            "Rechazados por zona",
            _summary_value(summary, "qualification_rejected_location"),
            "Usuarios rechazados por no vivir en CABA, GBA o La Plata.",
            "rejected",
        )
    with r3[1]:
        _render_summary_card(
            "Usuarios no vistos",
            _summary_value(summary, "users_unseen"),
            "Usuarios pendientes de revisión en la lista.",
            "pending",
        )

    st.markdown("##### Usuarios en el tiempo")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        days = st.number_input("Días", min_value=1, max_value=365, value=30, key="ov_days")
    with col_b:
        granularity = st.selectbox("Granularidad", ["day", "week"], key="ov_gran")

    mparams = {"days": int(days), "granularity": granularity}
    if tenant_id:
        mparams["tenant_id"] = tenant_id
    try:
        series_data = get_json("/api/metrics/users-over-time", mparams, base_url=base, auth_token=auth_token)
    except AuthenticationError:
        raise
    except (httpx.HTTPError, ValueError) as e:
        st.error(f"No se pudo cargar la serie: {e}")
        return

    rows = series_data.get("series") or []
    if not rows:
        st.info("Sin datos para el rango elegido.")
        return
    df = pd.DataFrame(rows)
    if "date" in df.columns and "count" in df.columns:
        fig = px.line(
            df,
            x="date",
            y="count",
            markers=True,
            title="Altas de usuarios",
        )
        fig.update_traces(line=dict(width=2.5), marker=dict(size=9))
        fig.update_layout(
            template=_plotly_template(),
            height=400,
            margin=dict(l=0, r=20, t=48, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_title="Cantidad",
            xaxis_title="",
            title_font_size=16,
            hovermode="x unified",
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.dataframe(df, width="stretch")


def _save_seen_changes(original: pd.DataFrame, edited: pd.DataFrame, base: str, auth_token: str) -> None:
    if "id" not in original.columns or "seen" not in original.columns or "seen" not in edited.columns:
        return

    edited = edited.copy()
    if "id" not in edited.columns:
        edited["id"] = original.reset_index(drop=True)["id"]

    original_seen = original.set_index("id")["seen"].fillna(False).astype(bool)
    edited_seen = edited.set_index("id")["seen"].fillna(False).astype(bool)
    updated_count = 0
    for user_id, seen in edited_seen.items():
        if user_id not in original_seen.index or bool(seen) == bool(original_seen.loc[user_id]):
            continue
        try:
            patch_json(f"/api/users/{user_id}", {"seen": bool(seen)}, base_url=base, auth_token=auth_token)
        except AuthenticationError:
            raise
        except (httpx.HTTPError, ValueError) as e:
            st.error(f"No se pudo actualizar visto para el usuario {str(user_id)[:8]}…: {e}")
            return
        updated_count += 1

    if updated_count:
        st.toast("Estado visto actualizado.")
        st.rerun()


def _style_seen_user_row(row: pd.Series) -> list[str]:
    if not bool(row.get("seen", False)):
        return [""] * len(row)

    styles = ["background-color: rgba(34, 197, 94, 0.08)"] * len(row)
    if styles:
        styles[0] += "; border-left: 4px solid #22c55e"
    return styles


def tab_users(base: str, tenant_id: str | None, auth_token: str) -> None:
    st.markdown('<p class="dashboard-title">Usuarios</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="dashboard-sub">Listado, filtros y conversación por usuario.</p>',
        unsafe_allow_html=True,
    )
    f1, f2, f3 = st.columns(3)
    with f1:
        qual = st.selectbox(
            "Calificación",
            ["(todas)", "pending", "passed", "rejected"],
            key="u_qual",
        )
    with f2:
        use_since = st.checkbox("Filtrar por fecha de alta", key="u_use_since")
    with f3:
        page = st.number_input("Página", min_value=1, value=1, key="u_page")
    created_since = None
    if use_since:
        d = st.date_input("Desde (creado)", value=date.today().replace(day=1), key="u_since")
        created_since = d.isoformat()

    params: dict = {"page": int(page), "limit": 20}
    if tenant_id:
        params["tenant_id"] = tenant_id
    if qual != "(todas)":
        params["qualification"] = qual
    if created_since:
        params["created_since"] = created_since

    try:
        data = get_json("/api/users", params, base_url=base, auth_token=auth_token)
    except AuthenticationError:
        raise
    except (httpx.HTTPError, ValueError) as e:
        st.error(f"Error al listar usuarios: {e}")
        return

    items = data.get("items") or []
    total = data.get("total", 0)
    st.caption(f"Total: **{total}** · página **{data.get('page', page)}** · **{data.get('limit', 20)}** por página")

    if not items:
        st.info("No hay usuarios en esta página.")
        return

    df = pd.DataFrame(items)
    display_cols = [
        c
        for c in [
            "name",
            "whatsapp_number",
            "message_count",
            "seen",
            "qualification_completed",
            "qualification_passed",
            "created_at",
            "last_message_at",
            "id",
        ]
        if c in df.columns
    ]
    show = df[display_cols].copy()
    if "seen" in show.columns:
        show["seen"] = show["seen"].fillna(False).astype(bool)
    if "created_at" in show.columns:
        show["created_at"] = pd.to_datetime(show["created_at"], utc=True, errors="coerce")
    if "last_message_at" in show.columns:
        show["last_message_at"] = pd.to_datetime(show["last_message_at"], utc=True, errors="coerce")
    edited_show = st.data_editor(
        show.style.apply(_style_seen_user_row, axis=1),
        width="stretch",
        hide_index=True,
        disabled=[column for column in show.columns if column != "seen"],
        key=f"users_editor_{tenant_id or 'all'}_{page}_{qual}_{created_since or 'all'}",
        column_config={
            "name": st.column_config.TextColumn("Nombre", width="small"),
            "whatsapp_number": st.column_config.TextColumn("WhatsApp", width="medium"),
            "message_count": st.column_config.NumberColumn("Msgs", width="small"),
            "seen": st.column_config.CheckboxColumn("Visto", width="small"),
            "qualification_completed": st.column_config.CheckboxColumn("Calif. hecha"),
            "qualification_passed": st.column_config.CheckboxColumn("Aprobado"),
            "created_at": st.column_config.DatetimeColumn("Alta", format="dd/MM/yyyy HH:mm"),
            "last_message_at": st.column_config.DatetimeColumn("Últ. mensaje", format="HH:mm", width="small"),
            "id": None,
        },
    )
    _save_seen_changes(show, edited_show, base, auth_token)

    user_options = {f"{r.get('name', '')} (`{str(r.get('id', ''))[:8]}…`)": str(r["id"]) for r in items if r.get("id")}
    if not user_options:
        return
    choice = st.selectbox("Ver detalle y mensajes", list(user_options.keys()))
    uid = user_options[choice]

    st.divider()
    try:
        detail = get_json(f"/api/users/{uid}", base_url=base, auth_token=auth_token)
    except AuthenticationError:
        raise
    except (httpx.HTTPError, ValueError) as e:
        st.error(f"No se pudo cargar el usuario: {e}")
        return

    st.subheader("Detalle")
    with st.expander("JSON completo", expanded=False):
        st.json(detail)

    st.subheader("Mensajes del usuario")
    msg_page = st.number_input("Página mensajes", min_value=1, value=1, key="um_page")
    try:
        msgs = get_json(
            f"/api/users/{uid}/messages",
            {"page": int(msg_page), "limit": 50},
            base_url=base,
            auth_token=auth_token,
        )
    except AuthenticationError:
        raise
    except (httpx.HTTPError, ValueError) as e:
        st.error(f"No se pudieron cargar mensajes: {e}")
        return
    mitems = msgs.get("items") or []
    if not mitems:
        st.info("Sin mensajes en esta página.")
        return
    mdf = pd.DataFrame(mitems)
    if "created_at" in mdf.columns:
        mdf = mdf.sort_values("created_at")
        mdf["created_at"] = pd.to_datetime(mdf["created_at"], utc=True, errors="coerce")
    st.dataframe(
        mdf,
        width="stretch",
        hide_index=True,
        column_config={
            "role": st.column_config.TextColumn("Rol", width="small"),
            "content": st.column_config.TextColumn("Mensaje", width="large"),
            "created_at": st.column_config.DatetimeColumn("Fecha", format="dd/MM/yyyy HH:mm"),
        },
    )


def _prepare_feed_dataframe(items: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(items)
    if df.empty:
        return df
    for col in ("id", "user_id"):
        if col in df.columns:
            df[col] = df[col].astype(str).str[:8] + "…"
    preferred = [
        "created_at",
        "user_name",
        "user_whatsapp",
        "role",
        "content",
        "user_id",
        "id",
    ]
    cols = [c for c in preferred if c in df.columns]
    rest = [c for c in df.columns if c not in cols]
    return df[cols + rest]


def tab_tenant_feed(base: str, tenant_id: str | None, auth_token: str) -> None:
    st.markdown('<p class="dashboard-title">Feed de mensajes</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="dashboard-sub">Historial del tenant (todos los usuarios).</p>',
        unsafe_allow_html=True,
    )
    if not tenant_id:
        st.warning("No hay tenant resuelto. Revisa el API `/api/tenants`.")
        return

    f1, f2, f3 = st.columns(3)
    with f1:
        role = st.selectbox("Rol", ["(todos)", "user", "assistant", "system", "tool"], key="tf_role")
    with f2:
        page = st.number_input("Página", min_value=1, value=1, key="tf_page")
    with f3:
        limit = st.number_input("Por página", min_value=1, max_value=100, value=50, key="tf_limit")

    user_filter = st.text_input("Filtrar por user_id (UUID completo)", "", key="tf_uid").strip()
    use_since = st.checkbox("Solo desde fecha", key="tf_use_since")
    created_since = None
    if use_since:
        d = st.date_input("Desde", value=date.today().replace(day=1), key="tf_since")
        created_since = d.isoformat()

    params: dict = {"page": int(page), "limit": int(limit)}
    if role != "(todos)":
        params["role"] = role
    if user_filter:
        params["user_id"] = user_filter
    if created_since:
        params["created_since"] = created_since

    try:
        data = get_json(f"/api/tenants/{tenant_id}/messages", params, base_url=base, auth_token=auth_token)
    except AuthenticationError:
        raise
    except (httpx.HTTPError, ValueError) as e:
        st.error(f"Error al cargar mensajes: {e}")
        return

    items = data.get("items") or []
    total = data.get("total", 0)
    st.caption(f"**{total}** mensajes en total (esta vista: página **{data.get('page', page)}**)")

    if not items:
        st.info("Sin resultados.")
        return
    df = _prepare_feed_dataframe(items)
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "created_at": st.column_config.DatetimeColumn("Fecha", format="dd/MM/yyyy HH:mm", width="small"),
            "user_name": st.column_config.TextColumn("Usuario", width="small"),
            "user_whatsapp": st.column_config.TextColumn("WhatsApp", width="medium"),
            "role": st.column_config.TextColumn("Rol", width="small"),
            "content": st.column_config.TextColumn("Mensaje", width="large"),
            "user_id": st.column_config.TextColumn("User id", width="small"),
            "id": st.column_config.TextColumn("Msg id", width="small"),
        },
    )


def main() -> None:
    _inject_styles()
    base = _sidebar_base_url()
    if not _render_login(base):
        st.stop()

    auth_token = _auth_token()
    if not auth_token:
        st.stop()

    _render_session_controls()
    try:
        tenant_id = _resolve_tenant_id(base, auth_token)

        tab1, tab2, tab3 = st.tabs(["Resumen", "Usuarios", "Feed"])
        with tab1:
            tab_overview(base, tenant_id, auth_token)
        with tab2:
            tab_users(base, tenant_id, auth_token)
        with tab3:
            tab_tenant_feed(base, tenant_id, auth_token)
    except AuthenticationError:
        _clear_auth_session()
        st.warning("La sesión expiró. Volvé a iniciar sesión.")
        st.stop()


if __name__ == "__main__":
    main()
