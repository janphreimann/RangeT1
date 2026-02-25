import os
from datetime import datetime, timezone
from supabase import create_client, Client
from pydexcom import Dexcom

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
DEXCOM_USERNAME = os.environ["DEXCOM_USERNAME"]
DEXCOM_PASSWORD = os.environ["DEXCOM_PASSWORD"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

dexcom = Dexcom(
    username=DEXCOM_USERNAME,
    password=DEXCOM_PASSWORD,
    region="ous",
)


def get_last_saved_value():
    res = (
        supabase.table("dexcom_glucose_logs")
        .select("*")
        .order("reading_time", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def save_row(row: dict):
    # Upsert verhindert Duplicate-Errors automatisch
    supabase.table("dexcom_glucose_logs") \
        .upsert(row, on_conflict="reading_time") \
        .execute()


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def main():
    print("Starte Dexcom Sync")

    readings = dexcom.get_glucose_readings(max_count=1)

    # Dexcom liefert neuen Wert
    if readings:
        bg = readings[0]
        dt = bg.datetime
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        row = {
            "reading_time": dt.isoformat(),
            "glucose_mgdl": int(bg.value),
            "glucose_mmol": float(bg.mmol_l),
            "trend_description": bg.trend_description,
            "trend_arrow": bg.trend_arrow,
            "user_id": "a4f07f34-075a-4b89-9c0a-db3e466a6ffb",
        }

        save_row(row)
        print("Dexcom Wert gespeichert:", row)
        return

    # Dexcom liefert None → letzten DB Wert mit aktueller Zeit speichern
    print("Dexcom liefert keinen Wert → nutze letzten DB Wert")

    last = get_last_saved_value()
    if not last:
        print("Noch kein Wert in DB vorhanden → nichts zu speichern")
        return

    row = {
        "reading_time": utc_now_iso(),
        "glucose_mgdl": int(last["glucose_mgdl"]),
        "glucose_mmol": float(last["glucose_mmol"]),
        "trend_description": last.get("trend_description"),
        "trend_arrow": last.get("trend_arrow"),
        "user_id": "a4f07f34-075a-4b89-9c0a-db3e466a6ffb",
    }

    save_row(row)
    print("Fallback Wert gespeichert:", row)


if __name__ == "__main__":
    main()
