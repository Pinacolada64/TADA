import asyncio
import logging

# Assuming these classes are in your common/client files
from net_common import Message, Mode, to_jsonb, from_jsonb

class Init:
    # server_id, server_key, protocol_version, type must all match between server + client.
    # character translation (e.g. 'utf-8', 'petscii', etc.) can be whatever the client wants.
    def __init__(self, server_id="test_server", server_key="test_key", protocol_version=1, translation="utf-8"):
            self.server_id = server_id
            self.server_key = server_key
            self.protocol_version = protocol_version
            self.translation = translation
            self.type = 'init'  # Adding type for clarity

async def send_message(writer, obj):
    """
    Serializes a data object (like Message or Init) to JSON and sends it.
    """
    writer.write(to_jsonb(obj) + b'\n')
    await writer.drain()


async def receive_message(reader):
    """
    Receives raw JSON data and deserializes it into a Python dictionary.
    """
    data = await reader.readline()
    if not data:
        return None
    return from_jsonb(data)


async def perform_handshake(reader, writer) -> bool:
    """
    Performs the initial handshake with the server.
    Waits for the server's Init, then sends the client's Init.
    Returns True on success, False on failure.
    """
    print("Waiting for server handshake...")
    try:
        # 1. Wait for server Init object
        server_init_data = await receive_message(reader)
        if not server_init_data:
            print("Did not receive Init from server.")
            return False
        print(f"Received server Init: {server_init_data}")

        # 2. Send client Init object to server
        client_init_data = Init()
        await send_message(writer, client_init_data)
        print(f"-> Sent Init with Server ID: {client_init_data.server_id}")

        # 3. Wait for handshake result (Message from server)
        handshake_result = await receive_message(reader)
        if handshake_result and handshake_result.get('mode') == Mode.login:
            print("Handshake successful!")
            return True
        else:
            print(f"Handshake failed: {handshake_result}")
            return False
    except Exception as e:
        print(f"Handshake error: {e}")
        return False


# ANSI color codes for message type prefixes
COLOR_MAP = {
    'system': '\033[91;1m',      # Bright Red
    'announcement': '\033[93m', # Yellow
    'regular': '\033[0m',       # Default
    'shout': '\033[95m',        # Magenta
    'page': '\033[96m',         # Cyan
    'say': '\033[92m',          # Green
    'mumble': '\033[94m',       # Blue
    'emote': '\033[92;1m',      # Bright Green
    'whisper': '\033[96;1m',    # Bright Cyan
}
RESET_COLOR = '\033[0m'

def color_prefix(msg_type):
    color = COLOR_MAP.get(str(msg_type).lower(), '\033[0m')
    return color

async def main():
    """
    Main coroutine to connect, handshake, and handle the message loop.
    """
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', 8888)
    except ConnectionRefusedError:
        print("Connection failed. Is the server running?")
        return

    # 1. Perform the handshake before doing anything else
    if not await perform_handshake(reader, writer):
        print("Could not establish a secure connection. Exiting.")
        writer.close()
        await writer.wait_closed()
        return

    # If handshake is successful, proceed to the main loop
    # Read and display the login message from the server
    login_message = await receive_message(reader)
    if login_message:
        in_message = Message(**login_message)
        for line in in_message.lines:
            print(f"{line}")
        print("-" * 20)

    loop = asyncio.get_running_loop()
    current_mode = Mode.login  # Start in login mode
    try:
        while True:
            prompt = "Command: "
            command = await loop.run_in_executor(None, input, prompt)
            text_input = command.strip()
            if text_input.lower() == 'quit':
                print("Sending 'bye' message and closing connection.")
                bye_message = Message(lines=[], mode=Mode.bye)
                await send_message(writer, bye_message)
                break

            # Send the user's command as a Message with the current mode
            out_message = Message(lines=[text_input], mode=current_mode)
            await send_message(writer, out_message)

            # Client-side aggregation: collect all messages until a prompt is received
            aggregated_messages = []
            while True:
                response_data = await receive_message(reader)
                if response_data is None:
                    print("Connection lost.")
                    return
                in_message = Message(**response_data)
                aggregated_messages.append(in_message)
                # Update current_mode if the server changes it
                if hasattr(in_message, 'mode') and in_message.mode:
                    current_mode = in_message.mode
                # Stop collecting if a prompt is present (end of server output for this command)
                if getattr(in_message, 'prompt', None):
                    break

            # Display all aggregated messages
            for in_message in aggregated_messages:
                if in_message.error:
                    print(f"Error from server: {in_message.error}")
                prefix = ''
                if hasattr(in_message, 'type') and in_message.type:
                    color = color_prefix(str(in_message.type).lower())
                    prefix = f"{color}[{str(in_message.type).upper()}]{RESET_COLOR} "
                for line in in_message.lines:
                    # If the line already has a prefix, don't double it
                    if line.startswith('['):
                        print(f"{color}{line}{RESET_COLOR}")
                    else:
                        print(f"{prefix}{line}")
    finally:
        print('Closing the connection.')
        writer.close()
        await writer.wait_closed()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nClient shut down.")
