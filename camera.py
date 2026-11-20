import os
import cv2
import time
import numpy as np
import pyrealsense2 as rs
from ultralytics import YOLO
from pathlib import Path


class VideoCamera:
    def __init__(self):
        if Path("best.engine").is_file():
            MODEL_PATH = "best.engine"
        else:
            MODEL_PATH = "best.pt"

        self.SAVE_FOLDER = "saved_images"

        os.makedirs(self.SAVE_FOLDER, exist_ok=True)

        self.model = YOLO(MODEL_PATH)
        self.config = None

        # pulsanti per la visualizzazione della segmentazione colorata
        self.show_rows = True
        self.show_good_tiles = True
        self.show_bad_tiles = True
        self.show_objects = False

        self.pipeline = None
        self.config = None
        self.is_connected = False
        self.no_cam_img = cv2.imread("NoCam.jpg")
        self.configCamera()

        # salvataggio del frame su file
        self.last_original_frame = None

        # conteggio della fila in un'area
        self.row_in_count_zone = False
        self.row_counted = False
        self.last_event = None
        self.last_count_time = 0

    def set_visibility(self, selected):
        self.show_rows = "Rows" in selected
        self.show_good_tiles = "Good" in selected
        self.show_bad_tiles = "Bad" in selected
        self.show_objects = "Objects" in selected

    def reset_camera(self):
        print("Avvio procedura di reset telecamera...")
        # 1. Ferma la pipeline esistente per liberare le risorse USB
        if self.pipeline is not None:
            try:
                self.pipeline.stop()
            except Exception:
                pass
            self.pipeline = None

        # 2. Esegui il reset hardware sui dispositivi rilevati
        ctx = rs.context()
        devices = ctx.query_devices()
        if len(devices) == 0:
            print("Nessun dispositivo trovato per il reset hardware.")
            return False

        for device in devices:
            try:
                device.hardware_reset()
                print("Reset hardware inviato. Attesa rinegoziazione USB...")
            except Exception as e:
                print(f"Errore durante hardware_reset: {e}")

        # 3. Attendi che il dispositivo si ricolleghi al bus USB (almeno 4-5 secondi)
        time.sleep(5)
        return True

    def configCamera(self):
        try:
            ctx = rs.context()
            if len(ctx.query_devices()) == 0:
                self.is_connected = False
                print("Nessuna RealSense collegata.")
                self.reset_camera()
                return False

            self.pipeline = rs.pipeline()
            self.config = rs.config()
            self.config.enable_stream(
                rs.stream.color, 1280, 720, rs.format.bgr8, 30
            )
            self.pipeline.start(self.config)
            self.is_connected = True
            print("Telecamera configurata e avviata con successo.")
            return True
        except Exception as e:
            self.is_connected = False
            print(f"Error Init Camera: {e}")
            return False

    def recover_camera(self):
        """Tenta il reset e la riconfigurazione completa."""
        self.reset_camera()
        return self.configCamera()

    def inference(self):
        # Se la camera non è connessa, prova a riconfigurarla prima di leggere
        if not self.is_connected or self.pipeline is None:
            if not self.configCamera():
                return self.no_cam_img, "No Cam connected"

        try:
            frames = self.pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()

            if not color_frame:
                return None, "Camera assente"

            frame = np.asanyarray(
                color_frame.get_data()
            )

            self.last_original_frame = frame.copy()
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            t0 = time.perf_counter()

            results = self.model.predict(
                frame,
                verbose=False
            )

            inference_ms = (time.perf_counter() - t0) * 1000

            result = results[0]

            objects, tile_areas = self.extract_objects(result)

            total_tiles, min_area, max_area = self.classify_tiles(objects)

            rows = self.find_rows(total_tiles)

            self.update_counter(rows)

            segmented = self.draw_segmentation(frame,objects,min_area,max_area)
            segmented = self.draw_count_area(segmented)
            segmented = self.draw_rows(segmented,rows)

            info = self.build_info( rows,objects,total_tiles,inference_ms)

            return segmented, info

        except Exception as e:
            print(f"Error During inference: {e}")
            self.is_connected = False

            # Tenta il ripristino immediato (Reset + Config)
            if self.recover_camera():
                return self.no_cam_img, "Camera ripristinata, ripresa al prossimo ciclo"
            else:
                return self.no_cam_img, "No Cam connected"

    def find_rows(self, tiles, tolerance=100, min_tiles_per_row=2):

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

                    if tile["valid"] == True:
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

            if conf < self.config["camera"]["min_confidence"]:
                continue

            class_id = int(result.boxes.cls[i])
            class_name = self.model.names[class_id]

            cnt = contour.astype(np.int32)

            area = cv2.contourArea(cnt)

            rect = cv2.minAreaRect(cnt)
            (cx, cy) = rect[0]

            width, height = rect[1]
            rect_area = width * height

            # calcolo il rapporto tra area effettiva e area del quadrato che la contiene
            ratio = area / rect_area

            obj = {
                "class_name": class_name,
                "contour": cnt,
                "area": area,
                "area_ratio": ratio,
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

        min_area = self.reference_area * (1 - self.config["camera"]["min_area_percentage"])
        max_area = self.reference_area * (1 + self.config["camera"]["max_area_percentage"])
        min_ratio  = self.config["camera"]["min_rect_ratio"]
        total_tiles = []

        for obj in objects:

            obj["valid"] = False

            if obj["class_name"].lower() != "tile":
                continue

            obj["valid"] = True if min_area <= obj["area"] <= max_area and obj["area_ratio"] >= min_ratio else False

            total_tiles.append({
                "cx": obj["cx"],
                "cy": obj["cy"],
                "area": obj["area"],
                "area_ratio": obj["area_ratio"],
                "contour": obj["contour"],
                "valid": obj["valid"]
            })

        return total_tiles, min_area, max_area

    def draw_segmentation(self, frame, objects, min_area,max_area):

        image = frame.copy()
        overlay = frame.copy()

        for obj in objects:

            if obj["class_name"].lower() != "tile":
                if not self.show_objects:
                    continue
                color = (0, 0, 255)

            elif obj["valid"]:
                if not self.show_good_tiles:
                    continue
                color = (0, 255, 0)

            else:
                if not self.show_bad_tiles:
                    continue
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
                f"{int(obj['area'])} px\n"
                f"{obj['area_ratio']:.2f}"
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
            if not self.show_rows:
                return image

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

    def build_info(self, rows, objects, total_tiles, inference_ms):

        valid = sum(
            1 for tile in total_tiles
            if tile["valid"] == True
        )

        rejected_tiles = len(total_tiles) - valid

        info = (
                f"Rows:         {len(rows)}\n"
                f"Total Tiles:  {len(total_tiles)}\n"
                f"Valid:        {valid}\n"
                f"Rejected:     {rejected_tiles}\n"
                f"Area Ref:     {self.reference_area:.0f}\n"
                f"Inference:    {inference_ms:.1f} ms\n"
        )

        return info

    def update_counter(self, rows):
        # funzione per contare le tile quando entrano nell'area
        row_inside_area = False


        for row in rows:

            y = row["mean_y"]

            current_time = time.time()

            if self.config["camera"]["count_area_top"] >= y >= self.config["camera"]["count_area_bottom"]:

                if current_time - self.last_count_time > self.config["camera"]["count_lock_time"]:

                    self.last_count_time = current_time

                    row_inside_area = True

                    total = len(row["tiles"])

                    good = sum(
                        1 for tile in row["tiles"]
                        if tile["valid"] == True
                    )
                    broken = total - good

                    if not self.row_counted:
                        self.row_counted = True
                        self.last_event = {
                            "tiles_row": total,
                            "good_tiles": good,
                            "broken_tiles": broken
                        }

                    break

        if not row_inside_area:
            self.row_counted = False
            self.last_event =  None

    def draw_count_area(self, image):
        overlay = image.copy()

        cv2.rectangle(
            overlay,
            (0, self.config["camera"]["count_area_top"]),
            (image.shape[1], self.config["camera"]["count_area_bottom"]),
            (0, 255, 255),
            -1
        )

        image = cv2.addWeighted(
            overlay,
            0.20,
            image,
            0.85,
            0
        )

        return image
