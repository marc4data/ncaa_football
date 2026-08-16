# Streamlit site image. Slim base and no build toolchain: the box has 1 GiB and one core,
# so image size and build time both matter more than they would elsewhere.
FROM python:3.12-slim

WORKDIR /app

# psycopg2-binary ships wheels, so no compiler is needed here.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app.py db.py /app/

EXPOSE 8501

# Bind to all interfaces inside the container network; nothing is published to the host.
# CORS/XSRF stay on — Cloudflare Access is the auth boundary, not a reason to weaken the app.
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
