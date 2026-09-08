
from yasmin import State
from yasmin.blackboard import Blackboard
from yasmin_ros.basic_outcomes import SUCCEED, ABORT, CANCEL 

PAUSE = 'PAUSE' # Estado personalizado de pausa

class DecisionState(State):
    def __init__(self):
        super().__init__(outcomes=[SUCCEED, CANCEL, ABORT, PAUSE])

    def execute(self, blackboard: Blackboard):
        token = str(blackboard.stt).strip().lower()
        
        # SI EL USUARIO QUIERE IR AL SIGUIENTE WAYPOINT
        if any(w in token for w in ('next', 'advance', 'go', 'continue')):
            
            # RUTA FINALIZADA?
            if (blackboard.current_waypoint_index + 1) >= len(blackboard.waypoints):
                blackboard.current_waypoint_index = 0 # Reiniciar
                blackboard.tts = "You have reached the final destination. Where do you want to go next?"
                return CANCEL

            blackboard.current_waypoint_index += 1 # Siguiente waypoint
            return SUCCEED
        
        # SI EL USUARIO QUIERE DETENER LA NAVEGACIÓN
        elif any(w in token for w in ('stop', 'wait')):
            # Se mantiene el waypoint actual
            blackboard.tts = "Stopping navigation and listening for your next command."
            return PAUSE
        
        # SI EL USUARIO QUIERE CANCELAR LA NAVEGACIÓN
        elif any(w in token for w in ('cancel', 'delete', 'abort')):
            # Se mantiene el waypoint actual
            blackboard.current_waypoint_index = 0 # Reiniciar
            blackboard.tts = "Cancelling the navigation. Where do you want to go next? "
            return CANCEL
        
        # SI EL USUARIO QUIERE REPETIR LA NAVEGACIÓN
        elif any(w in token for w in ('repeat', 'same', 'again')):
            # Se mantiene el waypoint actual
            blackboard.tts = "Repeating navigation to the same waypoint."
            return SUCCEED
        
        # NO SE HA ENTENDIDO EL COMANDO
        else:
            # Se mantiene el waypoint actual
            blackboard.tts = "I didn't understand you. Can you repeat?"
            return ABORT

