import db
from datetime import datetime, timedelta
import random
import os

# 1. Khởi tạo DB
db.init_db()

# 2. Làm sạch dữ liệu cũ
print("Đang làm sạch Database...")
db.users_table.truncate()
db.logs_table.truncate()

# 3. Danh sách 5 người dùng với UID CHÍNH XÁC
users = [
    {
        'username': 'admin',
        'password': 'admin',
        'name': 'Administrator',
        'role': 'admin',
        'uid': 'b9090f05',
        'salary': 200000,
        'position': 'System Admin',
        'allowed_rooms': ['all']
    },
    {
        'username': 'manager1',
        'password': 'password123',
        'name': 'Le Van Quan',
        'role': 'user',
        'uid': '93102056',
        'salary': 150000,
        'position': 'Manager',
        'allowed_rooms': ['p1', 'p2', 'p3']
    },
    {
        'username': 'staff1',
        'password': 'password123',
        'name': 'Nguyen Thi Mai',
        'role': 'user',
        'uid': 'e78b2625',
        'salary': 50000,
        'position': 'Staff',
        'allowed_rooms': ['p1']
    },
    {
        'username': 'staff2',
        'password': 'password123',
        'name': 'Tran Van Binh',
        'role': 'user',
        'uid': '47f0b501',
        'salary': 55000,
        'position': 'Staff',
        'allowed_rooms': ['p1', 'p2']
    },
    {
        'username': 'intern1',
        'password': 'password123',
        'name': 'Pham Van Tai',
        'role': 'user',
        'uid': 'c35ff82c',
        'salary': 25000,
        'position': 'Intern',
        'allowed_rooms': ['p1']
    }
]

account_list = []

print("Đang tạo 5 người dùng với UID mới...")
for u in users:
    account_list.append(f"User: {u['username']} | Pass: {u['password']} | Role: {u['role']} | UID: {u['uid']}")
    db.create_user(u)
    print(f"-> Tạo xong: {u['username']} (UID: {u['uid']})")

# 4. Tạo Log mẫu (30 ngày gần đây)
print("Đang tạo lịch sử chấm công...")
start_date = datetime.now() - timedelta(days=30)
end_date = datetime.now()

for u in users:
    if u['username'] == 'admin': continue
    
    current_day = start_date
    while current_day <= end_date:
        if current_day.weekday() >= 5: 
            if random.random() < 0.5:
                current_day += timedelta(days=1)
                continue

        check_in = current_day.replace(hour=8, minute=random.randint(0,30), second=0)
        check_out = current_day.replace(hour=17, minute=random.randint(30,59), second=0)
        
        db.logs_table.insert({'username': u['username'], 'action': 'in', 'timestamp': check_in.isoformat()})
        db.logs_table.insert({'username': u['username'], 'action': 'out', 'timestamp': check_out.isoformat()})
        
        current_day += timedelta(days=1)

# 5. Xuất file accounts.txt
with open('accounts.txt', 'w', encoding='utf-8') as f:
    f.write("DANH SÁCH TÀI KHOẢN HỆ THỐNG CHẤM CÔNG (CẬP NHẬT UID)\n")
    f.write("=====================================================\n")
    for acc in account_list:
        f.write(acc + "\n")

print("\nHOÀN TẤT! Đã cập nhật UID chuẩn và file accounts.txt.")
