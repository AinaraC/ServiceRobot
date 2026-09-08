import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess, DeclareLaunchArgument, TimerAction
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():

    nav2_pkg = get_package_share_directory('nav2_playground')
    navigation_launch_path = os.path.join(nav2_pkg, 'launch', 'navigation_launch.py')
    playground_launch_path = os.path.join(nav2_pkg, 'launch', 'playground_kobuki.launch.py')

    # Argumentos
    mode_arg = DeclareLaunchArgument('mode', default_value='sequential', description='Mode of operation', choices=['sequential', 'random'])
    yaml_path_arg = DeclareLaunchArgument('yaml_output_path', default_value='/home/ainara/unileon/servicios/proyecto/waypoints.yaml', description='Path to the YAML file')
    semantic_path_arg = DeclareLaunchArgument('semantic_path', default_value='/home/ainara/unileon/servicios/proyecto/semantic.yaml', description='Path to the semantic file')
    timeout_arg = DeclareLaunchArgument('timeout', default_value='500.0', description='Timeout for waypoint navigation')

    # TERMINAL DE NAVEGACIÓN (Se lanza inmediatamente)
    nav_terminal_cmd = ExecuteProcess(
        cmd=[
            "gnome-terminal",
            "--title=Navigation_System",
            "--",
            "bash",
            "-c",
            f"ros2 launch {playground_launch_path} & sleep 5; ros2 launch {navigation_launch_path}; exec bash"
        ],
        output="screen"
    )

    # TERMINAL DEL CHATBOT (Definición del comando)
    chatbot_launch_cmd = [
        "ros2 launch chatbot_bringup chatbot.launch.py ",
        "mode:=", LaunchConfiguration('mode'), " ",
        "yaml_output_path:=", LaunchConfiguration('yaml_output_path'), " ",
        "semantic_path:=", LaunchConfiguration('semantic_path'), " ",
        "timeout:=", LaunchConfiguration('timeout'),
        "; exec bash"
    ]

    chatbot_terminal_cmd = ExecuteProcess(
        cmd=[
            "gnome-terminal",
            "--title=Chatbot_AI_Core",
            "--",
            "bash",
            "-c",
            chatbot_launch_cmd
        ],
        output="screen"
    )

    # TIMER: Retrasa la apertura de la terminal del chatbot 
    delayed_chatbot_launch = TimerAction(
        period=10.0,
        actions=[chatbot_terminal_cmd]
    )

    ld = LaunchDescription()

    ld.add_action(mode_arg)
    ld.add_action(yaml_path_arg)
    ld.add_action(semantic_path_arg)    
    ld.add_action(timeout_arg)

    # Lanzar navegación ahora
    ld.add_action(nav_terminal_cmd)
    
    # Lanzar chatbot tras x segundos
    ld.add_action(delayed_chatbot_launch)

    return ld