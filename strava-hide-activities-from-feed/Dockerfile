FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Ensure Python outputs logs to stdout immediately
ENV PYTHONUNBUFFERED=1

# Copy the source code
COPY src/ ./src/

# Set the command to run the script
CMD ["python", "src/strava.py"]
