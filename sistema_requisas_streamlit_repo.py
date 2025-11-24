# Repo: sistema_requisas_streamlit
# Estructura del repo (archivos incluidos en este único documento):
#
# ├── README.md
# ├── requirements.txt
# ├── app.py
# ├── pages/
# │    ├── __init__.py
# │    ├── 1_solicitar.py
# │    ├── 2_aprobar.py
# │    ├── 3_historico.py
# │    └── 4_kpis.py
# └── utils/
#      ├── __init__.py
#      ├── db.py
#      ├── security.py
#      └── helpers.py
#
# ------------------------
# --- README.md
# ------------------------

"""
SISTEMA DE REQUISAS PARA BODEGA
Streamlit + Python + SQLite

Instrucciones rápidas:
1. Crear un entorno virtual: python -m venv .venv
2. Activarlo: source .venv/bin/activate  (Linux/Mac) o .\.venv\Scripts\activate (Windows)
3. Instalar dependencias: pip install -r requirements.txt
4. Inicializar DB: python -c "from utils.db import create_tables; create_tables()"
5. Correr la app: streamlit run app.py

Descripción: App para solicitar consumibles y repuestos desde supervisores y aprobación por parte de bodega.
"""

# ------------------------
# --- requirements.txt
# ------------------------

# contenido del archivo requirements.txt
# streamlit  
# pandas
# plotly
# openpyxl


# ------------------------
# --- app.py (launcher + navegación)
# ------------------------

from pathlib import Path
import streamlit as st
from utils.db import create_tables
from utils.security import authenticate_user, current_user, logout

# Inicializar DB si no existe
create_tables()

st.set_page_config(page_title="Sistema de Requisas - Bodega", layout="wide")

st.title("Sistema de Requisas para Bodega")

# --- Simple autenticación demo ---
if 'auth' not in st.session_state:
    st.session_state['auth'] = False

if not st.session_state['auth']:
    st.sidebar.subheader("Iniciar sesión")
    user = st.sidebar.text_input("Usuario")
    pwd = st.sidebar.text_input("Contraseña", type='password')
    if st.sidebar.button("Entrar"):
        ok = authenticate_user(user, pwd)
        if ok:
            st.session_state['auth'] = True
            st.experimental_rerun()
        else:
            st.sidebar.error("Usuario o contraseña incorrectos")
    st.sidebar.info("Usa: supervisor1 / sup123  o  bodega1 / bod123")
    st.stop()
else:
    st.sidebar.write(f"Conectado como: {current_user()['username']} ({current_user()['role']})")
    if st.sidebar.button("Cerrar sesión"):
        logout()
        st.session_state['auth'] = False
        st.experimental_rerun()

# Navegación
pages = {
    "Solicitar": "pages/1_solicitar.py",
    "Aprobar": "pages/2_aprobar.py",
    "Histórico": "pages/3_historico.py",
    "KPIs": "pages/4_kpis.py"
}

choice = st.sidebar.selectbox("Navegación", list(pages.keys()))

# Ejecutar la página seleccionada
page_path = Path(pages[choice])
with open(page_path, "r", encoding="utf-8") as f:
    code = compile(f.read(), str(page_path), 'exec')
    exec(code, globals())


# ------------------------
# --- pages/__init__.py
# ------------------------

# vacío (permite import como paquete)


# ------------------------
# --- pages/1_solicitar.py
# ------------------------

import streamlit as st
from utils.db import nueva_requisicion, listar_items, get_stock
from utils.helpers import generar_codigo_maquina
from utils.security import current_user

st.header("Nueva requisición")
user = current_user()

with st.form("form_solicitud"):
    supervisor = st.text_input("Supervisor", value=user['username'])
    area = st.selectbox("Área", ["Producción", "Mantenimiento", "Calidad", "Administración"]) 
    maquina = st.text_input("Código de máquina", value=generar_codigo_maquina())
    item = st.selectbox("Item", listar_items())
    cantidad = st.number_input("Cantidad", min_value=1, value=1)
    comentarios = st.text_area("Comentarios (opcional)")
    submitted = st.form_submit_button("Enviar requisición")

if submitted:
    req_id = nueva_requisicion(supervisor, area, maquina, item, int(cantidad), comentarios)
    st.success(f"Requisición creada: {req_id}")
    st.info("Se registró como PENDIENTE. Bodega deberá aprobarla.")

# Mostrar stock actual (opcional)
st.subheader("Stock (consulta rápida)")
stock_df = get_stock()
st.dataframe(stock_df)


# ------------------------
# --- pages/2_aprobar.py
# ------------------------

import streamlit as st
from utils.db import listar_pendientes, aprobar_requisicion, rechazar_requisicion
from utils.security import current_user

st.header("Panel de Aprobación - Bodega")
user = current_user()
if user['role'] != 'bodega':
    st.warning("Acceso restringido. Solo personal de bodega puede aprobar/rechazar.")
    st.stop()

pendientes = listar_pendientes()
if pendientes.empty:
    st.info("No hay requisiciones pendientes.")
else:
    for _, row in pendientes.iterrows():
        with st.expander(f"{row.req_id} - {row.item} ({row.cantidad})"):
            st.write(f"Supervisor: {row.supervisor}")
            st.write(f"Área: {row.area} — Máquina: {row.maquina}")
            st.write(f"Comentarios: {row.comentarios}")
            col1, col2 = st.columns(2)
            if col1.button(f"Aprobar {row.req_id}", key=f"apr_{row.req_id}"):
                aprobar_requisicion(row.req_id, user['username'])
                st.success("Aprobado")
                st.experimental_rerun()
            if col2.button(f"Rechazar {row.req_id}", key=f"rej_{row.req_id}"):
                rechazar_requisicion(row.req_id, user['username'])
                st.error("Rechazado")
                st.experimental_rerun()


# ------------------------
# --- pages/3_historico.py
# ------------------------

import streamlit as st
from utils.db import listar_todos, exportar_excel

st.header("Histórico de requisiciones")

col1, col2 = st.columns([3,1])
with col1:
    df = listar_todos()
    filtros_area = st.multiselect("Filtrar por área", options=df['area'].unique())
    if filtros_area:
        df = df[df['area'].isin(filtros_area)]
    st.dataframe(df)

with col2:
    if st.button("Exportar a Excel"):
        path = exportar_excel()
        st.success(f"Archivo generado: {path}")


# ------------------------
# --- pages/4_kpis.py
# ------------------------

import streamlit as st
import pandas as pd
import plotly.express as px
from utils.db import listar_todos

st.header("KPIs de Requisas")
df = listar_todos()

st.subheader("Tiempo promedio de aprobación")
if df.empty:
    st.info("No hay datos aún")
else:
    df['fecha_solicitud'] = pd.to_datetime(df['fecha_solicitud'])
    df['fecha_aprobacion'] = pd.to_datetime(df['fecha_aprobacion'], errors='coerce')
    df['tiempo_hrs'] = (df['fecha_aprobacion'] - df['fecha_solicitud']).dt.total_seconds() / 3600
    avg = df[df['estado']=='Aprobado']['tiempo_hrs'].mean()
    st.metric("Promedio horas hasta aprobación", f"{avg:.2f}" if not pd.isna(avg) else "-")

st.subheader("Top items solicitados")
if not df.empty:
    top = df.groupby('item').cantidad.sum().reset_index().sort_values('cantidad', ascending=False).head(10)
    fig = px.bar(top, x='item', y='cantidad', title='Top 10 Items')
    st.plotly_chart(fig, use_container_width=True)


# ------------------------
# --- utils/__init__.py
# ------------------------

# vacío


# ------------------------
# --- utils/db.py
# ------------------------

import sqlite3
from datetime import datetime
import uuid
import pandas as pd
from pathlib import Path

DB_PATH = Path("data/requisiciones.db")

def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS requisiciones (
        req_id TEXT PRIMARY KEY,
        supervisor TEXT,
        area TEXT,
        maquina TEXT,
        item TEXT,
        cantidad INTEGER,
        fecha_solicitud TEXT,
        estado TEXT,
        aprobado_por TEXT,
        fecha_aprobacion TEXT,
        comentarios TEXT
    );
    ''')
    # tabla de stock simple (demo)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS stock (
        item TEXT PRIMARY KEY,
        cantidad INTEGER
    );
    ''')
    # poblar stock demo si vacía
    cur.execute("SELECT count(1) as c FROM stock")
    if cur.fetchone()['c'] == 0:
        demo = [
            ("Tornillo M6", 500),
            ("Arandela 6mm", 1000),
            ("Lubricante 1L", 50),
            ("Filtro 123", 20),
            ("Soldadura 250g", 40)
        ]
        cur.executemany("INSERT INTO stock(item, cantidad) VALUES (?,?)", demo)
    conn.commit()
    conn.close()

# CRUD

def nueva_requisicion(supervisor, area, maquina, item, cantidad, comentarios=""):
    conn = get_connection()
    cur = conn.cursor()
    req_id = str(uuid.uuid4())[:8]
    fecha = datetime.now().isoformat()
    cur.execute("INSERT INTO requisiciones VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
        req_id, supervisor, area, maquina, item, cantidad, fecha, 'Pendiente', '', '', comentarios
    ))
    conn.commit()
    conn.close()
    return req_id

def listar_pendientes():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM requisiciones WHERE estado='Pendiente' ORDER BY fecha_solicitud DESC", conn)
    conn.close()
    return df

def listar_todos():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM requisiciones ORDER BY fecha_solicitud DESC", conn)
    conn.close()
    return df

def aprobar_requisicion(req_id, aprobador):
    conn = get_connection()
    cur = conn.cursor()
    fecha = datetime.now().isoformat()
    cur.execute("UPDATE requisiciones SET estado='Aprobado', aprobado_por=?, fecha_aprobacion=? WHERE req_id=?", (aprobador, fecha, req_id))
    conn.commit()
    conn.close()

def rechazar_requisicion(req_id, aprobador):
    conn = get_connection()
    cur = conn.cursor()
    fecha = datetime.now().isoformat()
    cur.execute("UPDATE requisiciones SET estado='Rechazado', aprobado_por=?, fecha_aprobacion=? WHERE req_id=?", (aprobador, fecha, req_id))
    conn.commit()
    conn.close()

# helpers para UI
def listar_items():
    conn = get_connection()
    df = pd.read_sql_query("SELECT item FROM stock ORDER BY item", conn)
    conn.close()
    return df['item'].tolist()

def get_stock():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM stock ORDER BY item", conn)
    conn.close()
    return df

def exportar_excel():
    df = listar_todos()
    path = Path("exports")
    path.mkdir(exist_ok=True)
    fn = path / f"requisiciones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(fn, index=False)
    return str(fn)


# ------------------------
# --- utils/security.py
# ------------------------

# Demo simple de usuarios (NO usar en producción tal cual)
USUARIOS = {
    'supervisor1': {'password': 'sup123', 'role': 'supervisor'},
    'bodega1': {'password': 'bod123', 'role': 'bodega'},
    'supervisor2': {'password': 'sup456', 'role': 'supervisor'}
}

import streamlit as st

def authenticate_user(username, password):
    u = USUARIOS.get(username)
    if u and u['password'] == password:
        st.session_state['user'] = {'username': username, 'role': u['role']}
        return True
    return False

def current_user():
    return st.session_state.get('user', {'username': 'anon', 'role': 'anon'})

def logout():
    if 'user' in st.session_state:
        del st.session_state['user']


# ------------------------
# --- utils/helpers.py
# ------------------------

import random

def generar_codigo_maquina():
    # función simple para generar un código de máquina demo
    return f"M-{random.randint(100,999)}"


# ------------------------
# FIN DEL DOCUMENTO
# ------------------------

# ------------------------
# --- .gitignore
# ------------------------

"""
# Entorno virtual\ n.venv/\ nvenv/\ n__pycache__/\ n*.pyc\ n# Archivos temporales\ n.DS_Store\ n# SQLite DB\ n*.db\ n"""


# ------------------------
# --- LICENSE (MIT)
# ------------------------

MIT License

Copyright (c) 2025 Sebastián Guerrero Mora

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

(The full MIT license text - include in your repo LICENSE file.)

# ------------------------
# --- requirements.txt
# ------------------------

streamlit
pandas
plotly
openpyxl

# ------------------------
# --- .github/workflows/ci.yml
# ------------------------

# GitHub Actions CI: instala dependencias y corre lint/test básicos
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build:
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
      - name: Run a quick streamlit check
        run: |
          python -c "import streamlit; print('streamlit', streamlit.__version__)"

# ------------------------
# --- Procfile (opcional para deploy)
# ------------------------

web: streamlit run app.py --server.port $PORT

# ------------------------
# --- runtime.txt (Heroku style)
# ------------------------

python-3.10.12

# ------------------------
# --- README: instrucciones rápidas (ya en canvas)
# ------------------------

# Cómo subir a GitHub (pasos rápidos):

1. Crea un repositorio nuevo en GitHub (sin README). Copia la URL.
2. En tu máquina local, inicializa git y sube:

```bash
git init
git add .
git commit -m "Initial commit - Sistema de Requisas"
git branch -M main
git remote add origin <URL_DEL_REPO>
git push -u origin main
```

3. Habilita GitHub Actions -> CI correrá en main.

# Deploy en Streamlit Cloud (opción rápida):

1. En streamlit.io -> Inicia sesión -> New app -> conecta con tu repo en GitHub -> selecciona rama `main` y `app.py` como entrypoint -> Deploy.
2. Streamlit Cloud instalará `requirements.txt` y levantará la app.

# Deploy en Railway/Heroku (opcional):

- Railway: crea un proyecto, conecta tu repo, configura `Procfile` y `runtime.txt`.
- Heroku: similar; recuerda configurar variable `PORT` si es necesario.


# ------------------------
# FIN - Archivos añadidos
# ------------------------

