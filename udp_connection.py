"""Small UDP client/server helpers.

UDP does not establish a reliable stream connection.  ``UdpConnection`` uses
``connect`` to select a default peer for outgoing datagrams and provides
bounded receive timeouts so callers do not block forever.
"""

from __future__ import annotations

import argparse
import socket
from contextlib import closing


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9999
DEFAULT_BUFFER_SIZE = 4096


class UdpConnection:
    """Send and receive UTF-8 messages over UDP."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        *,
        timeout: float = 5.0,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
    ) -> None:
        if not 1 <= port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if buffer_size <= 0:
            raise ValueError("buffer_size must be greater than zero")

        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.settimeout(timeout)
        self._socket.connect((host, port))

    def send(self, message: str) -> None:
        """Send one UTF-8 datagram to the configured peer."""
        self._socket.send(message.encode("utf-8"))

    def receive(self) -> str:
        """Receive one UTF-8 datagram from the configured peer."""
        data = self._socket.recv(self.buffer_size)
        return data.decode("utf-8")

    def close(self) -> None:
        """Release the underlying socket."""
        self._socket.close()

    def __enter__(self) -> UdpConnection:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def run_server(host: str, port: int, buffer_size: int) -> None:
    """Print each received message and acknowledge it."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as server:
        server.bind((host, port))
        print(f"Listening on {host}:{port}")
        while True:
            data, address = server.recvfrom(buffer_size)
            message = data.decode("utf-8")
            print(f"{address[0]}:{address[1]}: {message}")
            server.sendto(b"OK", address)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--message", help="send one message instead of listening")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    if args.message is None:
        run_server(args.host, args.port, DEFAULT_BUFFER_SIZE)
        return

    with UdpConnection(args.host, args.port, timeout=args.timeout) as connection:
        connection.send(args.message)
        print(connection.receive())


if __name__ == "__main__":
    main()