from app import app, db, CartItem

with app.app_context():
    # Create the CartItem table
    db.create_all()
    print("CartItem table created successfully!")
    
    # Verify the table was created
    try:
        cart_items = CartItem.query.all()
        print(f"CartItem table is working. Found {len(cart_items)} cart items.")
    except Exception as e:
        print(f"Error: {e}") 