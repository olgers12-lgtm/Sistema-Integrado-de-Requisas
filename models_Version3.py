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