import os
from datetime import datetime, timezone
from supabase import create_client, Client
from pydexcom import Dexcom

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
DEXCOM_USERNAME = os.environ["DEXCOM_USERNAME"]
DEXCOM_PASSWORD = os.environ["DEXCOM_PASSWORD"]

USER_ID = "a4f07f34-075a-4b89-9c0a-db3e466a6ffb"

# Wie weit zurück bei jedem Lauf abgefragt wird (Puffer gegen verpasste Läufe).
# 30 min / 6 Werte deckt einen ausgefallenen 5-Minuten-Lauf locker ab.
LOOKBACK_MINUTES = 30
MAX_COUNT = 6

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

dexcom = Dexcom(
    username=DEXCOM_USERNAME,
    password=DEXCOM_PASSWORD,
    region="ous",
)


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


def main():
    print("Starte Dexcom Sync")

    # Puffer holen statt nur den einen aktuellen Wert.
    # So fängt ein Lauf eine eventuell verpasste vorherige Ausführung wieder auf.
    readings = dexcom.get_glucose_readings(
        minutes=LOOKBACK_MINUTES,
        max_count=MAX_COUNT,
    )

    if not readings:
        print("Dexcom liefert keine Werte (Sensor offline / keine Daten im Fenster) → nichts zu speichern")
        return

    rows = [reading_to_row(bg) for bg in readings]
    save_rows(rows)

    print(f"{len(rows)} Dexcom Wert(e) gespeichert/aktualisiert:")
    for r in rows:
        print(" ", r["reading_time"], r["glucose_mgdl"], "mg/dL", r["trend_arrow"])


if __name__ == "__main__":
    main()