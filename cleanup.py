import os
import shutil

base = os.path.dirname(os.path.abspath(__file__))

# Delete __pycache__ folders
count = 0
for root, dirs, files in os.walk(base):
    if "__pycache__" in dirs:
        pycache_path = os.path.join(root, "__pycache__")
        shutil.rmtree(pycache_path)
        print(f"Deleted: {pycache_path}")
        count += 1

# Delete old database
db_path = os.path.join(base, "learning_system.db")
if os.path.exists(db_path):
    os.remove(db_path)
    print(f"Deleted: {db_path}")
    count += 1

if count == 0:
    print("Nothing to clean!")
else:
    print(f"\nDone! Cleaned {count} items.")
    print("Now run: python run.py")
