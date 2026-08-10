from fastapi import APIRouter, Depends, HTTPException, Header, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import get_db
import models
from BehaviorService import BehaviorService
from typing import Dict, List, Any

router = APIRouter(prefix="/api/v1", tags=["Player Behavior & Anomaly Detection"])

# Helper function to get current admin user from Authorization header locally
def get_admin_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    from main import get_current_admin_user
    return get_current_admin_user(authorization=authorization, db=db)

# Helper function to get any authenticated user from Authorization header locally
def get_auth_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    from main import get_current_user
    try:
        return get_current_user(authorization=authorization, db=db)
    except Exception:
        return None

# ── 1. POST /api/v1/behavior/log (Internal / Gameplay Hooks) ─────────────────────
@router.post("/behavior/log")
async def log_behavior(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_auth_user)
):
    action_type = payload.get("action_type")
    location = payload.get("location")
    metadata = payload.get("metadata", {})
    
    # If authenticated, use token subject; otherwise look in payload
    player_id = current_user.id if current_user else payload.get("player_id")
    
    if not player_id:
        raise HTTPException(status_code=400, detail="Missing player_id/authentication context")
    if not action_type:
        raise HTTPException(status_code=400, detail="Missing action_type")

    # If action is score submission, verify score is present
    if action_type == "score_submission" and "score" not in metadata:
        raise HTTPException(status_code=400, detail="Missing score in metadata for score_submission")

    service = BehaviorService(db)
    try:
        log_entry = await service.log_and_analyze_behavior(
            player_id=int(player_id),
            action_type=action_type,
            location_str=location,
            metadata=metadata
        )
        return {
            "success": True,
            "log_id": log_entry.id,
            "suspicion_score": log_entry.suspicion_score,
            "reasons": log_entry.extra_metadata.get("anomaly_reasons", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to log behavior pattern: {str(e)}")

# ── 2. GET /api/v1/admin/behavior/{player_id} (Admin Only) ──────────────────────
@router.get("/admin/behavior/{player_id}")
def get_player_behavior(
    player_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user)
):
    service = BehaviorService(db)
    try:
        analysis = service.get_player_behavior_analysis(player_id)
        return analysis
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 3. GET /api/v1/admin/devices/{player_id} (Admin Only) ───────────────────────
@router.get("/admin/devices/{player_id}")
def get_player_devices(
    player_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user)
):
    service = BehaviorService(db)
    try:
        devices = service.get_devices_by_player(player_id)
        return devices
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 4. POST /api/v1/admin/devices/revoke (Admin Only) ───────────────────────────
@router.post("/admin/devices/revoke")
def revoke_device(
    payload: Dict[str, str] = Body(...),
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user)
):
    device_id = payload.get("device_id") or payload.get("fingerprint")
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id or fingerprint parameter required")
        
    device = db.query(models.DeviceFingerprint).filter(
        models.DeviceFingerprint.device_id == device_id
    ).first()
    
    if not device:
        # Create a new untrusted fingerprint if it doesn't exist yet, to block future logins
        device = models.DeviceFingerprint(
            device_id=device_id,
            device_name="Revoked Device",
            is_trusted=False,
            risk_score=100
        )
        db.add(device)
    else:
        device.is_trusted = False
        device.risk_score = 100

    # Write Audit Log
    audit = models.AuditLog(
        admin_id=admin.id,
        action="Revoke Device",
        target_id=device_id,
        reason="Admin revocation action",
        details="Device trust status set to False, risk score set to 100"
    )
    db.add(audit)
    db.commit()
    
    return {"success": True, "message": f"Device {device_id} revoked successfully"}

# ── 5. GET /api/v1/admin/suspicious-players (Admin Only) ────────────────────────
@router.get("/admin/suspicious-players")
def get_suspicious_players(
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_admin_user)
):
    # Fetch users whose trust_score < 70, worst first
    suspicious_users = db.query(models.User).filter(
        models.User.trust_score < 70
    ).order_by(models.User.trust_score).all()
    
    res = []
    for u in suspicious_users:
        res.append({
            "id": u.id,
            "fullName": u.fullName or "Rescuer",
            "email": u.email,
            "trust_score": u.trust_score,
            "status": u.status,
            "last_known_location": u.last_known_location
        })
    return res
