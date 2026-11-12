import sqlite3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / 'data' / '번역.sqlite'
TRANS_DIR = ROOT / 'translations'

def import_all():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    total_updated = 0
    for json_file in TRANS_DIR.glob('*.json'):
        with open(json_file, 'r', encoding='utf-8') as f:
            items = json.load(f)
            
        print(f"Importing {json_file.name} ({len(items)} items)...")
        for item in items:
            uid = item['id']
            ko = item.get('ko', '')
            c.execute("UPDATE entries SET ko = ? WHERE id = ?", (ko, uid))
            total_updated += 1
            
    conn.commit()
    conn.close()
    print(f"\n[Success] Imported {total_updated} entries into {DB_PATH.name}")

if __name__ == '__main__':
    import_all()
