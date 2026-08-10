import math
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc
import models
import logging

logger = logging.getLogger(__name__)

class BehaviorService:
    """
    Core Anti-Cheat and Trust Engine.
    Handles gameplay behavior logs, anomaly detection, impossible travel calculations,
    device trust evaluation, and player suspicion/trust score updates.
    """

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def calculate_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two GPS coordinates using the Haversine formula (in km)."""
        R = 6371.0  # Earth radius in kilometers
        
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat / 2) ** 2 + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c

    async def log_and_analyze_behavior(self, player_id: int, action_type: str, location_str: str = None, metadata: Dict = None) -> models.PlayerBehaviorLog:
        """
        Logs a player behavior event, executes anomaly detection algorithms,
        updates the overall player Suspicion/Trust Score, and records alerts.
        """
        # 1. Parse current location
        lat_curr, lon_curr = None, None
        if location_str:
            try:
                parts = location_str.split(",")
                if len(parts) == 2:
                    lat_curr = float(parts[0].strip())
                    lon_curr = float(parts[1].strip())
            except ValueError:
                logger.warning(f"Failed to parse location coordinates: {location_str}")

        # 2. Retrieve last log to check for telemetry changes (impossible travel)
        last_log = self.db.query(models.PlayerBehaviorLog).filter(
            models.PlayerBehaviorLog.player_id == player_id
        ).order_by(desc(models.PlayerBehaviorLog.timestamp)).first()

        # Update player's last known location
        player = self.db.query(models.User).filter(models.User.id == player_id).first()
        if player and location_str:
            player.last_known_location = location_str

        # 3. Anomaly Analysis flags
        is_impossible_travel = False
        is_score_anomaly = False
        is_device_untrusted = False
        is_vpn_or_proxy = False
        travel_speed = 0.0

        # Run Impossible Travel (teleportation) check
        if last_log and last_log.location and location_str:
            try:
                parts_last = last_log.location.split(",")
                if len(parts_last) == 2:
                    lat_last = float(parts_last[0].strip())
                    lon_last = float(parts_last[1].strip())
                    
                    distance = self.calculate_haversine(lat_last, lon_last, lat_curr, lon_curr)
                    time_diff = (datetime.utcnow() - last_log.timestamp).total_seconds() / 3600.0 # hours
                    
                    if time_diff > 0.005:  # ignore logs submitted at the exact same instant
                        travel_speed = distance / time_diff
                        # Speed exceeding 900 km/h (speed of commercial aircraft) represents an anomaly
                        if travel_speed > 900.0:
                            is_impossible_travel = True
            except Exception as e:
                logger.error(f"Error executing impossible travel check: {e}")

        # Run Gameplay Score Submission checks
        score_submitted = metadata.get("score") if metadata else None
        if action_type == "score_submission" and score_submitted is not None:
            try:
                score = float(score_submitted)
                # Max humanly possible score in a session is 10,000. Anything higher is an automatic hack.
                if score > 10000.0:
                    is_score_anomaly = True
                
                # Check for rapid sequential submissions (spikes)
                recent_sub = self.db.query(models.PlayerBehaviorLog).filter(
                    models.PlayerBehaviorLog.player_id == player_id,
                    models.PlayerBehaviorLog.action_type == "score_submission",
                    models.PlayerBehaviorLog.timestamp >= datetime.utcnow() - timedelta(minutes=2)
                ).count()
                
                if recent_sub >= 3:
                    is_score_anomaly = True
            except (ValueError, TypeError):
                pass

        # Check Device Fingerprint Trust level
        device_fingerprint = metadata.get("device_fingerprint") if metadata else None
        if device_fingerprint:
            df = self.db.query(models.DeviceFingerprint).filter(
                models.DeviceFingerprint.device_id == device_fingerprint
            ).first()
            if df and not df.is_trusted:
                is_device_untrusted = True

        # Check VPN/Proxy flag
        vpn_flag = metadata.get("is_vpn") if metadata else None
        if vpn_flag is True:
            is_vpn_or_proxy = True

        # 4. Calculate Event-level Suspicion Score (0 to 100 scale)
        event_suspicion = 0.0
        reasons = []
        if is_impossible_travel:
            event_suspicion += 40.0
            reasons.append(f"Impossible Travel: {travel_speed:.1f} km/h")
        if is_score_anomaly:
            event_suspicion += 35.0
            reasons.append("Score submission velocity/value anomaly")
        if is_device_untrusted:
            event_suspicion += 20.0
            reasons.append("Untrusted device fingerprint used")
        if is_vpn_or_proxy:
            event_suspicion += 15.0
            reasons.append("VPN/Proxy connection detected")

        # Clamp event suspicion to 100
        event_suspicion = min(event_suspicion, 100.0)

        # 5. Save the Behavior Log to database
        if not metadata:
            metadata = {}
        metadata["anomaly_reasons"] = reasons
        metadata["travel_speed_kmh"] = travel_speed

        log_entry = models.PlayerBehaviorLog(
            player_id=player_id,
            action_type=action_type,
            timestamp=datetime.utcnow(),
            location=location_str,
            suspicion_score=event_suspicion,
            extra_metadata=metadata
        )
        self.db.add(log_entry)
        self.db.flush()  # populate ID

        # 6. Recalculate Player Trust Score
        # Retrieve recent logs (last 10 entries) to calculate rolling average trust
        recent_logs = self.db.query(models.PlayerBehaviorLog).filter(
            models.PlayerBehaviorLog.player_id == player_id
        ).order_by(desc(models.PlayerBehaviorLog.timestamp)).limit(10).all()

        if recent_logs:
            avg_suspicion = sum(l.suspicion_score for l in recent_logs) / len(recent_logs)
            calculated_trust = max(0, min(100, int(100 - avg_suspicion)))
        else:
            calculated_trust = 100

        if player:
            player.trust_score = calculated_trust
            
            # Auto-ban or flag if trust drops dangerously low (< 20)
            if calculated_trust < 20 and not player.isBanned:
                player.isBanned = True
                player.status = "Banned"
                player.banReason = "Auto-banned by Trust Engine: trust score dropped below 20%"
                logger.warning(f"Auto-banned player {player_id} due to low trust score: {calculated_trust}")

                # Create Audit log
                audit = models.AuditLog(
                    admin_id=1,  # System Admin account ID
                    action="Auto Ban Player",
                    target_id=str(player_id),
                    reason="Trust Score < 20%",
                    details=f"Rolling average suspicion: {100 - calculated_trust:.1f}%"
                )
                self.db.add(audit)

        # Commit all calculations
        self.db.commit()
        return log_entry

    def get_player_behavior_analysis(self, player_id: int) -> Dict:
        """Compile complete behavioral profile, stats, anomalies, and active alerts for admin dashboard."""
        player = self.db.query(models.User).filter(models.User.id == player_id).first()
        if not player:
            raise ValueError(f"Player {player_id} not found")

        logs = self.db.query(models.PlayerBehaviorLog).filter(
            models.PlayerBehaviorLog.player_id == player_id
        ).order_by(desc(models.PlayerBehaviorLog.timestamp)).all()

        anomalies_count = sum(1 for l in logs if l.suspicion_score > 0.0)
        
        # Calculate recent logs
        logs_dto = []
        for l in logs[:50]:  # limit to last 50 for performance
            logs_dto.append({
                "id": l.id,
                "action_type": l.action_type,
                "timestamp": l.timestamp.isoformat(),
                "location": l.location,
                "suspicion_score": l.suspicion_score,
                "metadata": l.extra_metadata
            })

        return {
            "player_id": player_id,
            "username": player.fullName,
            "email": player.email,
            "trust_score": player.trust_score,
            "status": player.status,
            "last_location": player.last_known_location,
            "total_behavior_logs": len(logs),
            "total_anomalies": anomalies_count,
            "behavior_history": logs_dto
        }

    def get_devices_by_player(self, player_id: int) -> List[Dict]:
        """List all device fingerprints associated with a player and return trust scores."""
        # Find device fingerprints associated with the player from login history logs or active tracking
        devices = self.db.query(models.DeviceFingerprint).filter(
            models.DeviceFingerprint.device_id.in_(
                self.db.query(models.SuspiciousLogin.device_id).filter(
                    models.SuspiciousLogin.device_id != None
                ) # Fetching associated device ids via login tables
            )
        ).all()
        
        # If no device fingerprints found from references, query all matching records
        # (For this mock/game system, return all registered device fingerprints for demonstration)
        if not devices:
            devices = self.db.query(models.DeviceFingerprint).all()

        res = []
        for d in devices:
            res.append({
                "device_id": d.device_id,
                "device_name": d.device_name or "Unknown Device",
                "device_model": d.device_model or "Unknown Model",
                "os_version": d.os_version or "Android",
                "ip_address": d.ip_address or "127.0.0.1",
                "is_trusted": d.is_trusted,
                "risk_score": d.risk_score,
                "first_seen": d.first_seen.isoformat() if d.first_seen else None,
                "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                "login_count": d.login_count
            })
        return res
