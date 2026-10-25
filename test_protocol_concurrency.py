
import socket
import threading

from shared.protocol import send_message, receive_message


def main():
    sender_socket, receiver_socket = socket.socketpair()

    sender_count = 10
    messages_per_sender = 100
    total_messages = sender_count * messages_per_sender

    received_messages = []
    receiver_errors = []

    def receive_all():
        try:
            for _ in range(total_messages):
                received_messages.append(
                    receive_message(receiver_socket)
                )
        except Exception as error:
            receiver_errors.append(error)

    receiver_thread = threading.Thread(target=receive_all)
    receiver_thread.start()

    def send_batch(sender_id):
        for message_id in range(messages_per_sender):
            send_message(
                sender_socket,
                {
                    "type": "concurrency_test",
                    "sender_id": sender_id,
                    "message_id": message_id,
                    "text": f"Message {sender_id}-{message_id}",
                },
            )

    send_threads = [
        threading.Thread(target=send_batch, args=(sender_id,))
        for sender_id in range(sender_count)
    ]

    try:
        for thread in send_threads:
            thread.start()

        for thread in send_threads:
            thread.join()

        receiver_thread.join(timeout=30)

        if receiver_thread.is_alive():
            raise RuntimeError("Receiver timed out.")

        if receiver_errors:
            raise receiver_errors[0]

        assert len(received_messages) == total_messages

        unique_ids = {
            (message["sender_id"], message["message_id"])
            for message in received_messages
        }

        assert len(unique_ids) == total_messages

        print(f"PASS: Received all {total_messages} messages.")
        print("PASS: No duplicate or corrupted message frames detected.")

    finally:
        sender_socket.close()
        receiver_socket.close()


if __name__ == "__main__":
    main()
