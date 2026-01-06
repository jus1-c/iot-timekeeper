from tinydb import TinyDB, Query, where
from datetime import datetime, timedelta
from passlib.context import CryptContext
import os

# Setup Database
db = TinyDB('db.json')
users_table = db.table('users')
logs_table = db.table('logs')
system_table = db.table('system')

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

class SystemState:
    def __init__(self):
        state = system_table.get(doc_id=1)
        if not state:
            self.time_offset_seconds = 0
            self.emergency_mode = False
            self.last_updated = datetime.now().timestamp()
            system_table.insert({'time_offset_seconds': 0, 'emergency_mode': False, 'last_updated': self.last_updated})
        else:
            self.time_offset_seconds = state.get('time_offset_seconds', 0)
            self.emergency_mode = state.get('emergency_mode', False)
            self.last_updated = state.get('last_updated', datetime.now().timestamp())

    def get_current_time(self):
        return datetime.now() + timedelta(seconds=self.time_offset_seconds)

    def set_time_offset(self, seconds):
        self.time_offset_seconds = seconds
        system_table.update({'time_offset_seconds': seconds}, doc_ids=[1])
        self.trigger_update()

    def set_emergency(self, is_active):
        self.emergency_mode = is_active
        system_table.update({'emergency_mode': is_active}, doc_ids=[1])
        if is_active:
            users_table.update({'status': 'checkout'})
        self.trigger_update()
            
    def trigger_update(self):
        self.last_updated = datetime.now().timestamp()
        system_table.update({'last_updated': self.last_updated}, doc_ids=[1])

state = SystemState()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def init_db():
    if not users_table.all():
        # Seed Admin
        users_table.insert({
            'username': 'admin',
            'password': get_password_hash('admin'),
            'role': 'admin',
            'name': 'Administrator',
            'salary': 0,
            'position': 'Manager',
            'status': 'checkout',
            'allowed_rooms': ['all'],
            'uid': 'admin_uid',
            'ignore_limit': False
        })
        # Seed User
        users_table.insert({
            'username': 'user1',
            'password': get_password_hash('123'),
            'role': 'user',
            'name': 'Nguyen Van A',
            'salary': 5000000,
            'position': 'Staff',
            'status': 'checkout',
            'allowed_rooms': ['p1', 'p2'],
            'uid': 'user1_uid',
            'ignore_limit': False
        })
        print("Database initialized with default users.")

def get_user_by_username(username):
    User = Query()
    return users_table.get(User.username == username)

def get_user_by_uid(uid):
    User = Query()
    return users_table.get(User.uid == uid)

def get_all_users():
    return users_table.all()

def update_user_status(uid, status):
    User = Query()
    users_table.update({'status': status}, User.uid == uid)
    state.trigger_update()

def update_user_details(doc_id, data):
    if 'password' in data and data['password']:
         data['password'] = get_password_hash(data['password'])
    elif 'password' in data:
        del data['password']
    users_table.update(data, doc_ids=[doc_id])
    state.trigger_update()

def delete_user(doc_id):
    users_table.remove(doc_ids=[doc_id])
    state.trigger_update()

def create_user(data):
    if 'password' in data:
        data['password'] = get_password_hash(data['password'])
    data['status'] = 'checkout'
    data['ignore_limit'] = data.get('ignore_limit', False)
    users_table.insert(data)
    state.trigger_update()

def add_log(uid, action):
    logs_table.insert({
        'uid': uid,
        'action': action,
        'timestamp': state.get_current_time().isoformat()
    })

def get_logs_by_user(uid):
    Log = Query()
    logs = logs_table.search(Log.uid == uid)
    logs.sort(key=lambda x: x['timestamp'], reverse=True)
    return logs

def get_logs_by_month(uid, year, month):
    all_logs = get_logs_by_user(uid)
    return [l for l in all_logs if datetime.fromisoformat(l['timestamp']).year == year and datetime.fromisoformat(l['timestamp']).month == month]

def reset_daily_limit(uid):
    User = Query()
    user = users_table.get(User.uid == uid)
    if user:
        users_table.update({'ignore_limit': True}, doc_ids=[user.doc_id])
        print(f"--- ĐÃ BẬT CỜ MỞ KHOÁ CHO {uid} ---")
        state.trigger_update()
        return True
    return False

def calculate_salary(uid, month, year):
    user = get_user_by_uid(uid)
    # Check explicitly for None or missing salary
    if not user or user.get('salary') is None: return 0
    
    try:
        hourly_rate = float(user['salary'])
    except (ValueError, TypeError):
        return 0
        
    logs = get_logs_by_month(uid, year, month)
    logs.sort(key=lambda x: x['timestamp']) # Sort chronologically
    
    total_salary = 0
    checkin_time = None
    
    # Danh sách ngày lễ Việt Nam (Dương lịch)
    holidays = [
        (1, 1),   # Tết Dương lịch
        (4, 30),  # Giải phóng miền Nam
        (5, 1),   # Quốc tế Lao động
        (9, 2),   # Quốc khánh
    ]
    
    for log in logs:
        t = datetime.fromisoformat(log['timestamp'])
        if log['action'] == 'in':
            checkin_time = t
        elif log['action'] == 'out' and checkin_time:
            # Calculate session
            duration_hours = (t - checkin_time).total_seconds() / 3600
            
            # Logic tăng lương
            multiplier = 1.0
            
            is_holiday = (t.month, t.day) in holidays
            is_weekend = t.weekday() >= 5
            
            if is_holiday:
                multiplier = 3.0 # Ngày lễ: x3
            elif is_weekend:
                multiplier = 2.0 # Cuối tuần: x2
            elif t.hour >= 18:
                multiplier = 1.5 # Ca đêm: x1.5
            
            total_salary += duration_hours * hourly_rate * multiplier
            checkin_time = None
            
    return int(total_salary)

def calculate_daily_stats(uid, target_date):
    """
    Trả về (số giờ làm, lương ngày) cho một ngày cụ thể.
    target_date: datetime.date object
    """
    user = get_user_by_uid(uid)
    if not user or user.get('salary') is None: return 0, 0
    
    try:
        hourly_rate = float(user['salary'])
    except (ValueError, TypeError):
        return 0, 0

    Log = Query()
    all_logs = logs_table.search(Log.uid == uid)
    day_logs = []
    for log in all_logs:
        dt = datetime.fromisoformat(log['timestamp'])
        if dt.date() == target_date:
            day_logs.append(log)
            
    day_logs.sort(key=lambda x: x['timestamp'])
    
    total_hours = 0
    daily_salary = 0
    checkin_time = None
    
    # Logic ngày lễ/cuối tuần áp dụng cho cả ngày
    holidays = [(1, 1), (4, 30), (5, 1), (9, 2)]
    is_holiday = (target_date.month, target_date.day) in holidays
    is_weekend = target_date.weekday() >= 5
    
    for log in day_logs:
        t = datetime.fromisoformat(log['timestamp'])
        if log['action'] == 'in':
            checkin_time = t
        elif log['action'] == 'out' and checkin_time:
            duration = (t - checkin_time).total_seconds() / 3600
            total_hours += duration
            
            multiplier = 1.0
            if is_holiday: multiplier = 3.0
            elif is_weekend: multiplier = 2.0
            elif t.hour >= 18: multiplier = 1.5
            
            daily_salary += duration * hourly_rate * multiplier
            checkin_time = None
            
    return round(total_hours, 1), int(daily_salary)

