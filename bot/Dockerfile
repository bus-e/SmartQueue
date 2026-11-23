FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY smartqueue_bot ./smartqueue_bot
CMD ["python", "-m", "smartqueue_bot.main"]
