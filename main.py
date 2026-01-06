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
        if not user: return JSONResponse({'status': 0})
            
        allowed = user.get('allowed_rooms', [])
        if 'all' not in allowed and room not in allowed: return JSONResponse({'status': 0})
             
        current_status = user.get('status', 'checkout')
        new_status = 'checkin' if current_status == 'checkout' else 'checkout'
        current_time = db.state.get_current_time()
        
        # --- TRIỂN KHAI CÁC QUY ĐỊNH MỚI ---
        if new_status == 'checkin':
            # 1. Khung giờ khoá: 20:00 đến 05:00 sáng
            if (current_time.hour >= 20 or current_time.hour < 5) and user['role'] != 'admin':
                print(f"Từ chối check-in cho {user['username']}: Đang trong giờ khoá")
                return JSONResponse({'status': 0})

            # 2. Quy tắc 1 lần duy nhất trong ngày
            today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            if any(datetime.fromisoformat(l['timestamp']) >= today_start and l['action'] == 'out' for l in db.get_logs_by_user(uid)):
                print(f"Từ chối check-in cho {user['username']}: Đã checkout hôm nay")
                return JSONResponse({'status': 0})

        db.update_user_status(uid, new_status)
        db.add_log(uid, 'in' if new_status == 'checkin' else 'out')
        return JSONResponse({'status': 1})
    except Exception as e:
        print(f"API Error: {e}")
        return JSONResponse({'status': 0})

@app.post('/emegency')
def api_emergency():
    db.state.set_emergency(True)
    return JSONResponse({}, status_code=200)

# --- UI Application ---

app.on_startup(db.init_db)

def login_page():
    def try_login():
        try:
            user = db.get_user_by_username(username.value)
            if user and db.verify_password(password.value, user['password']):
                app.storage.user.update({'username': user['username'], 'role': user['role'], 'uid': user.get('uid')})
                ui.navigate.to('/')
            else:
                ui.notify('Tên đăng nhập hoặc mật khẩu không đúng', color='negative')
        except Exception as e:
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
    header = ui.row().classes('w-full justify-center items-center bg-red-600 text-white p-2')
    with header: ui.label('CÓ SỰ CỐ KHẨN CẤP! VUI LÒNG SƠ TÁN NGAY LẬP TỨC!').classes('text-h5 font-bold blink')
    ui.timer(1.0, lambda: header.set_visibility(db.state.emergency_mode))
    return header

def render_efficiency_chart(uid):
    chart = ui.echart({
        'xAxis': {'type': 'category', 'data': []},
        'yAxis': {'type': 'value', 'name': 'Giờ'},
        'series': [{'data': [], 'type': 'bar', 'label': {'show': True, 'position': 'top'}}] 
    }).classes('h-[500px] w-full')

    def calculate_hours():
        now = db.state.get_current_time()
        days, hours = [], []
        for i in range(6, -1, -1):
            day = now - timedelta(days=i)
            day_start = datetime(day.year, day.month, day.day)
            day_end = day_start + timedelta(days=1)
            logs = sorted([l for l in db.get_logs_by_user(uid) if day_start <= datetime.fromisoformat(l['timestamp']) < day_end], key=lambda x: x['timestamp'])
            worked, checkin = 0, None
            for log in logs:
                if log['action'] == 'in': checkin = datetime.fromisoformat(log['timestamp'])
                elif log['action'] == 'out' and checkin:
                    worked += (datetime.fromisoformat(log['timestamp']) - checkin).total_seconds()
                    checkin = None
            days.append(day.strftime('%d/%m')); hours.append(round(worked / 3600, 1))
        return days, hours
    return chart, calculate_hours

def user_dashboard(user):
    view_state = {'year': db.state.get_current_time().year, 'month': db.state.get_current_time().month}
    calendar_container, history_container, status_label = None, None, None
    chart_comp, chart_calc = None, None

    def render_calendar_grid():
        if not calendar_container: return
        calendar_container.clear()
        with calendar_container:
            with ui.row().classes('w-full justify-between items-center'):
                ui.button('<', on_click=lambda: change_month(-1))
                ui.label(f"Tháng {view_state['month']} - {view_state['year']}").classes('text-h6')
                ui.button('>', on_click=lambda: change_month(1))
            
            cal = calendar.monthcalendar(view_state['year'], view_state['month'])
            logs = db.get_logs_by_month(user['uid'], view_state['year'], view_state['month'])
            days_with_logs = {datetime.fromisoformat(l['timestamp']).day for l in logs}
            with ui.grid(columns=7).classes('w-full gap-1'):
                for day_name in ['Hai', 'Ba', 'Tư', 'Năm', 'Sáu', 'Bảy', 'CN']: ui.label(day_name).classes('text-center font-bold')
                for week in cal:
                    for day in week:
                        if day == 0: ui.label(''); continue
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

    last_ts = {'v': 0}
    def refresh_all():
        render_calendar_grid(); render_history_list()
        if chart_comp:
            d, h = chart_calc()
            chart_comp.options['xAxis']['data'] = d
            chart_comp.options['series'][0]['data'] = h
            chart_comp.update()
        if status_label:
            st = db.get_user_by_username(user['username']).get('status', 'checkout')
            status_label.text = 'ĐANG LÀM VIỆC' if st == 'checkin' else 'ĐÃ NGHỈ'
            status_label.classes('bg-green-500 text-white' if st == 'checkin' else 'bg-gray-400 text-white', remove='bg-gray-400 bg-green-500')
        last_ts['v'] = db.state.last_updated

    ui.timer(0.5, lambda: refresh_all() if db.state.last_updated > last_ts['v'] else None)

    with ui.column().classes('w-full q-pa-md'):
        with ui.row().classes('w-full items-center justify-between'):
            with ui.row().classes('items-center gap-4'):
                ui.label(f"Xin chào, {user['name']}").classes('text-h4')
                status_label = ui.label().classes('text-h5 font-bold px-4 py-1 rounded')
            with ui.column().classes('items-end'):
                ui.label('Thời gian hệ thống').classes('text-caption text-gray-500')
                clock_label = ui.label().classes('text-h5 font-mono')
                def up_clock(): clock_label.text = db.state.get_current_time().strftime('%H:%M:%S %d/%m/%Y')
                ui.timer(1.0, up_clock); up_clock()

        with ui.row().classes('w-full items-start gap-4 no-wrap'):
            with ui.column().classes('w-[350px] shrink-0 gap-4'):
                ui.label('Lịch Chấm Công').classes('text-h6')
                calendar_container = ui.column().classes('w-full'); render_calendar_grid()
                ui.separator()
                ui.label('Lịch Sử Theo Tháng').classes('text-h6')
                history_container = ui.column().classes('w-full'); render_history_list()
            with ui.column().classes('flex-1 min-w-0'):
                ui.label('Hiệu Suất Tuần').classes('text-h6')
                chart_comp, chart_calc = render_efficiency_chart(user['uid'])
    refresh_all()

# --- Admin Dashboard Components ---

def admin_dashboard(admin_user):
    with ui.tabs().classes('w-full') as tabs:
        ui.tab('users', label='Người Dùng')
        ui.tab('debug', label='Debug')
    with ui.tab_panels(tabs, value='users').classes('w-full'):
        with ui.tab_panel('users'): render_user_management()
        with ui.tab_panel('debug'): render_debug_panel()

def render_user_management():
    is_dialog_open = {'value': False}
    def edit_user(u):
        is_dialog_open['value'] = True
        with ui.dialog() as dialog, ui.card():
            ui.label(f"Sửa Người Dùng: {u['username']}").classes('text-h6')
            name = ui.input('Họ Tên', value=u.get('name'))
            uid_f = ui.input('UID (Mã thẻ)', value=u.get('uid'))
            salary = ui.number('Lương', value=u.get('salary'))
            position = ui.input('Chức Vụ', value=u.get('position'))
            role = ui.select(['user', 'admin'], value=u.get('role'), label='Vai Trò')
            status = ui.select(['checkin', 'checkout'], value=u.get('status'), label='Trạng Thái')
            rooms_str = ui.input('Phòng được phép', value=','.join(u.get('allowed_rooms', [])))
            def save():
                db.update_user_details(u.doc_id, {'name': name.value, 'uid': uid_f.value, 'salary': salary.value, 'position': position.value, 'role': role.value, 'status': status.value, 'allowed_rooms': [r.strip() for r in rooms_str.value.split(',')]})
                dialog.close(); is_dialog_open['value'] = False; refresh_list(); ui.notify('Đã Lưu')
            with ui.row(): ui.button('Lưu', on_click=save); ui.button('Huỷ', on_click=lambda: [dialog.close(), setattr(is_dialog_open, 'value', False)])
            dialog.open()

    def delete_user_confirm(u):
        is_dialog_open['value'] = True
        with ui.dialog() as dialog, ui.card():
            ui.label(f"Xoá {u['username']}?")
            with ui.row():
                ui.button('Có', color='red', on_click=lambda: [db.delete_user(u.doc_id), dialog.close(), setattr(is_dialog_open, 'value', False), refresh_list()])
                ui.button('Không', on_click=lambda: [dialog.close(), setattr(is_dialog_open, 'value', False)])
            dialog.open()

    def add_user_dialog():
        is_dialog_open['value'] = True
        with ui.dialog() as dialog, ui.card():
            ui.label('Thêm Người Dùng Mới').classes('text-h6')
            username, password, name, uid_f = ui.input('Tên đăng nhập'), ui.input('Mật khẩu'), ui.input('Họ tên'), ui.input('UID (Mã thẻ)')
            def create():
                if not username.value or not password.value or not uid_f.value: return ui.notify('Thiếu thông tin', color='red')
                db.create_user({'username': username.value, 'password': password.value, 'name': name.value, 'uid': uid_f.value, 'role': 'user', 'allowed_rooms': [], 'salary': 0, 'position': 'Nhân viên'})
                dialog.close(); is_dialog_open['value'] = False; refresh_list()
            with ui.row(): ui.button('Tạo', on_click=create); ui.button('Huỷ', on_click=lambda: [dialog.close(), setattr(is_dialog_open, 'value', False)])
            dialog.open()

    user_list_container = ui.column().classes('w-full gap-2')
    def refresh_list():
        if is_dialog_open['value']: return
        user_list_container.clear()
        users = db.get_all_users()
        with user_list_container:
            ui.button('Thêm Người Dùng', on_click=add_user_dialog).classes('bg-blue-500 text-white')
            with ui.row().classes('w-full font-bold bg-gray-200 p-2'):
                ui.label('Họ Tên').classes('w-1/4'); ui.label('Vai Trò').classes('w-1/4'); ui.label('Trạng Thái').classes('w-1/4'); ui.label('Hành Động').classes('w-1/4')
            for u in users:
                with ui.row().classes('w-full items-center border-b p-2'):
                    ui.label(u.get('name', 'N/A')).classes('w-1/4'); ui.label(u.get('role')).classes('w-1/4')
                    st = u.get('status', 'checkout')
                    lbl = ui.label(st).classes('w-1/4')
                    if st == 'checkin': lbl.classes('text-green-600 font-bold')
                    with ui.row().classes('w-1/4 gap-2'):
                        ui.button('Sửa', on_click=lambda u=u: edit_user(u)).props('size=sm')
                        ui.button('Xoá', color='red', on_click=lambda u=u: delete_user_confirm(u)).props('size=sm')
    refresh_list()
    last_ts = {'v': db.state.last_updated}
    ui.timer(0.5, lambda: [refresh_list(), last_ts.update({'v': db.state.last_updated})] if db.state.last_updated > last_ts['v'] and not is_dialog_open['value'] else None)

def render_debug_panel():
    with ui.column().classes('p-4'):
        ui.label('Debug Console').classes('text-h5')
        ui.label('Mô Phỏng Thời Gian Hệ Thống').classes('text-h6 mt-4')
        with ui.row().classes('items-center gap-2'):
            date_in = ui.input('Ngày', value=datetime.now().strftime('%Y-%m-%d'))
            with date_in.add_slot('append'):
                ui.icon('event').classes('cursor-pointer').on('click', lambda: date_menu.open())
                with ui.menu() as date_menu: ui.date().bind_value(date_in)
            time_in = ui.input('Giờ', value=datetime.now().strftime('%H:%M'))
            with time_in.add_slot('append'):
                ui.icon('access_time').classes('cursor-pointer').on('click', lambda: time_menu.open())
                with ui.menu() as time_menu: ui.time().bind_value(time_in)
            def apply_t():
                try:
                    offset = (datetime.strptime(f"{date_in.value} {time_in.value}", '%Y-%m-%d %H:%M') - datetime.now()).total_seconds()
                    db.state.set_time_offset(int(offset)); ui.notify('Đã đặt thời gian')
                except Exception as e: ui.notify(f"Lỗi: {e}", color='red')
            ui.button('Áp dụng', on_click=apply_t)
            ui.button('Reset', on_click=lambda: db.state.set_time_offset(0), color='grey')
        offset_lbl = ui.label().classes('q-mt-md font-bold text-lg')
        def up_l(): offset_lbl.text = f"Thời Gian Hệ Thống: {db.state.get_current_time().strftime('%Y-%m-%d %H:%M:%S')}"
        ui.timer(1.0, up_l); up_l()
        ui.label('Điều Khiển Khẩn Cấp').classes('text-h6 mt-4')
        em_btn = ui.button('', on_click=lambda: db.state.set_emergency(not db.state.emergency_mode))
        def up_btn():
            em_btn.props(f'color={"red" if db.state.emergency_mode else "green"} label="{"TẮT KHẨN CẤP" if db.state.emergency_mode else "Kích Hoạt Khẩn Cấp"}"')
        ui.timer(0.5, up_btn)

@ui.page('/')
def main_page():
    if not app.storage.user.get('username'): ui.navigate.to('/login'); return
    db.init_db()
    ui.add_head_html('<style>.blink { animation: blinker 1s linear infinite; } @keyframes blinker { 50% { opacity: 0; } } .emergency-active { background-color: #ffebee !important; } .emergency-active .q-header, .emergency-active .bg-white { background-color: #ffcdd2 !important; }</style>')
    main_c = ui.column().classes('w-full min-h-screen items-center bg-gray-100 transition-colors duration-500')
    ui.timer(1.0, lambda: main_c.classes('emergency-active' if db.state.emergency_mode else '', remove='emergency-active' if not db.state.emergency_mode else ''))
    with main_c:
        emergency_header()
        with ui.row().classes('w-full bg-white shadow p-4 justify-between items-center'):
            ui.label('Hệ Thống Chấm Công').classes('text-h5')
            with ui.row().classes('items-center gap-4'):
                ui.label(app.storage.user['username'])
                ui.button('Đăng Xuất', on_click=lambda: [app.storage.user.clear(), ui.navigate.to('/login')]).props('flat')
        role = app.storage.user.get('role')
        if role == 'admin': admin_dashboard(app.storage.user)
        else:
            user_full = db.get_user_by_username(app.storage.user['username'])
            if user_full: user_dashboard(user_full)
            else: ui.label('Lỗi dữ liệu')

ui.run(storage_secret='my-secret-key-123', port=8081)
