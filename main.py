import os
import json
from datetime import datetime, timedelta
from modules.auth_manager import GoogleAuthManager
from modules.fit_service import GoogleFitService
from modules.db_manager import SupabaseManager
from googleapiclient.discovery import build

# CONFIGURAZIONE
START_DATE = "2026-01-01" 
END_DATE = "2026-01-10"   
GENERATE_REPORT_FILE = True 
SAVE_TO_DB = True          

def generate_daily_report(data, date_str):
    def val(v, unit="", default="N/D"):
        return f"{v} {unit}" if v is not None else default

    report = []
    report.append(f"========================================")
    report.append(f"📅 REPORT GIORNALIERO: {date_str}")
    report.append(f"========================================\n")

    report.append(f"🏃‍♂️ ATTIVITÀ FISICA")
    report.append(f"   • Passi: {val(data['health_steps'])}")
    report.append(f"   • Distanza: {val(data['health_distance_m'], 'm')}")
    report.append(f"   • Calorie Bruciate: {val(data['health_calories_burnt'], 'kcal')}")
    report.append(f"   • Punti Cardio: {val(data['health_cardio_points'])}")
    report.append(f"   • Minuti Attivi: {val(data['health_active_minutes'], 'min')}")
    report.append(f"   • Piani Saliti: {val(data['health_floors_climbed'])}")
    
    if data['raw_data']['sport_activities']:
        report.append(f"   • Sessioni Sportive:")
        for s in data['raw_data']['sport_activities']:
            report.append(f"     - {s['start_fmt']}: {s['name']} ({int(s['duration'])} min)")
    else:
        report.append(f"   • Nessuna sessione sportiva registrata.")
    report.append("")

    report.append(f"😴 SONNO & RECUPERO")
    report.append(f"   • Totale Sonno: {val(data['health_sleep_minutes'], 'min')} ({round(data['health_sleep_minutes']/60, 1) if data['health_sleep_minutes'] else 0} ore)")
    report.append(f"   • Punteggio Sonno: {val(data['health_sleep_score'], '/100')}")
    report.append(f"   • Energy Score: {val(data['health_energy_score'], '/100')}")
    
    if data['health_sleep_minutes'] and data['health_sleep_minutes'] > 0:
        report.append(f"   • Fasi del Sonno:")
        report.append(f"     - Sveglio: {val(data['health_sleep_awake_minutes'], 'min')}")
        report.append(f"     - REM: {val(data['health_sleep_rem_minutes'], 'min')}")
        report.append(f"     - Leggero: {val(data['health_sleep_light_minutes'], 'min')}")
        report.append(f"     - Profondo: {val(data['health_sleep_deep_minutes'], 'min')}")
    report.append("")

    report.append(f"❤️ PARAMETRI VITALI")
    report.append(f"   • Battito a Riposo (RHR): {val(data['health_resting_hr'], 'bpm')}")
    report.append(f"   • Battito Medio: {val(data['health_avg_hr'], 'bpm')}")
    report.append(f"   • Battito Max: {val(data['health_max_hr'], 'bpm')}")
    report.append(f"   • SpO2 Media: {val(data['health_avg_spo2'], '%')}")
    report.append(f"   • Pressione: {val(data['health_blood_pressure_sys'])}/{val(data['health_blood_pressure_dia'])} mmHg")
    report.append(f"   • Glicemia Media: {val(data['health_blood_glucose_avg'], 'mg/dL')}")
    
    skin = data.get('health_skin_temp_avg')
    resp = data.get('health_respiratory_rate_avg')
    if skin or resp:
        report.append(f"   • Monitoraggio Notturno:")
        report.append(f"     - Temp. Cutanea (Media): {val(skin, '°C')}")
        report.append(f"     - Freq. Respiratoria: {val(resp, 'rpm')}")
    report.append("")

    report.append(f"⚖️ COMPOSIZIONE CORPOREA")
    report.append(f"   • Peso: {val(data['health_weight_kg'], 'kg')}")
    report.append(f"   • BMI (IMC): {val(data['health_bmi'])}")
    report.append(f"   • Massa Grassa: {val(data['health_body_fat_kg'], 'kg')} ({val(data['health_body_fat_perc'], '%')})")
    report.append(f"   • Massa Muscolare (SMM): {val(data['health_muscle_mass_kg'], 'kg')}")
    report.append(f"   • Acqua Corporea: {val(data['health_body_water_kg'], 'kg')} ({val(data['health_body_water_perc'], '%')})")
    report.append(f"   • Metabolismo Basale (BMR): {val(data['health_bmr_kcal'], 'kcal')}")
    report.append("")

    report.append(f"🍎 NUTRIZIONE")
    report.append(f"   • Calorie Assunte: {val(data['health_calories_intake'], 'kcal')}")
    report.append(f"   • Acqua Bevuta: {val(data['health_water_ml'], 'ml')}")
    report.append("")
    
    report.append(f"----------------------------------------")
    report.append(f"Generato il: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return "\n".join(report)

def main():
    print("--- 🚀 MY LIFE TRACKER: REPORT GENERATOR ---")
    
    if GENERATE_REPORT_FILE and not os.path.exists("reports"):
        os.makedirs("reports")

    auth_manager = GoogleAuthManager()
    creds = auth_manager.authenticate()
    fit_service = build('fitness', 'v1', credentials=creds)
    
    app = GoogleFitService(fit_service)
    db = SupabaseManager()

    start = datetime.strptime(START_DATE, "%Y-%m-%d")
    end = datetime.strptime(END_DATE, "%Y-%m-%d")
    
    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        print(f"\n🔄 Elaborazione: {date_str}")
        
        metrics = None
        
        # 1. SCARICA DATI (Fondamentale)
        try:
            metrics = app.get_full_day_metrics(current)
            metrics['date'] = date_str # Chiave primaria per DB
        except Exception as e:
            print(f"   ❌ ERRORE FETCH DATI: {e}")
            current += timedelta(days=1)
            continue # Se non ho i dati, passo al prossimo giorno

        # 2. SALVA SU DB (Opzionale e Isolato)
        if SAVE_TO_DB:
            try:
                db.upsert_daily_log(metrics)
                print("   ✅ DB Aggiornato")
            except Exception as e:
                print(f"   ⚠️ Errore scrittura DB (Ma continuo): {e}")

        # 3. GENERA FILE REPORT (Isolato)
        if GENERATE_REPORT_FILE:
            try:
                report_text = generate_daily_report(metrics, date_str)
                filename = f"reports/report_{date_str}.txt"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(report_text)
                print(f"   📄 Report creato: {filename}")
            except Exception as e:
                print(f"   ❌ Errore creazione Report: {e}")

        current += timedelta(days=1)

    print("\n✅ FINE ELABORAZIONE.")

if __name__ == "__main__":
    main()