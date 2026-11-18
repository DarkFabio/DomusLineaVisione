
import gradio as gr
from camera import VideoCamera

camera = VideoCamera()

with gr.Blocks(title="Tiles Vision") as demo:

    gr.Markdown("# Domus Linea Vision")

    with gr.Row(equal_height=True):
        image = gr.Image(label="Live View", scale=9)
        with gr.Column(scale = 1):
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

    with gr.Row(equal_height=True):
        save_btn = gr.Button(
            "Salva immagine originale",
            scale=3
        )

        save_status = gr.Textbox(
            label="Salvataggio",
            scale=5
        )

        gr.Image(
            value="logo.png",
            show_label=False,
            width=400,
            interactive=False,
            scale=2
        )

    save_btn.click(
        fn=camera.save_image,
        outputs=save_status
    )

    timer = gr.Timer(0.03)

    timer.tick(
        camera.inference,
        outputs=[
            image,
            info
        ]
    )



demo.launch(
    server_name="0.0.0.0",
    server_port=7860
)