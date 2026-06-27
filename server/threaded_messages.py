import logging
import os
import datetime
import glob
import json

# from tada_utilities import text_pager

class Terminal:
    """attributes of the player's terminal"""
    def __init__(self):
        self.columns = 80
        self.rows = 24

class Player:
    """attributes of the player in the game"""
    def __init__(self):
        self.name = "Player1"
        self.flags = {}
        self.inventory = []
        self.terminal = Terminal()


MESSAGE_DIR = "../../../../../.config/JetBrains/PyCharmCE2025.2/scratches/messages"  # Directory to store message files

def ensure_message_directory():
    if not os.path.exists(MESSAGE_DIR):
        os.makedirs(MESSAGE_DIR)
        logging.info(f"Created message directory: {MESSAGE_DIR}/")
    else:
        logging.info("Message directory exists.")

def get_unique_thread_id():
    return datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")

def get_thread_filename(thread_id):
    return os.path.join(MESSAGE_DIR, f"thread_{thread_id}.json")

def get_all_threads():
    threads = []
    for filepath in glob.glob(os.path.join(MESSAGE_DIR, "thread_*.json")):
        thread_id = os.path.basename(filepath).replace("thread_", "").replace(".json", "")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                title = data.get("title", "[No Title Found]")
                threads.append((thread_id, title))
        except Exception as e:
            logging.info(f"Error reading thread {thread_id}: {e}")
            threads.append((thread_id, "[Error Reading]"))
    return {i + 1: (thread_id, title) for i, (thread_id, title) in enumerate(threads)}

def display_threads(threads):
    if not threads:
        print("\nNo message threads found.")
        return False
    print("\n--- Available Threads ---")
    print(" ## | Title")
    print("----+--------------------")
    for thread_id, title in threads.items():
        print(f"{thread_id:>3} | {title[1]}")
    print("----+--------------------")
    return True

def create_new_thread():
    print("\n--- Create New Message Thread ---")
    title = input("Enter message title: ").strip()
    if not title:
        print("Title cannot be empty. Aborting.")
        return

    recipient = input("To (e.g., 'John Doe' [Return = 'all']): ").strip()
    if not recipient:
        recipient = "all"
        print(f"Setting recipient to '{recipient}'.")

    author = input("Your name: ").strip()
    if not author:
        print("Your name cannot be empty. Aborting.")
        return

    message_content = []
    print("Enter your message (type 'END' on a new line to finish):")
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        message_content.append(line)
    message_content_str = "\n".join(message_content).strip()

    thread_id = get_unique_thread_id()
    filename = get_thread_filename(thread_id)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    thread_data = {
        "thread_id": thread_id,
        "title": title,
        "to": recipient,
        "from": author,
        "date": timestamp,
        "message": message_content_str,
        "replies": []
    }

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(thread_data, f, indent=2)
        print(f"\nNew thread '{title}' created with ID: {thread_id}")
    except IOError as e:
        print(f"Error creating thread file: {e}")

def reply_to_thread():
    threads = get_all_threads()
    if not display_threads(threads):
        return

    thread_num_to_reply = input("\nEnter the message number want to reply to: ").strip()
    if not thread_num_to_reply.isdigit() or int(thread_num_to_reply) not in threads:
        print("Invalid thread number. Please try again.")
        return

    author = input("Your name: ").strip()
    # TODO: add check for author.startswith('?') to prevent anonymous posting
    if not author:
        print("Your name cannot be empty. Aborting.")
        return

    reply_content = []
    print("Enter your reply (type 'END' on a new line to finish):")
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        reply_content.append(line)
    reply_content_str = "\n".join(reply_content).strip()

    thread_id_to_reply = threads[int(thread_num_to_reply)][0]
    filename = get_thread_filename(thread_id_to_reply)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with open(filename, 'r+', encoding='utf-8') as f:
            data = json.load(f)
            data.setdefault("replies", []).append({
                "from": author,
                "date": timestamp,
                "message": reply_content_str
            })
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()
        print(f"\nReply added to thread ID: {thread_id_to_reply}")
    except IOError as e:
        logging.error(f"Error writing reply to thread file: {e}")

def view_thread():
    threads = get_all_threads()
    if not display_threads(threads):
        print("There are no threads to view.")
        return

    thread_num_to_view = input("\nEnter the message number you want to view: ").strip()
    if not thread_num_to_view.isdigit() or int(thread_num_to_view) not in threads:
        print("Invalid thread number. Please try again.")
        return

    thread_id_to_view = threads[int(thread_num_to_view)][0]
    filename = get_thread_filename(thread_id_to_view)

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            messages = [{
                "type": "thread",
                "from": data.get("from"),
                "date": data.get("date"),
                "message": data.get("message"),
                "title": data.get("title"),
                "to": data.get("to")
            }]
            for reply in data.get("replies", []):
                messages.append({
                    "type": "reply",
                    "from": reply.get("from"),
                    "date": reply.get("date"),
                    "message": reply.get("message")
                })

        idx = 0
        while True:
            msg = messages[idx]
            print("\n--- " + ("THREAD START" if msg["type"] == "thread" else "REPLY") + " ---")
            if msg["type"] == "thread":
                print(f"Title: {msg['title']}")
                print(f"To: {msg['to']}")
            is_anonymous = msg['from'].startswith('?')
            # TODO: check ADMIN and DUNGEON_MASTER flags to show real name if anonymous:
            """
            if is_anonymous and (player.query_flag(PlayerFlags.ADMIN or player.query_flag(PlayerFlags.DUNGEON_MASTER):
                display_name = f"{msg['from'][1:]} (as Anonymous)"  # show real name without '?'
            """
            # display_name = "(Anonymous)" if is_anonymous else msg['from']
            display_name = f"Anonymous ({msg['from'][1:]})" if is_anonymous else msg['from']
            print(f"From: {display_name}")
            print(f"Date: {msg['date']}")
            print(f"\n{msg['message']}\n")
            print(f"Message {idx+1} of {len(messages)}")
            options = ["[N]ext" if idx < len(messages) - 1 else "",
                       "[P]revious" if idx > 0 else "",
                       "[R]eply", "[Q]uit reading"]
            print("Options: " + ", ".join(filter(None, options)))
            choice = input("Choice: ").strip().lower()
            if choice == "n" and idx < len(messages) - 1:
                idx += 1
            elif choice == "p" and idx > 0:
                idx -= 1
            elif choice == "r":
                reply_to_thread_id(thread_id_to_view)
                break
            elif choice == "q":
                break
            else:
                print("Invalid option.")
    except FileNotFoundError:
        print(f"Error: Thread file not found for message {threads[int(thread_num_to_view)][1]}.")
    except IOError as e:
        print(f"Error reading thread file: {e}")

def reply_to_thread_id(thread_id):
    filename = get_thread_filename(thread_id)
    # TODO: make asking for name optional if we have player context
    # TODO: subroutine asking for name and title
    # TODO: subroutine asking for message content
    # TODO: add Anonymous post option
    author = input("Your name: ").strip()
    if not author:
        print("Your name cannot be empty. Aborting.")
        return
    anonymous = input("Post anonymously? (y/N): ").strip().lower() == 'y'
    if anonymous:
        author = "?" + author
    reply_content = []
    print("Enter your reply (type 'END' on a new line to finish):")
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        reply_content.append(line)
    reply_content_str = "\n".join(reply_content).strip()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(filename, 'r+', encoding='utf-8') as f:
            data = json.load(f)
            data.setdefault("replies", []).append({
                "from": author,
                "date": timestamp,
                "message": reply_content_str
            })
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()
        print(f"\nReply added to thread ID: {thread_id}")
    except IOError as e:
        print(f"Error writing reply to thread file: {e}")

def main_menu():
    while True:
        print("\n--- Threaded Message System Menu ---")
        print("C. Create New Thread")
        print("R. Reply to Thread")
        print("L. List Threads")
        print("E. Exit")
        choice = input("Enter your choice (1-4): ").strip().lower()

        if choice == 'c':
            create_new_thread()
        elif choice == 'r':
            reply_to_thread()
        elif choice == 'l':
            view_thread()
        elif choice == 'e':
            print("Exiting message system. Goodbye!")
            break
        else:
            print("Invalid choice. Please enter an option listed above.")


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(format='%(levelname)10s | %(funcName)15s() | %(message)s', level=logging.DEBUG)

    player = Player()
    ensure_message_directory()
    main_menu()
