from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()
new_password = "admin@123"  
hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')

print(f"Hashed Password: {hashed_password}")
