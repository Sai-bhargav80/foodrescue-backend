from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from models import (
    User, Food, Rating, Message, UserBehaviorPattern,
    SuspiciousLogin, DeviceFingerprint, UserFraudScore
)
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import statistics
import logging

logger = logging.getLogger(__name__)

class BehaviorMonitoringService:
    """Monitor and analyze user behavior patterns"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== POSTING BEHAVIOR ====================
    
    async def analyze_posting_behavior(self, user_id: int) -> Dict:
        """Analyze user's posting patterns"""
        
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        food_posts = self.db.query(Food).filter(
            Food.user_id == user_id
        ).order_by(desc(Food.timestamp)).all()  # order by timestamp/created_at
        
        if not food_posts:
            return {
                "user_id": user_id,
                "total_posts": 0,
                "posting_frequency": 0,
                "avg_daily_posts": 0,
                "posting_times": [],
                "food_types": [],
                "avg_quantity": 0,
                "avg_expiry_hours": 0,
                "anomalies_detected": []
            }
        
        # Calculate basic statistics
        total_posts = len(food_posts)
        
        # Time-based analysis
        posting_times = [f.created_at.hour for f in food_posts]
        posting_days = [f.created_at.date() for f in food_posts]
        unique_days = len(set(posting_days))
        
        avg_daily_posts = total_posts / max(unique_days, 1)
        
        # Posting time patterns (when user posts)
        time_distribution = {}
        for hour in posting_times:
            time_distribution[hour] = time_distribution.get(hour, 0) + 1
        
        peak_posting_hour = max(time_distribution, key=time_distribution.get) if time_distribution else 0
        
        # Food type analysis
        food_types = {}
        for food in food_posts:
            if food.food_type:
                food_types[food.food_type] = food_types.get(food.food_type, 0) + 1
        
        # Quantity analysis
        quantities = [f.quantity for f in food_posts if f.quantity]
        avg_quantity = statistics.mean(quantities) if quantities else 0
        quantity_stddev = statistics.stdev(quantities) if len(quantities) > 1 else 0
        
        # Expiry time analysis
        expiry_times = []
        for food in food_posts:
            if food.expiry_time and food.created_at:
                hours_until_expiry = (food.expiry_time - food.created_at).total_seconds() / 3600
                expiry_times.append(hours_until_expiry)
        
        avg_expiry_hours = statistics.mean(expiry_times) if expiry_times else 0
        
        # Get or create behavior pattern record
        behavior = self.db.query(UserBehaviorPattern).filter(
            UserBehaviorPattern.user_id == user_id
        ).first()
        
        if not behavior:
            behavior = UserBehaviorPattern(user_id=user_id)
            self.db.add(behavior)
        
        # Detect anomalies
        anomalies = []
        
        # Anomaly 1: Spike in posting
        last_week_posts = [f for f in food_posts if 
                          f.created_at > datetime.utcnow() - timedelta(days=7)]
        
        if behavior.avg_posts_per_day > 0:
            current_avg = len(last_week_posts) / 7
            if current_avg > behavior.avg_posts_per_day * 3:
                anomalies.append({
                    "type": "posting_spike",
                    "severity": "high",
                    "description": f"Posting increased from {behavior.avg_posts_per_day:.1f} to {current_avg:.1f} posts/day",
                    "detected_at": datetime.utcnow().isoformat()
                })
                behavior.posting_spike_detected = True
        
        # Anomaly 2: Quantity outliers
        if quantity_stddev > 0:
            outliers = [q for q in quantities if 
                       abs(q - avg_quantity) > 2 * quantity_stddev]
            
            if len(outliers) > len(quantities) * 0.3:  # >30% are outliers
                anomalies.append({
                    "type": "quantity_outliers",
                    "severity": "medium",
                    "description": f"Unusual variation in posted quantities",
                    "detected_at": datetime.utcnow().isoformat()
                })
        
        # Anomaly 3: Very short expiry times
        short_expiry = [e for e in expiry_times if e < 2]  # Less than 2 hours
        if len(short_expiry) > len(expiry_times) * 0.5:
            anomalies.append({
                "type": "very_short_expiry",
                "severity": "low",
                "description": "Food posted with very short expiry windows",
                "detected_at": datetime.utcnow().isoformat()
            })
        
        # Update behavior record
        behavior.avg_posts_per_day = avg_daily_posts
        behavior.avg_food_quantity = avg_quantity
        behavior.avg_expiry_hours = avg_expiry_hours
        behavior.posting_time_pattern = time_distribution
        behavior.last_analyzed = datetime.utcnow()
        
        self.db.commit()
        
        return {
            "user_id": user_id,
            "total_posts": total_posts,
            "posting_frequency": {
                "avg_daily": avg_daily_posts,
                "peak_hour": peak_posting_hour,
                "time_distribution": time_distribution
            },
            "food_analysis": {
                "types": food_types,
                "avg_quantity": avg_quantity,
                "quantity_variance": quantity_stddev,
                "avg_expiry_hours": avg_expiry_hours
            },
            "anomalies_detected": anomalies,
            "recent_posts": [
                {
                    "id": f.id,
                    "title": f.title,
                    "quantity": f.quantity,
                    "expiry": f.expiry_time.isoformat() if f.expiry_time else None,
                    "created": f.created_at.isoformat()
                }
                for f in food_posts[:5]
            ]
        }
    
    # ==================== CLAIMING BEHAVIOR ====================
    
    async def analyze_claiming_behavior(self, user_id: int) -> Dict:
        """Analyze user's claiming patterns"""
        
        claimed_food = self.db.query(Food).filter(
            Food.claimed_by == user_id
        ).order_by(desc(Food.claimed_at)).all()
        
        if not claimed_food:
            return {
                "user_id": user_id,
                "total_claims": 0,
                "claiming_frequency": 0,
                "avg_claim_time_minutes": 0,
                "claim_sources": {},
                "anomalies_detected": []
            }
        
        # Get or create behavior pattern
        behavior = self.db.query(UserBehaviorPattern).filter(
            UserBehaviorPattern.user_id == user_id
        ).first()
        
        if not behavior:
            behavior = UserBehaviorPattern(user_id=user_id)
            self.db.add(behavior)
        
        # Basic statistics
        total_claims = len(claimed_food)
        
        # Claim speed analysis (how fast after posting)
        claim_times = []
        for food in claimed_food:
            if food.claimed_at and food.created_at:
                claim_time_minutes = (food.claimed_at - food.created_at).total_seconds() / 60
                claim_times.append(claim_time_minutes)
        
        avg_claim_time = statistics.mean(claim_times) if claim_times else 0
        
        # Claim sources (which donors user claims from)
        claim_sources = {}
        for food in claimed_food:
            donor_id = food.user_id
            if donor_id not in claim_sources:
                donor_name = "Unknown"
                if food.owner:
                    donor_name = food.owner.fullName or food.owner.email
                claim_sources[donor_id] = {
                    "donor_name": donor_name,
                    "count": 0,
                    "total_quantity": 0
                }
            claim_sources[donor_id]["count"] += 1
            claim_sources[donor_id]["total_quantity"] += food.quantity or 0
        
        # Detect anomalies
        anomalies = []
        
        # Anomaly 1: Extremely fast claims (bot-like behavior)
        instant_claims = [t for t in claim_times if t < 1]  # Claimed in <1 minute
        if len(instant_claims) > len(claim_times) * 0.5:
            anomalies.append({
                "type": "instant_claims",
                "severity": "high",
                "description": f"{len(instant_claims)} claims made within 1 minute of posting",
                "detected_at": datetime.utcnow().isoformat()
            })
            behavior.unusual_claim_pattern = True
        
        # Anomaly 2: Repeated claims from suspicious vendors
        for donor_id, source in claim_sources.items():
            if source["count"] > 10:
                # Check if donor is suspicious
                donor_fraud = self.db.query(UserFraudScore).filter(
                    UserFraudScore.user_id == donor_id
                ).first()
                
                if donor_fraud and donor_fraud.risk_level in ["high", "critical"]:
                    anomalies.append({
                        "type": "suspicious_donor_pattern",
                        "severity": "high",
                        "description": f"User claims repeatedly from high-risk donor {source['donor_name']}",
                        "detected_at": datetime.utcnow().isoformat()
                    })
        
        # Anomaly 3: Claiming all different vendors (spreading picks)
        if len(claim_sources) > 20 and total_claims > 50:
            anomalies.append({
                "type": "diverse_vendor_pattern",
                "severity": "medium",
                "description": "User claims from unusually many different vendors",
                "detected_at": datetime.utcnow().isoformat()
            })
        
        # Update behavior
        min_date = self.db.query(func.min(Food.claimed_at)).filter(
            Food.claimed_by == user_id
        ).scalar()
        days_diff = (datetime.utcnow() - min_date).days if min_date else 1
        
        behavior.avg_claims_per_day = total_claims / max(days_diff, 1)
        behavior.avg_claim_time = avg_claim_time
        behavior.last_analyzed = datetime.utcnow()
        
        self.db.commit()
        
        return {
            "user_id": user_id,
            "total_claims": total_claims,
            "claim_speed": {
                "avg_minutes": avg_claim_time,
                "min_minutes": min(claim_times) if claim_times else 0,
                "max_minutes": max(claim_times) if claim_times else 0
            },
            "claim_sources": {
                str(k): v for k, v in claim_sources.items()
            },
            "anomalies_detected": anomalies,
            "top_donors": sorted(
                claim_sources.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )[:5]
        }
    
    # ==================== LOCATION BEHAVIOR ====================
    
    async def analyze_location_behavior(self, user_id: int) -> Dict:
        """Analyze user's location patterns"""
        
        food_posts = self.db.query(Food).filter(
            Food.user_id == user_id
        ).filter(Food.latitude.isnot(None)).all()
        
        if not food_posts:
            return {
                "user_id": user_id,
                "locations_count": 0,
                "usual_locations": [],
                "anomalies_detected": []
            }
        
        behavior = self.db.query(UserBehaviorPattern).filter(
            UserBehaviorPattern.user_id == user_id
        ).first()
        
        if not behavior:
            behavior = UserBehaviorPattern(user_id=user_id)
            self.db.add(behavior)
        
        # Extract locations
        locations = [(f.latitude, f.longitude) for f in food_posts]
        
        # Cluster nearby locations (within 5km)
        location_clusters = self._cluster_locations(locations, radius_km=5)
        
        # Calculate average location
        avg_lat = statistics.mean([loc[0] for loc in locations])
        avg_lng = statistics.mean([loc[1] for loc in locations])
        avg_location = (avg_lat, avg_lng)
        
        # Calculate location variance
        distances = [self._distance_between(loc, avg_location) for loc in locations]
        location_variance = statistics.mean(distances) if distances else 0
        
        anomalies = []
        
        # Anomaly 1: Location jump
        if len(locations) > 1:
            for i in range(1, len(locations)):
                prev_location = locations[i-1]
                current_location = locations[i]
                
                distance = self._distance_between(prev_location, current_location)
                time_diff = (food_posts[i].created_at - food_posts[i-1].created_at).total_seconds() / 3600
                
                # If jumped >1000km in <24 hours, it's suspicious
                if distance > 1000 and time_diff < 24:
                    anomalies.append({
                        "type": "location_jump",
                        "severity": "high",
                        "description": f"Jumped {distance:.0f}km in {time_diff:.1f} hours",
                        "detected_at": datetime.utcnow().isoformat()
                    })
                    behavior.location_jump_detected = True
        
        # Anomaly 2: International jumps
        international_jumps = [loc for loc in location_clusters if len(loc["locations"]) == 1]
        if len(international_jumps) > 5:
            anomalies.append({
                "type": "multiple_countries",
                "severity": "medium",
                "description": f"User posts from {len(location_clusters)} different regions",
                "detected_at": datetime.utcnow().isoformat()
            })
        
        # Update behavior
        behavior.usual_locations = [
            {"lat": cluster["center"][0], "lng": cluster["center"][1], "count": len(cluster["locations"])}
            for cluster in location_clusters
        ]
        behavior.location_variance = location_variance
        behavior.last_analyzed = datetime.utcnow()
        
        self.db.commit()
        
        return {
            "user_id": user_id,
            "total_locations": len(locations),
            "location_clusters": [
                {
                    "center": cluster["center"],
                    "post_count": len(cluster["locations"]),
                    "radius_km": cluster["radius"]
                }
                for cluster in location_clusters
            ],
            "location_variance_km": location_variance,
            "anomalies_detected": anomalies
        }
    
    # ==================== RATING BEHAVIOR ====================
    
    async def analyze_rating_behavior(self, user_id: int) -> Dict:
        """Analyze rating patterns for manipulation"""
        
        ratings_given = self.db.query(Rating).filter(
            Rating.rater_user_id == user_id
        ).all()
        
        ratings_received = self.db.query(Rating).filter(
            Rating.rated_user_id == user_id
        ).all()
        
        behavior = self.db.query(UserBehaviorPattern).filter(
            UserBehaviorPattern.user_id == user_id
        ).first()
        
        if not behavior:
            behavior = UserBehaviorPattern(user_id=user_id)
            self.db.add(behavior)
        
        anomalies = []
        
        # Analyze ratings given
        if ratings_given:
            given_scores = [r.rating for r in ratings_given]
            avg_given = statistics.mean(given_scores)
            
            # Check for extreme consistency (all 5 stars or all 1 star)
            unique_scores = len(set(given_scores))
            if unique_scores == 1:
                anomalies.append({
                    "type": "extreme_rating_consistency",
                    "severity": "medium",
                    "description": f"User always gives {given_scores[0]} star ratings",
                    "detected_at": datetime.utcnow().isoformat()
                })
        
        # Analyze ratings received
        if ratings_received:
            received_scores = [r.rating for r in ratings_received]
            avg_received = statistics.mean(received_scores)
            score_variance = statistics.stdev(received_scores) if len(received_scores) > 1 else 0
            
            # Check for suspicious rating patterns
            five_star_count = len([r for r in ratings_received if r.rating == 5.0])
            one_star_count = len([r for r in ratings_received if r.rating == 1.0])
            
            # If all ratings are 5 stars, might be fake
            if five_star_count == len(ratings_received) and len(ratings_received) > 5:
                anomalies.append({
                    "type": "fake_positive_ratings",
                    "severity": "high",
                    "description": f"All {len(ratings_received)} ratings are 5 stars (suspicious)",
                    "detected_at": datetime.utcnow().isoformat()
                })
                behavior.rating_manipulation_suspected = True
            
            # If sudden jump in ratings
            recent_ratings = [r for r in ratings_received if 
                            r.created_at > datetime.utcnow() - timedelta(days=7)]
            
            if len(recent_ratings) > len(ratings_received) * 0.7:
                anomalies.append({
                    "type": "rating_spike",
                    "severity": "medium",
                    "description": f"70% of ratings received in last 7 days",
                    "detected_at": datetime.utcnow().isoformat()
                })
        
        # Update behavior
        behavior.avg_rating = statistics.mean(received_scores) if ratings_received else 0
        behavior.last_analyzed = datetime.utcnow()
        
        self.db.commit()
        
        return {
            "user_id": user_id,
            "ratings_given": len(ratings_given),
            "ratings_received": len(ratings_received),
            "given_stats": {
                "avg_rating": statistics.mean([r.rating for r in ratings_given]) if ratings_given else 0,
                "consistency": "high" if len(set([r.rating for r in ratings_given])) == 1 else "varied"
            } if ratings_given else {},
            "received_stats": {
                "avg_rating": statistics.mean([r.rating for r in ratings_received]) if ratings_received else 0,
                "five_star_count": len([r for r in ratings_received if r.rating == 5.0]),
                "variance": statistics.stdev([r.rating for r in ratings_received]) if len(ratings_received) > 1 else 0
            } if ratings_received else {},
            "anomalies_detected": anomalies
        }
    
    # ==================== MESSAGE BEHAVIOR ====================
    
    async def analyze_message_behavior(self, user_id: int) -> Dict:
        """Analyze messaging patterns for spam/harassment"""
        
        sent_messages = self.db.query(Message).filter(
            Message.sender_id == user_id
        ).order_by(desc(Message.created_at)).all()
        
        if not len(sent_messages):
            return {
                "user_id": user_id,
                "messages_sent": 0,
                "messaging_frequency": 0,
                "anomalies_detected": []
            }
        
        anomalies = []
        
        # Anomaly 1: Message spam (too many in short time)
        last_hour_messages = [m for m in sent_messages if 
                             m.created_at > datetime.utcnow() - timedelta(hours=1)]
        
        if len(last_hour_messages) > 20:
            anomalies.append({
                "type": "message_spam",
                "severity": "high",
                "description": f"{len(last_hour_messages)} messages sent in last hour",
                "detected_at": datetime.utcnow().isoformat()
            })
        
        # Anomaly 2: Repeated same message to multiple users
        message_content_frequency = {}
        for msg in sent_messages[:50]:  # Check recent messages
            content = msg.content[:50]  # First 50 chars
            message_content_frequency[content] = message_content_frequency.get(content, 0) + 1
        
        repeated_msgs = {k: v for k, v in message_content_frequency.items() if v > 5}
        if repeated_msgs:
            anomalies.append({
                "type": "repeated_messages",
                "severity": "medium",
                "description": f"Spam-like pattern: same message sent {max(repeated_msgs.values())} times",
                "detected_at": datetime.utcnow().isoformat()
            })
        
        # Anomaly 3: Flagged messages (already filtered as abusive)
        flagged_messages = [m for m in sent_messages if m.is_flagged]
        if len(flagged_messages) > len(sent_messages) * 0.2:  # >20% flagged
            anomalies.append({
                "type": "abusive_messaging",
                "severity": "high",
                "description": f"{len(flagged_messages)} messages flagged as abusive",
                "detected_at": datetime.utcnow().isoformat()
            })
        
        # Calculate avg message frequency
        days_diff = (datetime.utcnow() - sent_messages[-1].created_at).days
        avg_freq = len(sent_messages) / max(days_diff, 1)
        
        return {
            "user_id": user_id,
            "messages_sent": len(sent_messages),
            "messaging_frequency": {
                "last_hour": len(last_hour_messages),
                "last_day": len([m for m in sent_messages if m.created_at > datetime.utcnow() - timedelta(days=1)]),
                "avg_per_day": avg_freq
            },
            "flagged_messages": len(flagged_messages),
            "anomalies_detected": anomalies
        }
    
    # ==================== UTILITY METHODS ====================
    
    def _cluster_locations(self, locations: List[Tuple[float, float]], radius_km: float = 5) -> List[Dict]:
        """Cluster nearby locations"""
        
        if not locations:
            return []
        
        clusters = []
        used = set()
        
        for i, location in enumerate(locations):
            if i in used:
                continue
            
            cluster = {
                "center": location,
                "locations": [location],
                "radius": 0
            }
            
            for j, other_location in enumerate(locations):
                if j <= i or j in used:
                    continue
                
                distance = self._distance_between(location, other_location)
                if distance <= radius_km:
                    cluster["locations"].append(other_location)
                    used.add(j)
                    cluster["radius"] = max(cluster["radius"], distance)
            
            # Calculate cluster center
            avg_lat = statistics.mean([loc[0] for loc in cluster["locations"]])
            avg_lng = statistics.mean([loc[1] for loc in cluster["locations"]])
            cluster["center"] = (avg_lat, avg_lng)
            
            clusters.append(cluster)
        
        return clusters
    
    def _distance_between(self, loc1: Tuple[float, float], loc2: Tuple[float, float]) -> float:
        """Calculate distance between two coordinates in km"""
        
        import math
        
        lat1, lon1 = loc1
        lat2, lon2 = loc2
        
        R = 6371  # Earth's radius in km
        
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat/2) * math.sin(dlat/2) +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon/2) * math.sin(dlon/2))
        
        c = 2 * math.asin(math.sqrt(a))
        return R * c
