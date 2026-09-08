import yaml
import os

from llama_msgs.action import GenerateResponse
from yasmin import Blackboard
from yasmin_ros import ActionState
from yasmin_ros.basic_outcomes import SUCCEED, ABORT, CANCEL
from yasmin_ros.yasmin_node import YasminNode


class LoadRouteState(ActionState):

    def __init__(self, semantic_path: str, yaml_output_path: str) -> None:
        super().__init__(
            GenerateResponse,
            "/llama/generate_response",
            self.create_llama_goal,
            result_handler=self.handle_result,
        )

        self.yaml_output_path = yaml_output_path

        # Cargar semántica de habitaciones
        semantic_path = os.path.join(semantic_path)
        semantic_data = self._load_semantic_map(semantic_path)
        # Preparar habitaciones y waypoints (poses)
        rooms_info = semantic_data.get('rooms', [])
        self.rooms = {}
        for r in rooms_info:
            if 'name' in r and 'center' in r:
                key = r['name'].lower().strip()
                self.rooms[key] = r['center']


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
        
    def create_llama_goal(self, blackboard: Blackboard) -> GenerateResponse.Goal:
        goal = GenerateResponse.Goal()

        # Enviar imagen al modelo:
        # cv_bridge = CvBridge()
        # ros_image = cv_bridge.cv2_to_imgmsg(blackboard.llama_image, encoding="bgr8")
        # goal.images = [ros_image]
        # Dentro del prompt IMAGE: <__media__>
        
        goal.prompt = f"""<|im_start|>system
        You are the navigation brain of an autonomous domestic robot. Your mission is to interpret natural language commands and decide the SEQUENCE of rooms the robot should visit.
        
        CRITICAL RULE: You can ONLY select rooms that are explicitly listed in the "AVAILABLE ROOMS" list. NEVER invent, hallucinate, or guess a room name that is not in the list.
        
        You MUST provide a "reasoning" field in your response explaining your logic.
        <|im_end|>
        <|im_start|>user
        
        INSTRUCTION: "{blackboard.stt}"
        AVAILABLE ROOMS: {self.rooms.keys()}

        TASK:
        1. Analyze the INSTRUCTION to understand the intent (single goal or sequence).
        2. Select the appropriate rooms from AVAILABLE ROOMS. 
           - EXTREMELY IMPORTANT: IF A ROOM IS NOT IN "AVAILABLE ROOMS", DO NOT OUTPUT IT.
           - If the INSTRUCTION refers to a room NOT in AVAILABLE ROOMS, return an empty list [].
           - ONLY use the exact names found in AVAILABLE ROOMS.
        3. Formulate a VERY BRIEF reasoning string (max 1 sentence) explaining the path.
        4. Output the result in YAML format.

        OUTPUT FORMAT (Strict YAML):
        reasoning: "Concise explanation (max 15 words) of the logical path."
        target_rooms:
        - "room_a"
        - "room_b"

        Example:
        reasoning: "Going to kitchen for water, then bedroom."
        target_rooms:
        - "kitchen"
        - "bedroom"

        Respond ONLY with the YAML block.
        <|im_end|>
        <|im_start|>assistant
        """
     
        goal.reset = True
        goal.sampling_config.temp = 0.0 # Aleatoriedad de respuesta. 0.0 es la menor.

        return goal

    def handle_result(self, blackboard: Blackboard, result: GenerateResponse.Result) -> str:
        response_text = result.response.text.strip()
        self._node.get_logger().info(f"🤖 Llama Raw: {response_text}")

        # Limpieza y Parseo YAML
        clean_text = response_text.replace("```yaml", "").replace("```", "").strip()

        try:
            data = yaml.safe_load(clean_text)
        except Exception as e:
            self._node.get_logger().error(f"Error al parsear YAML: {e}")
            return ABORT

        # Asegurarse de que data es un diccionario y tiene la clave target_rooms
        if not isinstance(data, dict) or 'target_rooms' not in data:
            self._node.get_logger().error("El YAML no contiene la clave 'target_rooms'.")
            return ABORT

        target_rooms_list = data['target_rooms']
        reasoning = data['reasoning']
        if not reasoning:
             reasoning = ""

        # Si la lista esta vacia no ha logrado razonar una ruta valida
        if not target_rooms_list: 
            self._node.get_logger().warn("La lista de habitaciones objetivo está vacía.")
            blackboard.tts = f"{reasoning}. No sequence found. Please repeat."
            return CANCEL

        final_waypoints = []
        
        # Procesar destinos
        for target_room_raw in target_rooms_list:
            # Si alguno de los puntos esta vacio se ignora
            if not target_room_raw:
                continue

            target_room_key = target_room_raw.lower().strip()

            # Si la habitacion existe se agrega
            if target_room_key in self.rooms.keys():
                center = self.rooms[target_room_key]
                world_x = float(center[0])
                world_y = float(center[1])
                
                final_waypoints.append({
                    "location_name": target_room_raw, 
                    "x": world_x,
                    "y": world_y,
                    "theta": 0.0
                })
                self._node.get_logger().info(f"Destino agregado: {target_room_key} -> ({world_x}, {world_y})")
            else:
                self._node.get_logger().warn(f"Habitación desconocida ignorada: '{target_room_raw}'")

        # Ninguna habitacion se agrego porque no coinciden con las habitaciones cargadas
        if not final_waypoints:
            blackboard.tts = f"{reasoning}. Rooms not found. Please repeat."
            self._node.get_logger().warn("No se generaron waypoints válidos (habitaciones no encontradas).")
            return CANCEL

        # Guardar archivo
        try:
            with open(self.yaml_output_path, "w") as file:
                yaml.dump(final_waypoints, file, default_flow_style=False)
            self._node.get_logger().info(f"Ruta guardada en {self.yaml_output_path}")
        except Exception as e:
            self._node.get_logger().error(f"Error escribiendo archivo: {e}")
            return ABORT
        
        blackboard.tts = reasoning
        return SUCCEED
