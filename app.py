
from datetime import datetime, timedelta
import gradio as gr
from camera import VideoCamera
from DataLogger import DataLogger

camera = VideoCamera()
data_logger = DataLogger()

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
                value=[]
            )

            view_group.change(
                fn=camera.set_visibility,
                inputs=view_group
            )

            info = gr.Textbox(label="Risultati", interactive=False)

    gr.Markdown("### Analisi Produzione per Periodo")

    with gr.Row(equal_height=True):
        data_inizio = gr.DateTime(
            label="Data Inizio",
            value=data_logger.sette_giorni_fa,
            include_time=False,
            type="string"
        )
        data_fine = gr.DateTime(
            label="Data Fine",
            value=data_logger.oggi,
            include_time=False,
            type="string"
        )

        with gr.Column():
            btn_oggi = gr.Button("Solo Oggi", variant="primary")
            btn_7gg = gr.Button("Ultimi 7 Giorni", variant="primary")
            btn_30gg = gr.Button("Ultimi 30 Giorni", variant="primary")

    grafico = gr.BarPlot(
        value=data_logger.carica_dati_periodo(data_logger.sette_giorni_fa, data_logger.oggi),
        x="periodo",
        y="Quantità",
        color="Tipologia",
        color_map={"Totali": "#3b82f6", "Buone": "#22c55e", "Rotte": "#ef4444"},
        title="Riepilogo Produzione Mattonelle",
        x_title="Periodo (Ore o Giorni)",
        y_title="Numero Mattonelle",
        tooltip=["periodo", "Tipologia", "Quantità"],
        height=600
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
    timer_grafico = gr.Timer(0.03)

    timer_grafico.tick(
        fn=data_logger.carica_dati_periodo,
        inputs=[data_inizio, data_fine],
        outputs=grafico
    )



demo.launch(
    server_name="0.0.0.0",
    server_port=7860
)