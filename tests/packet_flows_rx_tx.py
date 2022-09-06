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


#
# tests/test_packet_flows__rx_tx.py - unit tests for received packets
# that generate stack's response
#
# ver 2.7
#


from __future__ import annotations

from testslide import StrictMock, TestCase

from pytcp.lib.ip4_address import Ip4Address, Ip4Host
from pytcp.lib.ip6_address import Ip6Address, Ip6Host
from pytcp.lib.mac_address import MacAddress
from pytcp.misc.packet import PacketRx
from pytcp.misc.packet_stats import PacketStatsRx, PacketStatsTx
from pytcp.subsystems.arp_cache import ArpCache
from pytcp.subsystems.nd_cache import NdCache
from pytcp.subsystems.packet_handler import PacketHandler
from pytcp.subsystems.tx_ring import TxRing

PACKET_HANDLER_MODULES = [
    "pytcp.subsystems.packet_handler",
    "protocols.ether.phrx",
    "protocols.ether.phtx",
    "protocols.arp.phrx",
    "protocols.arp.phtx",
    "protocols.ip4.phrx",
    "protocols.ip4.phtx",
    "protocols.ip6.phrx",
    "protocols.ip6.phtx",
    "protocols.icmp4.phrx",
    "protocols.icmp4.phtx",
    "protocols.icmp6.phrx",
    "protocols.icmp6.phtx",
    "protocols.udp.phrx",
    "protocols.udp.phtx",
    "protocols.tcp.phrx",
    "protocols.tcp.phtx",
]


# Ensure critical configuration settings are set properly for
# the testing regardless of actual configuration
CONFIG_PATCHES = {
    "LOG_CHANEL": set(),
    "IP6_SUPPORT": True,
    "IP4_SUPPORT": True,
    "PACKET_INTEGRITY_CHECK": True,
    "PACKET_SANITY_CHECK": True,
    "TAP_MTU": 1500,
    "UDP_ECHO_NATIVE_DISABLE": False,
}


# Addresses below match the test packets and should not be changed
STACK_MAC_ADDRESS = MacAddress("02:00:00:77:77:77")
STACK_IP4_HOST = Ip4Host("192.168.9.7/24")
STACK_IP6_HOST = Ip6Host("2603:9000:e307:9f09:0:ff:fe77:7777/64")
LOCNET_MAC_ADDRESS = MacAddress("52:54:00:df:85:37")
LOCNET_IP4_ADDRESS = Ip4Address("192.168.9.102")
LOCNET_IP6_ADDRESS = Ip6Address("2603:9000:e307:9f09::1fa1")


class TestPacketHandler(TestCase):
    """
    The RX-TX packet flow integration test class.
    """

    def setUp(self):
        """
        Setup tests.
        """

        super().setUp()

        self._patch_config()

        # Assembled packet result is usually taken from 'self.packet_tx',
        # below list is used only for tx fragmentation test where multiple
        # packets are being generated by single packet assembler run.
        self.packets_tx = []

        self.arp_cache_mock = StrictMock(template=ArpCache)
        self.mock_callable(
            target=self.arp_cache_mock,
            method="find_entry",
        ).for_call(LOCNET_IP4_ADDRESS).to_return_value(LOCNET_MAC_ADDRESS)

        self.nd_cache_mock = StrictMock(template=NdCache)
        self.mock_callable(
            target=self.nd_cache_mock,
            method="find_entry",
        ).for_call(LOCNET_IP6_ADDRESS).to_return_value(LOCNET_MAC_ADDRESS)
        self.mock_callable(
            target=self.nd_cache_mock,
            method="add_entry",
        ).for_call(LOCNET_IP6_ADDRESS, LOCNET_MAC_ADDRESS).to_return_value(None)

        self.tx_ring_mock = StrictMock(template=TxRing)
        self.mock_callable(
            target=self.tx_ring_mock,
            method="enqueue",
        ).with_implementation(
            lambda _: _.assemble(self.packet_tx)
            or self.packets_tx.append(self.packet_tx)
        )

        # Initialize packet handler and manually set all the variables
        # that normally would require network connectivity.
        self.packet_handler = PacketHandler(None)
        self.packet_handler.mac_address = STACK_MAC_ADDRESS
        self.packet_handler.mac_multicast = [
            STACK_IP6_HOST.address.solicited_node_multicast.multicast_mac
        ]
        self.packet_handler.ip4_host = [STACK_IP4_HOST]
        self.packet_handler.ip6_host = [STACK_IP6_HOST]
        self.packet_handler.ip6_multicast = [
            Ip6Address("ff02::1"),
            STACK_IP6_HOST.address.solicited_node_multicast,
        ]
        self.packet_handler.arp_cache = self.arp_cache_mock
        self.packet_handler.nd_cache = self.nd_cache_mock
        self.packet_handler.tx_ring = self.tx_ring_mock

        self.packet_tx = memoryview(bytearray(2048))

    def _patch_config(self):
        """
        Patch critical config setting for all packet handler modules.
        """
        for module in PACKET_HANDLER_MODULES:
            for attribute, new_value in CONFIG_PATCHES.items():
                try:
                    self.patch_attribute(
                        target=f"{module}.config",
                        attribute=attribute,
                        new_value=new_value,
                    )
                except ModuleNotFoundError:
                    continue

    # Test name format:
    # 'test_name__protocol_tested__test_description__optional_condition'

    def test_packet_flow_rx_tx__icmp4__ip4_ping(self):
        """
        [ICMPv4] Receive ICMPv4 echo-request packet, respond with echo-reply.
        """
        with open("tests/packets/rx_tx/ip4_ping.rx", "rb") as _:
            packet_rx = _.read()
        with open("tests/packets/rx_tx/ip4_ping.tx", "rb") as _:
            packet_tx = _.read()
        self.packet_handler._phrx_ether(PacketRx(packet_rx))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=1,
                ether__dst_unicast=1,
                ip4__pre_parse=1,
                ip4__dst_unicast=1,
                icmp4__pre_parse=1,
                icmp4__echo_request__respond_echo_reply=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                icmp4__pre_assemble=1,
                icmp4__echo_reply__send=1,
                ip4__pre_assemble=1,
                ip4__mtu_ok__send=1,
                ether__pre_assemble=1,
                ether__src_unspec__fill=1,
                ether__dst_unspec__ip4_lookup=1,
                ether__dst_unspec__ip4_lookup__locnet__arp_cache_hit__send=1,
            ),
        )
        self.assertEqual(self.packet_tx[: len(packet_tx)], packet_tx)

    def test_packet_flow_rx_tx__udp__ip4_udp_to_closed_port(self):
        """
        [UDP] Receive IPv4/UDP packet for closed port,
        respond with ICMPv4 unreachable packet.
        """
        with open("tests/packets/rx_tx/ip4_udp_to_closed_port.rx", "rb") as _:
            packet_rx = _.read()
        with open("tests/packets/rx_tx/ip4_udp_to_closed_port.tx", "rb") as _:
            packet_tx = _.read()
        self.packet_handler._phrx_ether(PacketRx(packet_rx))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=1,
                ether__dst_unicast=1,
                ip4__pre_parse=1,
                ip4__dst_unicast=1,
                udp__pre_parse=1,
                udp__no_socket_match__respond_icmp4_unreachable=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                icmp4__pre_assemble=1,
                icmp4__unreachable_port__send=1,
                ip4__pre_assemble=1,
                ip4__mtu_ok__send=1,
                ether__pre_assemble=1,
                ether__src_unspec__fill=1,
                ether__dst_unspec__ip4_lookup=1,
                ether__dst_unspec__ip4_lookup__locnet__arp_cache_hit__send=1,
            ),
        )
        self.assertEqual(self.packet_tx[: len(packet_tx)], packet_tx)

    def test_packet_flow_rx_tx__udp__ip4_udp_echo(self):
        """
        [UDP] Receive IPv4/UDP packet and echo it back to the sender.
        """
        with open("tests/packets/rx_tx/ip4_udp_echo.rx", "rb") as _:
            packet_rx = _.read()
        with open("tests/packets/rx_tx/ip4_udp_echo.tx", "rb") as _:
            packet_tx = _.read()
        self.packet_handler._phrx_ether(PacketRx(packet_rx))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=1,
                ether__dst_unicast=1,
                ip4__pre_parse=1,
                ip4__dst_unicast=1,
                udp__pre_parse=1,
                udp__echo_native__respond_udp=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                udp__pre_assemble=1,
                udp__send=1,
                ip4__pre_assemble=1,
                ip4__mtu_ok__send=1,
                ether__pre_assemble=1,
                ether__src_unspec__fill=1,
                ether__dst_unspec__ip4_lookup=1,
                ether__dst_unspec__ip4_lookup__locnet__arp_cache_hit__send=1,
            ),
        )
        self.assertEqual(self.packet_tx[: len(packet_tx)], packet_tx)

    def _test_packet_flow_rx_tx__ip4_frag__ip4_udp_echo_rx_frag(
        self, order: list(int)
    ):
        """
        [IPv4 frag] Receive fragmented IPv4/UDP packets and echo them
        back to the sender in specified order.
        """
        frags = []
        for index in range(5):
            with open(
                f"tests/packets/rx_tx/ip4_udp_echo_rx_frag_{index}.rx", "rb"
            ) as _:
                frags.append(_.read())
        with open("tests/packets/rx_tx/ip4_udp_echo_rx_frag.tx", "rb") as _:
            packet_tx = _.read()
        for index in order:
            self.packet_handler._phrx_ether(PacketRx(frags[index]))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=len(order),
                ether__dst_unicast=len(order),
                ip4__pre_parse=len(order),
                ip4__dst_unicast=len(order),
                ip4__frag=len(order),
                ip4__defrag=1,
                udp__pre_parse=1,
                udp__echo_native__respond_udp=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                udp__pre_assemble=1,
                udp__send=1,
                ip4__pre_assemble=1,
                ip4__mtu_ok__send=1,
                ether__pre_assemble=1,
                ether__src_unspec__fill=1,
                ether__dst_unspec__ip4_lookup=1,
                ether__dst_unspec__ip4_lookup__locnet__arp_cache_hit__send=1,
            ),
        )
        self.assertEqual(self.packet_tx[: len(packet_tx)], packet_tx)

    def test_packet_flow_rx_tx__ip4_frag__ip4_udp_echo_rx_frag_01234(self):
        """
        [IPv4 frag] Receive fragmented IPv4/UDP packets and echo them
        back to the sender.
        """
        self._test_packet_flow_rx_tx__ip4_frag__ip4_udp_echo_rx_frag(
            [0, 1, 2, 3, 4]
        )

    def test_packet_flow_rx_tx__ip4_frag__ip4_udp_echo_rx_frag_43210(self):
        """
        [IPv4 frag] Receive fragmented IPv4/UDP packets and echo them
        back to the sender.
        """
        self._test_packet_flow_rx_tx__ip4_frag__ip4_udp_echo_rx_frag(
            [4, 3, 2, 1, 0]
        )

    def test_packet_flow_rx_tx__ip4_frag__ip4_udp_echo_rx_frag_12043(self):
        """
        [IPv4 frag] Receive fragmented IPv4/UDP packets and echo them
        back to the sender.
        """

        self._test_packet_flow_rx_tx__ip4_frag__ip4_udp_echo_rx_frag(
            [1, 2, 0, 4, 3]
        )

    def test_packet_flow_rx_tx__ip4_frag__ip4_udp_echo_rx_frag_1202103341(
        self,
    ):
        """
        [IPv4 frag] Receive fragmented IPv4/UDP packets and echo them
        back to the sender.
        """
        self._test_packet_flow_rx_tx__ip4_frag__ip4_udp_echo_rx_frag(
            [1, 2, 0, 2, 1, 0, 3, 3, 4, 1]
        )

    def test_packet_flow_rx_tx__ip4_frag__ip4_udp_echo_tx_frag(self):
        """
        [IPv4 frag] Receive IPv4/UDP packet and echo it back to the sender
        in fragments.
        """
        with open("tests/packets/rx_tx/ip4_udp_echo_tx_frag.rx", "rb") as _:
            packet_rx = _.read()
        frags = []
        for index in range(5):
            with open(
                f"tests/packets/rx_tx/ip4_udp_echo_tx_frag_{index}.tx", "rb"
            ) as _:
                frags.append(_.read())
        self.packet_handler._phrx_ether(PacketRx(packet_rx))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=1,
                ether__dst_unicast=1,
                ip4__pre_parse=1,
                ip4__dst_unicast=1,
                udp__pre_parse=1,
                udp__echo_native__respond_udp=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                udp__pre_assemble=1,
                udp__send=1,
                ip4__pre_assemble=1,
                ip4__mtu_exceed__frag=1,
                ip4__mtu_exceed__frag__send=5,
                ether__pre_assemble=5,
                ether__src_unspec__fill=5,
                ether__dst_unspec__ip4_lookup=5,
                ether__dst_unspec__ip4_lookup__locnet__arp_cache_hit__send=5,
            ),
        )
        for index in range(5):
            self.assertEqual(
                self.packets_tx[index][: len(frags[index])], frags[index]
            )

    def test_packet_flow_rx_tx__tcp__ip4_tcp_syn_to_closed_port(self):
        """
        [TCP] Receive IPv4/TCP SYN packet to closed port, respond with
        IPv4/TCP RST/ACK packet.
        """
        with open(
            "tests/packets/rx_tx/ip4_tcp_syn_to_closed_port.rx", "rb"
        ) as _:
            packet_rx = _.read()
        with open(
            "tests/packets/rx_tx/ip4_tcp_syn_to_closed_port.tx", "rb"
        ) as _:
            packet_tx = _.read()
        self.packet_handler._phrx_ether(PacketRx(packet_rx))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=1,
                ether__dst_unicast=1,
                ip4__pre_parse=1,
                ip4__dst_unicast=1,
                tcp__pre_parse=1,
                tcp__no_socket_match__respond_rst=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                tcp__pre_assemble=1,
                tcp__flag_rst=1,
                tcp__flag_ack=1,
                tcp__send=1,
                ip4__pre_assemble=1,
                ip4__mtu_ok__send=1,
                ether__pre_assemble=1,
                ether__src_unspec__fill=1,
                ether__dst_unspec__ip4_lookup=1,
                ether__dst_unspec__ip4_lookup__locnet__arp_cache_hit__send=1,
            ),
        )
        self.assertEqual(self.packet_tx[: len(packet_tx)], packet_tx)

    def test_packet_flow_rx_tx__icmp6__ip6_ping(self):
        """
        [ICMPv6] Receive ICMPv6 echo-request packet, respond with echo-reply.
        """
        with open("tests/packets/rx_tx/ip6_ping.rx", "rb") as _:
            packet_rx = _.read()
        with open("tests/packets/rx_tx/ip6_ping.tx", "rb") as _:
            packet_tx = _.read()
        self.packet_handler._phrx_ether(PacketRx(packet_rx))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=1,
                ether__dst_unicast=1,
                ip6__pre_parse=1,
                ip6__dst_unicast=1,
                icmp6__pre_parse=1,
                icmp6__echo_request__respond_echo_reply=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                icmp6__pre_assemble=1,
                icmp6__echo_reply__send=1,
                ip6__pre_assemble=1,
                ip6__mtu_ok__send=1,
                ether__pre_assemble=1,
                ether__src_unspec__fill=1,
                ether__dst_unspec__ip6_lookup=1,
                ether__dst_unspec__ip6_lookup__locnet__nd_cache_hit__send=1,
            ),
        )
        self.assertEqual(self.packet_tx[: len(packet_tx)], packet_tx)

    def test_packet_flow_rx_tx__udp__ip6_udp_to_closed_port(self):
        """
        [UDP] Receive IPv6/UDP packet for closed port, respond with
        ICMPv6 unreachable packet.
        """
        with open("tests/packets/rx_tx/ip6_udp_to_closed_port.rx", "rb") as _:
            packet_rx = _.read()
        with open("tests/packets/rx_tx/ip6_udp_to_closed_port.tx", "rb") as _:
            packet_tx = _.read()
        self.packet_handler._phrx_ether(PacketRx(packet_rx))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=1,
                ether__dst_unicast=1,
                ip6__pre_parse=1,
                ip6__dst_unicast=1,
                udp__pre_parse=1,
                udp__no_socket_match__respond_icmp6_unreachable=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                icmp6__pre_assemble=1,
                icmp6__unreachable_port__send=1,
                ip6__pre_assemble=1,
                ip6__mtu_ok__send=1,
                ether__pre_assemble=1,
                ether__src_unspec__fill=1,
                ether__dst_unspec__ip6_lookup=1,
                ether__dst_unspec__ip6_lookup__locnet__nd_cache_hit__send=1,
            ),
        )
        self.assertEqual(self.packet_tx[: len(packet_tx)], packet_tx)

    def test_packet_flow_rx_tx__udp__ip6_udp_echo(self):
        """
        [UDP] Receive IPv4/UDP packet and echo it back to the sender.
        """
        with open("tests/packets/rx_tx/ip6_udp_echo.rx", "rb") as _:
            packet_rx = _.read()
        with open("tests/packets/rx_tx/ip6_udp_echo.tx", "rb") as _:
            packet_tx = _.read()
        self.packet_handler._phrx_ether(PacketRx(packet_rx))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=1,
                ether__dst_unicast=1,
                ip6__pre_parse=1,
                ip6__dst_unicast=1,
                udp__pre_parse=1,
                udp__echo_native__respond_udp=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                udp__pre_assemble=1,
                udp__send=1,
                ip6__pre_assemble=1,
                ip6__mtu_ok__send=1,
                ether__pre_assemble=1,
                ether__src_unspec__fill=1,
                ether__dst_unspec__ip6_lookup=1,
                ether__dst_unspec__ip6_lookup__locnet__nd_cache_hit__send=1,
            ),
        )
        self.assertEqual(self.packet_tx[: len(packet_tx)], packet_tx)

    def _test_packet_flow_rx_tx__ip6_frag__ip6_udp_echo_rx_frag(
        self, order: list(int)
    ):
        """
        [IPv6 frag] Receive fragmented IPv6/UDP packets and echo them back
        to the sender in specified order.
        """
        frags = []
        for index in range(5):
            with open(
                f"tests/packets/rx_tx/ip6_udp_echo_rx_frag_{index}.rx", "rb"
            ) as _:
                frags.append(_.read())
        with open("tests/packets/rx_tx/ip6_udp_echo_rx_frag.tx", "rb") as _:
            packet_tx = _.read()
        for index in order:
            self.packet_handler._phrx_ether(PacketRx(frags[index]))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=len(order),
                ether__dst_unicast=len(order),
                ip6__pre_parse=len(order)
                + 1,  # For the IPv6 frag implementation packet once reasembled
                ip6__dst_unicast=len(order)
                + 1,  # is put again through the IPv6 parser for processing
                ip6_ext_frag__pre_parse=len(order),
                ip6_ext_frag__defrag=1,
                udp__pre_parse=1,
                udp__echo_native__respond_udp=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                udp__pre_assemble=1,
                udp__send=1,
                ip6__pre_assemble=1,
                ip6__mtu_ok__send=1,
                ether__pre_assemble=1,
                ether__src_unspec__fill=1,
                ether__dst_unspec__ip6_lookup=1,
                ether__dst_unspec__ip6_lookup__locnet__nd_cache_hit__send=1,
            ),
        )
        self.assertEqual(self.packet_tx[: len(packet_tx)], packet_tx)

    def test_packet_flow_rx_tx__ip6_frag__ip6_udp_echo_rx_frag_01234(self):
        """
        [IPv6 frag] Receive fragmented IPv6/UDP packets and echo them back
        to the sender.
        """
        self._test_packet_flow_rx_tx__ip6_frag__ip6_udp_echo_rx_frag(
            [0, 1, 2, 3, 4]
        )

    def test_packet_flow_rx_tx__ip6_frag__ip6_udp_echo_rx_frag_43210(self):
        """
        [IPv6 frag] Receive fragmented IPv6/UDP packets and echo them back
        to the sender.
        """
        self._test_packet_flow_rx_tx__ip6_frag__ip6_udp_echo_rx_frag(
            [4, 3, 2, 1, 0]
        )

    def test_packet_flow_rx_tx__ip6_frag__ip6_udp_echo_rx_frag_12043(self):
        """
        [IPv6 frag] Receive fragmented IPv6/UDP packets and echo them back
        to the sender.
        """
        self._test_packet_flow_rx_tx__ip6_frag__ip6_udp_echo_rx_frag(
            [1, 2, 0, 4, 3]
        )

    def test_packet_flow_rx_tx__ip6_frag__ip6_udp_echo_rx_frag_1202103341(
        self,
    ):
        """
        [IPv6 frag] Receive fragmented IPv6/UDP packets and echo them back
        to the sender.
        """
        self._test_packet_flow_rx_tx__ip6_frag__ip6_udp_echo_rx_frag(
            [1, 2, 0, 2, 1, 0, 3, 3, 4, 1]
        )

    def test_packet_flow_rx_tx__ip6_frag__ip6_udp_echo_tx_frag(self):
        """
        [IPv6 frag] Receive IPv4/UDP packet and echo it back to the sender
        in fragments.
        """
        with open("tests/packets/rx_tx/ip6_udp_echo_tx_frag.rx", "rb") as _:
            packet_rx = _.read()
        frags = []
        for index in range(5):
            with open(
                f"tests/packets/rx_tx/ip6_udp_echo_tx_frag_{index}.tx", "rb"
            ) as _:
                frags.append(_.read())
        self.packet_handler._phrx_ether(PacketRx(packet_rx))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=1,
                ether__dst_unicast=1,
                ip6__pre_parse=1,
                ip6__dst_unicast=1,
                udp__pre_parse=1,
                udp__echo_native__respond_udp=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                udp__pre_assemble=1,
                udp__send=1,
                ip6__pre_assemble=6,  # 1 time for initial packet
                # and 5 times for frags
                ip6__mtu_exceed__frag=1,
                ip6__mtu_ok__send=5,
                ip6_ext_frag__pre_assemble=1,
                ip6_ext_frag__send=5,
                ether__pre_assemble=5,
                ether__src_unspec__fill=5,
                ether__dst_unspec__ip6_lookup=5,
                ether__dst_unspec__ip6_lookup__locnet__nd_cache_hit__send=5,
            ),
        )
        for index in range(5):
            self.assertEqual(
                self.packets_tx[index][: len(frags[index])], frags[index]
            )

    def test_packet_flow_rx_tx__tcp__ip6_tcp_syn_to_closed_port(self):
        """
        [TCP] Receive IPv6/TCP SYN packet to closed port, respond with
        IPv6/TCP RST/ACK packet.
        """
        with open(
            "tests/packets/rx_tx/ip6_tcp_syn_to_closed_port.rx", "rb"
        ) as _:
            packet_rx = _.read()
        with open(
            "tests/packets/rx_tx/ip6_tcp_syn_to_closed_port.tx", "rb"
        ) as _:
            packet_tx = _.read()
        self.packet_handler._phrx_ether(PacketRx(packet_rx))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=1,
                ether__dst_unicast=1,
                ip6__pre_parse=1,
                ip6__dst_unicast=1,
                tcp__pre_parse=1,
                tcp__no_socket_match__respond_rst=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                tcp__pre_assemble=1,
                tcp__flag_rst=1,
                tcp__flag_ack=1,
                tcp__send=1,
                ip6__pre_assemble=1,
                ip6__mtu_ok__send=1,
                ether__pre_assemble=1,
                ether__src_unspec__fill=1,
                ether__dst_unspec__ip6_lookup=1,
                ether__dst_unspec__ip6_lookup__locnet__nd_cache_hit__send=1,
            ),
        )
        self.assertEqual(self.packet_tx[: len(packet_tx)], packet_tx)

    def test_packet_flow_rx_tx__arp__arp_request(self):
        """
        [ARP] Receive ARP Request packet for stack IPv4 address,
        respond with ARP Reply.
        """
        with open("tests/packets/rx_tx/arp_request.rx", "rb") as _:
            packet_rx = _.read()
        with open("tests/packets/rx_tx/arp_request.tx", "rb") as _:
            packet_tx = _.read()
        self.mock_callable(self.arp_cache_mock, "add_entry").for_call(
            Ip4Address("192.168.9.102"), MacAddress("52:54:00:df:85:37")
        ).to_return_value(None).and_assert_called_once()
        self.packet_handler._phrx_ether(PacketRx(packet_rx))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=1,
                ether__dst_broadcast=1,
                arp__pre_parse=1,
                arp__op_request=1,
                arp__op_request__tpa_stack__respond=1,
                arp__op_request__update_arp_cache=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                arp__pre_assemble=1,
                arp__op_reply__send=1,
                ether__pre_assemble=1,
                ether__src_spec=1,
                ether__dst_spec__send=1,
            ),
        )
        self.assertEqual(self.packet_tx[: len(packet_tx)], packet_tx)

    def test_packet_flow_rx_tx__icmp6_nd__nd_ns__unicast_dst(self):
        """
        [ICMPv6 ND] Receive ICMPv6 Neighbor Solicitation packet for stack
        IPv6 address, respond with Neighbor Advertisement.
        """
        with open(
            "tests/packets/rx_tx/ip6_icmp6_nd_ns__unicast_dst.rx", "rb"
        ) as _:
            packet_rx = _.read()
        with open(
            "tests/packets/rx_tx/ip6_icmp6_nd_ns__unicast_dst.tx", "rb"
        ) as _:
            packet_tx = _.read()
        self.packet_handler._phrx_ether(PacketRx(packet_rx))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=1,
                ether__dst_unicast=1,
                ip6__pre_parse=1,
                ip6__dst_unicast=1,
                icmp6__pre_parse=1,
                icmp6__nd_neighbor_solicitation=1,
                icmp6__nd_neighbor_solicitation__update_nd_cache=1,
                icmp6__nd_neighbor_solicitation__target_stack__respond=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                icmp6__pre_assemble=1,
                icmp6__nd_neighbor_advertisement__send=1,
                ip6__pre_assemble=1,
                ip6__mtu_ok__send=1,
                ether__pre_assemble=1,
                ether__src_unspec__fill=1,
                ether__dst_unspec__ip6_lookup=1,
                ether__dst_unspec__ip6_lookup__locnet__nd_cache_hit__send=1,
            ),
        )
        self.assertEqual(self.packet_tx[: len(packet_tx)], packet_tx)

    def test_packet_flow_rx_tx__icmp6_nd__nd_ns__no_slla(self):
        """
        [ICMPv6 ND] Receive ICMPv6 Neighbor Solicitation packet,
        respond with Neighbor Advertisement.
        """
        with open("tests/packets/rx_tx/ip6_icmp6_nd_ns__no_slla.rx", "rb") as _:
            packet_rx = _.read()
        with open("tests/packets/rx_tx/ip6_icmp6_nd_ns__no_slla.tx", "rb") as _:
            packet_tx = _.read()
        self.packet_handler._phrx_ether(PacketRx(packet_rx))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=1,
                ether__dst_multicast=1,
                ip6__pre_parse=1,
                ip6__dst_multicast=1,
                icmp6__pre_parse=1,
                icmp6__nd_neighbor_solicitation=1,
                icmp6__nd_neighbor_solicitation__target_stack__respond=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                icmp6__pre_assemble=1,
                icmp6__nd_neighbor_advertisement__send=1,
                ip6__pre_assemble=1,
                ip6__mtu_ok__send=1,
                ether__pre_assemble=1,
                ether__src_unspec__fill=1,
                ether__dst_unspec__ip6_lookup=1,
                ether__dst_unspec__ip6_lookup__locnet__nd_cache_hit__send=1,
            ),
        )
        self.assertEqual(self.packet_tx[: len(packet_tx)], packet_tx)

    def test_packet_flow_rx_tx__icmp6_nd__nd_ns(self):
        """
        [ICMPv6 ND] Receive ICMPv6 Neighbor Solicitation packet,
        respond with Neighbor Advertisement.
        """
        with open("tests/packets/rx_tx/ip6_icmp6_nd_ns.rx", "rb") as _:
            packet_rx = _.read()
        with open("tests/packets/rx_tx/ip6_icmp6_nd_ns.tx", "rb") as _:
            packet_tx = _.read()
        self.packet_handler._phrx_ether(PacketRx(packet_rx))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=1,
                ether__dst_multicast=1,
                ip6__pre_parse=1,
                ip6__dst_multicast=1,
                icmp6__pre_parse=1,
                icmp6__nd_neighbor_solicitation=1,
                icmp6__nd_neighbor_solicitation__update_nd_cache=1,
                icmp6__nd_neighbor_solicitation__target_stack__respond=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                icmp6__pre_assemble=1,
                icmp6__nd_neighbor_advertisement__send=1,
                ip6__pre_assemble=1,
                ip6__mtu_ok__send=1,
                ether__pre_assemble=1,
                ether__src_unspec__fill=1,
                ether__dst_unspec__ip6_lookup=1,
                ether__dst_unspec__ip6_lookup__locnet__nd_cache_hit__send=1,
            ),
        )
        self.assertEqual(self.packet_tx[: len(packet_tx)], packet_tx)

    def test_packet_flow_rx_tx__icmp6_nd__nd_ns__dad(self):
        """
        [ICMPv6 ND] Receive ICMPv6 Neighbor Solicitation DAD packet,
        respond with Neighbor Advertisement
        """
        with open("tests/packets/rx_tx/ip6_icmp6_nd_ns__dad.rx", "rb") as _:
            packet_rx = _.read()
        with open("tests/packets/rx_tx/ip6_icmp6_nd_ns__dad.tx", "rb") as _:
            packet_tx = _.read()
        self.packet_handler._phrx_ether(PacketRx(packet_rx))
        self.assertEqual(
            self.packet_handler.packet_stats_rx,
            PacketStatsRx(
                ether__pre_parse=1,
                ether__dst_multicast=1,
                ip6__pre_parse=1,
                ip6__dst_multicast=1,
                icmp6__pre_parse=1,
                icmp6__nd_neighbor_solicitation=1,
                icmp6__nd_neighbor_solicitation__dad=1,
                icmp6__nd_neighbor_solicitation__target_stack__respond=1,
            ),
        )
        self.assertEqual(
            self.packet_handler.packet_stats_tx,
            PacketStatsTx(
                icmp6__pre_assemble=1,
                icmp6__nd_neighbor_advertisement__send=1,
                ip6__pre_assemble=1,
                ip6__mtu_ok__send=1,
                ether__pre_assemble=1,
                ether__src_unspec__fill=1,
                ether__dst_unspec__ip6_lookup=1,
                ether__dst_unspec__ip6_lookup__multicast__send=1,
            ),
        )
        self.assertEqual(self.packet_tx[: len(packet_tx)], packet_tx)
