import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.database import init_db, get_conn, save_deal

init_db()
conn = get_conn()
count = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
conn.close()

if count == 0:
    seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed.json")
    if os.path.exists(seed_path):
        with open(seed_path) as f:
            deals = json.load(f)
        saved = 0
        for d in deals:
            save_deal(d)
            saved += 1
        print(f"Seeded {saved} deals from seed.json")
    else:
        print(f"No seed.json found at {seed_path}")
else:
    print(f"DB already has {count} deals, skipping seed")
