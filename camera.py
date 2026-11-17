import os
import cv2
import time
import numpy as np
import pyrealsense2 as rs
from ultralytics import YOLO



class VideoCamera:
    def __init__(self):
        MODEL_PATH = "best.pt"
        self.SAVE_FOLDER = "saved_images"

        os.makedirs(self.SAVE_FOLDER, exist_ok=True)

        self.model = YOLO(MODEL_PATH)

        self.configCamera()

        last_original_frame = None

    def configCamera(self):
        try:
            self.pipeline = rs.pipeline()
            self.config = rs.config()

            self.config.enable_stream(
                rs.stream.color,
                1280,
                720,
                rs.format.bgr8,
                30
            )

            self.pipeline.start(self.config)
        except Exception as e:
            print(f"Error Init Camera: {e}")

    def inference(self):

        global last_original_frame

        try:

            frames = self.pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()

            if not color_frame:
                return None, "Camera assente"

            frame = np.asanyarray(
                color_frame.get_data()
            )

            last_original_frame = frame.copy()

            t0 = time.perf_counter()

            results = self.model.predict(
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

                    class_name = self.model.names[class_id]

                    if class_name.lower() == "tile":
                        tile_count += 1

            info = (
                f"Tile: {tile_count}    |    "
                f"Objects: {object_count}    |    "
                f"Inference: {inference_ms:.1f} ms"
            )

            return segmented, info

        except Exception as e:
            print(f'Error During inference: {e}')
            no_cam_img = cv2.imread('NoCam.jpg')
            return no_cam_img, "No Cam connected"


    # =====================================================
    # SALVATAGGIO
    # =====================================================

    def save_image(self):

        global last_original_frame

        if last_original_frame is None:
            return "Nessun frame disponibile"

        filename = os.path.join(
            self.SAVE_FOLDER,
            f"img_{time.strftime('%Y%m%d_%H%M%S')}.png"
        )

        cv2.imwrite(filename, last_original_frame)

        return f"Salvato: {filename}"