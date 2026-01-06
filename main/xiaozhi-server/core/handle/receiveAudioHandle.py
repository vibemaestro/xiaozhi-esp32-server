import time
import json
import asyncio
from core.utils.util import audio_to_data
from core.handle.abortHandle import handleAbortMessage
from core.handle.intentHandler import handle_user_intent
from core.utils.output_counter import check_device_output_limit
from core.handle.sendAudioHandle import send_stt_message, SentenceType

TAG = __name__


async def handleAudioMessage(conn, audio):
    # Whether there is voice in the current fragment
    have_voice = conn.vad.is_vad(conn, audio)
    # If the device is just woken up, temporarily ignore VAD detection
    if hasattr(conn, "just_woken_up") and conn.just_woken_up:
        have_voice = False
        # Set a short delay to resume VAD detection
        conn.asr_audio.clear()
        if not hasattr(conn, "vad_resume_task") or conn.vad_resume_task.done():
            conn.vad_resume_task = asyncio.create_task(resume_vad_detection(conn))
        return
    # In manual mode, do not interrupt the content being played
    if have_voice:
        if conn.client_is_speaking and conn.client_listen_mode != "manual":
            await handleAbortMessage(conn)
    # Long idle detection of device, used to say goodbye
    await no_voice_close_connect(conn, have_voice)
    # Receive audio
    await conn.asr.receive_audio(conn, audio, have_voice)


async def resume_vad_detection(conn):
    # Wait for 2 seconds to resume VAD detection
    await asyncio.sleep(2)
    conn.just_woken_up = False


async def startToChat(conn, text):
    # Check if the input is in JSON format (contains speaker information)
    speaker_name = None
    actual_text = text

    try:
        # Try to parse input in JSON format
        if text.strip().startswith("{") and text.strip().endswith("}"):
            data = json.loads(text)
            if "speaker" in data and "content" in data:
                speaker_name = data["speaker"]
                actual_text = data["content"]
                conn.logger.bind(tag=TAG).info(f"Parsed speaker information: {speaker_name}")

                # Directly use JSON formatted text, no parsing
                actual_text = text
    except (json.JSONDecodeError, KeyError):
        # If parsing fails, continue using original text
        pass

    # Save speaker information to connection object
    if speaker_name:
        conn.current_speaker = speaker_name
    else:
        conn.current_speaker = None

    if conn.need_bind:
        await check_bind_device(conn)
        return

    # If the output characters of the day exceed the limited number
    if conn.max_output_size > 0:
        if check_device_output_limit(
            conn.headers.get("device-id"), conn.max_output_size
        ):
            await max_out_size(conn)
            return
    # In manual mode, do not interrupt the content being played
    if conn.client_is_speaking and conn.client_listen_mode != "manual":
        await handleAbortMessage(conn)

    # First perform intent analysis, using actual text content
    intent_handled = await handle_user_intent(conn, actual_text)

    if intent_handled:
        # If the intent has been processed, no longer continue chatting
        return

    # Intent not processed, continue regular chat process, using actual text content
    await send_stt_message(conn, actual_text)
    conn.executor.submit(conn.chat, actual_text)


async def no_voice_close_connect(conn, have_voice):
    if have_voice:
        conn.last_activity_time = time.time() * 1000
        return
    # Only perform timeout check if the timestamp has been initialized
    if conn.last_activity_time > 0.0:
        no_voice_time = time.time() * 1000 - conn.last_activity_time
        close_connection_no_voice_time = int(
            conn.config.get("close_connection_no_voice_time", 120)
        )
        if (
            not conn.close_after_chat
            and no_voice_time > 1000 * close_connection_no_voice_time
        ):
            conn.close_after_chat = True
            conn.client_abort = False
            end_prompt = conn.config.get("end_prompt", {})
            if end_prompt and end_prompt.get("enable", True) is False:
                conn.logger.bind(tag=TAG).info("End conversation, no need to send end prompt")
                await conn.close()
                return
            prompt = end_prompt.get("prompt")
            if not prompt:
                prompt = "Please end the conversation with a touching and nostalgic tone."
            await startToChat(conn, prompt)


async def max_out_size(conn):
    # Play prompt for exceeding the maximum output character limit
    conn.client_abort = False
    text = "I'm sorry, I have something to do, we'll chat again tomorrow, okay? See you tomorrow, bye!"
    await send_stt_message(conn, text)
    file_path = "config/assets/max_output_size.wav"
    opus_packets = await audio_to_data(file_path)
    conn.tts.tts_audio_queue.put((SentenceType.LAST, opus_packets, text))
    conn.close_after_chat = True


async def check_bind_device(conn):
    if conn.bind_code:
        # Ensure bind_code is 6 digits
        if len(conn.bind_code) != 6:
            conn.logger.bind(tag=TAG).error(f"Invalid bind code format: {conn.bind_code}")
            text = "Invalid bind code format, please check the configuration."
            await send_stt_message(conn, text)
            return

        text = f"Please login to the control panel, input {conn.bind_code}, bind the device."
        await send_stt_message(conn, text)

        # Play notification sound
        music_path = "config/assets/bind_code_vi.mp3"
        opus_packets = await audio_to_data(music_path)
        conn.tts.tts_audio_queue.put((SentenceType.FIRST, opus_packets, text))

        # Play each digit
        for i in range(6):  # Ensure only 6 digits are played
            try:
                digit = conn.bind_code[i]
                num_path = f"config/assets/bind_code/vi/{digit}.mp3"
                num_packets = await audio_to_data(num_path)
                conn.tts.tts_audio_queue.put((SentenceType.MIDDLE, num_packets, None))
            except Exception as e:
                conn.logger.bind(tag=TAG).error(f"Failed to play digit audio: {e}")
                continue
        conn.tts.tts_audio_queue.put((SentenceType.LAST, [], None))
    else:
        # Play not bound prompt
        conn.client_abort = False
        text = f"No version information found for this device, please correctly configure the OTA address, then recompile the firmware."
        await send_stt_message(conn, text)
        music_path = "config/assets/bind_not_found.wav"
        opus_packets = await audio_to_data(music_path)
        conn.tts.tts_audio_queue.put((SentenceType.LAST, opus_packets, text))
