# ── Admin User Management Router ─────────────────────────────────────────────
# Provides endpoints for searching, moderating, warning, banning/suspending users,
# and managing associated authorized devices.
# Protected by get_current_admin_user dependency (JWT role check).

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Header
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import datetime, timedelta
from database import get_db
import models

router = APIRouter(prefix="/api/v1/admin", tags=["Admin User Management"])

# ── 1. List & Search Users with Pagination & Filters ──────────────────────────
@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query(None),
    role: str = Query(None),
    risk_level: str = Query(None),
    status: str = Query(None),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    # Verify administrator permissions
    from main import get_current_admin_user
    admin = get_current_admin_user(authorization=authorization, db=db)
    
    query = db.query(models.User)
    
    # Text search
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                models.User.fullName.like(search_pattern),
                models.User.email.like(search_pattern),
                func.cast(models.User.id, models.String).like(search_pattern)
            )
        )
        
    # Role filter
    if role:
        query = query.filter(models.User.role == role)
        
    # Status filter
    if status:
        query = query.filter(models.User.status == status)

    # Risk level filter (involves join with UserFraudScore)
    if risk_level:
        query = query.join(
            models.UserFraudScore, 
            models.User.id == models.UserFraudScore.user_id
        ).filter(models.UserFraudScore.risk_level == risk_level)

    # Count total matching users
    total = query.count()
    
    # Fetch paginated results
    users = query.offset((page - 1) * limit).limit(limit).all()
    
    # Process user response data, fetching fraud scores and levels if they exist
    user_list = []
    for u in users:
        fraud_score = db.query(models.UserFraudScore).filter(
            models.UserFraudScore.user_id == u.id
        ).first()
        
        score_val = fraud_score.overall_fraud_score if fraud_score else 10.0
        level_val = fraud_score.risk_level.value if (fraud_score and fraud_score.risk_level) else "low"
        
        # Check temporary ban status expiration
        if u.isBanned and u.banExpires and u.banExpires < datetime.utcnow():
            u.isBanned = False
            u.status = "Active"
            u.banReason = None
            u.banExpires = None
            db.commit()
            
        user_list.append({
            "id": str(u.id),
            "fullName": u.fullName or "Rescuer",
            "email": u.email,
            "role": u.role,
            "status": u.status,
            "warningCount": u.warningCount,
            "isBanned": u.isBanned,
            "riskScore": score_val,
            "riskLevel": level_val,
            "rescuesCount": u.rescuesCount or 0,
            "donationsCount": u.donationsCount or 0
        })
        
    return {
        "users": user_list,
        "page": page,
        "limit": limit,
        "total": total
    }

# ── 2. Get User Detail ────────────────────────────────────────────────────────
@router.get("/users/{user_id}")
def get_user_detail(
    user_id: int,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    from main import get_current_admin_user
    admin = get_current_admin_user(authorization=authorization, db=db)
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Check temporary ban status expiration
    if u.isBanned and u.banExpires and u.banExpires < datetime.utcnow():
        u.isBanned = False
        u.status = "Active"
        u.banReason = None
        u.banExpires = None
        db.commit()

    fraud_score = db.query(models.UserFraudScore).filter(
        models.UserFraudScore.user_id == u.id
    ).first()
    
    score_val = fraud_score.overall_fraud_score if fraud_score else 10.0
    level_val = fraud_score.risk_level.value if (fraud_score and fraud_score.risk_level) else "low"
    
    # Get associated devices
    devices = db.query(models.DeviceFingerprint).filter(
        models.DeviceFingerprint.user_id == u.id
    ).all()
    
    device_list = []
    for d in devices:
        device_list.append({
            "id": d.id,
            "deviceId": d.device_id,
            "deviceName": d.device_name or "Android Device",
            "deviceModel": d.device_model or "Unknown Model",
            "osVersion": d.os_version or "Android OS",
            "appVersion": d.app_version or "1.0.0",
            "ipAddress": d.ip_address or "0.0.0.0",
            "lastSeen": d.last_seen.isoformat() if d.last_seen else datetime.utcnow().isoformat(),
            "isTrusted": d.is_trusted,
            "riskScore": d.risk_score
        })
        
    # Get user listings & claims
    postings = db.query(models.FoodListing).filter(
        models.FoodListing.postedBy == u.id
    ).order_by(models.FoodListing.id.desc()).all()

    claims = db.query(models.FoodListing).filter(
        models.FoodListing.claimedBy == u.id
    ).order_by(models.FoodListing.id.desc()).all()

    postings_list = []
    for p in postings:
        postings_list.append({
            "id": p.id,
            "title": p.title,
            "status": p.status,
            "timestamp": p.timestamp or datetime.utcnow().isoformat()
        })

    claims_list = []
    for c in claims:
        claims_list.append({
            "id": c.id,
            "title": c.title,
            "status": c.status,
            "timestamp": c.timestamp or datetime.utcnow().isoformat()
        })

    return {
        "profile": {
            "id": str(u.id),
            "fullName": u.fullName or "Rescuer",
            "email": u.email,
            "phoneNumber": u.phoneNumber or "",
            "role": u.role,
            "status": u.status,
            "points": u.points or 0,
            "level": u.level or 1,
            "warningCount": u.warningCount,
            "isBanned": u.isBanned,
            "banReason": u.banReason,
            "banExpires": u.banExpires.isoformat() if u.banExpires else None,
            "rescuesCount": u.rescuesCount or 0,
            "donationsCount": u.donationsCount or 0,
            "totalCarbonSaved": u.totalCarbonSaved or 0.0,
            "riskScore": score_val,
            "riskLevel": level_val
        },
        "devices": device_list,
        "activity": {
            "postings": postings_list,
            "claims": claims_list
        }
    }

# ── 3. Get User Behavior & Anomalies ──────────────────────────────────────────
@router.get("/users/{user_id}/behavior")
def get_user_behavior(
    user_id: int,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    from main import get_current_admin_user
    admin = get_current_admin_user(authorization=authorization, db=db)
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Query behavior patterns
    pattern = db.query(models.UserBehaviorPattern).filter(
        models.UserBehaviorPattern.user_id == user_id
    ).first()
    
    pattern_data = {
        "avgPostsPerDay": pattern.avg_posts_per_day if pattern else 0.0,
        "avgFoodQuantity": pattern.avg_food_quantity if pattern else 0.0,
        "avgExpiryHours": pattern.avg_expiry_hours if pattern else 0.0,
        "avgClaimsPerDay": pattern.avg_claims_per_day if pattern else 0.0,
        "claimSuccessRate": pattern.claim_success_rate if pattern else 0.0,
        "avgClaimTime": pattern.avg_claim_time if pattern else 0.0,
        "avgRating": pattern.avg_rating if pattern else 5.0,
        "messageFrequency": pattern.message_frequency if pattern else 0,
        "lastAnalyzed": pattern.last_analyzed.isoformat() if (pattern and pattern.last_analyzed) else datetime.utcnow().isoformat()
    }
    
    # Query fraud alerts (anomalies)
    alerts = db.query(models.FraudAlert).filter(
        models.FraudAlert.user_id == user_id
    ).order_by(models.FraudAlert.created_at.desc()).all()
    
    anomalies = []
    for a in alerts:
        anomalies.append({
            "id": a.id,
            "type": a.fraud_type.value if a.fraud_type else "suspicious_activity",
            "severity": a.severity.value if a.severity else "medium",
            "title": a.title,
            "description": a.description,
            "createdAt": a.created_at.isoformat() if a.created_at else datetime.utcnow().isoformat()
        })
        
    # Extract structural behavioral flags
    if pattern:
        if pattern.posting_spike_detected:
            anomalies.append({"type": "posting_spike", "severity": "medium", "title": "Posting Spike Detected", "description": "Rapid spike in creation of food listings", "createdAt": pattern_data["lastAnalyzed"]})
        if pattern.unusual_claim_pattern:
            anomalies.append({"type": "unusual_claim", "severity": "high", "title": "Unusual Claim Behavior", "description": "Suspicious food listing claim patterns", "createdAt": pattern_data["lastAnalyzed"]})
        if pattern.location_jump_detected:
            anomalies.append({"type": "location_jump", "severity": "high", "title": "Location Jump Detected", "description": "User accessed the platform from wildly distant locations", "createdAt": pattern_data["lastAnalyzed"]})
        if pattern.rating_manipulation_suspected:
            anomalies.append({"type": "rating_manipulation", "severity": "critical", "title": "Rating Manipulation", "description": "Possible collision rating activity detected", "createdAt": pattern_data["lastAnalyzed"]})
            
    # Add suspicious logins
    logins = db.query(models.SuspiciousLogin).filter(
        models.SuspiciousLogin.user_id == user_id
    ).order_by(models.SuspiciousLogin.attempted_at.desc()).all()
    
    suspicious_logins = []
    for l in logins:
        suspicious_logins.append({
            "id": l.id,
            "ipAddress": l.ip_address,
            "deviceId": l.device_id,
            "riskScore": l.risk_score,
            "attemptedAt": l.attempted_at.isoformat() if l.attempted_at else datetime.utcnow().isoformat()
        })
        
    return {
        "behaviorPattern": pattern_data,
        "anomalies": anomalies,
        "suspiciousLogins": suspicious_logins
    }

# ── 4. Ban User ───────────────────────────────────────────────────────────────
@router.post("/users/{user_id}/ban")
def ban_user(
    user_id: int,
    payload: dict = Body(...),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    from main import get_current_admin_user
    admin = get_current_admin_user(authorization=authorization, db=db)
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
        
    reason = payload.get("reason", "Violated platform policy")
    note = payload.get("note", "")
    duration_hours = payload.get("durationHours", 0) # 0 means permanent
    
    u.isBanned = True
    u.banReason = reason
    
    if duration_hours > 0:
        u.status = "Suspended"
        u.banExpires = datetime.utcnow() + timedelta(hours=duration_hours)
        log_action = "Suspend User"
        details_str = f"Suspended for {duration_hours} hours. Note: {note}"
    else:
        u.status = "Banned"
        u.banExpires = None
        log_action = "Ban User"
        details_str = f"Permanently banned. Note: {note}"
        
    # Log Audit Log
    audit = models.AuditLog(
        admin_id=admin.id,
        action=log_action,
        target_id=str(u.id),
        reason=reason,
        timestamp=datetime.utcnow(),
        details=details_str
    )
    db.add(audit)
    db.commit()
    
    return {"success": True, "message": f"User status updated to {u.status} successfully."}

# ── 5. Issue Warning ──────────────────────────────────────────────────────────
@router.post("/users/{user_id}/warn")
def warn_user(
    user_id: int,
    payload: dict = Body(...),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    from main import get_current_admin_user
    admin = get_current_admin_user(authorization=authorization, db=db)
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
        
    reason = payload.get("reason", "Inappropriate behavior")
    note = payload.get("note", "")
    
    u.warningCount += 1
    if u.status not in ["Banned", "Suspended"]:
        u.status = "Warning"
        
    # Log Audit Log
    audit = models.AuditLog(
        admin_id=admin.id,
        action="Warn User",
        target_id=str(u.id),
        reason=reason,
        timestamp=datetime.utcnow(),
        details=f"Warning count increased to {u.warningCount}. Note: {note}"
    )
    db.add(audit)
    db.commit()
    
    return {"success": True, "message": "Warning issued successfully."}

# ── 6. Remove Ban / Unban User ────────────────────────────────────────────────
@router.post("/users/{user_id}/unban")
def unban_user(
    user_id: int,
    payload: dict = Body(default={}),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    from main import get_current_admin_user
    admin = get_current_admin_user(authorization=authorization, db=db)
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
        
    reason = payload.get("reason", "Ban lifted by administrator")
    
    u.isBanned = False
    u.status = "Active"
    u.banReason = None
    u.banExpires = None
    
    # Log Audit Log
    audit = models.AuditLog(
        admin_id=admin.id,
        action="Unban User",
        target_id=str(u.id),
        reason=reason,
        timestamp=datetime.utcnow(),
        details="Restored account to Active status"
    )
    db.add(audit)
    db.commit()
    
    return {"success": True, "message": "User unbanned successfully."}

# ── 7. Revoke Specific Authorized Device ──────────────────────────────────────
@router.post("/devices/{fingerprint}/revoke")
def revoke_device(
    fingerprint: str,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    from main import get_current_admin_user
    admin = get_current_admin_user(authorization=authorization, db=db)
    
    device = db.query(models.DeviceFingerprint).filter(
        models.DeviceFingerprint.device_id == fingerprint
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device fingerprint not found")
        
    user_id = device.user_id
    device_info = f"{device.device_name} ({device.device_model})"
    
    # Delete fingerprint record
    db.delete(device)
    
    # Log Audit Log
    audit = models.AuditLog(
        admin_id=admin.id,
        action="Revoke Device",
        target_id=str(user_id),
        reason="Revoked by admin decision",
        timestamp=datetime.utcnow(),
        details=f"Revoked device fingerprint {fingerprint}: {device_info}"
    )
    db.add(audit)
    db.commit()
    
    return {"success": True, "message": "Device revoked successfully."}
