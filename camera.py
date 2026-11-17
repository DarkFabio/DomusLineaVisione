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

            segmented = result.plot(boxes=False)

            segmented = cv2.cvtColor(
                segmented,
                cv2.COLOR_BGR2RGB
            )

            tiles = []

            if result.masks is not None:

                for i, contour in enumerate(result.masks.xy):

                    class_id = int(result.boxes.cls[i])

                    # soglia su confidence
                    conf = float(result.boxes.conf[i])
                    if conf < 0.50:
                        continue

                    # solo le classi Tile
                    class_name = self.model.names[class_id]
                    if class_name.lower() != "tile":
                        continue
                    cnt = contour.astype(np.int32)

                    rect = cv2.minAreaRect(cnt)

                    (cx, cy) = rect[0]

                    tiles.append({
                        "cx": cx,
                        "cy": cy,
                        "contour": cnt
                    })

                    cv2.circle(
                        segmented,
                        (int(cx), int(cy)),
                        5,
                        (0, 0, 255),
                        -1
                    )

            rows = self.find_rows(tiles)

            # disegna le file sulla foto

            for i, row in enumerate(rows):
                y = int(row["mean_y"])

                cv2.line(
                    segmented,
                    (0, y),
                    (segmented.shape[1], y),
                    (255, 0, 0),
                    2
                )

                cv2.putText(
                    segmented,
                    f"Row {i + 1}: {len(row['tiles'])}",
                    (20, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 0, 0),
                    2
                )

            # INFO
            row_info = []

            for i, row in enumerate(rows):
                row_info.append(
                    f"R{i + 1}: {len(row['tiles'])}"
                )

            info = (
                    f"Rows: {len(rows)} | "
                    + " | ".join(row_info)
                    + f" | Inference: {inference_ms:.1f} ms"
            )

            return segmented, info

        except Exception as e:
            print(f'Error During inference: {e}')
            no_cam_img = cv2.imread('NoCam.jpg')
            return no_cam_img, "No Cam connected"

    def find_rows(self, tiles, tolerance=50):

        rows = []

        tiles = sorted(
            tiles,
            key=lambda x: x["cy"]
        )

        for tile in tiles:

            assigned = False

            for row in rows:

                if abs(tile["cy"] - row["mean_y"]) < tolerance:
                    row["tiles"].append(tile)

                    row["mean_y"] = np.mean(
                        [t["cy"] for t in row["tiles"]]
                    )

                    assigned = True
                    break

            if not assigned:
                rows.append({
                    "tiles": [tile],
                    "mean_y": tile["cy"]
                })

        return rows

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