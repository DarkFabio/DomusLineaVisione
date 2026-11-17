
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

    info = gr.Textbox(
        label="Risultati",
        interactive=False
    )

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
        container=False
    )

    gr.Markdown("""
        <div align="center">
        <img src="/gradio_api/file=logo.png" width="400">
        </div>
        """)

demo.launch(
    server_name="0.0.0.0",
    server_port=7860
)