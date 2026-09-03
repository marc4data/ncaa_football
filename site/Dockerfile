# Streamlit site image. Slim base and no build toolchain: the box has 1 GiB and one core,
# so image size and build time both matter more than they would elsewhere.
FROM python:3.12-slim

WORKDIR /app

# psycopg2-binary ships wheels, so no compiler is needed here.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# The whole app: nav entrypoint, the shared Part 0 components, and the page modules.
# Copying only app.py silently produced `ModuleNotFoundError: No module named 'lib'` at
# runtime — the image built fine and the container started, so nothing surfaced it until a
# page was actually requested.
COPY app.py /app/
COPY lib/ /app/lib/
# R-099, AND IT WAS NEVER A COLOUR PROBLEM. The accent was chosen correctly a round ago and
# the radio stayed Streamlit red on the deployed site, because the config lived at the REPO
# ROOT while `deploy/docker-compose.yml` builds this image with `context: ./site`. The repo
# root is outside the build context, so no COPY could have reached it — Streamlit looked for
# /app/.streamlit/config.toml, found nothing, and used its own #FF4B4B.
#
# THE SAME WALL ALREADY BIT ONCE: `lib/lines_cadence.json` exists because this image cannot
# import `src/` for the same reason. One canonical file, inside the context, and the local run
# is done from inside site/ so dev and prod read the same one.
COPY .streamlit/ /app/.streamlit/
# NOT `pages/`: Streamlit auto-discovers that name and overrides st.navigation.
COPY views/ /app/views/

EXPOSE 8501

# Bind to all interfaces inside the container network; nothing is published to the host.
# CORS/XSRF stay on — Cloudflare Access is the auth boundary, not a reason to weaken the app.
CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
