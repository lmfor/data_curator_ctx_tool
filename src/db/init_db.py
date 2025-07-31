from database import db_manager
from dotenv import load_dotenv

db_manager.create_tables()

# Test Connection
if db_manager.test_connection():
    print("Database connection successful.")
else:
    print("Database connection failed.")
