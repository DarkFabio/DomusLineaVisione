
import gradio as gr
from camera import VideoCamera

camera = VideoCamera()

with gr.Blocks() as demo:

    gr.Markdown(
        "# Domus Linea Vision"
    )

    image = gr.Image(
        label="Live View"
    )
    with gr.Row():
        info = gr.Textbox(
            label="Risultati",
            interactive=False
        )

        with gr.Accordion(
                "Visualizzazione",
                open=True
        ):
            with gr.Column():
                show_rows = gr.Checkbox(
                    label="Rows"
                )

                show_good_tiles = gr.Checkbox(
                    label="Good"
                )

                show_bad_tiles = gr.Checkbox(
                    label="Bad"
                )

                show_objects = gr.Checkbox(
                    label="Objects"
                )

                show_rows.change(
                    lambda x: setattr(camera, "show_rows", x),
                    inputs=show_rows
                )

                show_good_tiles.change(
                    lambda x: setattr(camera, "show_good_tiles", x),
                    inputs=show_good_tiles
                )

                show_bad_tiles.change(
                    lambda x: setattr(camera, "show_bad_tiles", x),
                    inputs=show_bad_tiles
                )

                show_objects.change(
                    lambda x: setattr(camera, "show_objects", x),
                    inputs=show_objects
                )


    with gr.Row():
        save_btn = gr.Button(
            "Salva immagine originale"
        )

        save_status = gr.Textbox(
            label="Salvataggio"
        )

    save_btn.click(
        fn=camera.save_image,
        outputs=save_status
    )

    timer = gr.Timer(0.1)

    timer.tick(
        camera.inference,
        outputs=[
            image,
            info
        ]
    )

    gr.Image(
        value="logo.png",
        show_label=False,
        width=400,
        interactive=False,
    )

demo.launch(
    server_name="0.0.0.0",
    server_port=7860
)