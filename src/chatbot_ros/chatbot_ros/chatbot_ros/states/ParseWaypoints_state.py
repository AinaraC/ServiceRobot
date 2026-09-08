import os
import random
import yaml
import math

from geometry_msgs.msg import PoseStamped
from yasmin import State, Blackboard
from yasmin_ros.basic_outcomes import SUCCEED, ABORT
from yasmin_ros.yasmin_node import YasminNode

class ParseWaypointsState(State):
    def __init__(self, yaml_output_path: str, mode: str):
        super().__init__(outcomes=[SUCCEED, ABORT])
        self._node = YasminNode.get_instance()
        self.yaml_output_path = yaml_output_path
        self.mode = mode

    def execute(self, blackboard: Blackboard): 
        
        if not os.path.exists(self.yaml_output_path):
            self._node.get_logger().error(f"No se ha encontrado el archivo waypoints.yaml en: {self.yaml_output_path}")
            return ABORT
    
        # Verificación de archivo vacío
        file_size = os.path.getsize(self.yaml_output_path)
        if file_size == 0:
            self._node.get_logger().error(f"El archivo {self.yaml_output_path} tiene tamaño 0.")
            return ABORT

        try:
            with open(self.yaml_output_path, 'r') as f:
                coords = yaml.safe_load(f)
        except Exception as e:
            self._node.get_logger().error(f"Error procesando YAML o archivo: {e}")
            return ABORT

        if coords is None:
            self._node.get_logger().error("El archivo locations.yaml está vacío o mal formado.")
            return ABORT

        waypoint_dict = {}
        for wp in coords:
            try:
                pose = PoseStamped()
                pose.header.frame_id = 'map'
                pose.pose.position.x = float(wp.get('x', 0.0))
                pose.pose.position.y = float(wp.get('y', 0.0))
                theta = float(wp.get('theta', 0.0))
                pose.pose.orientation.z = math.sin(theta / 2.0)
                pose.pose.orientation.w = math.cos(theta / 2.0)

                waypoint_dict[wp.get('location_name')] = pose
                
            except Exception as e:
                self._node.get_logger().error(f"Waypoint inválido o datos faltantes: {e}")
                return  ABORT
            
        items = list(waypoint_dict.items())
        if self.mode == 'random':
            random.shuffle(items)

        blackboard.waypoints = [v for k, v in items]
        blackboard.current_waypoint_index = 0
        blackboard.target_names = [k for k, v in items]
                
        self._node.get_logger().info("Coordenadas cargadas correctamente.")
        return  SUCCEED

    