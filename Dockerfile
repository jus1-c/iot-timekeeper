# Sử dụng Python 3.11 (Bản slim nhẹ và ổn định)
FROM python:3.11-slim

# Thiết lập biến môi trường
# PYTHONUNBUFFERED=1: Log in ra ngay lập tức, không bị delay
ENV PYTHONUNBUFFERED=1

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Copy file requirements trước để tận dụng cache của Docker
COPY requirements.txt .

# Cài đặt các thư viện
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code vào container
COPY . .

# Mở port 8081
EXPOSE 8081

# Lệnh chạy ứng dụng
CMD ["python", "main.py"]
