#!/usr/bin/env python3
"""
Deployment-time database seeding script.
Run once during build/deploy phase, not on every worker startup.
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app, db
from seed_data import seed_database


def main():
    """Run database seeding for deployment."""
    app = create_app()
    
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        
        print("Seeding database...")
        try:
            seed_database()
            print("Database seeding completed successfully!")
        except Exception as e:
            print(f"Seeding error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()