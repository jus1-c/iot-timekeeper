import db

db.init_db()
admin = db.get_user_by_username('admin')
if admin:
    print(f"Resetting password for {admin['username']}...")
    db.update_user_details(admin.doc_id, {'password': 'admin'})
    print("Password reset to 'admin'.")
else:
    print("Admin user not found.")
