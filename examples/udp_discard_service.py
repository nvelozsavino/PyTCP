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
The example 'user space' service UDP Discard (RFC 863).

examples/udp_discard_service.py

ver 2.7
"""


from __future__ import annotations

import time
from typing import TYPE_CHECKING

import click

from examples.lib.udp_service import UdpService
from pytcp import TcpIpStack

if TYPE_CHECKING:
    from pytcp.lib.socket import Socket


class UdpDiscardService(UdpService):
    """
    UDP Echo service support class.
    """

    def __init__(
        self, *, local_ip_address: str = "0.0.0.0", local_port: int = 9
    ):
        """
        Class constructor.
        """

        super().__init__(
            service_name="Discard",
            local_ip_address=local_ip_address,
            local_port=local_port,
        )

    def service(self, *, listening_socket: Socket) -> None:
        """
        Inbound connection handler.
        """

        while self._run_thread:
            message, remote_address = listening_socket.recvfrom()
            click.echo(
                f"Service UDP Discard: Received {len(message)} bytes from "
                f"{remote_address[0]}, port {remote_address[1]}."
            )


@click.command()
@click.option("--interface", default="tap7")
def cli(*, interface: str) -> None:
    """
    Start PyTCP stack and stop it when user presses Ctrl-C.
    Run the UDP Discard service.
    """

    stack = TcpIpStack(interface=interface)
    service = UdpDiscardService()

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
