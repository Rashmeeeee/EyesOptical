from app import app, db, Contact

with app.app_context():
    # Create the Contact table
    db.create_all()
    print("Contact table created successfully!")
    
    # Verify the table was created
    try:
        contacts = Contact.query.all()
        print(f"Contact table is working. Found {len(contacts)} contacts.")
    except Exception as e:
        print(f"Error: {e}") 