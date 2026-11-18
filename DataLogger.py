from sqlalchemy import create_engine
import pandas as pd
import gradio as gr
from datetime import datetime, timedelta

class DataLogger():
    def __init__(self):
        self.engine = create_engine('sqlite:///history.db')

        self.oggi = datetime.now().strftime("%Y-%m-%d")
        self.sette_giorni_fa = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")

    def estrai_data_str(self, valore):
        if isinstance(valore, (int, float)):
            return datetime.fromtimestamp(valore).strftime("%Y-%m-%d")
        elif isinstance(valore, str) and valore:
            return valore[:10]
        return datetime.now().strftime("%Y-%m-%d")

    def carica_dati_periodo(self, data_inizio, data_fine):
        inizio_str = self.estrai_data_str(data_inizio)
        fine_str = self.estrai_data_str(data_fine)

        # Se la data di fine è precedente all'inizio, le inverte in automatico
        if inizio_str > fine_str:
            inizio_str, fine_str = fine_str, inizio_str

        # Calcola quanti giorni ci sono nel periodo selezionato
        dt_inizio = datetime.strptime(inizio_str, "%Y-%m-%d")
        dt_fine = datetime.strptime(fine_str, "%Y-%m-%d")
        giorni_diff = (dt_fine - dt_inizio).days

        query = """
            SELECT timestamp, tiles_row, good_tiles, broken_tiles 
            FROM production_events 
            WHERE date(timestamp) BETWEEN ? AND ?
        """
        df = pd.read_sql_query(query, self.engine, params=(inizio_str, fine_str))

        # CASO 1: Un solo giorno selezionato -> Raggruppa per ORA
        if giorni_diff == 0:
            etichette = [f"{h:02d}:00" for h in range(24)]
            formato_dt = "%H:00"

        # CASO 2: Fino a un mese (31 giorni) -> Raggruppa per GIORNO
        elif giorni_diff <= 31:
            range_date = pd.date_range(start=inizio_str, end=fine_str, freq="D")
            etichette = range_date.strftime("%d-%m").tolist()
            formato_dt = "%d-%m"

        # CASO 3: Più di un mese (> 31 giorni) -> Raggruppa per MESE
        else:
            # Genera tutti i mesi compresi tra la data di inizio e quella di fine
            range_mesi = pd.period_range(start=inizio_str, end=fine_str, freq="M")
            etichette = range_mesi.strftime("%Y-%m").tolist()
            formato_dt = "%Y-%m"

        # Aggregazione comune per tutti e 3 i casi
        if df.empty:
            df_agg = pd.DataFrame({
                "periodo": etichette,
                "tiles_row": 0,
                "good_tiles": 0,
                "broken_tiles": 0
            })
        else:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df["periodo"] = df["timestamp"].dt.strftime(formato_dt)
            df_agg = df.groupby("periodo", as_index=False)[["tiles_row", "good_tiles", "broken_tiles"]].sum()
            # Riempie eventuali ore, giorni o mesi senza produzione con 0
            df_agg = df_agg.set_index("periodo").reindex(etichette, fill_value=0).reset_index()

        df_agg = df_agg.rename(columns={
            "tiles_row": "Totali",
            "good_tiles": "Buone",
            "broken_tiles": "Rotte"
        })

        df_finale = df_agg.melt(
            id_vars=["periodo"],
            value_vars=["Totali", "Buone", "Rotte"],
            var_name="Tipologia",
            value_name="Quantità"
        )

        return df_finale

    def inserisci_evento(self, tiles_row, good_tiles, broken_tiles):
        try:
            # Crea un DataFrame di una riga con i nomi esatti delle colonne
            df_nuovo = pd.DataFrame([{
                "tiles_row": tiles_row,
                "good_tiles": good_tiles,
                "broken_tiles": broken_tiles
            }])

            # Scrive sul database usando self.engine
            df_nuovo.to_sql(
                name="production_events",
                con=self.engine,
                if_exists="append",
                index=False  # evita di inserire l'indice del DataFrame come colonna
            )
            #print("Dati inseriti correttamente.")
        except Exception as e:
            print(f"Errore durante inserisci_evento: {e}")