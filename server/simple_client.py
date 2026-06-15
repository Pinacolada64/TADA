import asyncio
import logging
from net_common import Message, MessageType, Mode, to_jsonb, from_jsonb  # Assumes these are defined elsewhere
from typing import Dict, Any, Optional

from colorama import Fore, Back

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')


def print_message(msg: Message):
    if msg:
        # logging.info("In print_message()")
        for line in msg.lines:
            print(line)


class Init:
    # server_id, server_key, protocol_version, type must all match between server + client.
    def __init__(self, server_id="test_server", server_key="test_key", protocol_version=1, translation="utf-8"):
        self.server_id = server_id
        self.server_key = server_key
        self.protocol_version = protocol_version
        self.translation = translation
        self.type = 'init'  # Adding type for clarity


async def send_message(writer: asyncio.StreamWriter, obj: Any) -> None:
    """
    Serializes a data object (like Message or Init) to JSON and sends it.
    Uses to_jsonb (Object -> JSON Bytes).
    """
    try:
        # Use to_jsonb to get the JSON bytes.
        json_bytes = to_jsonb(obj)

        # FIX: Log the object's representation, not the result of deserializing the object,
        # which was causing the "Init found" error.
        if hasattr(obj, '__dict__'):
            logging.info(f"Sending {obj.__class__.__name__}: {obj.__dict__}")
        else:
            logging.info(f"Sending raw dict/object: {obj}")

        # Log the actual bytes that will be written for debugging
        logging.debug(f"Client sending raw bytes: {json_bytes!r}")
        try:
            writer.write(json_bytes + b'\n')
            await writer.drain()
            logging.debug("Client writer.drain() completed successfully")
        except BrokenPipeError:
            logging.error("BrokenPipeError while sending message: server likely closed the connection")
            raise
        except Exception as e:
            logging.exception(f"Unexpected error while sending message: {e}")
            raise
    except Exception as e:
        logging.error(f"Error during send_message: {e}")
        raise


async def receive_message(reader: asyncio.StreamReader) -> Optional[Dict[str, Any]]:
    """
    Receives raw JSON data (terminated by newline) and deserializes it into a Python dictionary.
    Uses from_jsonb (JSON Bytes -> Object/Dict).
    """
    try:
        # Read until the newline delimiter sent by the server
        data = await reader.readline()
        if not data:
            return None

        # Remove the trailing newline and strip any extra whitespace/quotes
        raw_json_bytes = data.strip()

        # Log the raw data we received for debugging the double-quoting issue
        logging.info(f"Received raw bytes: {raw_json_bytes!r}")

        # FIX: Use from_jsonb (DESERIALIZER) to convert the raw JSON bytes into a Python dict.
        # The previous version incorrectly used 'to_jsonb' here.
        obj = from_jsonb(raw_json_bytes)

        # If the server explicitly signaled it will close (mode == 'bye'), wait for EOF
        try:
            mode_field = None
            if isinstance(obj, dict):
                mode_field = obj.get('mode')
            # net_common serializes Mode enums by name (e.g., 'bye')
            if mode_field == Mode.bye.name or mode_field == Mode.bye.value:
                logging.info("Received server 'bye' message — waiting for server to close connection")
                # Drain any remaining lines until EOF
                # Use a short loop that exits when readline returns empty bytes
                while True:
                    more = await reader.readline()
                    if not more:
                        break
                return obj
        except Exception:
            logging.debug("Error while handling bye/wait-for-close; continuing", exc_info=True)

        return obj

    except asyncio.IncompleteReadError:
        logging.info("Connection closed by peer.")
        return None
    except Exception as e:
        logging.error(f"Error receiving message: decoding to dict: {e}")
        return None


async def perform_handshake(reader, writer) -> Optional[dict]:
    """
    Performs the initial handshake with the server.
    Waits for the server's Init, then sends the client's Init.
    Returns True on success, False on failure.
    """
    print("Receiving server capabilities...")
    try:
        # 1. Wait for server Init object (This should now return a dict)
        server_init_data = await receive_message(reader)
        if not server_init_data:
            print("Did not receive Init from server.")
            return None
        print(f"Received server Init: {server_init_data}")

        # 2. Send client Init object to server
        client_init_data = Init()
        await send_message(writer, client_init_data)
        print(f"-> Sent Init with Server ID: {client_init_data.server_id}")

        # 3. Wait for handshake result (Message from server) -- usually a short success message
        handshake_result = await receive_message(reader)
        if not handshake_result:
            print('Handshake failed: no response from server after Init exchange')
            return None

        # 4. The server typically sends a follow-up login banner; consume that here so
        #    the main loop doesn't accidentally treat it as the next command response.
        login_banner = await receive_message(reader)
        # If the login banner isn't present, return the handshake result
        if login_banner:
            return login_banner
        return handshake_result
    except Exception as e:
        print(f"Handshake error: {e}")
        return None


# ANSI color codes for message type prefixes
COLOR_MAP = {
    'system': '\033[91;1m',  # Bright Red
    'announcement': '\033[93m',  # Yellow
    'regular': '\033[0m',  # Default
    'shout': '\033[95m',  # Magenta
    'page': '\033[96m',  # Cyan
    'say': '\033[92m',  # Green
    'mumble': '\033[94m',  # Blue
    'emote': '\033[92;1m',  # Bright Green
    'whisper': '\033[96;1m',  # Bright Cyan
    'error': '\033[91m'  # Red for errors
}
RESET_COLOR = '\033[0m'


def color_prefix(msg_type):
    color = COLOR_MAP.get(str(msg_type).lower(), '\033[0m')
    return color


async def main():
    """
    Main coroutine to connect, handshake, and handle the message loop.
    """
    # NOTE: You may need to update the port (8888) if your server is running on a different one (e.g., 5000)
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', 34083)
    except ConnectionRefusedError:
        print("Connection failed. Is the server running?")
        return

    # 1. Perform the handshake before doing anything else and get the login banner
    login_message = await perform_handshake(reader, writer)
    if not login_message:
        print("Could not establish a secure connection. Exiting.")
        writer.close()
        await writer.wait_closed()
        return

    # Read and display the login message from the server
    last_prompt = "Command: "
    if login_message:
        # Ensure we handle the dict conversion to Message object
        try:
            login_msg = Message(**login_message)
        except TypeError as e:
            logging.error(f"Failed to create Message from received dict: {login_message}. Error: {e}")
            login_msg = Message(lines=[f"Error: Could not display server login message. See logs."])
        print_message(login_msg)
        last_prompt = getattr(login_msg, 'prompt', last_prompt) or last_prompt

    loop = asyncio.get_running_loop()
    current_mode = Mode.login  # Start in login mode
    try:
        while True:
            # Prompt immediately (server is usually waiting for input at login prompt)
            prompt_text = last_prompt
            try:
                command = await loop.run_in_executor(None, input, prompt_text)
                logging.debug(f"Input received from user: {command!r}")
            except EOFError:
                # Happens when stdin is closed (e.g., user pressed Ctrl-D or running non-interactively)
                logging.info("Input closed (EOF). Exiting client input loop without sending bye to avoid racing the socket close.")
                break
            except Exception as e:
                logging.exception(f"Unexpected error while reading input: {e}")
                break
            text_input = command.strip()
            if text_input.lower() == 'quit':
                print("Sending 'bye' message and closing connection.")
                bye_message = Message(lines=[], mode=Mode.bye)
                await send_message(writer, bye_message)
                break

            # Send the user's command as a Message with the current mode
            out_message = Message(lines=[text_input], mode=current_mode)
            await send_message(writer, out_message)

            # Client-side aggregation: collect any immediate messages with a short timeout.
            # Rationale: some server commands may not include a prompt field; waiting for it
            # can cause the client to block until the next server message (appearing after
            # the next command), which yields the "one command behind" symptom. Using a
            # short receive timeout gathers responses sent immediately by the server and
            # then returns control to the user prompt.
            aggregated_messages = []
            read_timeout = 0.5  # seconds; slightly longer to allow nested menu responses to arrive
            while True:
                try:
                    response_data = await asyncio.wait_for(receive_message(reader), timeout=read_timeout)
                except asyncio.TimeoutError:
                    # No more immediate data from server; stop collecting and display
                    break

                if response_data is None:
                    print("Connection lost.")
                    return

                try:
                    in_message = Message(**response_data)
                except TypeError as e:
                    logging.error(f"Failed to create Message from received dict: {response_data}. Error: {e}")
                    in_message = Message(lines=[f"Error: Server sent malformed message: {response_data}"])

                aggregated_messages.append(in_message)

                # Update current_mode if the server changes it
                if in_message.mode:
                    current_mode = in_message.mode

                # If server provided a prompt, record it; still continue to collect briefly
                if getattr(in_message, 'prompt', None):
                    last_prompt = in_message.prompt or last_prompt
                    # continue collecting until the timeout expires to gather any remaining lines
                    continue

            # Display all aggregated messages
            for in_message in aggregated_messages:

                # Prioritize displaying server errors directly
                if in_message.error:
                    print(f"{color_prefix('error')}[ERROR]{RESET_COLOR} Server Error: {in_message.error}")

                prefix = ''
                # Handle message type prefixing and coloring
                if in_message.type:
                    type_str = in_message.type.upper()
                    color = color_prefix(type_str)
                    prefix = f"{color}[{type_str}]{RESET_COLOR} "

                for line in in_message.lines:
                    # Print the line with color/prefix except if it's a regular message:
                    output = f"{prefix.title()}{line}" if in_message.type == MessageType.REGULAR else \
                        f"{prefix.title()}{line}"
                    print(f"{prefix.title()}{line}")
    except Exception as e:
        logging.exception(f"Unexpected exception in client main loop: {e}")
    finally:
        print('Closing the connection.')
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nClient shut down.")
