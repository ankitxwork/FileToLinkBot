# -------- BASE IMAGE --------
FROM python:3.13-slim

# -------- SYSTEM DEPENDENCIES --------
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libffi-dev \
    build-essential \
    && apt-get clean

# -------- APP SETUP --------
WORKDIR /app

# Copy all repo files to container
COPY . /app

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# -------- RUN THE BOT --------
CMD ["python", "main.py"]