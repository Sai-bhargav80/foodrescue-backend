from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum
from database import Base

class FraudType(str, Enum):
    FAKE_LISTING = "fake_listing"
    REPEATED_CLAIMS = "repeated_claims"
    FAKE_IMAGES = "fake_images"
    SUSPICIOUS_PATTERN = "suspicious_pattern"
    RAPID_POSTING = "rapid_posting"
    LOCATION_SPOOFING = "location_spoofing"
    ACCOUNT_MANIPULATION = "account_manipulation"
    SPAM_CONTENT = "spam_content"
    SEXUAL_HARASSMENT = "sexual_harassment"
    PRICE_EXPLOITATION = "price_exploitation"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class UserFraudScore(Base):
    """Tracks fraud risk score for each user"""
    __tablename__ = "user_fraud_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    
    # Fraud metrics
    overall_fraud_score = Column(Float, default=0.0)  # 0-100
    risk_level = Column(SQLEnum(RiskLevel), default=RiskLevel.LOW)
    
    # Component scores
    posting_pattern_score = Column(Float, default=0.0)
    claim_pattern_score = Column(Float, default=0.0)
    content_quality_score = Column(Float, default=0.0)
    behavior_pattern_score = Column(Float, default=0.0)
    image_authenticity_score = Column(Float, default=0.0)
    
    # Flags
    is_flagged = Column(Boolean, default=False)
    flags = Column(JSON, default=list)  # List of fraud types detected
    
    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_notes = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])

class FraudAlert(Base):
    """Fraud alerts for suspicious activities"""
    __tablename__ = "fraud_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Alert details
    fraud_type = Column(SQLEnum(FraudType), nullable=False)
    severity = Column(SQLEnum(RiskLevel), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    
    # Context
    target_type = Column(String(50))  # food, user, message
    target_id = Column(Integer)
    
    # Alert status
    is_acknowledged = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    resolution_action = Column(String(255), nullable=True)
    
    # Metadata
    evidence = Column(JSON, nullable=True)  # Supporting data
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

class IPAddressBlock(Base):
    """Blocked IP addresses"""
    __tablename__ = "ip_address_blocks"
    
    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String(45), unique=True, nullable=False, index=True)
    
    # Block details
    reason = Column(String(255), nullable=False)
    severity = Column(SQLEnum(RiskLevel), nullable=False)
    is_permanent = Column(Boolean, default=False)
    
    # Blocking
    blocked_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    blocked_at = Column(DateTime, default=datetime.utcnow)
    unblocked_at = Column(DateTime, nullable=True)
    
    # Metadata
    associated_accounts = Column(JSON, default=list)  # User IDs using this IP
    violation_count = Column(Integer, default=0)

class DeviceFingerprint(Base):
    """Device fingerprints for fraud detection"""
    __tablename__ = "device_fingerprints"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Device info
    device_id = Column(String(255), unique=True, nullable=False)
    device_name = Column(String(255))
    device_model = Column(String(255))
    os_version = Column(String(255))
    app_version = Column(String(255))
    
    # Network info
    ip_address = Column(String(45), index=True)
    mac_address = Column(String(17), nullable=True)
    
    # Risk assessment
    is_trusted = Column(Boolean, default=False)
    risk_score = Column(Float, default=0.0)
    
    # Activity
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    login_count = Column(Integer, default=0)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

class SuspiciousLogin(Base):
    """Tracks suspicious login attempts"""
    __tablename__ = "suspicious_logins"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Login details
    ip_address = Column(String(45), nullable=False)
    device_id = Column(String(255))
    location_change = Column(Boolean, default=False)  # Different from usual location
    is_vpn = Column(Boolean, default=False)
    
    # Risk assessment
    risk_score = Column(Float, default=0.0)
    reasons = Column(JSON, default=list)
    
    # Action taken
    requires_verification = Column(Boolean, default=False)
    was_blocked = Column(Boolean, default=False)
    
    # Timestamp
    attempted_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

class ContentQualityScore(Base):
    """Evaluates content quality and authenticity"""
    __tablename__ = "content_quality_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    food_id = Column(Integer, ForeignKey("food_listings.id"), nullable=False, index=True)
    
    # Content metrics
    image_quality_score = Column(Float, default=0.0)  # Image clarity, resolution
    description_quality = Column(Float, default=0.0)  # Grammar, detail level
    plausibility_score = Column(Float, default=0.0)  # Does listing seem real?
    
    # Flags
    has_low_quality_image = Column(Boolean, default=False)
    has_misleading_description = Column(Boolean, default=False)
    has_fake_image_indicators = Column(Boolean, default=False)
    
    # Overall assessment
    authenticity_score = Column(Float, default=0.0)  # 0-100
    recommendation = Column(String(50))  # approve, review, reject
    
    # Metadata
    analysis_method = Column(JSON)  # Which checks were performed
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    food = relationship("FoodListing", foreign_keys=[food_id])

class UserBehaviorPattern(Base):
    """Analyzes user behavior patterns for anomalies"""
    __tablename__ = "user_behavior_patterns"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    
    # Posting behavior
    avg_posts_per_day = Column(Float, default=0.0)
    avg_food_quantity = Column(Float, default=0.0)
    avg_expiry_hours = Column(Float, default=0.0)
    posting_time_pattern = Column(JSON)  # Peak posting hours
    
    # Claim behavior
    avg_claims_per_day = Column(Float, default=0.0)
    claim_success_rate = Column(Float, default=0.0)
    avg_claim_time = Column(Float, default=0.0)  # Time between post and claim
    
    # Geographic behavior
    usual_locations = Column(JSON, default=list)  # List of lat/lng
    location_variance = Column(Float, default=0.0)  # How far user travels
    
    # Social behavior
    avg_rating = Column(Float, default=0.0)
    rating_consistency = Column(Float, default=0.0)  # Do ratings vary?
    message_frequency = Column(Integer, default=0)
    
    # Anomaly flags
    posting_spike_detected = Column(Boolean, default=False)
    unusual_claim_pattern = Column(Boolean, default=False)
    location_jump_detected = Column(Boolean, default=False)
    rating_manipulation_suspected = Column(Boolean, default=False)
    
    # Last analysis
    last_analyzed = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])

class ImageAnalysisCache(Base):
    """Cache image analysis results for performance"""
    __tablename__ = "image_analysis_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    image_url = Column(String(500), unique=True, nullable=False, index=True)
    
    # Analysis results
    is_real_food = Column(Boolean, nullable=True)
    confidence_score = Column(Float, default=0.0)
    
    # Detailed metrics
    image_hash = Column(String(64), nullable=True)  # For duplicate detection
    has_been_edited = Column(Boolean, default=False)
    contains_faces = Column(Boolean, default=False)  # Privacy concern
    is_ai_generated = Column(Boolean, default=False)
    
    # Metadata
    analysis_method = Column(String(50))  # google_vision, custom_ml, manual
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # Cache expiration
