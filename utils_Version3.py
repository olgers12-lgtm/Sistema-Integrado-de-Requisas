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