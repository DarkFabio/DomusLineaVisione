
from datetime import datetime, timedelta
import gradio as gr
from camera import VideoCamera
from DataLogger import DataLogger

camera = VideoCamera()
data_logger = DataLogger()

def salva_eventi():
    # prende l'evento generato dalla telecamera e scrive una riga sul database con il metodo dentro a DataLogger
    if camera.last_event is not None:

        data_logger.inserisci_evento(
            camera.last_event["tiles_row"],
            camera.last_event["good_tiles"],
            camera.last_event["broken_tiles"]
        )

        camera.last_event = None

with gr.Blocks(title="Tiles Vision") as demo:

    gr.Markdown("# Domus Linea Vision")

    with gr.Row(equal_height=True):
        image = gr.Image(label="Live View", scale=9)

        with gr.Column(scale = 1):
            gr.Image(
                value="logo.png",
                show_label=False,
                width=400,
                interactive=False,
                scale=2
            )
            view_group = gr.CheckboxGroup(
                choices=["Rows", "Good", "Bad", "Objects"],
                label="Visualizzazione",
                value=["Rows", "Good", "Bad"]
            )

            view_group.change(
                fn=camera.set_visibility,
                inputs=view_group
            )

            info = gr.Textbox(label="Risultati", interactive=False)

        with gr.Column(scale = 1):
            data_inizio = gr.DateTime(
                label="Data Inizio",
                value=data_logger.oggi,
                include_time=False,
                type="string"
            )
            data_fine = gr.DateTime(
                label="Data Fine",
                value=data_logger.oggi,
                include_time=False,
                type="string"
            )

            btn_oggi = gr.Button("Solo Oggi", variant="primary")
            btn_7gg = gr.Button("Ultimi 7 Giorni", variant="primary")
            btn_30gg = gr.Button("Ultimi 30 Giorni", variant="primary")

    gr.Markdown("### Analisi Produzione per Periodo")

    grafico = gr.BarPlot(
        value=data_logger.carica_dati_periodo(data_logger.oggi, data_logger.oggi),
        x="periodo",
        y="Quantità",
        color="Tipologia",
        color_map={"Totali": "#3b82f6", "Buone": "#22c55e", "Rotte": "#ef4444"},
        title="Produzione Forno",
        x_title="Periodo",
        y_title="Numero Mattonelle",
        tooltip=["periodo", "Tipologia", "Quantità"],
        height=500
    )

    # Aggiorna il grafico quando cambia una delle due date
    for selettore in [data_inizio, data_fine]:
        selettore.change(
            fn=data_logger.carica_dati_periodo,
            inputs=[data_inizio, data_fine],
            outputs=grafico
        )

    # Pulsanti rapidi per velocizzare l'operatore
    btn_oggi.click(
        fn=lambda: (datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d")),
        outputs=[data_inizio, data_fine]
    )
    btn_7gg.click(
        fn=lambda: ((datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d")),
        outputs=[data_inizio, data_fine]
    )
    btn_30gg.click(
        fn=lambda: ((datetime.now() - timedelta(days=29)).strftime("%Y-%m-%d"), datetime.now().strftime("%Y-%m-%d")),
        outputs=[data_inizio, data_fine]
    )

    # timer aggiornamento immagine telecamera
    timer_camera = gr.Timer(0.03)

    timer_camera.tick(
        camera.inference,
        outputs=[image,info]
    )

    # timer aggiornamento grafico
    timer_grafico = gr.Timer(60)

    timer_grafico.tick(
        fn=data_logger.carica_dati_periodo,
        inputs=[data_inizio, data_fine],
        outputs=grafico
    )

    # timer inserimento evento dentro al database
    timer_database = gr.Timer(1)

    timer_database.tick(
        fn=salva_eventi
    )



demo.launch(
    server_name="0.0.0.0",
    server_port=7860
)