import os
import cv2
import time
import numpy as np
import pyrealsense2 as rs
import gradio as gr
from ultralytics import YOLO

# =====================================================
# CONFIG
# =====================================================

MODEL_PATH = "best.pt"
SAVE_FOLDER = "saved_images"

os.makedirs(SAVE_FOLDER, exist_ok=True)

# =====================================================
# MODELLO
# =====================================================

model = YOLO(MODEL_PATH)

# =====================================================
# REALSENSE
# =====================================================

pipeline = rs.pipeline()
config = rs.config()

config.enable_stream(
    rs.stream.color,
    1280,
    720,
    rs.format.bgr8,
    30
)

pipeline.start(config)

last_original_frame = None

# =====================================================
# ACQUISIZIONE + SEGMENTAZIONE
# =====================================================

def inference():

    global last_original_frame

    try:

        frames = pipeline.wait_for_frames()
        color_frame = frames.get_color_frame()

        if not color_frame:
            return None, "Camera assente"

        frame = np.asanyarray(
            color_frame.get_data()
        )

        last_original_frame = frame.copy()

        t0 = time.perf_counter()

        results = model.predict(
            frame,
            verbose=False
        )

        inference_ms = (
                               time.perf_counter() - t0
                       ) * 1000

        result = results[0]

        segmented = result.plot()

        segmented = cv2.cvtColor(
            segmented,
            cv2.COLOR_BGR2RGB
        )

        tile_count = 0
        object_count = 0

        if result.boxes is not None:

            object_count = len(result.boxes)

            for cls in result.boxes.cls:

                class_id = int(cls)

                class_name = model.names[class_id]

                if class_name.lower() == "tile":
                    tile_count += 1

        info = (
            f"Tile: {tile_count}    |    "
            f"Objects: {object_count}    |    "
            f"Inference: {inference_ms:.1f} ms"
        )

        return segmented, info

    except Exception as e:
        print(e)
        return None


# =====================================================
# SALVATAGGIO
# =====================================================

def save_image():

    global last_original_frame

    if last_original_frame is None:
        return "Nessun frame disponibile"

    filename = os.path.join(
        SAVE_FOLDER,
        f"img_{time.strftime('%Y%m%d_%H%M%S')}.png"
    )

    cv2.imwrite(filename, last_original_frame)

    return f"Salvato: {filename}"

# =====================================================
# GUI
# =====================================================

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
        fn=save_image,
        outputs=save_status
    )

    timer = gr.Timer(0.1)

    timer.tick(
        inference,
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