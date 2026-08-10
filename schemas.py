from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class UserBase(BaseModel):
    email: str
    fullName: Optional[str] = None
    phoneNumber: Optional[str] = None
    points: int = 0
    level: int = 1
    rescuesCount: int = 0
    donationsCount: int = 0
    totalCarbonSaved: float = 0.0
    provider: str = "Email"
    role: str = "USER"

class UserCreate(UserBase):
    password: str
    mpin: Optional[str] = None
    securityAnswer: Optional[str] = None

class User(UserBase):
    id: int

    class Config:
        from_attributes = True

class AuthResponse(BaseModel):
    success: bool
    message: str
    user: Optional[User] = None
    token: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: str

class VerifyOtpRequest(BaseModel):
    email: str
    otp: str

class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str

class GoogleAuthRequest(BaseModel):
    email: str
    fullName: str
    idToken: str

class FoodListingBase(BaseModel):
    title: str
    description: str
    quantity: str
    expiryTime: str
    location: str
    imageUrl: Optional[str] = None
    status: str = "Available"
    category: str = "Veg"
    priorityScore: int = 0
    priorityLevel: str = "Low"
    carbonSaved: float = 0.0
    estimatedMeals: int = 0
    timestamp: Optional[str] = None
    claimedBy: Optional[int] = None

class FoodListingCreate(FoodListingBase):
    postedBy: Optional[int] = None

class FoodListing(FoodListingBase):
    id: int
    postedBy: Optional[int] = None

    class Config:
        from_attributes = True

class NotificationBase(BaseModel):
    userId: int
    title: str
    message: str
    type: str
    isRead: bool = False
    timestamp: Optional[str] = None

class Notification(NotificationBase):
    id: int

    class Config:
        from_attributes = True

class CommunityStats(BaseModel):
    totalRescues: int
    totalMealsSaved: int
    totalCarbonSaved: float
    activeUsers: int
    totalDonations: int

class RatingCreate(BaseModel):
    rated_user_id: int
    rating: float

class RatingResponse(BaseModel):
    id: int
    rater_user_id: int
    rated_user_id: int
    rating: float
    created_at: datetime

    class Config:
        from_attributes = True

class LeaderboardEntry(BaseModel):
    id: int
    fullName: Optional[str] = None
    points: int
    rescuesCount: int
    donationsCount: int
    role: str
    level: int

class BadgeResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    xp_required: int

    class Config:
        from_attributes = True

class ReportCreate(BaseModel):
    reported_user_id: Optional[int] = None
    reported_listing_id: Optional[int] = None
    reason: str

class ReportResponse(BaseModel):
    id: int
    reporter_id: int
    reported_user_id: Optional[int] = None
    reported_listing_id: Optional[int] = None
    reason: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

