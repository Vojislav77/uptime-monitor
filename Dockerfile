# Use an official lightweight Python image
FROM python:3.13-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Tell Flask to listen on all network interfaces
ENV FLASK_RUN_HOST=0.0.0.0

# Expose the port your app runs on
EXPOSE 5000

# Run the application
CMD ["python", "uptime_monitor.py"]