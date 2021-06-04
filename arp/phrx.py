#!/usr/bin/env python3

############################################################################
#                                                                          #
#  PyTCP - Python TCP/IP stack                                             #
#  Copyright (C) 2020-2021  Sebastian Majewski                             #
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
#  Author'w email: ccie18643@gmail.com                                     #
#  Github repository: https://github.com/ccie18643/PyTCP                   #
#                                                                          #
############################################################################


#
# arp/phrx.py - packet handler for inbound ARP packets
#


from __future__ import annotations  # Required by Python ver < 3.10

from typing import TYPE_CHECKING

import arp.ps
import config
from arp.fpp import ArpParser
from lib.ip4_address import Ip4Address
from lib.logger import log

if TYPE_CHECKING:
    from misc.packet import PacketRx


def _phrx_arp(self, packet_rx: PacketRx) -> None:
    """Handle inbound ARP packets"""

    ArpParser(packet_rx)

    if packet_rx.parse_failed:
        log("arp", f"{packet_rx.tracker} - <CRIT>{packet_rx.parse_failed}</>")
        return

    log("arp", f"{packet_rx.tracker} - {packet_rx.arp}")

    if packet_rx.arp.oper == arp.ps.ARP_OP_REQUEST:
        # Check if request contains our IP address in SPA field, this indicates IP address conflict
        if packet_rx.arp.spa in self.ip4_unicast:
            log("arp", f"{packet_rx.tracker} - <WARN>IP ({packet_rx.arp.spa}) conflict detected with host at {packet_rx.arp.sha}</>")
            return

        # Check if the request is for one of our IP addresses, if so the craft ARP reply packet and send it out
        if packet_rx.arp.tpa in self.ip4_unicast:
            self._phtx_arp(
                ether_src=self.mac_unicast,
                ether_dst=packet_rx.arp.sha,
                arp_oper=arp.ps.ARP_OP_REPLY,
                arp_sha=self.mac_unicast,
                arp_spa=packet_rx.arp.tpa,
                arp_tha=packet_rx.arp.sha,
                arp_tpa=packet_rx.arp.spa,
                echo_tracker=packet_rx.tracker,
            )

            # Update ARP cache with the mapping learned from the received ARP request that was destined to this stack
            if config.arp_cache_update_from_direct_request:
                log(
                    "arp",
                    f"{packet_rx.tracker} - <INFO>Adding/refreshing ARP cache entry from direct request " + f"- {packet_rx.arp.spa} -> {packet_rx.arp.sha}</>",
                )
                self.arp_cache.add_entry(packet_rx.arp.spa, packet_rx.arp.sha)

            return

    # Handle ARP reply
    elif packet_rx.arp.oper == arp.ps.ARP_OP_REPLY:
        # Check for ARP reply that is response to our ARP probe, that indicates that IP address we trying to claim is in use
        if packet_rx.ether.dst == self.mac_unicast:
            if (
                packet_rx.arp.spa in [_.address for _ in self.ip4_host_candidate]
                and packet_rx.arp.tha == self.mac_unicast
                and packet_rx.arp.tpa == Ip4Address("0.0.0.0")
            ):
                log("arp", f"{packet_rx.tracker} - <WARN>ARP Probe detected conflict for IP {packet_rx.arp.spa} with host at {packet_rx.arp.sha}</>")
                self.arp_probe_unicast_conflict.add(packet_rx.arp.spa)
                return

        # Update ARP cache with mapping received as direct ARP reply
        if packet_rx.ether.dst == self.mac_unicast:
            log("arp", f"{packet_rx.tracker} - Adding/refreshing ARP cache entry from direct reply - {packet_rx.arp.spa} -> {packet_rx.arp.sha}")
            self.arp_cache.add_entry(packet_rx.arp.spa, packet_rx.arp.sha)
            return

        # Update ARP cache with mapping received as gratuitous ARP reply
        if packet_rx.ether.dst.is_broadcast and packet_rx.arp.spa == packet_rx.arp.tpa and config.arp_cache_update_from_gratuitious_reply:
            log("arp", f"{packet_rx.tracker} - Adding/refreshing ARP cache entry from gratuitous reply - {packet_rx.arp.spa} -> {packet_rx.arp.sha}")
            self.arp_cache.add_entry(packet_rx.arp.spa, packet_rx.arp.sha)
            return
