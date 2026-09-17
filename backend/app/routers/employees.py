import secrets
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..auth import get_current_user, require_hr, hash_password

router = APIRouter(prefix="/api/employees", tags=["employees"])


def serialize(e: models.Employee, db: Session):
    user = db.query(models.User).filter(models.User.employee_id == e.id).first()
    return {
        "id": e.id,
        "name": e.name,
        "dept": e.dept,
        "designation": e.designation or "",
        "email": e.email,
        "phone": e.phone or "",
        "location": e.location or "",
        "color": e.color,
        "joined": e.joined,
        "isActive": e.is_active,
        "role": user.role if user else None,
        "hasLogin": user is not None,
    }


@router.get("")
def list_employees(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [serialize(e, db) for e in db.query(models.Employee).all()]


@router.get("/me")
def get_own_profile(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Return the authenticated user's own employee profile."""
    if not user.employee_id:
        raise HTTPException(status_code=404, detail="No employee profile linked to this account")
    employee = db.query(models.Employee).filter(models.Employee.id == user.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return serialize(employee, db)


@router.post("")
def create_employee(payload: schemas.EmployeeCreateIn, db: Session = Depends(get_db), user=Depends(require_hr)):
    if db.query(models.Employee).filter(models.Employee.email == payload.email).first():
        raise HTTPException(status_code=400, detail="An employee with this email already exists")
    if payload.createLogin and db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="A login account with this email already exists")

    palette = ["#8B5CF6", "#06B6D4", "#F59E0B", "#FB7185", "#10B981", "#4F46E5"]
    color = payload.color or palette[db.query(models.Employee).count() % len(palette)]

    employee = models.Employee(
        name=payload.name, dept=payload.dept, designation=payload.designation or "",
        email=payload.email, phone=payload.phone or "", location=payload.location or "",
        color=color,
        joined=date.today().isoformat(), is_active=True,
    )
    db.add(employee)
    db.flush()

    temp_password = None
    if payload.createLogin:
        temp_password = payload.password or secrets.token_urlsafe(9)
        VALID_ROLES = {"employee", "manager", "hr", "hr_manager", "chro", "vp", "cto", "ceo", "system_admin", "admin"}
        login_role = payload.role if payload.role in VALID_ROLES else "employee"
        db.add(models.User(
            name=payload.name, email=payload.email,
            password_hash=hash_password(temp_password),
            role=login_role, employee_id=employee.id,
        ))

    db.commit()
    db.refresh(employee)
    return {
        "employee": serialize(employee, db),
        "temporaryPassword": temp_password,
    }


@router.patch("/me")
def update_own_profile(name: str = None, dept: str = None, designation: str = None,
                       phone: str = None, location: str = None,
                       db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Allow any authenticated user to update their own employee profile fields."""
    if not user.employee_id:
        raise HTTPException(status_code=400, detail="No employee profile linked to this account")
    employee = db.query(models.Employee).filter(models.Employee.id == user.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    if name is not None:
        employee.name = name
        user.name = name
    if dept is not None:
        employee.dept = dept
    if designation is not None:
        employee.designation = designation
    if phone is not None:
        employee.phone = phone
    if location is not None:
        employee.location = location
    db.commit()
    db.refresh(employee)
    return serialize(employee, db)


@router.patch("/me/profile")
def update_own_profile_body(payload: schemas.EmployeeUpdateIn,
                            db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Allow any authenticated user to update their own profile via JSON body."""
    if not user.employee_id:
        raise HTTPException(status_code=400, detail="No employee profile linked to this account")
    employee = db.query(models.Employee).filter(models.Employee.id == user.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    if payload.name is not None:
        employee.name = payload.name
        user.name = payload.name
    if payload.dept is not None:
        employee.dept = payload.dept
    if payload.designation is not None:
        employee.designation = payload.designation
    if payload.phone is not None:
        employee.phone = payload.phone
    if payload.location is not None:
        employee.location = payload.location
    db.commit()
    db.refresh(employee)
    return serialize(employee, db)


@router.put("/{employee_id}")
def update_employee(employee_id: str, payload: schemas.EmployeeUpdateIn,
                     db: Session = Depends(get_db), user=Depends(require_hr)):
    employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if payload.name is not None:
        employee.name = payload.name
    if payload.dept is not None:
        employee.dept = payload.dept
    if payload.designation is not None:
        employee.designation = payload.designation
    if payload.phone is not None:
        employee.phone = payload.phone
    if payload.location is not None:
        employee.location = payload.location
    if payload.color is not None:
        employee.color = payload.color
    if payload.isActive is not None:
        employee.is_active = payload.isActive
        # Keep the linked login account in lockstep so a deactivated employee can't sign in.
        linked_user = db.query(models.User).filter(models.User.employee_id == employee.id).first()
        if linked_user:
            linked_user.is_active = payload.isActive

    db.commit()
    db.refresh(employee)
    return serialize(employee, db)


@router.patch("/{employee_id}/role")
def change_role(employee_id: str, role: str, db: Session = Depends(get_db), user=Depends(require_hr)):
    VALID_ROLES = {"employee", "manager", "hr", "hr_manager", "chro", "vp", "cto", "ceo", "system_admin", "admin"}
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(sorted(VALID_ROLES))}")
    linked_user = db.query(models.User).filter(models.User.employee_id == employee_id).first()
    if not linked_user:
        raise HTTPException(status_code=404, detail="This employee has no login account to promote")
    linked_user.role = role
    db.commit()
    employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    return serialize(employee, db)
