-- ═══════════════════════════════════════════════════════════
-- FoodRescue Demo Data Seed
-- Run this on your MySQL database before testing
-- Command: mysql -u root -p foodrescue_db < seed_demo_data.sql
-- ═══════════════════════════════════════════════════════════

-- Create test user (password stored as plain text — dev only)
INSERT IGNORE INTO users (email, password, fullName, phoneNumber, points, level, rescuesCount, donationsCount, totalCarbonSaved, provider)
VALUES 
  ('test@foodrescue.com', 'Test@1234', 'Test User', '9876543210', 250, 3, 5, 8, 24.5, 'local'),
  ('donor@test.com',      'Test@1234', 'Donor Test', '9111111111', 300, 4, 0, 15, 45.0, 'local'),
  ('ngo@test.com',        'Test@1234', 'NGO Test',   '9222222222', 800, 7, 42, 0, 120.5, 'local'),
  ('volunteer@test.com',  'Test@1234', 'Volunteer Test', '9333333333', 450, 5, 20, 0, 60.0, 'local');

-- Get the ID of the first user (adjust if your auto-increment starts differently)
SET @user_id = (SELECT id FROM users WHERE email = 'test@foodrescue.com' LIMIT 1);

-- Insert 5 realistic food listings
INSERT INTO food_listings (title, category, quantity, location, expiryTime, status, postedBy, priorityScore, priorityLevel, carbonSaved, estimatedMeals, imageUrl)
VALUES 
(
  '50 Servings of Wedding Buffet Surplus',
  'Veg',
  '50 portions',
  'Hitech City, Hyderabad',
  DATE_ADD(NOW(), INTERVAL 3 HOUR),
  'Available',
  @user_id,
  75,
  'High',
  3.2,
  50,
  'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?q=80&w=600&auto=format&fit=crop'
),
(
  'Restaurant Surplus: Chicken Curry',
  'Non-Veg',
  '20 portions',
  'Banjara Hills, Hyderabad',
  DATE_ADD(NOW(), INTERVAL 2 HOUR),
  'Available',
  @user_id,
  90,
  'High',
  4.1,
  20,
  'https://images.unsplash.com/photo-1550258987-190a2d41a8ba?q=80&w=600&auto=format&fit=crop'
),
(
  'Fresh Artisan Sourdough Breads',
  'Bakery',
  '10 loaves',
  'Jubilee Hills, Hyderabad',
  DATE_ADD(NOW(), INTERVAL 8 HOUR),
  'Available',
  @user_id,
  45,
  'Low',
  1.8,
  10,
  'https://images.unsplash.com/photo-1509440159596-0249088772ff?q=80&w=600&auto=format&fit=crop'
),
(
  'Mixed Fruit Basket',
  'Fruits',
  '5 kg',
  'Gachibowli, Hyderabad',
  DATE_ADD(NOW(), INTERVAL 24 HOUR),
  'Available',
  @user_id,
  30,
  'Low',
  2.5,
  25,
  'https://images.unsplash.com/photo-1550583724-b2692b85b150?q=80&w=600&auto=format&fit=crop'
),
(
  'Dal Makhani + Steamed Rice',
  'Veg',
  '30 portions',
  'Madhapur, Hyderabad',
  DATE_ADD(NOW(), INTERVAL 2 HOUR),
  'Available',
  @user_id,
  95,
  'High',
  5.6,
  30,
  'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?q=80&w=600&auto=format&fit=crop'
);

SELECT 'Demo data inserted successfully!' as status;
SELECT COUNT(*) as total_listings FROM food_listings;
SELECT id, email, fullName FROM users WHERE email IN ('test@foodrescue.com', 'donor@test.com', 'ngo@test.com', 'volunteer@test.com');
