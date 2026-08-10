content = open('main.py', 'r', encoding='utf-8').read()

# Clean replacement block
new_block = '''@app.post("/api/v1/food/listings")
@app.post("/post-food")
def post_food(data: dict = Body(...), db: Session = Depends(get_db)):
    qty = data.get("quantity", 1)
    unit = data.get("unit", "Plates")
    quantity_str = f"{qty} {unit}"
    expiry_ms = data.get("expiryTime", 0)
    expiry_str = parse_ms_to_iso(expiry_ms)
    posted_ms = data.get("postedAt", 0)
    posted_str = parse_ms_to_iso(posted_ms)

    image_url_val = ""
    if data.get("imageUrls"):
        image_url_val = ",".join(data.get("imageUrls"))
    else:
        image_url_val = data.get("imageUrl", "")

    new_listing = models.FoodListing(
        title=data.get("foodName", "Rescue Food"),
        description=data.get("description", ""),
        quantity=quantity_str,
        expiryTime=expiry_str,
        location=data.get("address", "Chennai"),
        imageUrl=image_url_val,
        postedBy=int(data.get("userId")) if data.get("userId") else 1,
        status="Available",
        category="Veg" if data.get("foodType") == "VEG" else "Non-Veg",
        timestamp=posted_str,
        latitude=float(data.get("latitude", 13.0827)),
        longitude=float(data.get("longitude", 80.2707))
    )
    db.add(new_listing)

    user = db.query(models.User).filter(models.User.id == new_listing.postedBy).first()
    if user:
        user.donationsCount += 1
        user.points += 10
        user.level = 1 + (user.points // 100)

    db.commit()
    db.refresh(new_listing)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.broadcast({
                "type": "NEW_POST",
                "title": "New Food Available Nearby!",
                "message": f"{new_listing.title} is available at {new_listing.location}.",
                "listing": map_listing_to_android(new_listing)
            }))
    except Exception:
        pass

    return map_listing_to_android(new_listing)

@app.post("/claim-food/{listing_id}")
def claim_food(listing_id: int, data: dict = Body(None), db: Session = Depends(get_db)):
    listing = db.query(models.FoodListing).filter(models.FoodListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.status != "Available":
        raise HTTPException(status_code=400, detail="Listing is not available")

    user_id = 1
    if data:
        user_id = data.get("userId") or data.get("user_id") or 1

    otp = "".join([str(random.randint(0, 9)) for _ in range(6)])
    listing.status = "Claimed"
    listing.claimedBy = user_id
    listing.verification_otp = otp
    listing.claimed_at = datetime.utcnow()

    new_notif = models.Notification(
        userId=listing.postedBy,
        title="Food Claimed!",
        message=f"Someone has accepted your donation: {listing.title}",
        type="CLAIMED",
        timestamp=datetime.now().isoformat()
    )
    db.add(new_notif)
    db.commit()
    db.refresh(listing)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(manager.send_personal_message({
                "type": "CLAIMED",
                "title": new_notif.title,
                "message": new_notif.message,
                "timestamp": new_notif.timestamp,
                "id": new_notif.id
            }, str(listing.postedBy)))
    except Exception:
        pass

    return {
        "postId": str(listing.id),
        "userId": str(user_id),
        "claimedAt": int(time.time() * 1000),
        "verification_otp": otp
    }

'''

end_marker = '@app.delete("/food-listings/{listing_id}/save")'

# Find ALL occurrences of the api/v1 route
import re
# Find the first occurrence
pattern = r'@app\.post\("/api/v1/food/listings"\).*?(?=@app\.delete\("/food-listings/\{listing_id\}/save"\))'
match = re.search(pattern, content, re.DOTALL)

if match:
    print(f"Found block from {match.start()} to {match.end()}")
    new_content = content[:match.start()] + new_block + content[match.end():]
    open('main.py', 'w', encoding='utf-8').write(new_content)
    print("SUCCESS: main.py has been fixed!")
else:
    # Try to find markers manually
    all_occurrences = [m.start() for m in re.finditer(r'@app\.post\("/api/v1/food/listings"\)', content)]
    print(f"Found {len(all_occurrences)} occurrences at positions: {all_occurrences}")
    end_pos = content.find(end_marker)
    print(f"End marker at: {end_pos}")
