
from datetime import datetime, timedelta
import gradio as gr
import plotly.graph_objects as go
from camera import VideoCamera
from DataLogger import DataLogger
import yaml
from aphyt import omron

camera = VideoCamera()
data_logger = DataLogger()

def salva_eventi():
    # prende l'evento generato dalla telecamera e scrive una riga sul database con il metodo dentro a DataLogger
    if camera.last_event is not None:
        pezzi_fila = 0
        area = 0
        # leggo i dati dal plc
        with omron.NSeries(camera.config["plc"]["ip"]) as eip_conn:
            pezzi_fila = eip_conn.read_variable("pc_pezzi_per_fila")
            area = eip_conn.read_variable("pc_area_tile")

        # Preparo i dati da scrivere nel database
        data = {
            "tiles_row": pezzi_fila,
            "good_tiles": camera.last_event["good_tiles"],
            "broken_tiles": camera.last_event["broken_tiles"],
            "area_tiles": area,
             }

        data_logger.inserisci_evento(data)

        camera.last_event = None

def load_config(config_path='config.yaml'):
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

def config_update():
    camera.config = load_config()
    data_logger.config = load_config()


config_update()

with gr.Blocks(title="Tiles Vision") as demo:

    with gr.Row(equal_height=True):
        image = gr.Image(label="Live View", scale=9, height=camera.config["ui"]["camera_heigh"])

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
                value=f"{data_logger.oggi} 00:00:00",
                include_time=False,
                type="string"
            )
            data_fine = gr.DateTime(
                label="Data Fine",
                value=f"{data_logger.oggi} 23:59:59",
                include_time=False,
                type="string"
            )

            view_periodo = gr.Radio(
                choices=["Ultima ora", "Oggi", "7 Giorni", "30 Giorni"],
                label="Periodo da visualizzare",
                value="Oggi"
            )
            view_periodo.change(
                fn=data_logger.set_periodo,
                inputs=view_periodo
            )


            view_scale = gr.Radio(
                choices=["m2", "pz"],
                label="Unità di misura",
                value="m2"
            )

            view_scale.change(
                fn=data_logger.set_unti_scale,
                inputs=view_scale
            )

    grafico = gr.Plot(
        value=data_logger.crea_grafico_periodo()
    )

    # Aggiorna il grafico quando cambia una delle due date
    # Se l'operatore modifica a mano le date, passa a modalità "manuale"
    for selettore in [data_inizio, data_fine]:
        selettore.change(
            fn=data_logger.set_manual_dates,
            inputs=[data_inizio,data_fine]
        )

    view_scale.change(
        fn=data_logger.set_periodo,
        inputs=view_scale
    )

    # timer aggiornamento immagine telecamera
    timer_camera = gr.Timer(0.03)

    timer_camera.tick(
        camera.inference,
        outputs=[image,info]
    )

    # timer aggiornamento grafico
    timer_grafico = gr.Timer(5)

    timer_grafico.tick(
        fn=data_logger.crea_grafico_periodo,
        outputs=grafico
    )

    # timer inserimento evento dentro al database
    timer_database = gr.Timer(1)

    timer_database.tick(
        fn=salva_eventi
    )

    # timer aggiornamento config
    timer_config = gr.Timer(5)

    timer_config.tick(
        fn=config_update
    )



demo.launch(
    server_name="0.0.0.0",
    server_port=7860
)