import os
import time

from ament_index_python.packages import get_package_share_directory
from audio_common_msgs.action import TTS
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from yasmin import State
from yasmin.blackboard import Blackboard
from yasmin_ros.basic_outcomes import SUCCEED, CANCEL, ABORT
from yasmin_ros.yasmin_node import YasminNode
from sensor_msgs.msg import LaserScan
from rclpy.qos import QoSProfile, HistoryPolicy, ReliabilityPolicy, DurabilityPolicy

class NavigateToWaypointState(State):

    def __init__(self, timeout: float = 500.0):
        super().__init__(outcomes=[SUCCEED, CANCEL, ABORT])
        self.navigator = BasicNavigator()
        self.min_scan_dist = float('inf')
        self._total_texts = 0
        self._say_texts = 0
        self.timeout = timeout

        self._tts_client = ActionClient(
            YasminNode.get_instance(),
            TTS,
            "/say",
            callback_group=ReentrantCallbackGroup(),
        )

        # Configuración del QoS para el escáner
        qos_scan = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT, 
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            durability=DurabilityPolicy.VOLATILE
        )
       
        self.scan_sub = YasminNode.get_instance().create_subscription(
            LaserScan,
            '/scan_raw',
            self._scan_cb,
            callback_group=ReentrantCallbackGroup(),
            qos_profile=qos_scan
        )
        
        pkg_path = get_package_share_directory('chatbot_ros')
        base_path = os.path.join(pkg_path, 'config')
        
        self.bt_rpp = os.path.join(base_path, 'navigate_w_rpp.xml')
        self.bt_dwb = os.path.join(base_path, 'navigate_w_dwb.xml')
        self.bt_mppi = os.path.join(base_path, 'navigate_w_mppi.xml')

    def _scan_cb(self, msg):
        """
        Callback para obtener la distancia mínima detectada en el escáner.
        """
        try:
            # Filtrar rangos válidos
            valid_ranges = [r for r in msg.ranges if msg.range_min < r < msg.range_max]
            if valid_ranges:
                self.min_scan_dist = min(valid_ranges)
            else:
                self.min_scan_dist = float('inf')
        except Exception:
            pass

    def say(self, text: str) -> None:
        """
        Callback para decir un texto.
        """
        goal = TTS.Goal()
        goal.text = text
        self._tts_client.wait_for_server(timeout_sec=10.0)

        send_goal_future = self._tts_client.send_goal_async(goal)
        send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future) -> None:
        """
        Callback para manejar la respuesta del goal.
        """
        goal_handle = future.result()
        get_result_future = goal_handle.get_result_async()
        get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        """
        Callback para manejar el resultado del goal.
        """
        self._say_texts += 1

        if self._say_texts == self._total_texts:
            self._tts_end_event.set()



    def execute(self, blackboard: Blackboard):
        idx = int(blackboard.current_waypoint_index)
        pose = list(blackboard.waypoints)[idx]
        current_bt = self.bt_dwb # Por defecto planificador DWB
        last_recoveries = 0 # Para rastrear recuperaciones
        
        # Iniciar el navegador (Nav2)
        self.navigator.waitUntilNav2Active()
        pose.header.stamp = self.navigator.get_clock().now().to_msg()
        self.say(f"Navigating to {blackboard.target_names[int(idx)]} using {current_bt.split('_')[-1].split('.')[0]}.")
        self.navigator.get_logger().info(f"Navegando a {blackboard.target_names[int(idx)]} usando planificador local {current_bt.split('_')[-1].split('.')[0]}.")

        start_time = time.time()
        if not os.path.exists(current_bt):
            self.navigator.goToPose(pose) # Si no se ha cargado el planificador, usar el planificador por defecto
        else:
            self.navigator.goToPose(pose, behavior_tree=current_bt)

        # Mostrar feedback y gestionar planificadores segun criterios
        while not self.navigator.isTaskComplete():
            feedback = self.navigator.getFeedback()
            if feedback:
                dist = feedback.distance_remaining # Distancia restante a la meta
                recoveries = feedback.number_of_recoveries # Recuperaciones
                scan_min = self.min_scan_dist # Distancia minima detectada en el escáner
                
                self.navigator.get_logger().info(
                    f"WP {idx+1} distancia restante: {dist:.2f} m | Rec: {recoveries} | ScanMin: {scan_min:.2f} | BT: {current_bt.split('_')[-1].split('.')[0]}"
                )
                
                # Lógica de Cambio de Planificador
                new_bt = current_bt
                state = "" # Para rastrear el estado

                # CRITERIO 1: RECUPERACIÓN 
                if recoveries > last_recoveries and recoveries >= 2:
                    state = "recovery"
                    new_bt = self.bt_mppi
                    self.navigator.get_logger().info("Recuperación detectada! Cambiando al planificador MPPI.")

                # CRITERIO 2: OBSTÁCULOS CERCANOS 
                elif scan_min < 0.35:
                    state = "obstacle detection"
                    new_bt = self.bt_mppi
                    self.navigator.get_logger().info("Congestion detectada! Cambiando al planificador MPPI.")

                # MANTENER MPPI (HISTERESIS): Si ya estamos en MPPI, mantenerlo hasta que se despeje
                elif current_bt == self.bt_mppi and scan_min < 0.60:
                     new_bt = self.bt_mppi

                # CRITERIO 3: DISTANCIA HACIA META
                elif dist > 8.0:
                    state = "far goal"
                    new_bt = self.bt_rpp
                elif dist < 4.0:
                    state = "close goal"
                    new_bt = self.bt_dwb
                
                last_recoveries = recoveries

                # Cambiar planificador si es necesario
                if new_bt != current_bt:
                     # Verificar si el archivo XML existe
                    if not os.path.exists(new_bt):
                        self.navigator.get_logger().warn(f"No se encuentra el archivo: {new_bt}. No se cambia el planificador. Planificador actual: {current_bt}")
                        new_bt = current_bt # No cambiar
                    else:
                        self.navigator.get_logger().info(f'Intentando cambiar el planner: {current_bt} -> {new_bt}')
                        self.navigator.cancelTask()

                    # Bucle de espera corto para asegurar que Nav2 está inactivo
                    while not self.navigator.isTaskComplete():
                        time.sleep(0.1)

                    try:
                        self.navigator.goToPose(pose, behavior_tree=new_bt)
                        self.navigator.get_logger().info(f'Cambiando planner: {current_bt} -> {new_bt}')
                        current_bt = new_bt
                        self.say(f"Changing local planner to {current_bt.split('_')[-1].split('.')[0]} due to {state}")
                    except Exception as e:
                        self.navigator.get_logger().warn(f'El planificador no ha cambiado: {e}')
                        continue
    
            if (time.time() - start_time) > self.timeout:
                self.navigator.get_logger().warn('Tiempo de navegación alcanzado, cancelando objetivo.')
                self.navigator.cancelTask()
   
            time.sleep(0.1) # Esperar un poco antes de la próxima iteración

        # Resultado final
        result_status = self.navigator.getResult()
        elapsed = time.time() - start_time
        if result_status == TaskResult.SUCCEEDED:
            self.navigator.get_logger().info(f'Tarea completada con éxito después de {elapsed:.2f} segundos.')
            blackboard.tts = f"Reached waypoint {idx + 1}. Waiting for a command"
            return SUCCEED
        elif result_status == TaskResult.CANCELED:
            self.navigator.get_logger().warn(f"Navegación cancelada después de {elapsed:.2f} segundos")
            blackboard.tts = f"Navigation canceled. Waiting for a command"
            return CANCEL
        else:
            self.navigator.get_logger().warn(f'No se pudo alcanzar el waypoint después de {elapsed:.2f} segundos')
            blackboard.tts = f"Navigation failed. Waiting for a command"
            return CANCEL

        
    

    
