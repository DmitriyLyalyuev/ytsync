FROM python:3.12-slim

ARG USER_UID=1000
ARG USER_GID=1000

RUN apt-get update && apt-get install -y \
    ffmpeg \
    &&  curl -fsSL https://deno.land/install.sh | sh \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

RUN mkdir -p /app/downloads
RUN mkdir -p /home/ytuser

RUN groupadd -g ${USER_GID} ytuser && \
    useradd -r -u ${USER_UID} -g ${USER_GID} ytuser
RUN chown -R ytuser:ytuser /app
RUN chown -R ytuser:ytuser /home/ytuser
USER ytuser

ENV PYTHONUNBUFFERED=1
ENV USER_UID=${USER_UID}
ENV USER_GID=${USER_GID}

EXPOSE 8000

CMD ["python", "main.py"]
