# ── Admin Dashboard API ─────────────────────────────────────────────────────
# Provides aggregated overview data for the FoodRescue admin dashboard.
# Protected by get_current_admin_user dependency (JWT role check).

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from database import get_db
import models

router = APIRouter(prefix="/api/v1/admin/dashboard", tags=["Admin Dashboard"])


def get_current_admin_user_dep(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Re-use the admin auth logic from main.py via import"""
    from main import get_current_admin_user
    from fastapi import Header
    # We need to call it properly
    return get_current_admin_user(authorization=authorization, db=db)


@router.get("/overview")
def get_dashboard_overview(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Returns comprehensive admin dashboard overview data:
    - User stats, listing counts, rescue metrics
    - System health indicators
    - Recent activity feed (last 10 actions)
    """
    # ── Auth check ──────────────────────────────────────────────────────────
    from main import get_current_admin_user
    admin_user = get_current_admin_user(authorization=authorization, db=db)

    # ── User Metrics ────────────────────────────────────────────────────────
    total_users = db.query(func.count(models.User.id)).scalar() or 0

    # ── Listing Metrics ─────────────────────────────────────────────────────
    active_listings = db.query(func.count(models.FoodListing.id)).filter(
        models.FoodListing.status == "Available"
    ).scalar() or 0

    total_listings = db.query(func.count(models.FoodListing.id)).scalar() or 0

    # ── Rescue Metrics ──────────────────────────────────────────────────────
    meals_rescued = db.query(func.count(models.FoodListing.id)).filter(
        models.FoodListing.status.in_(["Completed", "Collected"])
    ).scalar() or 0

    claimed_listings = db.query(func.count(models.FoodListing.id)).filter(
        models.FoodListing.status.in_(["Claimed", "On The Way", "Reached"])
    ).scalar() or 0

    # ── Pending Reports (placeholder — no reports table yet) ────────────────
    pending_reports = 0

    # ── Average Risk Score (placeholder — returns safe default) ─────────────
    avg_risk_score = 12.5

    # ── System Health ───────────────────────────────────────────────────────
    system_health = {
        "apiStatus": "healthy",
        "dbStatus": "healthy",
        "moderationQueueSize": pending_reports,
        "uptimeSeconds": 0  # Placeholder
    }

    # ── Recent Activity Feed (last 10 food listing events) ──────────────────
    recent_listings = db.query(models.FoodListing).order_by(
        models.FoodListing.id.desc()
    ).limit(10).all()

    recent_activity = []
    for listing in recent_listings:
        # Determine action type from status
        if listing.status == "Available":
            action = f"New listing posted: \"{listing.title}\""
            actor = "User"
        elif listing.status in ["Claimed", "On The Way", "Reached"]:
            action = f"Listing claimed: \"{listing.title}\""
            actor = "User"
        elif listing.status in ["Completed", "Collected"]:
            action = f"Rescue completed: \"{listing.title}\""
            actor = "System"
        elif listing.status == "Expired":
            action = f"Listing expired: \"{listing.title}\""
            actor = "System"
        else:
            action = f"Listing updated: \"{listing.title}\" → {listing.status}"
            actor = "System"

        recent_activity.append({
            "id": listing.id,
            "action": action,
            "actor": actor,
            "timestamp": listing.timestamp or datetime.utcnow().isoformat(),
            "type": listing.status.lower() if listing.status else "unknown"
        })

    # ── Build Response ──────────────────────────────────────────────────────
    return {
        "totalUsers": total_users,
        "activeListings": active_listings,
        "totalListings": total_listings,
        "pendingReports": pending_reports,
        "mealsRescued": meals_rescued,
        "claimedListings": claimed_listings,
        "avgRiskScore": avg_risk_score,
        "systemHealth": system_health,
        "recentActivity": recent_activity,
        "adminName": admin_user.fullName or "Administrator",
        "adminEmail": admin_user.email
    }
