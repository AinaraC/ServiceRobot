import os
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import SetEnvironmentVariable, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
from llama_bringup.utils import create_llama_launch
from launch.actions import DeclareLaunchArgument

def generate_launch_description():

    stdout_linebuf_envvar = SetEnvironmentVariable(
        "RCUTILS_CONSOLE_STDOUT_LINE_BUFFERED", "1"
    )

    whisper_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("whisper_bringup"),
                "launch",
                "whisper.launch.py",
            )
        ),
        launch_arguments={
            "launch_audio_capturer": LaunchConfiguration(
                "launch_audio_capturer", default=True
            ),
            "model_repo": "ggerganov/whisper.cpp",
            "model_filename": "ggml-large-v3-turbo-q5_0.bin",
        }.items(),
    )

    llama_cmd = create_llama_launch(
        n_ctx=4096,
        n_batch=256,
        n_gpu_layers=-1,
        n_threads=-1,
        n_predict=-1,
        model_repo="mradermacher/InternVL3-8B-GGUF",
        model_filename="InternVL3-8B.Q4_K_M.gguf",
        system_prompt_type="ChatML",
    )

    piper_node_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("piper_bringup"),
                "launch",
                "piper.launch.py",
            )
        ),
        launch_arguments={
            "launch_audio_player": LaunchConfiguration(
                "launch_audio_player", default=True
            ),
            "model_repo": "rhasspy/piper-voices",
            "model_filename": "en/en_US/lessac/low/en_US-lessac-low.onnx",
            "config_model_repo": "rhasspy/piper-voices",
            "config_model_filename": "en/en_US/lessac/low/en_US-lessac-low.onnx.json",
        }.items(),
    )

    mode_arg = DeclareLaunchArgument(
        'mode', default_value='sequential',
        description='Mode of operation'
    )
    yaml_path_arg = DeclareLaunchArgument(
        'yaml_output_path', default_value='/home/ainara/unileon/servicios/proyecto/waypoints.yaml',
        description='Path to the YAML file'
    )
    semantic_path_arg = DeclareLaunchArgument(
        'semantic_path', default_value='/home/ainara/unileon/servicios/proyecto/semantic.yaml',
        description='Path to the semantic file'
    )
    timeout_arg = DeclareLaunchArgument(
        'timeout', default_value='500.0',
        description='Timeout for waypoint navigation'
    )

    chatbot_node_cmd = Node(
        package="chatbot_ros",
        executable="main_node",
        output="both",
        parameters=[{
            'use_sim_time': True,
            'mode': LaunchConfiguration('mode'),
            'yaml_output_path': LaunchConfiguration('yaml_output_path'),
            'semantic_path': LaunchConfiguration('semantic_path'),
            'timeout': LaunchConfiguration('timeout'),
        }],
    )

    yasmin_viewer_cmd = Node(
        package="yasmin_viewer",
        executable="yasmin_viewer_node",
        output="both",
        parameters=[{"host": "0.0.0.0", 'use_sim_time': True}],
    )

    return LaunchDescription([
        mode_arg,
        yaml_path_arg,
        semantic_path_arg,
        timeout_arg,
        stdout_linebuf_envvar,
        whisper_cmd,
        piper_node_cmd,
        llama_cmd,
        chatbot_node_cmd,
        yasmin_viewer_cmd
    ])