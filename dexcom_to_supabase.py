import os
from datetime import timezone
from supabase import create_client, Client
from pydexcom import Dexcom

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
DEXCOM_USERNAME = os.environ["DEXCOM_USERNAME"]
DEXCOM_PASSWORD = os.environ["DEXCOM_PASSWORD"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
dexcom = Dexcom(username=DEXCOM_USERNAME, password=DEXCOM_PASSWORD)

def main():
    print("Starte Dexcom Sync")

    bg = dexcom.get_current_glucose_reading()

    if bg is None:
        print("Kein neuer Wert verfügbar")
        return

    row = {
        "reading_time": bg.time.replace(tzinfo=timezone.utc).isoformat(),
        "glucose_mgdl": int(bg.value),
        "glucose_mmol": float(bg.mmol_l),
        "trend_description": bg.trend_description,
        "trend_arrow": bg.trend_arrow
    }

    supabase.table("dexcom_glucose_logs").insert(row).execute()

    print("Upload erfolgreich:", row)

if __name__ == "__main__":
    main()
