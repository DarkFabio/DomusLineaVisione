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

            inference_ms = (time.perf_counter() - t0) * 1000

            result = results[0]

            objects, tile_areas = self.extract_objects(result)

            valid_tiles, min_area, max_area = self.classify_tiles(objects)

            rows = self.find_rows(valid_tiles)

            segmented = self.draw_segmentation(
                frame,
                objects,
                min_area,
                max_area
            )

            segmented = self.draw_rows(
                segmented,
                rows
            )

            info = self.build_info(
                rows,
                objects,
                valid_tiles,
                inference_ms
            )

            return segmented, info

        except Exception as e:
            print(f'Error During inference: {e}')
            no_cam_img = cv2.imread('NoCam.jpg')
            return no_cam_img, "No Cam connected"

    def find_rows(self, tiles, tolerance=50, min_tiles_per_row=2):

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

        # tolgo le file che contengono meno mattonelle del minino impostato
        rows = [
            row
            for row in rows
            if len(row["tiles"]) >= min_tiles_per_row
        ]

        return rows

    def extract_objects(self, result):

        objects = []
        tile_areas = []

        if result.masks is None:
            return objects, tile_areas

        for i, contour in enumerate(result.masks.xy):

            conf = float(result.boxes.conf[i])

            if conf < 0.50:
                continue

            class_id = int(result.boxes.cls[i])
            class_name = self.model.names[class_id]

            cnt = contour.astype(np.int32)

            area = cv2.contourArea(cnt)

            rect = cv2.minAreaRect(cnt)
            (cx, cy) = rect[0]

            obj = {
                "class_name": class_name,
                "contour": cnt,
                "area": area,
                "cx": cx,
                "cy": cy
            }

            objects.append(obj)

            if class_name.lower() == "tile":
                tile_areas.append(area)

        return objects, tile_areas

    def classify_tiles(self, objects):

        tile_areas = [
            obj["area"]
            for obj in objects
            if obj["class_name"].lower() == "tile"
        ]

        if not tile_areas:
            return [], 0, 0

        self.reference_area = np.median(tile_areas)

        min_area = self.reference_area * (1 - 0.3)
        max_area = self.reference_area * (1 + 0.7)

        valid_tiles = []

        for obj in objects:

            obj["valid"] = False

            if obj["class_name"].lower() != "tile":
                continue

            if min_area <= obj["area"] <= max_area:
                obj["valid"] = True

                valid_tiles.append({
                    "cx": obj["cx"],
                    "cy": obj["cy"],
                    "area": obj["area"],
                    "contour": obj["contour"]
                })

        return valid_tiles, min_area, max_area

    def draw_segmentation(self, frame, objects, min_area,max_area):

        image = frame.copy()
        overlay = frame.copy()

        for obj in objects:

            if obj["class_name"].lower() != "tile":

                color = (0, 0, 255)

            elif min_area <= obj["area"] <= max_area:

                color = (0, 255, 0)

            else:

                color = (255, 0, 0)

            cv2.fillPoly(
                overlay,
                [obj["contour"]],
                color
            )

            cv2.drawContours(
                image,
                [obj["contour"]],
                -1,
                color,
                2
            )

            label = (
                f"{obj['class_name']} "
                f"{int(obj['area'])}"
            )

            cv2.putText(
                image,
                label,
                (int(obj["cx"]) - 40, int(obj["cy"]) - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2
            )

            cv2.circle(
                image,
                (int(obj["cx"]), int(obj["cy"])),
                5,
                (255, 255, 255),
                -1
            )

        image = cv2.addWeighted(
            overlay,
            0.25,
            image,
            0.65,
            0
        )

        return image

    def draw_rows(self, image, rows):

        for i, row in enumerate(rows):
            y = int(row["mean_y"])

            cv2.line(
                image,
                (0, y),
                (image.shape[1], y),
                (255, 255, 0),
                2
            )

            cv2.putText(
                image,
                f"Row {i + 1}: {len(row['tiles'])}",
                (20, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 0),
                2
            )

        return image

    def build_info(self,rows,objects,valid_tiles,inference_ms):

        row_info = []

        for i, row in enumerate(rows):
            row_info.append(
                f"R{i + 1}: {len(row['tiles'])}"
            )

        total_tiles = sum(
            1 for obj in objects
            if obj["class_name"].lower() == "tile"
        )

        rejected_tiles = total_tiles - len(valid_tiles)

        info = (
                f"Rows:         {len(rows)}\n"
                f"Valid Tiles:  {len(valid_tiles)}\n"
                f"Rejected:     {rejected_tiles}\n"
                f"Area Ref:     {self.reference_area:.0f}\n"
                f"Inference:    {inference_ms:.1f} ms\n"
        )

        return info

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