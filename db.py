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
        # If emergency is triggered, checkout all users
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
            'uid': 'admin_uid' 
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
            'uid': 'user1_uid'
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
    # Only update provided fields
    if 'password' in data and data['password']:
         data['password'] = get_password_hash(data['password'])
    elif 'password' in data:
        del data['password'] # Don't update if empty
        
    users_table.update(data, doc_ids=[doc_id])
    state.trigger_update()

def delete_user(doc_id):
    users_table.remove(doc_ids=[doc_id])
    state.trigger_update()

def create_user(data):
    data['password'] = get_password_hash(data['password'])
    data['status'] = 'checkout' # Default
    users_table.insert(data)
    state.trigger_update()

def add_log(uid, action):
    logs_table.insert({
        'uid': uid,
        'action': action, # 'in' or 'out'
        'timestamp': state.get_current_time().isoformat()
    })

def get_logs_by_user(uid):
    Log = Query()
    # TinyDB doesn't sort by default, we'll sort in memory
    logs = logs_table.search(Log.uid == uid)
    logs.sort(key=lambda x: x['timestamp'], reverse=True)
    return logs

def get_logs_by_month(uid, year, month):
    # Filter logs for a specific month
    all_logs = get_logs_by_user(uid)
    filtered = []
    for log in all_logs:
        dt = datetime.fromisoformat(log['timestamp'])
        if dt.year == year and dt.month == month:
            filtered.append(log)
    return filtered
