import sys
from pathlib import Path
from backend.api import run_audit

if __name__ == "__main__":
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/invoices/sample_invoice.txt")
    result = run_audit(path.read_bytes(), path.name)
    import json
    print(json.dumps(result, indent=2))