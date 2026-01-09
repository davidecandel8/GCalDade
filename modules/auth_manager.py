import os
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Definiamo gli SCOPES necessari. 
# NOTA: Devono coincidere con quelli che hai abilitato su Google Cloud.
SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.location.read',
    'https://www.googleapis.com/auth/fitness.body.read',      # Peso, Grasso, Altezza
    'https://www.googleapis.com/auth/fitness.nutrition.read', # Acqua, Cibo
    'https://www.googleapis.com/auth/fitness.sleep.read',
    'https://www.googleapis.com/auth/fitness.heart_rate.read',
    'https://www.googleapis.com/auth/fitness.blood_pressure.read',
    'https://www.googleapis.com/auth/fitness.blood_glucose.read',
    'https://www.googleapis.com/auth/fitness.oxygen_saturation.read',
    'https://www.googleapis.com/auth/fitness.body_temperature.read', # Temp Cutanea/Corporea
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/youtube.readonly'
]

class GoogleAuthManager:
    def __init__(self):
        # Percorsi assoluti per evitare errori se lanci lo script da altre cartelle
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.secrets_file = os.path.join(base_path, 'config', 'client_secrets.json')
        self.token_file = os.path.join(base_path, 'config', 'token.json')

    def authenticate(self):
        """
        Gestisce il flusso OAuth 2.0.
        Se esiste già un token valido in config/token.json, lo usa.
        Altrimenti, apre il browser per il login e salva il nuovo token.
        """
        creds = None
        
        # 1. Controllo se esiste già un token salvato
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            
        # 2. Se non ci sono credenziali o non sono valide
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # 2a. Il token è scaduto ma possiamo aggiornarlo (Refresh Token)
                print("🔄 Refreshing del token scaduto...")
                creds.refresh(Request())
            else:
                # 2b. Primo login assoluto: Apertura Browser
                print("🌐 Avvio procedura di login nel browser...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.secrets_file, SCOPES)
                # run_local_server apre una porta locale per ricevere il callback da Google
                creds = flow.run_local_server(port=0)
                
            # 3. Salvataggio del token per il futuro
            print("💾 Salvataggio nuove credenziali in token.json")
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
                
        return creds

# Test rapido se esegui questo file direttamente
if __name__ == "__main__":
    manager = GoogleAuthManager()
    manager.authenticate()
    print("✅ Autenticazione test completata con successo.")