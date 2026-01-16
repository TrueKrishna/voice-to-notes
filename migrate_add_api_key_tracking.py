#!/usr/bin/env python3
"""
Migration script to add API key tracking columns to recordings table.
Run this once to update the database schema.
"""

import sqlite3
import os

DB_PATH = "./data/voice_notes.db"

def migrate():
    """Add api_key_id and api_key_name columns to recordings table."""
    
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(recordings)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if "api_key_id" in columns and "api_key_name" in columns:
            print("✓ Columns already exist. No migration needed.")
            return
        
        # Add api_key_id column
        if "api_key_id" not in columns:
            print("Adding api_key_id column...")
            cursor.execute("ALTER TABLE recordings ADD COLUMN api_key_id INTEGER")
            print("✓ Added api_key_id column")
        
        # Add api_key_name column
        if "api_key_name" not in columns:
            print("Adding api_key_name column...")
            cursor.execute("ALTER TABLE recordings ADD COLUMN api_key_name VARCHAR(100)")
            print("✓ Added api_key_name column")
        
        conn.commit()
        print("\n✓ Migration completed successfully!")
        print("  - api_key_id: INTEGER (stores API key ID)")
        print("  - api_key_name: VARCHAR(100) (stores friendly key name)")
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("=== Database Migration: Add API Key Tracking ===\n")
    migrate()
