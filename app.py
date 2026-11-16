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
            return None

        frame = np.asanyarray(color_frame.get_data())

        last_original_frame = frame.copy()

        results = model.predict(
            source=frame,
            verbose=False
        )

        segmented = results[0].plot()

        segmented = cv2.cvtColor(
            segmented,
            cv2.COLOR_BGR2RGB
        )

        return segmented

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

    gr.Markdown("# RealSense D455 Semantic Segmentation")

    image = gr.Image(
        label="Segmentazione Live"
    )

    save_btn = gr.Button(
        "Salva immagine originale"
    )

    save_status = gr.Textbox(
        label="Stato"
    )

    save_btn.click(
        fn=save_image,
        outputs=save_status
    )

    timer = gr.Timer(0.1)

    timer.tick(
        fn=inference,
        outputs=image
    )

demo.launch(
    server_name="0.0.0.0",
    server_port=7860
)