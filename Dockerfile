# Use the latest Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /bot

# Install system dependencies needed for tgcrypto
RUN apt-get update && apt-get install -y gcc python3-dev

# Copy bot files, requirements file, and the run script
COPY bot.py bot2.py requirements.txt run.sh ./

# Install required Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Make run.sh executable
RUN chmod +x run.sh

# Expose ports for health check endpoints (8000 for bot.py and 8001 for bot2)
EXPOSE 8000 8001

# Set the default command to run both bots concurrently
CMD ["./run.sh"]
