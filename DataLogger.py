from sqlalchemy import create_engine
import pandas as pd
import gradio as gr
import plotly.graph_objects as go
from datetime import datetime, timedelta

class DataLogger():
    def __init__(self):
        self.engine = create_engine('sqlite:///history.db')

        self.oggi = datetime.now().strftime("%Y-%m-%d")
        self.sette_giorni_fa = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")

        self.config = None

        self.measure_unit = 'm2'
        self.periodo_attivo = "oggi"  # Può essere: "1h", "oggi", "7gg", "30gg",

    def estrai_data_str(self, valore):
        if isinstance(valore, (int, float)):
            return datetime.fromtimestamp(valore).strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(valore, str) and valore:
            # Se manca l'orario (es. solo YYYY-MM-DD), aggiunge 00:00:00
            return valore[:19] if len(valore) >= 19 else f"{valore[:10]} 00:00:00"
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def set_periodo(self, periodo, data_inizio = None, data_fine = None):
        self.periodo_attivo = periodo
        adesso = datetime.now()

        fine = adesso

        # 1. Calcolo dinamico di inizio e fine in base alla modalità
        if self.periodo_attivo == "Ultima ora":
            inizio = adesso - timedelta(hours=1)
        elif self.periodo_attivo == "Oggi":
            inizio = adesso.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.periodo_attivo == "7 Giorni":
            inizio = (adesso - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.periodo_attivo == "30 Giorni":
            inizio = (adesso - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            inizio = self.estrai_data_str(data_inizio)
            fine = self.estrai_data_str(data_fine)

        if inizio > fine:
            inizio, fine_str = fine, inizio


        return inizio, fine



    def crea_grafico_periodo(self, dt_inizio=None, dt_fine=None):

        inizio_query = dt_inizio.strftime("%Y-%m-%d %H:%M:%S")
        fine_query = dt_fine.strftime("%Y-%m-%d %H:%M:%S")


        # Query sull'intero timestamp, non più solo su date(timestamp)
        query = """
            SELECT * FROM production_events
            WHERE timestamp BETWEEN ? AND ?
        """
        df = pd.read_sql_query(
            query,
            self.engine,
            params=(inizio_query, fine_query)
        )

        if not df.empty and self.measure_unit == "m2":
            df["tiles_row"] = df["tiles_row"] * df["area_tiles"]
            df["good_tiles"] = df["good_tiles"] * df["area_tiles"]
            df["broken_tiles"] = df["broken_tiles"] * df["area_tiles"]

        # 3. Granularità asse X
        giorni_diff = (dt_fine.date() - dt_inizio.date()).days

        if self.periodo_attivo == "1h":
            # Arrotonda l'inizio al blocco di 5 minuti precedente (es. 14:23 -> 14:20)
            dt_inizio_floor = dt_inizio.replace(minute=(dt_inizio.minute // 5) * 5, second=0, microsecond=0)
            dt_fine_floor = dt_fine.replace(minute=(dt_fine.minute // 5) * 5, second=0, microsecond=0)

            etichette = (
                pd.date_range(start=dt_inizio_floor, end=dt_fine_floor, freq="5min")
                .strftime("%H:%M")
                .tolist()
            )
            formato = "5min"
        elif giorni_diff == 0:
            etichette = [f"{h:02d}:00" for h in range(24)]
            formato = "%H:00"
        elif giorni_diff <= 31:
            etichette = (
                pd.date_range(start=dt_inizio.date(), end=dt_fine.date(), freq="D")
                .strftime("%d-%m")
                .tolist()
            )
            formato = "%d-%m"
        else:
            etichette = (
                pd.period_range(start=dt_inizio.date(), end=dt_fine.date(), freq="M")
                .strftime("%Y-%m")
                .tolist()
            )
            formato = "%Y-%m"

        # ------------------------
        # AGGREGAZIONE
        # ------------------------

        if df.empty:

            df_agg = pd.DataFrame({
                "periodo": etichette,
                "tiles_row": 0,
                "good_tiles": 0,
                "broken_tiles": 0
            })

        else:

            df["timestamp"] = pd.to_datetime(df["timestamp"])

            if formato == "5min":
                df["periodo"] = df["timestamp"].dt.floor("5min").dt.strftime("%H:%M")
            else:
                df["periodo"] = df["timestamp"].dt.strftime(formato)

            df_agg = (
                df.groupby(
                    "periodo",
                    as_index=False
                )[[
                    "tiles_row",
                    "good_tiles",
                    "broken_tiles"
                ]]
                .sum()
            )

            df_agg = (
                df_agg
                .set_index("periodo")
                .reindex(
                    etichette,
                    fill_value=0
                )
                .reset_index()
            )

            df_agg.rename(
                columns={
                    "index": "periodo"
                },
                inplace=True
            )

        # ------------------------
        # PLOTLY
        # ------------------------

        fig = go.Figure()

        fig.add_bar(
            x=df_agg["periodo"],
            y=df_agg["tiles_row"],
            name="Totali",
            marker_color="#3b82f6"
        )

        fig.add_bar(
            x=df_agg["periodo"],
            y=df_agg["good_tiles"],
            name="Buone",
            marker_color="#22c55e"
        )

        fig.add_bar(
            x=df_agg["periodo"],
            y=df_agg["broken_tiles"],
            name="Rotte",
            marker_color="#ef4444"
        )

        fig.update_layout(
            barmode="group",
            title="Produzione Forno",
            xaxis_title="Periodo",
            yaxis_title="Mattonelle",
            height=500,
            legend_title="Tipologia",
            plot_bgcolor="rgba(0, 0, 0, 0)",
            paper_bgcolor="rgba(0, 0, 0, 0)",
            font=dict(
                color="#f3f4f6",
                size=13),
            xaxis=dict(
                type="category",
                color="#9ca3af",  # Colore dei numeri sull'asse X
                gridcolor="#374151",  # Linee della griglia sottili e discrete
                zerolinecolor="#4b5563"),  # Linea dello zero leggermente più marcata
            yaxis=dict(
                color="#9ca3af",  # Colore dei numeri sull'asse Y
                gridcolor="#374151",
                zerolinecolor="#4b5563")
        )

        fig.update_xaxes(
            categoryorder="array",
            categoryarray=etichette
        )

        return fig

    def inserisci_evento(self, data):
        try:
            # Crea un DataFrame di una riga con i nomi esatti delle colonne
            df_nuovo = pd.DataFrame([data])

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

    def set_unti_scale(self, view_scale):
        # funzione richiamata quando si cambia l'unità di misura di visualizzazione
        self.measure_unit = view_scale
