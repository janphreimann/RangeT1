import os
import sys
import time
from datetime import datetime, timezone

from supabase import create_client, Client
from pydexcom import Dexcom
from pydexcom.errors import ServerError, SessionError

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
DEXCOM_USERNAME = os.environ["DEXCOM_USERNAME"]
DEXCOM_PASSWORD = os.environ["DEXCOM_PASSWORD"]

USER_ID = "a4f07f34-075a-4b89-9c0a-db3e466a6ffb"

# Wie weit zurück bei jedem Lauf abgefragt wird (Puffer gegen verpasste/fehlgeschlagene Läufe).
# 30 min / 6 Werte deckt einen ausgefallenen 5-Minuten-Lauf locker ab.
LOOKBACK_MINUTES = 30
MAX_COUNT = 6

# Retry-Einstellungen für transiente Dexcom-Serverfehler (z. B. 504 Gateway Timeout).
MAX_RETRIES = 4
BASE_DELAY_SECONDS = 5  # 5s, 10s, 20s, 40s ...

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def with_retry(action, what: str):
    """Fuehrt action() aus und wiederholt bei transienten Dexcom-Serverfehlern."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return action()
        except (ServerError, SessionError) as err:
            # Diese Fehler decken die 504/Timeout/INVALID_JSON-Faelle der Share-API ab.
            last_error = err
            if attempt == MAX_RETRIES:
                break
            delay = BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            print(f"{what}: Versuch {attempt}/{MAX_RETRIES} fehlgeschlagen ({err}) "
                  f"-> erneuter Versuch in {delay}s")
            time.sleep(delay)
    raise last_error


def save_rows(rows: list[dict]):
    # Upsert verhindert Duplicate-Errors automatisch (Konflikt auf reading_time).
    if not rows:
        return
    supabase.table("dexcom_glucose_logs") \
        .upsert(rows, on_conflict="reading_time") \
        .execute()


def reading_to_row(bg) -> dict:
    dt = bg.datetime
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return {
        "reading_time": dt.isoformat(),
        "glucose_mgdl": int(bg.value),
        "glucose_mmol": float(bg.mmol_l),
        "trend_description": bg.trend_description,
        "trend_arrow": bg.trend_arrow,
        "user_id": USER_ID,
    }


def main() -> int:
    print("Starte Dexcom Sync")

    try:
        # Login (haeufigste Fehlerquelle: 504 beim Auth-Endpoint)
        dexcom = with_retry(
            lambda: Dexcom(
                username=DEXCOM_USERNAME,
                password=DEXCOM_PASSWORD,
                region="ous",
            ),
            what="Login",
        )

        # Puffer holen statt nur den aktuellen Wert -> faengt verpasste Laeufe wieder auf.
        readings = with_retry(
            lambda: dexcom.get_glucose_readings(
                minutes=LOOKBACK_MINUTES,
                max_count=MAX_COUNT,
            ),
            what="Glukose-Abruf",
        )
    except (ServerError, SessionError) as err:
        # Transienter Serverfehler nach allen Retries: NICHT hart abstuerzen.
        # Der naechste Cron-Lauf in 5 min holt die Luecke dank Puffer wieder auf.
        print(f"Dexcom-Server momentan nicht erreichbar (transient): {err}")
        print("Ueberspringe diesen Lauf, naechster Lauf holt die Daten nach.")
        return 0

    if not readings:
        print("Dexcom liefert keine Werte (Sensor offline / keine Daten im Fenster) -> nichts zu speichern")
        return 0

    rows = [reading_to_row(bg) for bg in readings]
    save_rows(rows)

    print(f"{len(rows)} Dexcom Wert(e) gespeichert/aktualisiert:")
    for r in rows:
        print(" ", r["reading_time"], r["glucose_mgdl"], "mg/dL", r["trend_arrow"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
