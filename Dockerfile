# Use Python base image
FROM python:3.9

# Set the working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install dependencies
RUN pip install -r requirements.txt

# Expose port for health check
EXPOSE 8000

# Run the application
CMD ["python", "app.py"]
