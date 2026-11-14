# Backend publik "Flame in Freefall": dashboard /insight/ + asisten POST /ask.
# Mode publik (FIF_PUBLIC=1): hanya jalur baca + /ask; jalur tulis ditutup.
# Kunci API TIDAK dimasukkan ke image: isi ANTHROPIC_API_KEY sebagai rahasia di layanan hosting.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FIF_PUBLIC=1 \
    HOST=0.0.0.0 \
    PORT=8765

WORKDIR /srv
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

# Hanya yang dibaca server saat berjalan (lihat docs/deploy.md)
COPY scripts/ scripts/
COPY kb/gold/ kb/gold/
# freefall.sqlite dilacak git sebagai .gz (>100 MB mentah): buka saat build, buang .gz-nya
RUN python -c "import gzip,shutil; shutil.copyfileobj(gzip.open('kb/gold/freefall.sqlite.gz','rb'), open('kb/gold/freefall.sqlite','wb'), 1<<20)" \
    && rm kb/gold/freefall.sqlite.gz
COPY analysis/ analysis/
COPY app/ app/
# indeks pencarian paper (LSA) dibangun sekali saat build, bukan pada permintaan pertama
RUN python scripts/retrieval.py build

RUN useradd --create-home fif && chown -R fif /srv
USER fif

EXPOSE 8765
CMD ["python", "scripts/brain.py", "serve"]
