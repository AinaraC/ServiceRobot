import base64
import os

import cv2
import numpy as np
import yaml

import rclpy
from rclpy.duration import Duration
from tf2_ros import Buffer, TransformListener
from yasmin import State, Blackboard
from yasmin_ros.basic_outcomes import SUCCEED, ABORT 
from yasmin_ros.yasmin_node import YasminNode


class LoadMapState(State):
    def __init__(self, map_yaml_path: str):
        super().__init__(outcomes=[SUCCEED, ABORT])
        self._node = YasminNode.get_instance()

        # Inicializar Buffer y Listener para acumular transformadas desde el inicio
        self.tf_buffer = Buffer(cache_time=Duration(seconds=5.0))
        self.tf_listener = TransformListener(self.tf_buffer, self._node)

        # Cargar mapa
        self.map_metadata, self.base_image = self._load_resources(map_yaml_path)
        map_dir = os.path.dirname(map_yaml_path)

        # Cargar semántica de habitaciones
        semantic_path = os.path.join(map_dir, 'semantic.yaml')
        self.semantic_data = self._load_semantic_map(semantic_path)

    def _load_semantic_map(self, semantic_path: str):
        """Lee el archivo YAML de habitaciones si existe."""
        if not os.path.exists(semantic_path):
            self._node.get_logger().error(f"No se ha encontrado semántica en: {semantic_path}")
            return ABORT
        try:
            with open(semantic_path, 'r') as f:
                data = yaml.safe_load(f)
            self._node.get_logger().info(f"Semántica cargada: {len(data['rooms'])} habitaciones.")
            return data
        except Exception as e:
            self._node.get_logger().error(f"Error leyendo YAML semántico: {e}")
            return ABORT

    def _load_resources(self, map_yaml_path: str):
        """Carga el mapa de ocupación si existe."""
        if not os.path.exists(map_yaml_path):
            self._node.get_logger().error(f"No se ha encontrado mapa en: {map_yaml_path}")
            return ABORT
        try:
            with open(map_yaml_path, 'r') as f:
                data = yaml.safe_load(f)
            map_dir = os.path.dirname(map_yaml_path)
            pgm_path = os.path.join(map_dir, data['image'])
            img = cv2.imread(pgm_path, cv2.IMREAD_GRAYSCALE)
            if img is None: 
                self._node.get_logger().error(f"Error leyendo imagen del mapa: {pgm_path}")
                return ABORT
            return data, cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        except Exception as e:
            self._node.get_logger().error(f"Error leyendo YAML mapa: {e}")
            return ABORT

    def execute(self, blackboard: Blackboard):

        self._node.get_logger().info("Cargando mapa y localizando robot...")

        # Limpiar buffer para eliminar datos antiguos
        # self.tf_buffer.clear()

        # TF del robot
        target_frame = 'map'
        source_frame = 'base_link'

        try:
            trans = self.tf_buffer.lookup_transform(
                    target_frame,
                    source_frame,
                    rclpy.time.Time(), 
                    timeout=Duration(seconds=5.0) 
                )        
            
            # Centro del robot
            rx = trans.transform.translation.x
            ry = trans.transform.translation.y
            self._node.get_logger().info(f"Robot capturado en: ({rx:.2f}, {ry:.2f})")

            # Dibujar sobre mapa
            current_view = self.base_image.copy()
            final_image = self._draw_scene(current_view, rx, ry)
            
            # Guardar en disco para debug
            cv2.imwrite("./debug_robot_map.png", final_image)

            # Guardar imagen y metadata en Blackboard
            blackboard.llama_image = np.array(final_image)
            blackboard.semantic_data = self.semantic_data
            
            return SUCCEED

        except Exception as e:
            self._node.get_logger().error(f"Error procesando mapa: {e}")
            return ABORT

    def _draw_scene(self, img, rx, ry, orientation_q=None, target_pose=None):
        h, w, _ = img.shape
        res = self.map_metadata['resolution']
        ox = self.map_metadata['origin'][0]
        oy = self.map_metadata['origin'][1]

        def to_pix(mx, my):
            px = int((mx - ox) / res)
            py = h - int((my - oy) / res)
            return px, py

        # --- PRE-CALCULAR COLORES Y HABITACIONES ---
        # Usar HSV para generar colores distinguidos
        rooms = []
        if self.semantic_data and 'rooms' in self.semantic_data:
            rooms = self.semantic_data['rooms']
        num_rooms = len(rooms)

        room_colors = []
        for i, room in enumerate(rooms):
            if 'color' in room:
                # Usar color del YAML (se asume formato [B, G, R])
                c = room['color']
                room_colors.append((int(c[0]), int(c[1]), int(c[2])))
            else:
                # Generar color aleatorio, llama puede fallar si son muy similares
                room_colors.append((random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))

        # --- DIBUJAR HABITACIONES EN EL MAPA ---
        # Se dibujan bounding boxes de las habitaciones
        for i, room in enumerate(rooms):
            border_color = room_colors[i]
            cx, cy = room['center']
            rw_room, rh_room = room['size']
            tl_m = (cx - rw_room/2, cy + rh_room/2)
            br_m = (cx + rw_room/2, cy - rh_room/2)
            cv2.rectangle(img, to_pix(tl_m[0], tl_m[1]), to_pix(br_m[0], br_m[1]), border_color, 3)


        # --- DIBUJAR ROBOT ---
        cv2.circle(img, to_pix(rx, ry), 5, (0,0,255), -1) # Circulo rojo

        # --- CREAR LEYENDA (Si hay habitaciones) ---
        if num_rooms > 0:
            legend_w = max(int(w * 0.12), 120)  
            new_w = w + legend_w
            new_img = np.ones((h, new_w, 3), dtype=np.uint8) * 255 
            new_img[:, :w] = img

            margin = int(legend_w * 0.06)
            sw = int(min(28, max(14, h * 0.035))) 
            spacing = int(max(6, h * 0.016))
            x0 = w + margin
            y0 = margin
            font_scale = float(max(0.38, min(0.5, h / 1000.0)))
            font_thickness = 1

            for i, room in enumerate(rooms):
                items_per_col = max(1, (h - 2 * margin) // (sw + spacing))
                row = i % items_per_col
                
                x = x0 
                y = y0 + row * (sw + spacing)
                
                # Dibujar cuadro de entrada de la leyenda
                cv2.rectangle(new_img, (x, y), (x + sw, y + sw), room_colors[i], -1)

                name = room.get('name', f'Room {i}')
                text_x = x + sw + int(margin / 2)
                
                cv2.putText(new_img, name, (text_x, y + sw - 5), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,0,0), font_thickness, cv2.LINE_AA)

            return new_img # Devuelve imagen con leyenda
        
        return img # Devuelve la imagen normal sin leyenda