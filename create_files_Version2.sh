#!/usr/bin/env bash
set -e
echo "Creando archivos del proyecto..."

cat > README.md <<'EOF'
# Sistema de Requisas para Bodega (Streamlit + Python)

Descripción
- Aplicación web para gestionar requisiciones de consumibles y repuestos.
- Roles: supervisor (solicita), warehouse/bodega (aprueba/despacha), admin (gestión).
- Registra petición, aprobación/rechazo, cantidades, máquina, área, código de requisición, fechas y auditoría de acciones.

Contenido del repo
- app.py                -> Interfaz Streamlit
- models.py             -> Modelos SQLAlchemy
- db.py                 -> Conexión y helper de sesión
- utils.py              -> Lógica de negocio (crear/aprobar requisición, códigos, password)
- alembic/              -> Config Alembic para migraciones
- Dockerfile, docker-compose.yml
- tests/                -> Tests básicos con pytest
- .github/workflows/ci.yml -> CI GitHub Actions
- .env.example
- requirements.txt

Requisitos
- Python 3.10+
- Docker (opcional)
- Streamlit, SQLAlchemy, Alembic (instaladas vía requirements.txt)

Ejecución local (sin docker)
1. python -m venv .venv
2. source .venv/bin/activate
3. pip install -r requirements.txt
4. cp .env.example .env  (editar si deseas)
5. streamlit run app.py

Ejecución con Docker (Postgres)
1. cp .env.example .env (editar DATABASE_URL si deseas)
2. docker-compose up --build
3. Acceder a http://localhost:8501

Migraciones (Alembic)
- Configuración lista en /alembic
- Inicializar y crear migraciones:
  alembic revision --autogenerate -m "initial"
  alembic upgrade head

Despliegue
- Streamlit Community Cloud (conectar repo) — usar SQLite para demo o Postgres con variables
- Docker en VPS, Heroku (Procfile incluido), AWS ECS, etc.

Próximos pasos recomendados
- Integrar autenticación OAuth (GitHub/SSO) y RBAC robusto
- Añadir pruebas E2E de UI
- Ajustes de seguridad y logging (auditoría inmutable si es requerido)
- Revisión de concurrencia/locking según DB de producción
EOF

cat > requirements.txt <<'EOF'
streamlit==1.22.0
SQLAlchemy==1.4.53
alembic==1.11.1
pydantic==1.10.12
bcrypt==4.0.1
python-dotenv==1.0.0
pandas==2.2.3
gunicorn==20.1.0
psycopg2-binary==2.9.7
pytest==7.4.0
EOF

cat > db.py <<'EOF'
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import os

DB_URL = os.getenv("DATABASE_URL", "sqlite:///./requisas.db")

# Para SQLite necesitamos check_same_thread=False
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}

engine = create_engine(DB_URL, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
EOF

cat > models.py <<'EOF'
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Enum, Float
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class RoleEnum(str, enum.Enum):
    supervisor = "supervisor"
    warehouse = "warehouse"
    admin = "admin"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String)
    hashed_password = Column(String, nullable=True)
    role = Column(Enum(RoleEnum), default=RoleEnum.supervisor)

    requisitions = relationship("Requisition", back_populates="requester")
    approvals = relationship("Approval", back_populates="approver")

class Area(Base):
    __tablename__ = "areas"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    machines = relationship("Machine", back_populates="area")

class Machine(Base):
    __tablename__ = "machines"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    area_id = Column(Integer, ForeignKey("areas.id"))
    area = relationship("Area", back_populates="machines")

class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=False)
    stock = Column(Float, default=0.0)
    unit = Column(String, default="un")

class RequisitionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    partially_approved = "partially_approved"
    cancelled = "cancelled"

class Requisition(Base):
    __tablename__ = "requisitions"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    requester_id = Column(Integer, ForeignKey("users.id"))
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=True)
    status = Column(Enum(RequisitionStatus), default=RequisitionStatus.pending)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    note = Column(Text)

    requester = relationship("User", back_populates="requisitions")
    items = relationship("RequisitionItem", back_populates="requisition", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="requisition", cascade="all, delete-orphan")

class RequisitionItem(Base):
    __tablename__ = "requisition_items"
    id = Column(Integer, primary_key=True, index=True)
    requisition_id = Column(Integer, ForeignKey("requisitions.id"))
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"))
    qty_requested = Column(Float, nullable=False)
    qty_approved = Column(Float, nullable=True)

    requisition = relationship("Requisition", back_populates="items")
    inventory_item = relationship("InventoryItem")

class Approval(Base):
    __tablename__ = "approvals"
    id = Column(Integer, primary_key=True, index=True)
    requisition_id = Column(Integer, ForeignKey("requisitions.id"))
    approver_id = Column(Integer, ForeignKey("users.id"))
    approved = Column(Boolean, nullable=False)
    comment = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    requisition = relationship("Requisition", back_populates="approvals")
    approver = relationship("User", back_populates="approvals")
EOF

cat > utils.py <<'EOF'
from sqlalchemy.orm import Session
from models import (
    User, Machine, Area, InventoryItem,
    Requisition, RequisitionItem, Approval, RequisitionStatus
)
from datetime import datetime, date
from sqlalchemy import func, and_
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def generate_requisition_code(db: Session):
    today_str = date.today().strftime("%Y%m%d")
    # Contar requisiciones del día (compatible con SQLite y Postgres vía date range)
    start = datetime.combine(date.today(), datetime.min.time())
    end = datetime.combine(date.today(), datetime.max.time())
    cnt = db.query(func.count(Requisition.id)).filter(Requisition.created_at >= start, Requisition.created_at <= end).scalar() or 0
    seq = cnt + 1
    return f"REQ-{today_str}-{seq:04d}"

def create_requisition(db: Session, requester: User, machine: Machine, area: Area, items: list, note: str = ""):
    code = generate_requisition_code(db)
    req = Requisition(
        code=code,
        requester_id=requester.id,
        machine_id=machine.id if machine else None,
        area_id=area.id if area else None,
        note=note
    )
    db.add(req)
    db.flush()  # para obtener req.id
    for it in items:
        inv = db.query(InventoryItem).filter_by(id=it["inventory_item_id"]).first()
        if not inv:
            continue
        ri = RequisitionItem(
            requisition_id=req.id,
            inventory_item_id=inv.id,
            qty_requested=it["qty"]
        )
        db.add(ri)
    db.commit()
    db.refresh(req)
    return req

def approve_requisition(db: Session, requisition: Requisition, approver: User, approved_items: dict, approved: bool, comment: str = ""):
    """
    approved_items: dict mapping requisition_item_id -> qty_approved
    If approved == False, marks requisition as rejected and records Approval row.
    """
    approval = Approval(requisition_id=requisition.id, approver_id=approver.id, approved=approved, comment=comment)
    db.add(approval)

    any_partial = False
    for ri in requisition.items:
        qty = float(approved_items.get(ri.id, 0.0))
        ri.qty_approved = qty
        if approved and qty > 0:
            inv = db.query(InventoryItem).filter_by(id=ri.inventory_item_id).with_for_update().first()
            if inv is not None:
                inv.stock = max(0.0, (inv.stock or 0.0) - qty)
        if qty < (ri.qty_requested or 0.0):
            any_partial = True

    if not approved:
        requisition.status = RequisitionStatus.rejected
    else:
        requisition.status = RequisitionStatus.partially_approved if any_partial else RequisitionStatus.approved

    requisition.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(requisition)
    return requisition
EOF

cat > app.py <<'EOF'
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
EOF

cat > Dockerfile <<'EOF'
# Imagen base
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema (si se necesita psycopg2)
RUN apt-get update && apt-get install -y build-essential libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
EOF

cat > docker-compose.yml <<'EOF'
version: "3.8"
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: requisas
    volumes:
      - db-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  web:
    build: .
    depends_on:
      - db
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db:5432/requisas
    ports:
      - "8501:8501"
    volumes:
      - .:/app
    command: ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]

volumes:
  db-data:
EOF

mkdir -p alembic
cat > alembic.ini <<'EOF'
[alembic]
script_location = alembic

sqlalchemy.url = driver://user:pass@localhost/dbname
EOF

cat > alembic/env.py <<'EOF'
from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
fileConfig(config.config_file_name)

# Import models metadata
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from models import Base  # noqa

target_metadata = Base.metadata

def get_url():
    return os.getenv("DATABASE_URL", "sqlite:///./requisas.db")

def run_migrations_offline():
    url = get_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = get_url()
    connectable = engine_from_config(configuration, prefix='sqlalchemy.', poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
EOF

cat > .env.example <<'EOF'
# Ejemplo de variables de entorno
# Para Postgres:
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/requisas
DATABASE_URL=sqlite:///./requisas.db
SECRET_KEY=replace-with-secure-key
EOF

mkdir -p .github/workflows
cat > .github/workflows/ci.yml <<'EOF'
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run tests
        run: |
          pytest -q
EOF

cat > Procfile <<'EOF'
web: streamlit run app.py --server.port $PORT --server.address 0.0.0.0
EOF

cat > .gitignore <<'EOF'
__pycache__/
*.pyc
.venv/
.env
requisas.db
*.sqlite3
instance/
.vscode/
.idea/
*.egg-info/
dist/
build/
EOF

cat > Makefile <<'EOF'
.PHONY: run docker-up test migrate

run:
	python -m venv .venv || true
	. .venv/bin/activate && pip install -r requirements.txt
	streamlit run app.py

docker-up:
	docker-compose up --build

test:
	pytest -q

migrate-init:
	alembic revision --autogenerate -m "initial" || true
	alembic upgrade head
EOF

mkdir -p tests
cat > tests/test_basic.py <<'EOF'
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest
from models import Base, User, Area, InventoryItem
import utils
from db import get_session

# Usaremos una DB sqlite en memoria para tests
@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        # Seed básico
        u = User(username="sup", full_name="Sup", hashed_password=utils.hash_password("pass"), role="supervisor")
        a = Area(code="A1", name="Area 1")
        i = InventoryItem(sku="SKU-1", description="Item 1", stock=10)
        session.add_all([u, a, i])
        session.commit()
        yield session
    finally:
        session.close()

def test_create_and_approve(db_session):
    db = db_session
    user = db.query(User).filter_by(username="sup").first()
    area = db.query(Area).first()
    item = db.query(InventoryItem).first()

    # Crear requisición
    req = utils.create_requisition(db, requester=user, machine=None, area=area, items=[{"inventory_item_id": item.id, "qty": 3}], note="Test")
    assert req.code.startswith("REQ-")
    assert len(req.items) == 1

    # Aprobar
    approved = {req.items[0].id: 2.0}
    utils.approve_requisition(db, requisition=req, approver=user, approved_items=approved, approved=True, comment="OK")
    db.refresh(req)
    assert req.status.name in ("approved", "partially_approved") or req.status.value in ("approved", "partially_approved")
    db.refresh(item)
    assert item.stock == 8.0 or item.stock == pytest.approx(8.0)
EOF

echo "Archivos creados. Revisa, commitea y pushea manualmente:"
echo "  git add ."
echo "  git commit -m \"Initial commit: Streamlit requisitions app with DB, Docker, Alembic, CI, tests\""
echo "  git push origin main"
echo "Listo."