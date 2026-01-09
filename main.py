from googleapiclient.discovery import build
from modules.auth_manager import GoogleAuthManager
from modules.db_manager import SupabaseManager
from modules.fit_service import GoogleFitService
from datetime import datetime, timedelta
import json

def main():
    print("--- 🚀 MY LIFE TRACKER: DEBUG MODE ---")
    
    auth = GoogleAuthManager()
    creds = auth.authenticate()
    fit_api = build('fitness', 'v1', credentials=creds)
    fit_service = GoogleFitService(fit_api)
    db_manager = SupabaseManager()
    
    start_date = datetime(2026, 1, 1)
    end_date = datetime.now()
    
    current_date = start_date
    print(f"📅 Loop: {start_date.strftime('%Y-%m-%d')} -> {end_date.strftime('%Y-%m-%d')}\n")

    while current_date.date() <= end_date.date():
        target_str = current_date.strftime('%Y-%m-%d')
        print(f"🔄 Processing: {target_str}")
        
        try:
            data = fit_service.get_full_day_metrics(target_date=current_date)
            
            raw = data['raw_data']['fit_aggregates_dump']
            
            print(f"   [ATTIVITÀ] Passi Finali: {data['health_steps']}")
            print(f"   --> Merged: {raw.get('debug_steps_merged', 'N/A')} | Watch: {raw.get('debug_steps_watch', 'N/A')}")
            print(f"   Dist: {data['health_distance_m']} m | Cal: {data['health_calories_burnt']} kcal | Min: {data['health_active_minutes']}")

            print(f"   [VITALI] HR Avg/Rest/Act: {data['health_avg_hr']} / {data['health_resting_hr']} / {data['health_active_hr']}")
            
            # Scrittura DB
            db_manager.save_daily_log(target_str, data)
            
        except Exception as e:
            print(f"   ❌ ERRORE: {e}")
        
        current_date += timedelta(days=1)
        print("-" * 30)

    print("\n✅ DONE.")

if __name__ == "__main__":
    main()