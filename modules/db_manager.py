import os
from supabase import create_client, Client
from dotenv import load_dotenv
import json

class SupabaseManager:
    def __init__(self):
        load_dotenv() # Carica variabili da .env
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            raise ValueError("❌ ERRORE: Variabili SUPABASE mancanti nel file .env")
            
        self.client: Client = create_client(url, key)

    def save_daily_log(self, date_str: str, data: dict):
        """
        Esegue un UPSERT (Update or Insert) nella tabella daily_logs.
        Se la riga per quella data esiste, la aggiorna. Se no, la crea.
        """
        try:
            # Aggiungiamo la data al payload per sicurezza
            data['date'] = date_str
            data['last_update'] = "now()" 
            
            # Eseguiamo l'upsert
            result = self.client.table("daily_logs").upsert(data).execute()
            print(f"💾 Database aggiornato per il giorno {date_str}")
            return result
        except Exception as e:
            print(f"❌ Errore scrittura DB: {e}")
            return None