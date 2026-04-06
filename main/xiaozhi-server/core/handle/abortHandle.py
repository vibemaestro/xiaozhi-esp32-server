import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler
TAG = __name__


async def handleAbortMessage(conn: "ConnectionHandler"):
    if conn.close_after_chat or conn.is_exiting:
        conn.logger.bind(tag=TAG).info("退出流程中被打断，直接关闭连接")
        return
        
    conn.logger.bind(tag=TAG).info("Abort message received")
    # Set to interrupt status, will automatically interrupt llm、tts tasks
    conn.client_abort = True
    conn.clear_queues()
    # Interrupt client speaking status
    await conn.websocket.send(
        json.dumps({"type": "tts", "state": "stop", "session_id": conn.session_id})
    )
    conn.clearSpeakStatus()
    conn.logger.bind(tag=TAG).info("Abort message received-end")
