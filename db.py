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
        create_user({
            'username': 'admin',
            'password': 'admin',
            'role': 'admin',
            'name': 'Administrator',
            'salary': 200000,
            'position': 'Manager',
            'uid': 'admin_uid'
        })
        print("Database initialized.")

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

def add_log(username, action):
    logs_table.insert({
        'username': username,
        'action': action,
        'timestamp': state.get_current_time().isoformat()
    })

def get_logs_by_username(username):
    Log = Query()
    logs = logs_table.search(Log.username == username)
    logs.sort(key=lambda x: x['timestamp'], reverse=True)
    return logs

def get_logs_by_month(username, year, month):
    all_logs = get_logs_by_username(username)
    return [l for l in all_logs if datetime.fromisoformat(l['timestamp']).year == year and datetime.fromisoformat(l['timestamp']).month == month]

def reset_daily_limit(username):
    curr_time = state.get_current_time()
    today = curr_time.date()
    User = Query()
    user = users_table.get(User.username == username)
    
    all_logs = logs_table.search(where('username') == username)
    ids_to_remove = [log.doc_id for log in all_logs if datetime.fromisoformat(log['timestamp']).date() == today]
    if ids_to_remove:
        logs_table.remove(doc_ids=ids_to_remove)

    if user:
        users_table.update({'ignore_limit': True}, doc_ids=[user.doc_id])
        state.trigger_update()
        return True
    return False

def calculate_salary(username, month, year):
    user = get_user_by_username(username)
    if not user or user.get('salary') is None: return 0
    try:
        hourly_rate = float(user['salary'])
    except:
        return 0
        
    logs = get_logs_by_month(username, year, month)
    logs.sort(key=lambda x: x['timestamp']) 
    
    total_salary = 0
    checkin_time = None
    holidays = [(1, 1), (4, 30), (5, 1), (9, 2)]
    
    for log in logs:
        t = datetime.fromisoformat(log['timestamp'])
        if log['action'] == 'in':
            checkin_time = t
        elif log['action'] == 'out' and checkin_time:
            duration = (t - checkin_time).total_seconds() / 3600
            multiplier = 1.0
            if (t.month, t.day) in holidays: multiplier = 3.0
            elif t.weekday() >= 5: multiplier = 2.0
            elif t.hour >= 18: multiplier = 1.5
            total_salary += duration * hourly_rate * multiplier
            checkin_time = None
    return int(total_salary)

def calculate_daily_stats(username, target_date):
    user = get_user_by_username(username)
    if not user or user.get('salary') is None: return 0, 0
    try:
        hourly_rate = float(user['salary'])
    except:
        return 0, 0
    Log = Query()
    all_logs = logs_table.search(Log.username == username)
    day_logs = [log for log in all_logs if datetime.fromisoformat(log['timestamp']).date() == target_date]
    day_logs.sort(key=lambda x: x['timestamp'])
    total_hours, daily_salary, checkin_time = 0, 0, None
    holidays = [(1, 1), (4, 30), (5, 1), (9, 2)]
    for log in day_logs:
        t = datetime.fromisoformat(log['timestamp'])
        if log['action'] == 'in': checkin_time = t
        elif log['action'] == 'out' and checkin_time:
            duration = (t - checkin_time).total_seconds() / 3600
            total_hours += duration
            multiplier = 1.0
            if (t.month, t.day) in holidays: multiplier = 3.0
            elif t.weekday() >= 5: multiplier = 2.0
            elif t.hour >= 18: multiplier = 1.5
            daily_salary += duration * hourly_rate * multiplier
            checkin_time = None
    return round(total_hours, 1), int(daily_salary)
