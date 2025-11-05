#!/usr/bin/env python3
"""
Convert UMM messages CSV to SQLite database for efficient querying
"""
import sqlite3
import csv
import json
import sys
from datetime import datetime

def create_database(db_path):
    """Create SQLite database with optimized schema"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create main messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            version INTEGER,
            message_type INTEGER,
            event_status TEXT,
            is_outdated INTEGER,
            publication_date TEXT,
            event_start TEXT,
            event_stop TEXT,
            publisher_id TEXT,
            publisher_name TEXT,
            unavailability_type TEXT,
            reason_code TEXT,
            unavailability_reason TEXT,
            cancellation_reason TEXT,
            remarks TEXT,
            
            -- JSON fields (stored as TEXT)
            areas_json TEXT,
            production_units_json TEXT,
            generation_units_json TEXT,
            transmission_units_json TEXT,
            related_messages_json TEXT,
            
            -- Derived fields for quick filtering
            area_names TEXT,  -- Comma-separated
            production_unit_names TEXT,  -- Comma-separated
            generation_unit_names TEXT,  -- Comma-separated
            
            -- Capacity info
            installed_mw REAL,
            unavailable_mw REAL,
            available_mw REAL,
            fuel_type TEXT,
            
            -- Duration calculation
            duration_hours REAL,
            
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes for fast queries
    print("Creating indexes...")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_publication_date ON messages(publication_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_message_type ON messages(message_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_publisher_name ON messages(publisher_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_event_start ON messages(event_start)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_event_stop ON messages(event_stop)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_area_names ON messages(area_names)')
    
    conn.commit()
    return conn

def extract_area_names(row):
    """Extract all area names from JSON fields"""
    areas = set()
    
    # From areas_json
    try:
        areas_data = json.loads(row.get('areas_json', '[]') or '[]')
        if isinstance(areas_data, list):
            for item in areas_data:
                if isinstance(item, dict) and item.get('name'):
                    areas.add(item['name'])
    except:
        pass
    
    # From production_units_json
    try:
        prod_units = json.loads(row.get('production_units_json', '[]') or '[]')
        if isinstance(prod_units, list):
            for unit in prod_units:
                if isinstance(unit, dict) and unit.get('areaName'):
                    areas.add(unit['areaName'])
    except:
        pass
    
    # From generation_units_json
    try:
        gen_units = json.loads(row.get('generation_units_json', '[]') or '[]')
        if isinstance(gen_units, list):
            for unit in gen_units:
                if isinstance(unit, dict) and unit.get('areaName'):
                    areas.add(unit['areaName'])
    except:
        pass
    
    # From transmission_units_json
    try:
        trans_units = json.loads(row.get('transmission_units_json', '[]') or '[]')
        if isinstance(trans_units, list):
            for unit in trans_units:
                if isinstance(unit, dict):
                    if unit.get('inAreaName'):
                        areas.add(unit['inAreaName'])
                    if unit.get('outAreaName'):
                        areas.add(unit['outAreaName'])
    except:
        pass
    
    return ','.join(sorted(areas))

def extract_unit_names(json_str):
    """Extract unit names from JSON array"""
    names = set()
    try:
        data = json.loads(json_str or '[]')
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    name = item.get('name') or item.get('productionUnitName') or item.get('generationUnitName')
                    if name:
                        names.add(name)
    except:
        pass
    return ','.join(sorted(names))

def extract_capacity_info(row):
    """Extract capacity information from JSON fields"""
    total_installed = 0
    total_unavailable = 0
    total_available = 0
    fuel_types = set()
    
    fuel_map = {
        1: "Nuclear", 2: "Lignite", 3: "Hard Coal", 4: "Natural Gas",
        5: "Oil", 6: "Biomass", 7: "Geothermal", 8: "Waste",
        9: "Wind Onshore", 10: "Wind Offshore", 11: "Solar", 12: "Hydro",
        13: "Pumped Storage", 14: "Marine", 15: "Other"
    }
    
    # Process production units
    try:
        prod_units = json.loads(row.get('production_units_json', '[]') or '[]')
        if isinstance(prod_units, list):
            for unit in prod_units:
                if isinstance(unit, dict):
                    total_installed += unit.get('installedCapacity', 0)
                    if unit.get('fuelType'):
                        fuel_types.add(fuel_map.get(unit['fuelType'], f"Type {unit['fuelType']}"))
                    if unit.get('timePeriods') and len(unit['timePeriods']) > 0:
                        period = unit['timePeriods'][0]
                        total_unavailable += period.get('unavailableCapacity', 0)
                        total_available += period.get('availableCapacity', 0)
    except:
        pass
    
    # Process generation units
    try:
        gen_units = json.loads(row.get('generation_units_json', '[]') or '[]')
        if isinstance(gen_units, list):
            for unit in gen_units:
                if isinstance(unit, dict):
                    total_installed += unit.get('installedCapacity', 0)
                    if unit.get('fuelType'):
                        fuel_types.add(fuel_map.get(unit['fuelType'], f"Type {unit['fuelType']}"))
                    if unit.get('timePeriods') and len(unit['timePeriods']) > 0:
                        period = unit['timePeriods'][0]
                        total_unavailable += period.get('unavailableCapacity', 0)
                        total_available += period.get('availableCapacity', 0)
    except:
        pass
    
    return {
        'installed_mw': total_installed if total_installed > 0 else None,
        'unavailable_mw': total_unavailable if total_unavailable > 0 else None,
        'available_mw': total_available if total_available > 0 else None,
        'fuel_type': ', '.join(sorted(fuel_types)) if fuel_types else None
    }

def calculate_duration_hours(start, stop):
    """Calculate duration in hours between two datetime strings"""
    if not start or not stop:
        return None
    try:
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        stop_dt = datetime.fromisoformat(stop.replace('Z', '+00:00'))
        duration = (stop_dt - start_dt).total_seconds() / 3600
        return duration
    except:
        return None

def import_csv_to_db(csv_path, db_path):
    """Import CSV data into SQLite database"""
    # Increase CSV field size limit for large JSON fields
    csv.field_size_limit(10 * 1024 * 1024)  # 10MB per field
    
    print(f"Creating database: {db_path}")
    conn = create_database(db_path)
    cursor = conn.cursor()
    
    print(f"Reading CSV: {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        batch = []
        batch_size = 1000
        total_rows = 0
        
        for row in reader:
            # Extract derived fields
            area_names = extract_area_names(row)
            prod_unit_names = extract_unit_names(row.get('production_units_json', ''))
            gen_unit_names = extract_unit_names(row.get('generation_units_json', ''))
            capacity = extract_capacity_info(row)
            duration_hours = calculate_duration_hours(row.get('event_start'), row.get('event_stop'))
            
            # Prepare row for insertion
            # Convert boolean strings to integers
            is_outdated_val = row.get('is_outdated', '')
            if is_outdated_val in ('true', 'True', '1'):
                is_outdated = 1
            elif is_outdated_val in ('false', 'False', '0', ''):
                is_outdated = 0
            else:
                is_outdated = int(is_outdated_val) if is_outdated_val else 0
            
            batch.append((
                row.get('message_id'),
                int(row.get('version', 0)) if row.get('version') else None,
                int(row.get('message_type', 0)) if row.get('message_type') else None,
                row.get('event_status'),
                is_outdated,
                row.get('publication_date'),
                row.get('event_start'),
                row.get('event_stop'),
                row.get('publisher_id'),
                row.get('publisher_name'),
                row.get('unavailability_type'),
                row.get('reason_code'),
                row.get('unavailability_reason'),
                row.get('cancellation_reason'),
                row.get('remarks'),
                row.get('areas_json'),
                row.get('production_units_json'),
                row.get('generation_units_json'),
                row.get('transmission_units_json'),
                row.get('related_messages_json'),
                area_names,
                prod_unit_names,
                gen_unit_names,
                capacity['installed_mw'],
                capacity['unavailable_mw'],
                capacity['available_mw'],
                capacity['fuel_type'],
                duration_hours
            ))
            
            # Insert in batches
            if len(batch) >= batch_size:
                cursor.executemany('''
                    INSERT OR REPLACE INTO messages (
                        message_id, version, message_type, event_status, is_outdated,
                        publication_date, event_start, event_stop,
                        publisher_id, publisher_name,
                        unavailability_type, reason_code, unavailability_reason,
                        cancellation_reason, remarks,
                        areas_json, production_units_json, generation_units_json,
                        transmission_units_json, related_messages_json,
                        area_names, production_unit_names, generation_unit_names,
                        installed_mw, unavailable_mw, available_mw, fuel_type,
                        duration_hours
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', batch)
                conn.commit()
                total_rows += len(batch)
                print(f"  Imported {total_rows} rows...")
                batch = []
        
        # Insert remaining rows
        if batch:
            cursor.executemany('''
                INSERT OR REPLACE INTO messages (
                    message_id, version, message_type, event_status, is_outdated,
                    publication_date, event_start, event_stop,
                    publisher_id, publisher_name,
                    unavailability_type, reason_code, unavailability_reason,
                    cancellation_reason, remarks,
                    areas_json, production_units_json, generation_units_json,
                    transmission_units_json, related_messages_json,
                    area_names, production_unit_names, generation_unit_names,
                    installed_mw, unavailable_mw, available_mw, fuel_type,
                    duration_hours
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', batch)
            conn.commit()
            total_rows += len(batch)
    
    print(f"✅ Successfully imported {total_rows} messages into database")
    
    # Get database size
    cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
    db_size = cursor.fetchone()[0]
    print(f"📊 Database size: {db_size / (1024*1024):.1f} MB")
    
    conn.close()

if __name__ == '__main__':
    csv_path = 'data/umm_messages.csv'
    db_path = 'data/umm_messages.db'
    
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    if len(sys.argv) > 2:
        db_path = sys.argv[2]
    
    print("=" * 60)
    print("UMM Messages CSV to SQLite Converter")
    print("=" * 60)
    
    import_csv_to_db(csv_path, db_path)
    
    print("\n✅ Conversion complete!")
    print(f"Database created at: {db_path}")
