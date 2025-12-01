# FILE: app/services/db_service.py
import sqlite3
import json
import os
from datetime import datetime

DB_FILE = "forge.db"

class ArsenalDB:
    def __init__(self):
        self.conn = None
        self._init_db()

    def _init_db(self):
        """Initialize SQLite schema if not exists."""
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        
        # Components Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                part_type TEXT NOT NULL,
                product_name TEXT NOT NULL,
                model_name TEXT,
                price REAL,
                source_url TEXT,
                image_url TEXT,
                specs_json TEXT,
                visuals_json TEXT,
                verified BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_name)
            )
        ''')
        
        # Missions/Projects Table (To store the Rancher's requests)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                mission_profile_json TEXT,
                bom_json TEXT,
                status TEXT
            )
        ''')
        
        self.conn.commit()

    def add_component(self, part_data):
        """
        Upsert a component into the arsenal.
        """
        cursor = self.conn.cursor()
        
        # Serialize dicts to JSON strings
        specs_str = json.dumps(part_data.get('engineering_specs', {}))
        visuals_str = json.dumps(part_data.get('visuals', {}))
        
        try:
            cursor.execute('''
                INSERT INTO components (part_type, product_name, model_name, price, source_url, image_url, specs_json, visuals_json, verified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_name) DO UPDATE SET
                    price=excluded.price,
                    specs_json=excluded.specs_json,
                    visuals_json=excluded.visuals_json,
                    verified=excluded.verified
            ''', (
                part_data.get('part_type'),
                part_data.get('product_name'),
                part_data.get('model_name', part_data.get('product_name')),
                part_data.get('price'),
                part_data.get('source_url'),
                part_data.get('reference_image'),
                specs_str,
                visuals_str,
                True
            ))
            self.conn.commit()
            print(f"      💾 DB: Saved {part_data['product_name'][:30]}...")
            return True
        except Exception as e:
            print(f"      ❌ DB Error: {e}")
            return False

    def find_component(self, part_type, query_string=None):
        """
        Search for a component.
        """
        cursor = self.conn.cursor()
        if query_string:
            # Simple fuzzy search
            cursor.execute('''
                SELECT * FROM components 
                WHERE part_type = ? AND (product_name LIKE ? OR specs_json LIKE ?)
                ORDER BY verified DESC, price ASC
                LIMIT 1
            ''', (part_type, f"%{query_string}%", f"%{query_string}%"))
        else:
            # Get any valid part of type
            cursor.execute('''
                SELECT * FROM components 
                WHERE part_type = ? 
                ORDER BY verified DESC 
                LIMIT 1
            ''', (part_type,))
            
        row = cursor.fetchone()
        if row:
            d = dict(row)
            # Deserialize JSON
            d['engineering_specs'] = json.loads(d['specs_json']) if d['specs_json'] else {}
            d['visuals'] = json.loads(d['visuals_json']) if d['visuals_json'] else {}
            return d
        return None

    def get_all_inventory(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM components")
        rows = cursor.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d['engineering_specs'] = json.loads(d['specs_json']) if d['specs_json'] else {}
            results.append(d)
        return results

    def close(self):
        if self.conn:
            self.conn.close()