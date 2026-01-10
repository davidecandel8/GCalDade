import os
from dotenv import load_dotenv
from supabase import create_client, Client

class SupabaseManager:
    def __init__(self):
        # 1. Calcoliamo il percorso assoluto della root del progetto
        # (Saliamo di due livelli da modules/db_manager.py)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(base_dir, '.env')

        # 2. Carichiamo le variabili d'ambiente dal file .env
        # override=True forza l'aggiornamento se per caso ce ne sono già in memoria
        loaded = load_dotenv(dotenv_path=env_path, override=True)

        # 3. Recuperiamo le credenziali
        # NOTA: Assumo che nel .env le chiavi si chiamino SUPABASE_URL e SUPABASE_KEY.
        # Se hanno nomi diversi (es. NEXT_PUBLIC_SUPABASE_URL), modificali qui sotto.
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")

        # 4. Validazione Ingegneristica
        if not self.url or not self.key:
            print(f"\n❌ ERRORE CRITICO: Variabili d'ambiente Supabase mancanti!")
            print(f"   Ho letto il file .env in: {env_path}")
            print(f"   Stato caricamento .env: {'Successo' if loaded else 'Fallito'}")
            print(f"   Cerco le chiavi: 'SUPABASE_URL' e 'SUPABASE_KEY'")
            print(f"   Trovato URL: {'✅ Sì' if self.url else '❌ No'}")
            print(f"   Trovato KEY: {'✅ Sì' if self.key else '❌ No'}\n")
            raise ValueError("Credenziali Supabase mancanti nel file .env")

        # 5. Inizializzazione Client
        self.supabase: Client = create_client(self.url, self.key)

    def upsert_daily_log(self, data_dict):
        """
        Inserisce o aggiorna (Upsert) una riga nella tabella daily_logs.
        """
        try:
            response = self.supabase.table('daily_logs').upsert(data_dict).execute()
            return response
        except Exception as e:
            print(f"   ⚠️ Errore Supabase interno: {e}")
            raise e