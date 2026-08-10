from sqlalchemy import Column, Integer, String, Text, ForeignKey, Float, Boolean, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime, timedelta
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False) # In production, always hash passwords!
    fullName = Column(String(255))
    phoneNumber = Column(String(20))
    points = Column(Integer, default=0)
    level = Column(Integer, default=1)
    rescuesCount = Column(Integer, default=0)
    totalCarbonSaved = Column(Float, default=0.0)
    donationsCount = Column(Integer, default=0)
    role = Column(String(50), default="USER", nullable=False) # Enum: USER, ADMIN, MODERATOR

    # Moderation & Ban fields
    status = Column(String(50), default="Active", nullable=False) # Active, Warning, Suspended, Banned
    banReason = Column(Text, nullable=True)
    banExpires = Column(DateTime, nullable=True)
    warningCount = Column(Integer, default=0, nullable=False)
    isBanned = Column(Boolean, default=False, nullable=False)
    moderation_status = Column(String(50), default="APPROVED") # PENDING, APPROVED, REJECTED, MANUAL_REVIEW

    # Phase 2 Anti-Cheat & Trust Engine fields
    trust_score = Column(Integer, default=100, nullable=False)
    last_known_location = Column(String(255), nullable=True)

    # Auth & Recovery
    otpCode = Column(String(10), nullable=True)
    otpExpiry = Column(String(100), nullable=True)
    provider = Column(String(50), default="Email") # Email, Google
    mpin = Column(String(10), nullable=True)          # 4-digit MPIN
    securityAnswer = Column(String(255), nullable=True) # Answer to reset MPIN

    listings = relationship("FoodListing", foreign_keys="[FoodListing.postedBy]", back_populates="owner")
    claims = relationship("FoodListing", foreign_keys="[FoodListing.claimedBy]", back_populates="claimer")

class FoodListing(Base):
    __tablename__ = "food_listings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    _quantity = Column("quantity", String(100))
    expiryTime = Column(String(100))
    location = Column(String(255))
    imageUrl = Column(Text)  # LONGTEXT — supports base64 image data
    postedBy = Column(Integer, ForeignKey("users.id"))
    claimedBy = Column(Integer, ForeignKey("users.id"), nullable=True) # User who claimed the food
    status = Column(String(50), default="Available") # Available, Claimed, On The Way, Reached, Collected, Completed, Expired
    category = Column(String(50), default="Veg")
    priorityScore = Column(Integer, default=0)
    priorityLevel = Column(String(20), default="Low")
    carbonSaved = Column(Float, default=0.0)
    estimatedMeals = Column(Integer, default=0)
    timestamp = Column(String(100))

    # New tracking fields for maps and behavior monitoring
    latitude = Column(Float, default=13.0827, nullable=True)
    longitude = Column(Float, default=80.2707, nullable=True)
    claimed_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    verification_otp = Column(String(10), nullable=True)

    # Hybrid properties for behavior monitoring service queries
    @hybrid_property
    def user_id(self):
        return self.postedBy

    @user_id.setter
    def user_id(self, value):
        self.postedBy = value

    @user_id.expression
    def user_id(cls):
        return cls.postedBy

    @hybrid_property
    def claimed_by(self):
        return self.claimedBy

    @claimed_by.setter
    def claimed_by(self, value):
        self.claimedBy = value

    @claimed_by.expression
    def claimed_by(cls):
        return cls.claimedBy

    @hybrid_property
    def food_type(self):
        return self.category

    @food_type.setter
    def food_type(self, value):
        self.category = value

    @hybrid_property
    def quantity(self):
        if not self._quantity:
            return 0.0
        try:
            return float(self._quantity)
        except ValueError:
            import re
            match = re.search(r"[-+]?\d*\.\d+|\d+", self._quantity)
            return float(match.group()) if match else 0.0

    @quantity.setter
    def quantity(self, value):
        self._quantity = str(value)

    @quantity.expression
    def quantity(cls):
        from sqlalchemy import cast, Float
        return cast(cls._quantity, Float)

    @hybrid_property
    def created_at(self):
        if not self.timestamp:
            return datetime.utcnow()
        try:
            if self.timestamp.isdigit():
                return datetime.fromtimestamp(float(self.timestamp) / 1000.0)
            return datetime.fromisoformat(self.timestamp)
        except Exception:
            return datetime.utcnow()

    @created_at.setter
    def created_at(self, value):
        if isinstance(value, datetime):
            self.timestamp = value.isoformat()
        else:
            self.timestamp = str(value)

    @hybrid_property
    def expiry_time(self):
        if not self.expiryTime:
            return datetime.utcnow()
        try:
            if self.expiryTime.isdigit():
                return datetime.fromtimestamp(float(self.expiryTime) / 1000.0)
            return datetime.fromisoformat(self.expiryTime)
        except Exception:
            try:
                hours = float(self.expiryTime)
                return self.created_at + timedelta(hours=hours)
            except Exception:
                return datetime.utcnow()

    @expiry_time.setter
    def expiry_time(self, value):
        if isinstance(value, datetime):
            self.expiryTime = value.isoformat()
        else:
            self.expiryTime = str(value)

    owner = relationship("User", foreign_keys=[postedBy], back_populates="listings")
    claimer = relationship("User", foreign_keys=[claimedBy], back_populates="claims")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    userId = Column(Integer, ForeignKey("users.id"))
    title = Column(String(255))
    message = Column(Text)
    type = Column(String(50)) # CLAIMED, STATUS_UPDATE, COMPLETED
    isRead = Column(Boolean, default=False)
    timestamp = Column(String(100))

    user = relationship("User")

from datetime import datetime

class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, index=True)
    rater_user_id = Column(Integer, ForeignKey("users.id"))
    rated_user_id = Column(Integer, ForeignKey("users.id"))
    rating = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text, nullable=False)
    is_flagged = Column(Boolean, default=False)
    moderation_status = Column(String(50), default="APPROVED") # PENDING, APPROVED, REJECTED, MANUAL_REVIEW
    created_at = Column(DateTime, default=datetime.utcnow)

class CustomSkin(Base):
    __tablename__ = "custom_skins"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    image_url = Column(Text, nullable=False)
    moderation_status = Column(String(50), default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)

class ContentModeration(Base):
    __tablename__ = "content_moderations"

    id = Column(Integer, primary_key=True, index=True)
    content_id = Column(String(255), nullable=False)
    content_type = Column(String(50), nullable=False) # USERNAME, BIO, PROFILE_IMAGE, SKIN, CHAT
    player_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quality_score = Column(Float, default=100.0)
    recommendation = Column(String(50), nullable=False) # APPROVE, MANUAL_REVIEW, REJECT
    reasons = Column(JSON, nullable=True)
    vision_response = Column(JSON, nullable=True)
    status = Column(String(50), default="PENDING") # PENDING, REVIEWED
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(255), nullable=False) # e.g. Ban User, Warn User, Unban User, Revoke Device
    target_id = Column(String(255), nullable=True)
    reason = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    details = Column(Text, nullable=True)

    admin = relationship("User", foreign_keys=[admin_id])

class PlayerBehaviorLog(Base):
    __tablename__ = "player_behavior_logs"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action_type = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    location = Column(String(255), nullable=True)
    suspicion_score = Column(Float, default=0.0, nullable=False)
    extra_metadata = Column(JSON, nullable=True)

    player = relationship("User")

class Badge(Base):
    __tablename__ = "badges"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(255))
    icon = Column(String(255))
    xp_required = Column(Integer, default=0)

class UserBadge(Base):
    __tablename__ = "user_badges"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    badge_id = Column(Integer, ForeignKey("badges.id"), nullable=False)
    unlocked_at = Column(DateTime, default=datetime.utcnow)

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reported_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reported_listing_id = Column(Integer, ForeignKey("food_listings.id"), nullable=True)
    reason = Column(Text, nullable=False)
    status = Column(String(50), default="Pending") # Pending, Resolved, Dismissed
    created_at = Column(DateTime, default=datetime.utcnow)

class UserBlock(Base):
    __tablename__ = "user_blocks"

    id = Column(Integer, primary_key=True, index=True)
    blocker_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    blocked_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Alias Food to FoodListing as expected by behavior analysis models
Food = FoodListing


# Import fraud detection models
from backend.models.fraud_detection import (
    UserFraudScore, FraudAlert, IPAddressBlock, DeviceFingerprint,
    SuspiciousLogin, ContentQualityScore, UserBehaviorPattern, ImageAnalysisCache
)
