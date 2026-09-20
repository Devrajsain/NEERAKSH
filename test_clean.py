import csv
from pathlib import Path
import sys

backend_dir = Path("backend").resolve()
sys.path.insert(0, str(backend_dir))

from app.feature3.cleaning import clean_and_validate_ais

def test_clean():
    csv_path = Path("backend/uploads/SLK-E095_synthetic_ais.csv")
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        ais_data = list(reader)
        
    cleaned, audit = clean_and_validate_ais(ais_data)
    print(f"Cleaned records: {len(cleaned)}")
    print(f"Audit stats: {audit}")
    
    if len(cleaned) == 0:
        print("Everything got filtered out!")

if __name__ == "__main__":
    test_clean()
