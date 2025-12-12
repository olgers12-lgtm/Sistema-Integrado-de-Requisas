import streamlit as st
from db import engine, get_session
from models import Base, User, Area, Machine, InventoryItem, Requisition, RequisitionItem, RoleEnum
import utils
import pandas as pd
import os

# Inicializar DB (solo demo - para producción usar Alembic/migrations)
def init_db():
    Base.metadata.create_all(bind=engine)
    with get_session() as db:
        if db.query(User).count() == 0:
            u1 = User(username="supervisor1", full_name="Supervisor Uno", hashed_password=utils.hash_password("pass"), role=RoleEnum.supervisor)
            u2 = User(username="bodega1", full_name="Bodega Uno", hashed_password=utils.hash_password("pass"), role=RoleEnum.warehouse)
            admin = User(username="admin", full_name="Admin", hashed_password=utils.hash_password("pass"), role=RoleEnum.admin)
            db.add_all([u1, u2, admin])
        if db.query(Area).count() == 0:
            a1 = Area(code="A1", name="Area A")
            a2 = Area(code="A2", name="Area B")
            db.add_all([a1, a2])
        if db.query(Machine).count() == 0:
            m1 = Machine(code="MACH-001", name="Corte 1", area_id=1)
            m2 = Machine(code="MACH-002", name="Taladro 1", area_id=2)
            db.add_all([m1, m2])
        if db.query(InventoryItem).count() == 0:
            i1 = InventoryItem(sku="SKU-001", description="Filtro", stock=50, unit="un")
            i2 = InventoryItem(sku="SKU-002", description="Tornillo M8", stock=1000, unit="pcs")
            db.add_all([i1, i2])
        db.commit()

init_db()

st.set_page_config(page_title="Requisas Bodega", layout="wide")

# --- Simple login demo (para desarrollo) ---
if "user_id" not in st.session_state:
    st.session_state.user_id = None

def login_form():
    st.sidebar.title("Iniciar sesión (demo)")
    username = st.sidebar.text_input("Usuario")
    password = st.sidebar.text_input("Contraseña", type="password")
    if st.sidebar.button("Entrar"):
        with get_session() as db:
            user = db.query(User).filter_by(username=username).first()
            if user and utils.verify_password(password, user.hashed_password):
                st.session_state.user_id = user.id
                st.experimental_rerun()
            else:
                st.sidebar.error("Credenciales inválidas")

def logout():
    st.session_state.user_id = None
    st.experimental_rerun()

if not st.session_state.user_id:
    login_form()
    st.title("Sistema de Requisas para Bodega - Demo")
    st.markdown("Usuarios demo: supervisor1 / bodega1 / admin  — contraseña: pass")
    st.stop()

# Cargar usuario
with get_session() as db:
    user = db.query(User).get(st.session_state.user_id)

st.sidebar.write(f"Conectado: {user.full_name} ({user.role.value})")
if st.sidebar.button("Cerrar sesión"):
    logout()

# Navegación
if user.role == RoleEnum.supervisor:
    pages = ["Nueva requisición", "Mis requisiciones", "Historial"]
elif user.role == RoleEnum.warehouse:
    pages = ["Pendientes por aprobar", "Historial"]
else:
    pages = ["Nueva requisición", "Pendientes por aprobar", "Inventario", "Usuarios", "Historial"]

page = st.sidebar.radio("Menú", pages)

def load_options(db):
    areas = db.query(Area).all()
    machines = db.query(Machine).all()
    inventory = db.query(InventoryItem).all()
    return areas, machines, inventory

# Página: Nueva requisición
if page == "Nueva requisición":
    st.header("Crear nueva requisición")
    with get_session() as db:
        areas, machines, inventory = load_options(db)
        col1, col2 = st.columns(2)
        with col1:
            area_sel = st.selectbox("Área", options=areas, format_func=lambda a: f"{a.code} - {a.name}")
            machine_sel = st.selectbox("Máquina (opcional)", options=[None] + machines, format_func=lambda m: f"{m.code} - {m.name}" if m else "Ninguna")
            note = st.text_area("Nota (máquina, motivo, prioridad)")
        with col2:
            st.markdown("Selecciona ítems y cantidades")
            items_to_add = []
            for inv in inventory:
                qty = st.number_input(f"{inv.sku} - {inv.description} (stock: {inv.stock})", min_value=0.0, step=1.0, key=f"qty_{inv.id}")
                if qty > 0:
                    items_to_add.append({"inventory_item_id": inv.id, "qty": qty})
        if st.button("Enviar requisición"):
            if len(items_to_add) == 0:
                st.warning("Agrega al menos un ítem con cantidad mayor que 0")
            else:
                req = utils.create_requisition(db, requester=user, machine=machine_sel, area=area_sel, items=items_to_add, note=note)
                st.success(f"Requisición creada: {req.code}")
                st.experimental_rerun()

# Página: Mis requisiciones
if page == "Mis requisiciones":
    st.header("Mis requisiciones")
    with get_session() as db:
        rows = db.query(Requisition).filter_by(requester_id=user.id).order_by(Requisition.created_at.desc()).all()
        for r in rows:
            st.subheader(f"{r.code} - {r.status.value}")
            st.write(f"Fecha: {r.created_at} - Máquina: {getattr(r.machine,'name',None)} - Área: {getattr(r.area,'name',None)}")
            for it in r.items:
                st.write(f"- {it.inventory_item.sku} | {it.inventory_item.description} | solicitado: {it.qty_requested} | aprobado: {it.qty_approved}")
            st.write("-----")

# Página: Pendientes por aprobar
if page == "Pendientes por aprobar":
    st.header("Requisiciones pendientes")
    with get_session() as db:
        pending = db.query(Requisition).filter(Requisition.status == "pending").order_by(Requisition.created_at).all()
        for r in pending:
            st.subheader(f"{r.code} - Solicitante: {r.requester.full_name}")
            st.write(f"Fecha: {r.created_at} - Área: {getattr(r.area,'name',None)} - Máquina: {getattr(r.machine,'name',None)}")
            approved_items = {}
            cols = st.columns(2)
            with cols[0]:
                st.markdown("Ítems")
                for it in r.items:
                    max_stock = float(it.inventory_item.stock or 0.0)
                    qty = st.number_input(f"Apr: {it.inventory_item.sku} - {it.inventory_item.description} (solic: {it.qty_requested}, stock: {max_stock})",
                                          min_value=0.0, max_value=max_stock, value=float(it.qty_requested), key=f"apr_{it.id}")
                    approved_items[it.id] = qty
            with cols[1]:
                comment = st.text_area("Comentario de aprobación", key=f"comment_{r.id}")
                if st.button("Aprobar requisición", key=f"app_{r.id}"):
                    utils.approve_requisition(db, requisition=r, approver=user, approved_items=approved_items, approved=True, comment=comment)
                    st.success(f"Aprobada {r.code}")
                    st.experimental_rerun()
                if st.button("Rechazar requisición", key=f"rej_{r.id}"):
                    utils.approve_requisition(db, requisition=r, approver=user, approved_items={}, approved=False, comment=comment)
                    st.warning(f"Rechazada {r.code}")
                    st.experimental_rerun()

if page == "Inventario":
    st.header("Inventario")
    with get_session() as db:
        inventory = db.query(InventoryItem).all()
        df = pd.DataFrame([{"sku": i.sku, "description": i.description, "stock": i.stock, "unit": i.unit} for i in inventory])
        st.dataframe(df)

if page == "Usuarios":
    st.header("Usuarios (admin)")
    with get_session() as db:
        users = db.query(User).all()
        for u in users:
            st.write(f"- {u.username} | {u.full_name} | {u.role.value}")

if page == "Historial":
    st.header("Historial y export")
    with get_session() as db:
        reqs = db.query(Requisition).order_by(Requisition.created_at.desc()).limit(500).all()
        rows = []
        for r in reqs:
            for it in r.items:
                rows.append({
                    "code": r.code,
                    "requester": r.requester.username,
                    "area": getattr(r.area, "name", None),
                    "machine": getattr(r.machine, "name", None),
                    "item_sku": it.inventory_item.sku,
                    "item_desc": it.inventory_item.description,
                    "qty_requested": it.qty_requested,
                    "qty_approved": it.qty_approved,
                    "status": r.status.value,
                    "created_at": r.created_at
                })
        df = pd.DataFrame(rows)
        st.dataframe(df)
        st.download_button("Exportar CSV", df.to_csv(index=False).encode("utf-8"), file_name="requisas_hist.csv")