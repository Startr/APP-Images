# Stage 1: Build
FROM python:3.9-slim as builder

# Set environment variables
ENV PIPENV_VENV_IN_PROJECT=1 \
    PYTHONUNBUFFERED=1

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install pipenv
RUN pip install --upgrade pip
RUN pip install pipenv

# Set work directory
WORKDIR /app

# Copy Pipfile and Pipfile.lock
COPY Pipfile Pipfile.lock ./

# Install dependencies
RUN pipenv install --deploy --ignore-pipfile --verbose

# Stage 2: Final
FROM python:3.9-slim

# Set environment variables
ENV PIPENV_VENV_IN_PROJECT=1 \
    PYTHONUNBUFFERED=1

# Install pipenv in the final stage
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install pipenv

# Set work directory
WORKDIR /app

# Copy the installed virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application files
COPY . /app

# Expose the port the app runs on
EXPOSE 5000

# Set the PATH to use the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Command to run the application
CMD ["pipenv", "run", "flask", "run", "--host=0.0.0.0"]
