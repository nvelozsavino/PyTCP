#!/usr/bin/env python3

############################################################################
#                                                                          #
#  PyTCP - Python TCP/IP stack                                             #
#  Copyright (C) 2020-present Sebastian Majewski                           #
#                                                                          #
#  This program is free software: you can redistribute it and/or modify    #
#  it under the terms of the GNU General Public License as published by    #
#  the Free Software Foundation, either version 3 of the License, or       #
#  (at your option) any later version.                                     #
#                                                                          #
#  This program is distributed in the hope that it will be useful,         #
#  but WITHOUT ANY WARRANTY; without even the implied warranty of          #
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the           #
#  GNU General Public License for more details.                            #
#                                                                          #
#  You should have received a copy of the GNU General Public License       #
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.  #
#                                                                          #
#  Author's email: ccie18643@gmail.com                                     #
#  Github repository: https://github.com/ccie18643/PyTCP                   #
#                                                                          #
############################################################################


"""
The example 'user space' service TCP Daytime (RFC 867).

examples/tcp_daytime_service.py - The 'user space' service TCP Daytime (RFC 867).

ver 2.7
"""


from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING

import click

from examples.lib.tcp_service import TcpService
from pytcp import TcpIpStack

if TYPE_CHECKING:
    from pytcp.lib.socket import Socket


class TcpDaytimeService(TcpService):
    """
    TCP Daytime service support class.
    """

    def __init__(
        self,
        *,
        local_ip_address: str = "0.0.0.0",
        local_port: int = 13,
        message_count: int = -1,
        message_delay: int = 1,
    ):
        """
        Class constructor.
        """

        super().__init__(
            service_name="Daytime",
            local_ip_address=local_ip_address,
            local_port=local_port,
        )

        self._message_count = message_count
        self._message_delay = message_delay

    def service(self, *, connected_socket: Socket) -> None:
        """
        Inbound connection handler.
        """

        # Create local copy of this variable.
        message_count = self._message_count

        click.echo(
            "Service TCP Daytime: Sending first message to "
            f"{connected_socket.remote_ip_address}, port {connected_socket.remote_port}."
        )
        connected_socket.send(b"***CLIENT OPEN / SERVICE OPEN***\n")

        while self._run_thread and message_count:
            message = bytes(str(datetime.now()) + "\n", "utf-8")

            try:
                connected_socket.send(message)
            except OSError as error:
                click.echo(f"Service TCP Daytime: send() error - {error!r}.")
                break

            click.echo(
                f"Service TCP Daytime: Sent {len(message)} bytes of data "
                f"to {connected_socket.remote_ip_address}, port {connected_socket.remote_port}."
            )
            time.sleep(self._message_delay)
            message_count = min(message_count, message_count - 1)

        connected_socket.close()
        click.echo(
            "Service TCP Daytime: Closed connection to "
            f"{connected_socket.remote_ip_address}, port {connected_socket.remote_port}.",
        )


@click.command()
@click.option("--interface", default="tap7")
def cli(*, interface: str) -> None:
    """
    Start PyTCP stack and stop it when user presses Ctrl-C.
    Run the TCP Daytime service.
    """

    stack = TcpIpStack(interface=interface)
    service = TcpDaytimeService()

    try:
        stack.start()
        service.start()
        while True:
            time.sleep(60)

    except KeyboardInterrupt:
        service.stop()
        stack.stop()


if __name__ == "__main__":
    cli()  # pylint: disable = missing-kwoa
