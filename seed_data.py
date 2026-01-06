import db
from datetime import datetime, timedelta
import random

# Initialize DB connection
db.init_db()

# Clear existing data (optional, but good for clean state)
db.users_table.truncate()
db.logs_table.truncate()

# Create Users
users = [
    {
        'username': 'admin',
        'password': 'admin_password',
        'name': 'Administrator',
        'role': 'admin',
        'uid': 'admin_card',
        'salary': 20000000,
        'position': 'System Admin',
        'allowed_rooms': ['all']
    },
    {
        'username': 'manager1',
        'password': 'password123',
        'name': 'Le Van Quan',
        'role': 'user',
        'uid': 'card_001',
        'salary': 15000000,
        'position': 'Manager',
        'allowed_rooms': ['p1', 'p2', 'p3']
    },
    {
        'username': 'staff1',
        'password': 'password123',
        'name': 'Nguyen Thi Mai',
        'role': 'user',
        'uid': 'card_002',
        'salary': 8000000,
        'position': 'Staff',
        'allowed_rooms': ['p1']
    },
    {
        'username': 'staff2',
        'password': 'password123',
        'name': 'Tran Van Binh',
        'role': 'user',
        'uid': 'card_003',
        'salary': 8500000,
        'position': 'Staff',
        'allowed_rooms': ['p1', 'p2']
    },
    {
        'username': 'intern1',
        'password': 'password123',
        'name': 'Pham Van Tai',
        'role': 'user',
        'uid': 'card_004',
        'salary': 3000000,
        'position': 'Intern',
        'allowed_rooms': ['p1']
    }
]

print("Creating users...")
for u in users:
    db.create_user(u)
    print(f"Created {u['username']}")

# Generate Logs for the last 30 days
print("\nGenerating logs...")
start_date = datetime.now() - timedelta(days=30)
end_date = datetime.now()

for u in users:
    if u['username'] == 'admin': continue
    
    current_day = start_date
    while current_day <= end_date:
        # Randomly skip weekends or some days
        if current_day.weekday() >= 5: # Sat/Sun
            current_day += timedelta(days=1)
            continue
            
        if random.random() < 0.1: # 10% chance to be absent
            current_day += timedelta(days=1)
            continue

        # Check in time (random between 7:30 and 9:00)
        check_in_hour = 7
        check_in_minute = random.randint(30, 59)
        if random.random() > 0.5:
             check_in_hour = 8
             check_in_minute = random.randint(0, 30)
             
        checkin_dt = current_day.replace(hour=check_in_hour, minute=check_in_minute, second=0)
        
        # Check out time (random between 17:00 and 19:00)
        checkout_hour = random.randint(17, 18)
        checkout_minute = random.randint(0, 59)
        checkout_dt = current_day.replace(hour=checkout_hour, minute=checkout_minute, second=0)
        
        # Insert Logs manually to bypass "current time" logic in db.add_log
        # We need to construct the log entry directly
        db.logs_table.insert({
            'uid': u['uid'],
            'action': 'in',
            'timestamp': checkin_dt.isoformat()
        })
        
        db.logs_table.insert({
            'uid': u['uid'],
            'action': 'out',
            'timestamp': checkout_dt.isoformat()
        })
        
        current_day += timedelta(days=1)

    # Set random current status
    if random.choice([True, False]):
        db.update_user_status(u['uid'], 'checkin')
        # Add a checkin for today if 'checkin' status
        db.logs_table.insert({
            'uid': u['uid'],
            'action': 'in',
            'timestamp': datetime.now().isoformat()
        })
        print(f"User {u['username']} is currently checked IN")
    else:
        db.update_user_status(u['uid'], 'checkout')
        print(f"User {u['username']} is currently checked OUT")

print("\nSeed data generation complete.")
