import sys
import os
import logging

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Now import should work
from db.database import db_manager

# Set up logging
logging.basicConfig(level=logging.INFO)

def test_database():
    print("Testing database connection...")
    
    # Test connection
    if db_manager.test_connection():
        print("✅ Database connection successful!")
    else:
        print("❌ Database connection failed!")
        return
    
    # Create tables
    print("Creating database tables...")
    db_manager.create_tables()
    
    # Test adding a validated URL
    print("Testing URL operations...")
    url_data = db_manager.add_validated_url(
        url="https://weshare.advantest.com/vs/display/aetsV93k/The+SmarTest+8+Resources+Guide%3A+Where+to+Find+Help+for+SmarTest+8",
        title="V93K Setup Guide",
        ctx_relevance_score=0.95,
        ctx_currency_score=0.88,
        page_metadata={"page_size": 1024, "author": "John Doe"}
    )
    
    if url_data:
        print(f"✅ Added URL: {url_data['url']}")
        
        # Test retrieval
        retrieved = db_manager.get_validated_url(url_data['url'])
        if retrieved:
            print(f"✅ Retrieved URL: {retrieved.title}")
        
        # Test logging
        log = db_manager.log_validation(
            url=url_data['url'],
            validation_type="relevance",
            result="pass",
            confidence_score=0.95,
            reasoning="Content clearly relates to V93K setup procedures"
        )
        
        if log:
            print(f"✅ Logged validation: {log.validation_type}")
    
    print("Database test completed!")

def test_connection():
    """Pytest-style test function"""
    assert db_manager.test_connection(), "Database connection should work"

if __name__ == "__main__":
    test_database()