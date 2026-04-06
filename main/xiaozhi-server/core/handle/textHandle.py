from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler
from core.handle.textMessageHandlerRegistry import TextMessageHandlerRegistry
from core.handle.textMessageProcessor import TextMessageProcessor

TAG = __name__

# Global processor registration table
message_registry = TextMessageHandlerRegistry()

# Create global message processor instance
message_processor = TextMessageProcessor(message_registry)


async def handleTextMessage(conn: "ConnectionHandler", message):
    """处理文本消息"""
    await message_processor.process_message(conn, message)
