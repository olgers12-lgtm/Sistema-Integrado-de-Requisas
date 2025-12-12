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