import db
from datetime import datetime, timedelta
import random

# Initialize DB connection
db.init_db()

# Clear existing data
db.users_table.truncate()
db.logs_table.truncate()

# Create Users with HOURLY SALARY
users = [
    {
        'username': 'admin',
        'password': 'admin', # Mật khẩu gốc (chưa hash)
        'name': 'Administrator',
        'role': 'admin',
        'uid': 'admin_card',
        'salary': 200000, # 200k/giờ
        'position': 'System Admin',
        'allowed_rooms': ['all']
    },
    {
        'username': 'manager1',
        'password': 'password123',
        'name': 'Le Van Quan',
        'role': 'user',
        'uid': 'card_001',
        'salary': 150000, # 150k/giờ
        'position': 'Manager',
        'allowed_rooms': ['p1', 'p2', 'p3']
    },
    {
        'username': 'staff1',
        'password': 'password123',
        'name': 'Nguyen Thi Mai',
        'role': 'user',
        'uid': 'card_002',
        'salary': 50000, # 50k/giờ
        'position': 'Staff',
        'allowed_rooms': ['p1']
    },
    {
        'username': 'staff2',
        'password': 'password123',
        'name': 'Tran Van Binh',
        'role': 'user',
        'uid': 'card_003',
        'salary': 55000, # 55k/giờ
        'position': 'Staff',
        'allowed_rooms': ['p1', 'p2']
    },
    {
        'username': 'intern1',
        'password': 'password123',
        'name': 'Pham Van Tai',
        'role': 'user',
        'uid': 'card_004',
        'salary': 25000, # 25k/giờ
        'position': 'Intern',
        'allowed_rooms': ['p1']
    }
]

# List to store account details for file output
account_list = []

print("Creating users...")
for u in users:
    # Save plain credentials for file output before hashing in db.create_user
    account_info = f"User: {u['username']} | Pass: {u['password']} | Role: {u['role']} | UID: {u['uid']}"
    account_list.append(account_info)
    
    # Create user (this will hash the password)
    db.create_user(u)
    print(f"Created {u['username']} - Rate: {u['salary']}/h")

# Generate Logs for the last 30 days
print("\nGenerating logs...")
start_date = datetime.now() - timedelta(days=30)
end_date = datetime.now()

for u in users:
    if u['username'] == 'admin': continue
    
    current_day = start_date
    while current_day <= end_date:
        if random.random() < 0.1: # 10% nghỉ
            current_day += timedelta(days=1)
            continue

        check_in_hour = 7
        check_in_minute = random.randint(30, 59)
        if random.random() > 0.5: check_in_hour = 8; check_in_minute = random.randint(0, 30)
        checkin_dt = current_day.replace(hour=check_in_hour, minute=check_in_minute, second=0)
        
        checkout_hour = random.randint(17, 19) 
        checkout_minute = random.randint(0, 59)
        checkout_dt = current_day.replace(hour=checkout_hour, minute=checkout_minute, second=0)
        
        # Insert raw log entries
        db.logs_table.insert({'uid': u['uid'], 'action': 'in', 'timestamp': checkin_dt.isoformat()})
        db.logs_table.insert({'uid': u['uid'], 'action': 'out', 'timestamp': checkout_dt.isoformat()})
        
        current_day += timedelta(days=1)

    db.update_user_status(u['uid'], 'checkout')

# Write accounts to file
with open('accounts.txt', 'w', encoding='utf-8') as f:
    f.write("DANH SÁCH TÀI KHOẢN HỆ THỐNG CHẤM CÔNG\n")
    f.write("=========================================\n")
    for acc in account_list:
        f.write(acc + "\n")
    f.write("\nLưu ý: Mật khẩu admin đã được reset về mặc định 'admin'.\n")

print("\nSeed data complete. Accounts saved to 'accounts.txt'.")
print("Run 'python main.py' to start the server.")
