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
        uid, room = data.get('uid'), data.get('room')
        user = db.get_user_by_uid(uid)
        if not user: return JSONResponse({'status': 0})
        uname = user['username']
        allowed = user.get('allowed_rooms', [])
        if 'all' not in allowed and room not in allowed: return JSONResponse({'status': 0})
        current_status = user.get('status', 'checkout')
        new_status = 'checkin' if current_status == 'checkout' else 'checkout'
        current_time = db.state.get_current_time()
        
        if new_status == 'checkin':
            # 1. Cờ hiệu mở khoá (Ưu tiên cao nhất)
            if user.get('ignore_limit'):
                print(f"Chấp nhận check-in cho {uname} do Admin đã mở khoá")
                db.update_user_details(user.doc_id, {'ignore_limit': False})
            else:
                # 2. Khung giờ khoá: 20:00 đến 05:00 sáng
                if (current_time.hour >= 20 or current_time.hour < 5) and user['role'] != 'admin':
                    return JSONResponse({'status': 0})
                
                # 3. Quy tắc 1 lần duy nhất trong ngày
                today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                if any(datetime.fromisoformat(l['timestamp']) >= today_start and l['action'] == 'out' for l in db.get_logs_by_username(uname)):
                    return JSONResponse({'status': 0})
        
        db.update_user_status(uid, new_status)
        db.add_log(uname, 'in' if new_status == 'checkin' else 'out')
        return JSONResponse({'status': 1})
    except: return JSONResponse({'status': 0})

@app.post('/emegency')
def api_emergency():
    db.state.set_emergency(True)
    return JSONResponse({}, status_code=200)

app.on_startup(db.init_db)

# --- Background Tasks ---
def check_auto_checkout():
    # Kiểm tra mỗi phút, nếu là 5:00 sáng thì force checkout
    now = db.state.get_current_time()
    if now.hour == 5 and now.minute == 0:
        db.force_checkout_all()

ui.timer(60.0, check_auto_checkout)

@ui.page('/login')
def login():
    def try_login():
        user = db.get_user_by_username(username.value)
        if user and db.verify_password(password.value, user['password']):
            app.storage.user.update({'username': user['username'], 'role': user['role']})
            ui.open('/')
        else: ui.notify('Sai tài khoản hoặc mật khẩu', color='negative')
    with ui.card().classes('absolute-center'):
        ui.label('Hệ Thống Chấm Công').classes('text-h5 q-mb-md')
        username = ui.input('Tên đăng nhập').on('keydown.enter', try_login)
        password = ui.input('Mật khẩu', password=True, password_toggle_button=True).on('keydown.enter', try_login)
        ui.button('Đăng nhập', on_click=try_login).classes('full-width q-mt-md')

def user_dashboard(user):
    uname = user['username']
    view_state = {'year': db.state.get_current_time().year, 'month': db.state.get_current_time().month}
    calendar_container, history_container, status_label, salary_label = None, None, None, None
    def render_calendar_grid():
        if not calendar_container: return
        calendar_container.clear()
        with calendar_container:
            with ui.row().classes('w-full justify-between items-center'):
                ui.button('<', on_click=lambda: change_month(-1))
                ui.label(f"Tháng {view_state['month']} - {view_state['year']}").classes('text-h6')
                ui.button('>', on_click=lambda: change_month(1))
            cal = calendar.monthcalendar(view_state['year'], view_state['month'])
            logs = db.get_logs_by_month(uname, view_state['year'], view_state['month'])
            days_with_logs = {datetime.fromisoformat(l['timestamp']).day for l in logs}
            with ui.grid(columns=7).classes('w-full gap-1'):
                for day_name in ['Hai', 'Ba', 'Tư', 'Năm', 'Sáu', 'Bảy', 'CN']: ui.label(day_name).classes('text-center font-bold')
                for week in cal:
                    for day in week:
                        if day == 0: ui.label(''); continue
                        cell_date = datetime(view_state['year'], view_state['month'], day)
                        is_future = cell_date.date() > db.state.get_current_time().date()
                        card = ui.card().classes('items-center justify-center h-16 relative group')
                        with card: 
                            ui.label(str(day))
                            if day in days_with_logs:
                                h, p = db.calculate_daily_stats(uname, cell_date.date())
                                ui.tooltip(f"Giờ làm: {h}h | Lương: {p:,}đ").classes('bg-black text-white p-2')
                        if is_future: card.classes('bg-grey-3 opacity-50')
                        elif day in days_with_logs: card.classes('bg-green-300 cursor-pointer')
                        else: card.classes('bg-white')
    def render_history_list():
        if not history_container: return
        history_container.clear()
        with history_container:
            logs = db.get_logs_by_month(uname, view_state['year'], view_state['month'])
            rows = [{'timestamp': datetime.fromisoformat(l['timestamp']).strftime('%Y-%m-%d %H:%M:%S'), 'action': 'VÀO' if l['action'] == 'in' else 'RA'} for l in logs]
            ui.table(columns=[{'name': 't', 'label': 'Thời gian', 'field': 'timestamp'}, {'name': 'a', 'label': 'Hành động', 'field': 'action'}], rows=rows, pagination=5).classes('w-full')
    def change_month(delta):
        view_state['month'] += delta
        if view_state['month'] > 12: view_state['month'] = 1; view_state['year'] += 1
        elif view_state['month'] < 1: view_state['month'] = 12; view_state['year'] -= 1
        render_calendar_grid(); render_history_list(); refresh_salary()
    def refresh_salary():
        if salary_label: salary_label.text = f"Lương tháng {view_state['month']}: {db.calculate_salary(uname, view_state['month'], view_state['year']):,} VNĐ"
    last_ts = {'v': 0}
    def refresh_all():
        render_calendar_grid(); render_history_list(); refresh_salary()
        if status_label:
            st = db.get_user_by_username(uname).get('status', 'checkout')
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
                clock_label = ui.label().classes('text-h5 font-mono')
                salary_label = ui.label().classes('text-lg text-green-600 font-bold')
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
                chart = ui.echart({'xAxis': {'type': 'category', 'data': []}, 'yAxis': {'type': 'value', 'name': 'Giờ'}, 'series': [{'data': [], 'type': 'bar', 'label': {'show': True, 'position': 'top'}}]}).classes('h-[500px] w-full')
                def up_chart():
                    now = db.state.get_current_time()
                    d, h = [], []
                    for i in range(6, -1, -1):
                        day = now - timedelta(days=i)
                        day_start, day_end = datetime(day.year, day.month, day.day), datetime(day.year, day.month, day.day) + timedelta(days=1)
                        logs = sorted([l for l in db.get_logs_by_username(uname) if day_start <= datetime.fromisoformat(l['timestamp']) < day_end], key=lambda x: x['timestamp'])
                        worked, checkin = 0, None
                        for l in logs:
                            if l['action'] == 'in': checkin = datetime.fromisoformat(l['timestamp'])
                            elif l['action'] == 'out' and checkin: worked += (datetime.fromisoformat(l['timestamp']) - checkin).total_seconds(); checkin = None
                        d.append(day.strftime('%d/%m')); h.append(round(worked / 3600, 1))
                    chart.options['xAxis']['data'] = d; chart.options['series'][0]['data'] = h; chart.update()
                ui.timer(5.0, up_chart); up_chart()
    refresh_all()

def admin_dashboard(user):
    with ui.tabs().classes('w-full') as tabs:
        ui.tab('users', label='Người Dùng'); ui.tab('debug', label='Debug')
    with ui.tab_panels(tabs, value='users').classes('w-full'):
        with ui.tab_panel('users'):
            is_dialog_open = {'v': False}
            user_list_container = ui.column().classes('w-full gap-2')
            def refresh_list():
                if is_dialog_open['v']: return
                user_list_container.clear()
                users, cur_date = db.get_all_users(), db.state.get_current_time()
                with user_list_container:
                    ui.button('Thêm Người Dùng', on_click=lambda: add_user_dialog())
                    with ui.row().classes('w-full font-bold bg-gray-200 p-2'):
                        ui.label('Họ Tên').classes('w-1/6'); ui.label('Lương/h').classes('w-1/6'); ui.label('Lương Tháng').classes('w-1/6'); ui.label('Trạng Thái').classes('w-1/6'); ui.label('Hành Động').classes('w-1/3')
                    for u in users:
                        with ui.row().classes('w-full items-center border-b p-2'):
                            ui.label(u.get('name', 'N/A')).classes('w-1/6'); ui.label(f"{int(u.get('salary', 0)):,}").classes('w-1/6'); ui.label(f"{db.calculate_salary(u['username'], cur_date.month, cur_date.year):,}").classes('w-1/6 text-green-700 font-bold')
                            st = u.get('status', 'checkout')
                            lbl = ui.label(st).classes('w-1/6')
                            if st == 'checkin': lbl.classes('text-green-600 font-bold')
                            with ui.row().classes('w-1/3 gap-2'):
                                def do_reset(u_name=u['username']):
                                    if db.reset_daily_limit(u_name): ui.notify(f'Đã mở khoá cho {u_name}')
                                    else: ui.notify(f'Lỗi mở khoá', color='negative')
                                    refresh_list()
                                ui.button('Mở', color='orange', on_click=do_reset).props('size=sm')
                                ui.button('Sửa', on_click=lambda u=u: edit_user(u)).props('size=sm')
                                ui.button('Xoá', color='red', on_click=lambda u=u: [db.delete_user(u.doc_id), refresh_list()]).props('size=sm')
            def edit_user(u):
                is_dialog_open['v'] = True
                with ui.dialog() as dialog, ui.card():
                    name, uid_f, salary = ui.input('Họ Tên', value=u.get('name')), ui.input('UID', value=u.get('uid')), ui.number('Lương/h', value=u.get('salary'))
                    role = ui.select(['user', 'admin'], value=u.get('role'), label='Vai Trò')
                    status = ui.select(['checkin', 'checkout'], value=u.get('status'), label='Trạng Thái')
                    rooms = ui.input('Phòng', value=','.join(u.get('allowed_rooms', [])))
                    def save():
                        db.update_user_details(u.doc_id, {'name': name.value, 'uid': uid_f.value, 'salary': salary.value, 'role': role.value, 'status': status.value, 'allowed_rooms': [r.strip() for r in rooms.value.split(',')]})
                        dialog.close(); is_dialog_open['v'] = False; refresh_list()
                    with ui.row(): ui.button('Lưu', on_click=save); ui.button('Huỷ', on_click=lambda: [dialog.close(), is_dialog_open.update({'v': False})])
                dialog.open()
            def add_user_dialog():
                is_dialog_open['v'] = True
                with ui.dialog() as dialog, ui.card():
                    uname, pwd, name, uid_f = ui.input('Tên đăng nhập'), ui.input('Mật khẩu'), ui.input('Họ tên'), ui.input('UID')
                    def create():
                        db.create_user({'username': uname.value, 'password': pwd.value, 'name': name.value, 'uid': uid_f.value, 'role': 'user', 'allowed_rooms': [], 'salary': 25000})
                        dialog.close(); is_dialog_open['v'] = False; refresh_list()
                    with ui.row(): ui.button('Tạo', on_click=create); ui.button('Huỷ', on_click=lambda: [dialog.close(), is_dialog_open.update({'v': False})])
                dialog.open()
            refresh_list()
            last_ts = {'v': db.state.last_updated}
            ui.timer(0.5, lambda: [refresh_list(), last_ts.update({'v': db.state.last_updated})] if db.state.last_updated > last_ts['v'] and not is_dialog_open['v'] else None)
        with ui.tab_panel('debug'):
            with ui.column().classes('p-4'):
                ui.label('Mô Phỏng Thời Gian').classes('text-h6')
                with ui.row().classes('items-center gap-2'):
                    date_in, time_in = ui.input('Ngày', value=datetime.now().strftime('%Y-%m-%d')), ui.input('Giờ', value=datetime.now().strftime('%H:%M'))
                    ui.button('Áp dụng', on_click=lambda: db.state.set_time_offset(int((datetime.strptime(f"{date_in.value} {time_in.value}", "%Y-%m-%d %H:%M") - datetime.now()).total_seconds())))
                    ui.button('Reset', on_click=lambda: db.state.set_time_offset(0))
                def up_clock(): clock_lbl.text = f"Thời Gian Hệ Thống: {db.state.get_current_time().strftime('%Y-%m-%d %H:%M:%S')}"
                clock_lbl = ui.label(); ui.timer(1.0, up_clock); up_clock()
                em_btn = ui.button('', on_click=lambda: db.state.set_emergency(not db.state.emergency_mode))
                ui.timer(0.5, lambda: em_btn.props(f'color={"red" if db.state.emergency_mode else "green"} label="{"TẮT KHẨN CẤP" if db.state.emergency_mode else "Kích Hoạt Khẩn Cấp"}"'))

@ui.page('/')
def main_page():
    if not app.storage.user.get('username'): ui.open('/login'); return
    db.init_db()
    ui.add_head_html('<style>.blink { animation: blinker 1s linear infinite; } @keyframes blinker { 50% { opacity: 0; } } .emergency-active { background-color: #ffebee !important; } .emergency-active .q-header, .emergency-active .bg-white { background-color: #ffcdd2 !important; }</style>')
    main_c = ui.column().classes('w-full min-h-screen items-center bg-gray-100 transition-colors duration-500')
    ui.timer(1.0, lambda: main_c.classes('emergency-active' if db.state.emergency_mode else '', remove='emergency-active' if not db.state.emergency_mode else ''))
    with main_c:
        header = ui.row().classes('w-full justify-center items-center bg-red-600 text-white p-2')
        with header: ui.label('CÓ SỰ CỐ KHẨN CẤP! VUI LÒNG SƠ TÁN NGAY LẬP TỨC!').classes('text-h5 font-bold blink')
        ui.timer(1.0, lambda: header.set_visibility(db.state.emergency_mode))
        with ui.row().classes('w-full bg-white shadow p-4 justify-between items-center'):
            ui.label('Hệ Thống Chấm Công').classes('text-h5')
            with ui.row().classes('items-center gap-4'):
                ui.label(app.storage.user['username'])
                ui.button('Đăng Xuất', on_click=lambda: [app.storage.user.clear(), ui.open('/login')]).props('flat')
        user_full = db.get_user_by_username(app.storage.user['username'])
        if user_full:
            if user_full['role'] == 'admin': admin_dashboard(user_full)
            else: user_dashboard(user_full)
        else: ui.label('Lỗi dữ liệu')

ui.run(storage_secret='my-secret-key-123', port=8081)