import json

from core.handle.textMessageHandlerRegistry import TextMessageHandlerRegistry

TAG = __name__


class TextMessageProcessor:
    """Message processor main class"""

    def __init__(self, registry: TextMessageHandlerRegistry):
        self.registry = registry

    async def process_message(self, conn, message: str) -> None:
        """Main entry point to process messages"""
        try:
            # Parse JSON message
            msg_json = json.loads(message)

            # Process JSON message
            if isinstance(msg_json, dict):
                message_type = msg_json.get("type")

                # Log message
                conn.logger.bind(tag=TAG).info(f"收到{message_type}消息：{message}")

                # Get and execute processor
                handler = self.registry.get_handler(message_type)
                if handler:
                    await handler.handle(conn, msg_json)
                else:
                    conn.logger.bind(tag=TAG).error(f"Received unknown message type: {message}")
            # 处理纯数字消息
            elif isinstance(msg_json, int):
                conn.logger.bind(tag=TAG).info(f"Received number message: {message}")
                await conn.websocket.send(message)

        except json.JSONDecodeError:
            # Non-JSON message directly forwarded
            conn.logger.bind(tag=TAG).error(f"Parsed error message: {message}")
            await conn.websocket.send(message)
