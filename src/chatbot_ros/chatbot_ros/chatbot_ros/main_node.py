#!/usr/bin/env python3
import threading
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.parameter import Parameter

from yasmin import Blackboard
from yasmin import StateMachine
from yasmin_viewer import YasminViewerPub
from yasmin_ros.ros_logs import set_ros_loggers
from yasmin_ros.basic_outcomes import SUCCEED, CANCEL, ABORT, TIMEOUT
from yasmin_ros.yasmin_node import YasminNode


from chatbot_ros.states import ListenState
from chatbot_ros.states import SpeakState
from chatbot_ros.states import LoadRouteState
from chatbot_ros.states import DecisionState
from chatbot_ros.states import NavigateToWaypointState
from chatbot_ros.states import ParseWaypointsState

# Cargar parámetros desde launch
def load_launch_parameters(node):
    names_and_defaults = {
        "mode": "sequential",
        "yaml_output_path": "/home/ainara/unileon/servicios/proyecto/waypoints.yaml",
        "semantic_path": "/home/ainara/unileon/servicios/proyecto/semantic.yaml",
        "timeout": 500.0,
    }
    params = {}
    for name, default in names_and_defaults.items():
        try:
            node.declare_parameter(name, default)
            params[name] = node.get_parameter(name).value
        except Exception:
            params[name] = default
    return params

class ChatBot:

    def __init__(self, params) -> None:
        
        # Asegurar que use_sim_time está activo
        node = YasminNode.get_instance()
        if not node.has_parameter("use_sim_time"):
            node.declare_parameter("use_sim_time", True)

        # Crear máquina de estados
        self.sm = StateMachine(outcomes=[CANCEL, ABORT])

        # 1. SALUDO INICIAL ("¿A dónde quieres ir?")
        self.sm.add_state(
            "OPENING",
            SpeakState(),
            transitions={
                SUCCEED: "LISTENING_TASK",
                ABORT: ABORT,
                CANCEL: CANCEL,
                TIMEOUT: ABORT,
            },
        )

        # 2. ESCUCHAR LA RUTA
        self.sm.add_state(
            "LISTENING_TASK",
            ListenState(),
            transitions={
                SUCCEED: "CREATING_ROUTE",
                ABORT: ABORT,
                CANCEL: CANCEL,
            },
        )

        # 3. CREAR RUTA (guardar waypoints en yaml)
        self.sm.add_state(
            "CREATING_ROUTE",
            LoadRouteState(params["semantic_path"], params["yaml_output_path"]),
            transitions={
                SUCCEED: "REASONING",
                CANCEL: "OPENING",
                ABORT: ABORT,
            },
        )

        # 4. RAZONAR
        self.sm.add_state(
            "REASONING",
            SpeakState(),
            transitions={
                SUCCEED: "PARSE_WAYPOINTS",
                CANCEL: CANCEL,
                ABORT: ABORT,
                TIMEOUT: ABORT,
            },
        )

        # 5. PARSEAR WAYPOINTS MODO SECUENCIAL O RANDOM (obtener waypoints del yaml)
        self.sm.add_state(
            "PARSE_WAYPOINTS",
            ParseWaypointsState(yaml_output_path=params["yaml_output_path"], mode=params["mode"]),
            transitions={
                SUCCEED: "NAVIGATING",
                ABORT: ABORT,
            },
        )

        # 6. NAVEGAR 
        self.sm.add_state(
            "NAVIGATING",
            NavigateToWaypointState(timeout=params["timeout"]),
            transitions={
                SUCCEED: "ASKING_NEXT_MOVE", # Llegó al punto
                CANCEL: "ASKING_NEXT_MOVE", # No llegó
                ABORT: ABORT,
            },
        )

        # 7. PREGUNTAR SIGUIENTE PASO ("¿Qué quieres hacer ahora?")
        self.sm.add_state(
            "ASKING_NEXT_MOVE",
            SpeakState(),
            transitions={
                SUCCEED: "LISTENING_COMMAND",
                CANCEL: CANCEL,
                ABORT: ABORT,
                TIMEOUT: ABORT,
            },
        )

        # 8. ESCUCHAR COMANDO 
        self.sm.add_state(
            "LISTENING_COMMAND",
            ListenState(),
            transitions={
                SUCCEED: "DECIDING",
                CANCEL: CANCEL,
                ABORT: ABORT,
            },
        )

        # 9. TOMAR DECISIÓN ("Stop", "Next", "Cancel", "Repeat")
        self.sm.add_state(
            "DECIDING",
            DecisionState(),
            transitions={
                SUCCEED: "NAVIGATING",        # Next -> Navegar siguiente punto
                CANCEL: "OPENING",            # Cancel -> Volver al inicio
                "PAUSE": "ASKING_NEXT_MOVE",   # Stop -> Preguntar de nuevo 
                ABORT: "ASKING_NEXT_MOVE",    # No entendí -> Preguntar de nuevo
            },
        )

        YasminViewerPub(self.sm, "CHAT_BOT")

    def execute_chat_bot(self) -> None:
        blackboard = Blackboard()
        # Inicio del chatbot
        blackboard.tts = "Hi, where should I go?" 
        self.sm(blackboard)


def main():
    rclpy.init()
    set_ros_loggers()
    
    node = YasminNode.get_instance()
    params = load_launch_parameters(node)
    node.get_logger().info(f"Launch parameters: {params}")
        
    # Configurar el Executor Multihilo
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    
    # Hilo que se encarga de executor.spin() para que no bloquee
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()
    
    try:
        chatbot = ChatBot(params)
        chatbot.execute_chat_bot()
        
    except Exception as e:
        node.get_logger().error(f"Error executing ChatBot: {e}")
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()
        spin_thread.join()

if __name__ == "__main__":
    main()