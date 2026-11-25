from sqlalchemy import create_engine
import pandas as pd
import sqlite3
import plotly.graph_objects as go
from datetime import datetime, timedelta

class DataLogger():
    def __init__(self):
        self.crea_database()
        self.engine = create_engine('sqlite:///history.db')

        self.oggi = datetime.now().strftime("%Y-%m-%d")
        self.sette_giorni_fa = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")

        self.config = None

        self.measure_unit = 'm²'
        self.periodo_attivo = "Oggi"
        self.manual_start = datetime.now()
        self.manual_end = datetime.now()
        self.trace_type = "Barre"

        self.last_stats = ""

    def crea_database(self):
        connection = sqlite3.connect("history.db")
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS production_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
                tiles_row INTEGER,
                good_tiles INTEGER,
                broken_tiles INTEGER,
                area_tiles REAL,
                periodo_carico INTEGER
            );
        """)

    def estrai_data_str(self, valore):
        if isinstance(valore, (int, float)):
            return datetime.fromtimestamp(valore).strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(valore, str) and valore:
            # Se manca l'orario (es. solo YYYY-MM-DD), aggiunge 00:00:00
            return valore[:19] if len(valore) >= 19 else f"{valore[:10]} 00:00:00"
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def set_periodo(self, periodo):
        self.periodo_attivo = periodo

        # aggiorno il grafico subito
        return self.crea_grafico_periodo()

    def get_date_range(self):

        adesso = datetime.now()

        if self.periodo_attivo == "Ultima ora":
            inizio = adesso - timedelta(hours=1)
            fine = adesso

        elif self.periodo_attivo == "Oggi":
            inizio = adesso.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0
            )
            fine = adesso

        elif self.periodo_attivo == "7 Giorni":
            inizio = (
                    adesso - timedelta(days=6)
            ).replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0
            )

            fine = adesso

        elif self.periodo_attivo == "30 Giorni":

            inizio = (
                    adesso - timedelta(days=29)
            ).replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0
            )

            fine = adesso

        else:
            # modalità manuale

            inizio = self.manual_start
            fine = self.manual_end

        return inizio, fine

    def set_manual_dates(self,data_inizio,data_fine):

        self.periodo_attivo = "manuale"
        self.manual_start = pd.to_datetime(data_inizio)
        self.manual_end = pd.to_datetime(data_fine)
        # aggiorno il grafico subito
        return self.crea_grafico_periodo()

    def crea_grafico_periodo(self):

        dt_inizio, dt_fine = self.get_date_range()

        inizio_query = dt_inizio.strftime("%Y-%m-%d %H:%M:%S")
        fine_query = dt_fine.strftime("%Y-%m-%d %H:%M:%S")


        # Query sull'intero timestamp, non più solo su date(timestamp)
        query = """
            SELECT * FROM production_events
            WHERE timestamp BETWEEN ? AND ?
        """
        df = pd.read_sql_query(query,self.engine,params=(inizio_query, fine_query))

        if not df.empty and self.measure_unit == "m²":
            df["tiles_row"] = df["tiles_row"] * df["area_tiles"]
            df["good_tiles"] = df["good_tiles"] * df["area_tiles"]
            df["broken_tiles"] = df["broken_tiles"] * df["area_tiles"]

        # 3. Granularità asse X
        giorni_diff = (dt_fine.date() - dt_inizio.date()).days

        if self.periodo_attivo == "Ultima ora":
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

        elif giorni_diff <= 60:
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
        # PLOTLY a barre
        # ------------------------

        fig = go.Figure()
        if self.trace_type=="Barre":


            fig.add_bar(
                x=df_agg["periodo"],
                y=df_agg["tiles_row"],
                name="Totali",
                marker_color="#3b82f6"
            )

            fig.add_bar(
                x=df_agg["periodo"],
                y=df_agg["good_tiles"] + df_agg["broken_tiles"],
                name="Reali",
                marker_color="#d6cf06"
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
        # ------------------------
        # PLOTLY a linee
        # ------------------------
        if self.trace_type == "Linee":

            if df.empty:
                df_linee = pd.DataFrame(columns=["timestamp", "tiles_row", "good_tiles", "broken_tiles"])
            else:
                df = df.sort_values("timestamp").reset_index(drop=True)
                # Fallback a 11s se il campo nel DB è nullo/mancante
                periodo_nom = df["periodo_carico"]

                df["delta_s"] = df["timestamp"].diff().dt.total_seconds()
                df["soglia"] = periodo_nom * 1.3  # Tolleranza 30% (es. 11s -> 14.3s)

                righe_finali = []

                # 1. Zero iniziale (da dt_inizio fino a 1s prima del primo record)
                primo_ts = df.loc[0, "timestamp"]
                prima_soglia = float(periodo_nom.iloc[0]) * 1.3
                if (primo_ts - dt_inizio).total_seconds() > prima_soglia:
                    righe_finali.append({"timestamp": dt_inizio, "tiles_row": 0, "good_tiles": 0, "broken_tiles": 0})
                    t_rise_init = primo_ts - pd.Timedelta(seconds=float(periodo_nom.iloc[-1]))
                    if t_rise_init > dt_inizio:
                        righe_finali.append(
                            {"timestamp": t_rise_init, "tiles_row": 0, "good_tiles": 0, "broken_tiles": 0})

                # 2. Ciclo sui record e sui buchi interni
                for i, row in df.iterrows():
                    if i > 0 and row["delta_s"] > row["soglia"]:
                        t_prev = df.loc[i - 1, "timestamp"]
                        p_prev = float(periodo_nom.iloc[i - 1])

                        t_drop = t_prev + pd.Timedelta(seconds=p_prev)
                        t_rise = row["timestamp"] - pd.Timedelta(seconds=1)

                        righe_finali.append({"timestamp": t_drop, "tiles_row": 0, "good_tiles": 0, "broken_tiles": 0})
                        if t_rise > t_drop:
                            righe_finali.append(
                                {"timestamp": t_rise, "tiles_row": 0, "good_tiles": 0, "broken_tiles": 0})

                    righe_finali.append({
                        "timestamp": row["timestamp"],
                        "tiles_row": row["tiles_row"],
                        "good_tiles": row["good_tiles"],
                        "broken_tiles": row["broken_tiles"]
                    })

                # 3. Zero finale (dal termine dell'ultimo periodo fino a dt_fine)
                ultimo_ts = df.loc[len(df) - 1, "timestamp"]
                ultima_soglia = float(periodo_nom.iloc[-1]) * 1.3
                if (dt_fine - ultimo_ts).total_seconds() > ultima_soglia:
                    t_drop_end = ultimo_ts + pd.Timedelta(seconds=float(periodo_nom.iloc[-1]))
                    if t_drop_end < dt_fine:
                        righe_finali.append(
                            {"timestamp": t_drop_end, "tiles_row": 0, "good_tiles": 0, "broken_tiles": 0})
                    righe_finali.append({"timestamp": dt_fine, "tiles_row": 0, "good_tiles": 0, "broken_tiles": 0})

                df_linee = pd.DataFrame(righe_finali)

            fig.add_trace(go.Scatter(
                x=df_linee["timestamp"], y=df_linee["tiles_row"],
                mode="lines", name="Totali",
                line=dict(color="#3b82f6", width=2),
                fill="tozeroy", fillcolor="rgba(59,130,246,0.15)"
            ))

            fig.add_trace(go.Scatter(
                x=df_linee["timestamp"], y=df_linee["good_tiles"] + df_linee["broken_tiles"],
                mode="lines", name="Reali",
                line=dict(color="#ded837", width=2),
                fill="tozeroy", fillcolor="rgba(222,216,55,0.15)"
            ))

            fig.add_trace(go.Scatter(
                x=df_linee["timestamp"], y=df_linee["good_tiles"],
                mode="lines", name="Buone",
                line=dict(color="#57e841", width=2),
                fill="tozeroy", fillcolor="rgba(87,232,65,0.15)"
            ))

            fig.add_trace(go.Scatter(
                x=df_linee["timestamp"], y=df_linee["broken_tiles"],
                mode="lines", name="Rotte",
                line=dict(color="#ef4444", width=2),
                fill="tozeroy", fillcolor="rgba(239,68,68,0.15)"
            ))

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

        if self.trace_type == "Barre":
            fig.update_xaxes(
                type="category",
                categoryorder="array",
                categoryarray=etichette
            )
        else:
            fig.update_xaxes(
                type="date",
                range=[dt_inizio, dt_fine]  # <-- Blocca la finestra esatta (es. 10:30 -> 11:30)
            )

        return fig, self.build_stats(df, df_agg, dt_inizio, dt_fine)

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
        # aggiorno il grafico subito
        return self.crea_grafico_periodo()

    def set_trace_type(self, type):
        self.trace_type = type
        # aggiorno il grafico subito
        return self.crea_grafico_periodo()

    def build_stats(self, df, df_agg, dt_inizio, dt_fine):
        # 1. Totali da df_agg (già sommati e convertiti in m² o Pezzi)
        tot_teorico = df_agg["tiles_row"].sum()
        tot_buone = df_agg["good_tiles"].sum()
        tot_rotte = df_agg["broken_tiles"].sum()
        tot_reale = tot_buone + tot_rotte

        perc_reale = (tot_reale / tot_teorico * 100) if tot_teorico > 0 else 0.0
        perc_buone = (tot_buone / tot_reale * 100) if tot_reale > 0 else 0.0
        perc_rotte = (tot_rotte / tot_reale * 100) if tot_reale > 0 else 0.0

        # 2. Utilizzo forno e vuoti da df (contiene timestamp e periodo_carico)
        durata_totale_s = (dt_fine - dt_inizio).total_seconds()
        if not df.empty and durata_totale_s > 0:
            df_sorted = df.sort_values("timestamp").reset_index(drop=True)
            periodi = df_sorted["periodo_carico"].fillna(11).astype(float)
            delta_next = (df_sorted["timestamp"].shift(-1) - df_sorted["timestamp"]).dt.total_seconds()
            secondi_attivi = delta_next.combine(periodi, min)
            secondi_attivi.iloc[-1] = max(
                0.0,
                min(float(periodi.iloc[-1]), (dt_fine - df_sorted["timestamp"].iloc[-1]).total_seconds())
            )
            perc_utilizzo = min(100.0, (secondi_attivi.sum() / durata_totale_s) * 100)
        else:
            perc_utilizzo = 0.0

        perc_vuoti = max(0.0, 100.0 - perc_utilizzo)
        fmt = ".0f" if self.measure_unit == "m²" else ".0f"

        self.last_stats = (
            f"📊 UTILIZZO FORNO\n"
            f"• Attivo: {int(perc_utilizzo)}%  |  Vuoti: {int(perc_vuoti)}%\n"
            f"• Reale/Totale: {int(perc_reale)}% ({tot_reale:{fmt}} / {tot_teorico:{fmt}} {self.measure_unit})\n\n"
            f"🧱 QUALITÀ MATERIALE\n"
            f"• Buone: {int(perc_buone)}% ({tot_buone:{fmt}} {self.measure_unit})\n"
            f"• Rotte: {int(perc_rotte)}% ({tot_rotte:{fmt}} {self.measure_unit})"
        )
        return self.last_stats

    def get_stats(self):
        return self.last_stats


