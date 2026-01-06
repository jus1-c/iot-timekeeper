import pkgutil
import importlib.util

if not hasattr(pkgutil, 'find_loader'):
    def find_loader(fullname):
        spec = importlib.util.find_spec(fullname)
        return spec.loader if spec else None
    pkgutil.find_loader = find_loader

from nicegui import ui, app

from fastapi import Request
from fastapi.responses import JSONResponse
import db
from datetime import datetime, timedelta
import calendar

# --- API Endpoints ---

@app.post('/check')
async def api_check(request: Request):
    try:
        data = await request.json()
        uid = data.get('uid')
        room = data.get('room')
        
        user = db.get_user_by_uid(uid)
        
        if not user:
            return JSONResponse({'status': 0})
            
        allowed = user.get('allowed_rooms', [])
        if 'all' not in allowed and room not in allowed:
             return JSONResponse({'status': 0})
             
        current_status = user.get('status', 'checkout')
        new_status = 'checkin' if current_status == 'checkout' else 'checkout'
        
        # --- TRIỂN KHAI CÁC QUY ĐỊNH MỚI ---
        
        current_time = db.state.get_current_time()
        
        # 1. Khung giờ khoá: 20:00 đến 05:00 sáng (Chỉ Admin mới có thể check-in)
        if new_status == 'checkin':
            hour = current_time.hour
            if (hour >= 20 or hour < 5):
                if user['role'] != 'admin':
                    print(f"Từ chối check-in cho {user['username']}: Đang trong giờ khoá ({current_time})")
                    return JSONResponse({'status': 0})

        # 2. Quy tắc 1 lần duy nhất: Không thể check-in nếu đã checkout trong ngày hôm nay
        if new_status == 'checkin':
            today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            logs = db.get_logs_by_user(uid)
            
            has_checked_out_today = False
            for log in logs:
                log_dt = datetime.fromisoformat(log['timestamp'])
                if log_dt < today_start:
                    break # Đã xem hết log của ngày hôm nay
                if log['action'] == 'out':
                    has_checked_out_today = True
                    break
            
            if has_checked_out_today:
                print(f"Từ chối check-in cho {user['username']}: Đã hoàn thành 1 lượt check-in/out hôm nay")
                return JSONResponse({'status': 0})

        # --------------------------------
        
        db.update_user_status(uid, new_status)
        db.add_log(uid, 'in' if new_status == 'checkin' else 'out')
        
        return JSONResponse({'status': 1})
        
    except Exception as e:
        print(f"API Error: {e}")
        return JSONResponse({'status': 0})

@app.post('/emegency') # Mispelled as per requirements
def api_emergency():
    db.state.set_emergency(True)
    return JSONResponse({}, status_code=200)

# --- UI Application ---

app.on_startup(db.init_db)

def login_page():
    def try_login():
        print(f"Attempting login with username: {username.value}")
        try:
            user = db.get_user_by_username(username.value)
            print(f"User found: {user is not None}")
            if user:
                print(f"Verifying password...")
                is_valid = db.verify_password(password.value, user['password'])
                print(f"Password valid: {is_valid}")
                if is_valid:
                    app.storage.user['username'] = user['username']
                    app.storage.user['role'] = user['role']
                    app.storage.user['uid'] = user.get('uid')
                    print("Redirecting to /")
                    ui.open('/')
                    return

            print("Login failed")
            ui.notify('Tên đăng nhập hoặc mật khẩu không đúng', color='negative')
        except Exception as e:
            print(f"Login Error: {e}")
            ui.notify(f'Lỗi: {e}', color='negative')

    with ui.card().classes('absolute-center'):
        ui.label('Hệ Thống Chấm Công').classes('text-h5 q-mb-md')
        username = ui.input('Tên đăng nhập').on('keydown.enter', try_login)
        password = ui.input('Mật khẩu', password=True, password_toggle_button=True).on('keydown.enter', try_login)
        ui.button('Đăng nhập', on_click=try_login).classes('full-width q-mt-md')

@ui.page('/login')
def login():
    login_page()

def emergency_header():
    # A notification bar at the top that only shows during emergency
    header = ui.row().classes('w-full justify-center items-center bg-red-600 text-white p-2')
    with header:
        ui.label('CÓ SỰ CỐ KHẨN CẤP! VUI LÒNG SƠ TÁN NGAY LẬP TỨC!').classes('text-h5 font-bold blink')
    
    def update():
        header.set_visibility(db.state.emergency_mode)
    ui.timer(1.0, update)
    return header

# --- User Dashboard Components ---

def render_efficiency_chart(uid):
    chart = ui.echart({
        'xAxis': {'type': 'category', 'data': []},
        'yAxis': {'type': 'value', 'name': 'Giờ'},
        'series': [{'data': [], 'type': 'bar', 'label': {'show': True, 'position': 'top'}}] 
    }).classes('h-[500px] w-full')

    def calculate_hours():
        now = db.state.get_current_time()
        days = []
        hours = []
        
        # Last 7 days
        for i in range(6, -1, -1):
            day = now - timedelta(days=i)
            day_start = datetime(day.year, day.month, day.day)
            day_end = day_start + timedelta(days=1)
            
            # Get logs for this day (This is inefficient but simple for prototype)
            logs = db.get_logs_by_user(uid)
            day_logs = [l for l in logs if day_start <= datetime.fromisoformat(l['timestamp']) < day_end]
            day_logs.sort(key=lambda x: x['timestamp']) # Ascending
            
            worked_seconds = 0
            checkin_time = None
            
            for log in day_logs:
                t = datetime.fromisoformat(log['timestamp'])
                if log['action'] == 'in':
                    checkin_time = t
                elif log['action'] == 'out' and checkin_time:
                    worked_seconds += (t - checkin_time).total_seconds()
                    checkin_time = None
            
            h = round(worked_seconds / 3600, 1)
            days.append(day.strftime('%d/%m'))
            hours.append(h)
            
        return days, hours

    def update():
        d, h = calculate_hours()
        chart.options['xAxis']['data'] = d
        chart.options['series'][0]['data'] = h
        chart.update()

    update()
    # No internal timer here, controlled by parent refresh
    return chart, calculate_hours # Return control to parent

def user_dashboard(user):
    # Shared state
    current_date = db.state.get_current_time()
    view_state = {'year': current_date.year, 'month': current_date.month}
    
    calendar_container = None
    history_container = None
    chart_component = None
    chart_calc_func = None
    status_label = None

    def render_calendar_grid():
        if not calendar_container: return
        calendar_container.clear()
        with calendar_container:
            with ui.row().classes('w-full justify-between items-center'):
                ui.button('<', on_click=lambda: change_month(-1))
                # Việt hoá tên tháng
                ui.label(f"Tháng {view_state['month']} - {view_state['year']}").classes('text-h6')
                ui.button('>', on_click=lambda: change_month(1))
            
            cal = calendar.monthcalendar(view_state['year'], view_state['month'])
            logs = db.get_logs_by_month(user['uid'], view_state['year'], view_state['month'])
            days_with_logs = {datetime.fromisoformat(l['timestamp']).day for l in logs}

            with ui.grid(columns=7).classes('w-full gap-1'):
                for day_name in ['Hai', 'Ba', 'Tư', 'Năm', 'Sáu', 'Bảy', 'CN']:
                    ui.label(day_name).classes('text-center font-bold')
                for week in cal:
                    for day in week:
                        if day == 0:
                            ui.label(''); continue
                        cell_date = datetime(view_state['year'], view_state['month'], day)
                        is_future = cell_date.date() > db.state.get_current_time().date()
                        card = ui.card().classes('items-center justify-center h-16')
                        with card: ui.label(str(day))
                        if is_future: card.classes('bg-grey-3 opacity-50')
                        elif day in days_with_logs: card.classes('bg-green-300')
                        else: card.classes('bg-white')

    def render_history_list():
        if not history_container: return
        history_container.clear()
        with history_container:
            logs = db.get_logs_by_month(user['uid'], view_state['year'], view_state['month'])
            rows = [{'timestamp': datetime.fromisoformat(l['timestamp']).strftime('%Y-%m-%d %H:%M:%S'), 'action': 'VÀO' if l['action'] == 'in' else 'RA'} for l in logs]
            ui.table(columns=[{'name': 'timestamp', 'label': 'Thời gian', 'field': 'timestamp', 'align': 'left'}, {'name': 'action', 'label': 'Hành động', 'field': 'action', 'align': 'left'}], rows=rows, pagination=5).classes('w-full')

    def change_month(delta):
        view_state['month'] += delta
        if view_state['month'] > 12: view_state['month'] = 1; view_state['year'] += 1
        elif view_state['month'] < 1: view_state['month'] = 12; view_state['year'] -= 1
        render_calendar_grid(); render_history_list()

    # Smart Polling State
    last_rendered_ts = {'value': 0}

    def refresh_all():
        render_calendar_grid()
        render_history_list()
        
        if chart_component and chart_calc_func:
            d, h = chart_calc_func()
            chart_component.options['xAxis']['data'] = d
            chart_component.options['series'][0]['data'] = h
            chart_component.update()
            
        if status_label:
            u = db.get_user_by_username(user['username'])
            st = u.get('status', 'checkout')
            status_label.text = 'ĐANG LÀM VIỆC' if st == 'checkin' else 'ĐÃ NGHỈ'
            status_label.classes('bg-green-500 text-white' if st == 'checkin' else 'bg-gray-400 text-white', remove='bg-gray-400 bg-green-500')
        
        last_rendered_ts['value'] = db.state.last_updated

    def check_for_updates():
        if db.state.last_updated > last_rendered_ts['value']:
            refresh_all()

    # Poll for updates
    ui.timer(0.5, check_for_updates)

    with ui.column().classes('w-full q-pa-md'):
        with ui.row().classes('w-full items-center justify-between'):
            with ui.row().classes('items-center gap-4'):
                ui.label(f"Xin chào, {user['name']}").classes('text-h4')
                status_label = ui.label().classes('text-h5 font-bold px-4 py-1 rounded')
            
            # Server Clock
            with ui.column().classes('items-end'):
                ui.label('Thời gian hệ thống').classes('text-caption text-gray-500')
                clock_label = ui.label().classes('text-h5 font-mono')
                def update_clock():
                    clock_label.text = db.state.get_current_time().strftime('%H:%M:%S %d/%m/%Y')
                update_clock() # Initial call
                ui.timer(1.0, update_clock)

        with ui.row().classes('w-full items-start gap-4 no-wrap'):
            with ui.column().classes('w-[350px] shrink-0 gap-4'):
                ui.label('Lịch Chấm Công').classes('text-h6')
                calendar_container = ui.column().classes('w-full')
                ui.separator()
                ui.label('Lịch Sử Theo Tháng').classes('text-h6')
                history_container = ui.column().classes('w-full')

            with ui.column().classes('flex-1 min-w-0'):
                ui.label('Hiệu Suất Tuần').classes('text-h6')
                chart_component, chart_calc_func = render_efficiency_chart(user['uid'])

    refresh_all() # Initial Load

# --- Admin Dashboard Components ---

def admin_dashboard(admin_user):
    with ui.tabs().classes('w-full') as tabs:
        ui.tab('users', label='Người Dùng')
        ui.tab('debug', label='Debug')

    with ui.tab_panels(tabs, value='users').classes('w-full'):
        with ui.tab_panel('users'):
            render_user_management()
        with ui.tab_panel('debug'):
            render_debug_panel()

def render_user_management():
    # State to track if a dialog is open to pause refreshing
    is_dialog_open = {'value': False}

    def edit_user(u):
        is_dialog_open['value'] = True
        with ui.dialog() as dialog, ui.card():
            ui.label(f"Sửa Người Dùng: {u['username']}").classes('text-h6')
            name = ui.input('Họ Tên', value=u.get('name'))
            uid_field = ui.input('UID (Mã thẻ)', value=u.get('uid'))
            salary = ui.number('Lương', value=u.get('salary'))
            position = ui.input('Chức Vụ', value=u.get('position'))
            role = ui.select(['user', 'admin'], value=u.get('role'), label='Vai Trò')
            status = ui.select(['checkin', 'checkout'], value=u.get('status'), label='Trạng Thái')
            rooms_str = ui.input('Phòng được phép (phân cách dấu phẩy)', value=','.join(u.get('allowed_rooms', [])))
            
            def save():
                rooms = [r.strip() for r in rooms_str.value.split(',')]
                db.update_user_details(u.doc_id, {
                    'name': name.value,
                    'uid': uid_field.value,
                    'salary': salary.value,
                    'position': position.value,
                    'role': role.value,
                    'status': status.value,
                    'allowed_rooms': rooms
                })
                dialog.close()
                is_dialog_open['value'] = False
                refresh_list()
                ui.notify('Đã Lưu')
            
            def close():
                dialog.close()
                is_dialog_open['value'] = False

            with ui.row():
                ui.button('Lưu', on_click=save)
                ui.button('Huỷ', on_click=close)
            
            dialog.open()

    def delete_user_confirm(u):
        is_dialog_open['value'] = True
        with ui.dialog() as dialog, ui.card():
            ui.label(f"Xoá {u['username']}?")
            with ui.row():
                def confirm():
                    db.delete_user(u.doc_id)
                    dialog.close()
                    is_dialog_open['value'] = False
                    refresh_list()
                
                def close():
                    dialog.close()
                    is_dialog_open['value'] = False
                    
                ui.button('Có', color='red', on_click=confirm)
                ui.button('Không', on_click=close)
            dialog.open()
            
    def add_user_dialog():
        is_dialog_open['value'] = True
        with ui.dialog() as dialog, ui.card():
            ui.label('Thêm Người Dùng Mới').classes('text-h6')
            username = ui.input('Tên đăng nhập')
            password = ui.input('Mật khẩu')
            name = ui.input('Họ tên')
            uid_field = ui.input('UID (Mã thẻ)')
            
            def create():
                if not username.value or not password.value or not uid_field.value:
                    ui.notify('Thiếu thông tin bắt buộc', color='red')
                    return
                db.create_user({
                    'username': username.value,
                    'password': password.value,
                    'name': name.value,
                    'uid': uid_field.value,
                    'role': 'user',
                    'allowed_rooms': [],
                    'salary': 0,
                    'position': 'Nhân viên'
                })
                dialog.close()
                is_dialog_open['value'] = False
                refresh_list()
            
            def close():
                dialog.close()
                is_dialog_open['value'] = False

            with ui.row():
                ui.button('Tạo', on_click=create)
                ui.button('Huỷ', on_click=close)
            dialog.open()

    # Container
    user_list_container = ui.column().classes('w-full gap-2')

    def refresh_list():
        # Don't refresh if user is interacting with a dialog
        if is_dialog_open['value']:
            return

        user_list_container.clear()
        users = db.get_all_users()
        with user_list_container:
            ui.button('Thêm Người Dùng', on_click=add_user_dialog).classes('bg-blue-500 text-white')
            
            # Header
            with ui.row().classes('w-full font-bold bg-gray-200 p-2'):
                ui.label('Họ Tên').classes('w-1/4')
                ui.label('Vai Trò').classes('w-1/4')
                ui.label('Trạng Thái').classes('w-1/4')
                ui.label('Hành Động').classes('w-1/4')
                
            for u in users:
                with ui.row().classes('w-full items-center border-b p-2'):
                    ui.label(u.get('name', 'N/A')).classes('w-1/4')
                    ui.label(u.get('role')).classes('w-1/4')
                    
                    st = u.get('status', 'checkout')
                    lbl = ui.label(st).classes('w-1/4')
                    if st == 'checkin': lbl.classes('text-green-600 font-bold')
                    
                    with ui.row().classes('w-1/4 gap-2'):
                        ui.button('Sửa', on_click=lambda u=u: edit_user(u)).props('size=sm')
                        ui.button('Xoá', color='red', on_click=lambda u=u: delete_user_confirm(u)).props('size=sm')

    refresh_list()
    
    # Smart Polling
    last_rendered_ts = {'value': db.state.last_updated}
    
    def check_for_updates():
        if db.state.last_updated > last_rendered_ts['value']:
            if not is_dialog_open['value']:
                refresh_list()
                last_rendered_ts['value'] = db.state.last_updated
                
    ui.timer(0.5, check_for_updates)

def render_debug_panel():
    with ui.column().classes('p-4'):
        ui.label('Debug Console').classes('text-h5')
        
        # System Time
        ui.label('Mô Phỏng Thời Gian Hệ Thống').classes('text-h6 mt-4')
        ui.label('Đặt Thời Gian Tùy Chỉnh:')
        
        with ui.row().classes('items-center gap-2'):
            date_input = ui.input('Ngày', value=datetime.now().strftime('%Y-%m-%d'))
            with date_input.add_slot('append'):
                ui.icon('event').classes('cursor-pointer').on('click', lambda: date_menu.open())
                with ui.menu() as date_menu:
                    ui.date().bind_value(date_input)
            
            time_input = ui.input('Giờ', value=datetime.now().strftime('%H:%M'))
            with time_input.add_slot('append'):
                ui.icon('access_time').classes('cursor-pointer').on('click', lambda: time_menu.open())
                with ui.menu() as time_menu:
                    ui.time().bind_value(time_input)
            
            def apply_time():
                try:
                    target_str = f"{date_input.value} {time_input.value}"
                    target_dt = datetime.strptime(target_str, '%Y-%m-%d %H:%M')
                    real_now = datetime.now()
                    offset = (target_dt - real_now).total_seconds()
                    db.state.set_time_offset(int(offset))
                    ui.notify(f"Thời gian đã đặt: {target_dt}")
                    update_offset_label()
                except Exception as e:
                    ui.notify(f"Lỗi định dạng ngày/giờ: {e}", color='red')

            ui.button('Áp dụng', on_click=apply_time)
            
            ui.button('Reset về Thực Tế', on_click=lambda: [db.state.set_time_offset(0), update_offset_label()], color='grey')

        offset_label = ui.label().classes('q-mt-md font-bold text-lg')
        
        def update_offset_label():
            current_sim = db.state.get_current_time()
            offset_label.text = f"Thời Gian Hệ Thống Hiện Tại: {current_sim.strftime('%Y-%m-%d %H:%M:%S')}"
            
        update_offset_label()
        ui.timer(1.0, update_offset_label) # Clock tick

        # Emergency
        ui.label('Điều Khiển Khẩn Cấp').classes('text-h6 mt-4')
        
        def toggle_emergency():
            # Only allow turning OFF here, turning ON is via API usually, but let's allow both for debug
            new_state = not db.state.emergency_mode
            db.state.set_emergency(new_state)
            
        em_btn = ui.button('Bật/Tắt Logic Khẩn Cấp', on_click=toggle_emergency)
        
        def update_btn():
            if db.state.emergency_mode:
                em_btn.props('color=red label="TẮT KHẨN CẤP"')
            else:
                em_btn.props('color=green label="Kích Hoạt Khẩn Cấp (Debug)"')
        
        ui.timer(0.5, update_btn)

# --- Main Page ---

@ui.page('/')
def main_page():
    # Auth Check
    if not app.storage.user.get('username'):
        ui.open('/login')
        return

    db.init_db()
    
    ui.add_head_html('''
        <style>
        .blink { animation: blinker 1s linear infinite; }
        @keyframes blinker { 50% { opacity: 0; } }
        .blink-bg { background-color: #ff0000 !important; }
        .emergency-active { background-color: #ffebee !important; }
        .emergency-active .q-header, .emergency-active .bg-white { background-color: #ffcdd2 !important; }
        </style>
    ''')

    main_container = ui.column().classes('w-full min-h-screen items-center bg-gray-100 transition-colors duration-500')
    
    def update_emergency_ui():
        if db.state.emergency_mode:
            main_container.classes('emergency-active')
        else:
            main_container.classes(remove='emergency-active')
            
    ui.timer(1.0, update_emergency_ui)

    with main_container:
        emergency_header()
        
        # Header
        with ui.row().classes('w-full bg-white shadow p-4 justify-between items-center'):
            ui.label('Hệ Thống Chấm Công').classes('text-h5')
            with ui.row().classes('items-center gap-4'):
                ui.label(app.storage.user['username'])
                ui.button('Đăng Xuất', on_click=lambda: (app.storage.user.clear(), ui.open('/login'))).props('flat')

        # Content
        role = app.storage.user.get('role')
        if role == 'admin':
            admin_dashboard(app.storage.user)
        else:
            # Need to get full user details for the dashboard
            user_full = db.get_user_by_username(app.storage.user['username'])
            if user_full:
                user_dashboard(user_full)
            else:
                ui.label('Lỗi dữ liệu người dùng')

ui.run(storage_secret='my-secret-key-123', port=8081)