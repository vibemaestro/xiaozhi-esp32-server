"""
TTS reporting functionality is integrated into the ConnectionHandler class.

Reporting functionality includes:
1. Each connection object has its own reporting queue and processing thread
2. The lifecycle of the reporting thread is bound to the connection object
3. Use the ConnectionHandler.enqueue_tts_report method for reporting

Please refer to the relevant code in core/connection.py for implementation details.
"""

import time
import json
import opuslib_next
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

from config.manage_api_client import report as manage_report

TAG = __name__


async def report(conn: "ConnectionHandler", type, text, opus_data, report_time):
    """执行聊天记录上报操作

    Args:
        conn: 连接对象
        type: 上报类型，1为用户，2为智能体，3为工具调用
        text: 合成文本
        opus_data: opus音频数据
        report_time: 上报时间
    """
    try:
        if opus_data:
            audio_data = opus_to_wav(conn, opus_data)
        else:
            audio_data = None
        # Execute asynchronous reporting
        await manage_report(
            mac_address=conn.device_id,
            session_id=conn.session_id,
            chat_type=type,
            content=text,
            audio=audio_data,
            report_time=report_time,
        )
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"Chat history reporting failed: {e}")


def opus_to_wav(conn: "ConnectionHandler", opus_data):
    """将Opus数据转换为WAV格式的字节流

    Args:
        output_dir: Output directory (kept for interface compatibility)
        opus_data: Opus audio data

    Returns:
        bytes: WAV audio data
    """
    decoder = None
    try:
        decoder = opuslib_next.Decoder(16000, 1)  # 16kHz, single channel
        pcm_data = []

        for opus_packet in opus_data:
            try:
                pcm_frame = decoder.decode(opus_packet, 960)  # 960 samples = 60ms
                pcm_data.append(pcm_frame)
            except opuslib_next.OpusError as e:
                conn.logger.bind(tag=TAG).error(f"Opus decoding error: {e}", exc_info=True)

        if not pcm_data:
            raise ValueError("No valid PCM data")

        # Create WAV header
        pcm_data_bytes = b"".join(pcm_data)
        num_samples = len(pcm_data_bytes) // 2  # 16-bit samples

        # WAV header
        wav_header = bytearray()
        wav_header.extend(b"RIFF")  # ChunkID
        wav_header.extend((36 + len(pcm_data_bytes)).to_bytes(4, "little"))  # ChunkSize
        wav_header.extend(b"WAVE")  # Format
        wav_header.extend(b"fmt ")  # Subchunk1ID
        wav_header.extend((16).to_bytes(4, "little"))  # Subchunk1Size
        wav_header.extend((1).to_bytes(2, "little"))  # AudioFormat (PCM)
        wav_header.extend((1).to_bytes(2, "little"))  # NumChannels
        wav_header.extend((16000).to_bytes(4, "little"))  # SampleRate
        wav_header.extend((32000).to_bytes(4, "little"))  # ByteRate
        wav_header.extend((2).to_bytes(2, "little"))  # BlockAlign
        wav_header.extend((16).to_bytes(2, "little"))  # BitsPerSample
        wav_header.extend(b"data")  # Subchunk2ID
        wav_header.extend(len(pcm_data_bytes).to_bytes(4, "little"))  # Subchunk2Size

        # Return complete WAV data
        return bytes(wav_header) + pcm_data_bytes
    finally:
        if decoder is not None:
            try:
                del decoder
            except Exception as e:
                conn.logger.bind(tag=TAG).debug(f"Error releasing decoder resource: {e}")


def enqueue_tts_report(conn: "ConnectionHandler", text, opus_data):
    if not conn.read_config_from_api or conn.need_bind or not conn.report_tts_enable:
        return
    if conn.chat_history_conf == 0:
        return
    """Add TTS data to reporting queue

    Args:
        conn: Connection object
        text: Synthesized text
        opus_data: Opus audio data
    """
    try:
        # Use connection object's queue, pass text and binary data instead of file path
        if conn.chat_history_conf == 2:
            conn.report_queue.put((2, text, opus_data, int(time.time())))
            conn.logger.bind(tag=TAG).debug(
                f"TTS data added to reporting queue: {conn.device_id}, audio size: {len(opus_data)} "
            )
        else:
            conn.report_queue.put((2, text, None, int(time.time())))
            conn.logger.bind(tag=TAG).debug(
                f"TTS data added to reporting queue: {conn.device_id}, no audio reporting"
            )
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"Failed to add TTS data to reporting queue: {text}, {e}")


def enqueue_tool_report(conn: "ConnectionHandler", tool_name: str, tool_input: dict, tool_result: str = None, report_tool_call: bool = True):
    """将工具调用数据加入上报队列

    Args:
        conn: 连接对象
        tool_name: 工具名称
        tool_input: 工具输入参数
        tool_result: 工具执行结果（可选）
        report_tool_call: 是否上报工具调用本身，默认True；仅上报结果时设为False
    """
    if not conn.read_config_from_api or conn.need_bind:
        return
    if conn.chat_history_conf == 0:
        return

    try:
        timestamp = int(time.time())

        # 构建工具调用内容
        if report_tool_call:
            tool_text = json.dumps(
                [
                    {
                        "type": "tool",
                        "text": f"{tool_name}({json.dumps(tool_input, ensure_ascii=False)})",
                    }
                ]
            )
            conn.report_queue.put((3, tool_text, None, timestamp))

        # 构建工具结果内容
        if tool_result:
            result_display = f'{{"result":"{str(tool_result)}"}}'
            result_content = json.dumps([{"type": "tool_result", "text": result_display}], ensure_ascii=False)
            conn.report_queue.put((3, result_content, None, timestamp + 1))
    except Exception as e:
        conn.logger.bind(tag=TAG).error(f"加入工具上报队列失败: {e}")


def enqueue_asr_report(conn: "ConnectionHandler", text, opus_data):
    if not conn.read_config_from_api or conn.need_bind or not conn.report_asr_enable:
        return
    if conn.chat_history_conf == 0:
        return
    """Add ASR data to reporting queue

    Args:
        conn: Connection object
        text: Synthesized text
        opus_data: Opus audio data
    """
    try:
        # Use connection object's queue, pass text and binary data instead of file path
        if conn.chat_history_conf == 2:
            conn.report_queue.put((1, text, opus_data, int(time.time())))
            conn.logger.bind(tag=TAG).debug(
                f"ASR data added to reporting queue: {conn.device_id}, audio size: {len(opus_data)} "
            )
        else:
            conn.report_queue.put((1, text, None, int(time.time())))
            conn.logger.bind(tag=TAG).debug(
                f"ASR data added to reporting queue: {conn.device_id}, no audio reporting"
            )
    except Exception as e:
        conn.logger.bind(tag=TAG).debug(f"Failed to add ASR data to reporting queue: {text}, {e}")
