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
    region="ous"
)


def get_last_saved_value():
    res = (
        supabase.table("dexcom_glucose_logs")
        .select("*")
        .order("reading_time", desc=True)
        .limit(1)
        .execute()
    )
    if res.data:
        return res.data[0]
    return None


def main():
    print("Starte Dexcom Sync")

    readings = dexcom.get_glucose_readings(max_count=1)

    if readings:
        bg = readings[0]
        row = {
            # echte Messzeit von Dexcom verwenden
            "reading_time": bg.datetime.isoformat(),
            "glucose_mgdl": int(bg.value),
            "glucose_mmol": float(bg.mmol_l),
            "trend_description": bg.trend_description,
            "trend_arrow": bg.trend_arrow
        }
        print("Dexcom Wert gefunden")

    else:
        print("Dexcom liefert keinen Wert → nutze letzten DB Wert")

        last = get_last_saved_value()
        if not last:
            print("Noch kein Wert in DB vorhanden → nichts zu speichern")
            return

        # Wert bleibt gleich, Zeitstempel wird auf 'jetzt' gesetzt (keine Lücke)
        row = {
            "reading_time": datetime.now(timezone.utc).isoformat(),
            "glucose_mgdl": int(last["glucose_mgdl"]),
            "glucose_mmol": float(last["glucose_mmol"]),
            "trend_description": last.get("trend_description"),
            "trend_arrow": last.get("trend_arrow")
        }

    supabase.table("dexcom_glucose_logs").insert(row).execute()
    print("Upload erfolgreich:", row)


if __name__ == "__main__":
    main()
