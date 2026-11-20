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

    def estrai_data_str(self, valore):
        if isinstance(valore, (int, float)):
            return datetime.fromtimestamp(valore).strftime("%Y-%m-%d")
        elif isinstance(valore, str) and valore:
            return valore[:10]
        return datetime.now().strftime("%Y-%m-%d")

    def crea_grafico_periodo(self, data_inizio, data_fine):

        inizio_str = self.estrai_data_str(data_inizio)
        fine_str = self.estrai_data_str(data_fine)

        if inizio_str > fine_str:
            inizio_str, fine_str = fine_str, inizio_str

        dt_inizio = datetime.strptime(
            inizio_str,
            "%Y-%m-%d"
        )

        dt_fine = datetime.strptime(
            fine_str,
            "%Y-%m-%d"
        )

        giorni_diff = (
                dt_fine - dt_inizio
        ).days

        query = """
            SELECT * FROM production_events
            WHERE date(timestamp) BETWEEN ? AND ?
        """

        df = pd.read_sql_query(
            query,
            self.engine,
            params=(inizio_str, fine_str)
        )

        # dal database leggo il numero di mattonelle, poi li converto in m2
        if self.measure_unit == "m2":
            df["tiles_row"] = (df["tiles_row"] * df["area_tiles"])

            df["good_tiles"] = (df["good_tiles"] * df["area_tiles"])

            df["broken_tiles"] = (df["broken_tiles"] * df["area_tiles"])

        # ------------------------
        # SELEZIONE PERIODO
        # ------------------------

        if giorni_diff == 0:

            etichette = [
                f"{h:02d}:00"
                for h in range(24)
            ]

            formato = "%H:00"

        elif giorni_diff <= 31:

            etichette = (
                pd.date_range(
                    start=inizio_str,
                    end=fine_str,
                    freq="D"
                )
                .strftime("%d-%m")
                .tolist()
            )

            formato = "%d-%m"

        else:

            etichette = (
                pd.period_range(
                    start=inizio_str,
                    end=fine_str,
                    freq="M"
                )
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

            df["timestamp"] = pd.to_datetime(
                df["timestamp"]
            )

            df["periodo"] = (
                df["timestamp"]
                .dt.strftime(formato)
            )

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
