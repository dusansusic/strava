FROM python:3.12-slim

# Install cron
RUN apt update && apt install -y \
    cron \
    && rm -rf /var/lib/apt/lists/*

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

# Create tokens directory
RUN mkdir -p /app/tokens

# Create log directory
RUN mkdir -p /var/log/strava && \
    touch /var/log/strava/cron.log

# Create a script to set up environment variables for cron
RUN echo '#!/bin/sh\n\
env > /app/env.sh\n\
echo "#!/bin/sh" > /app/env_vars.sh\n\
env | while read -r line; do\n\
  echo "export $line" >> /app/env_vars.sh\n\
done\n\
chmod +x /app/env_vars.sh\n\
\n\
# Create a cron job with environment variables\n\
echo "* * * * * root cd /app && . /app/env_vars.sh && /usr/local/bin/python src/strava.py >> /var/log/strava/cron.log 2>&1" > /etc/cron.d/strava-job\n\
chmod 0644 /etc/cron.d/strava-job\n\
\n\
# Start cron\n\
cron\n\
\n\
# Keep container running and display logs\n\
tail -f /var/log/strava/cron.log\n\
' > /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set the command to run the entrypoint script
CMD ["/app/entrypoint.sh"]
