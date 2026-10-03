# ============================================================
# Alfa Commander - Frame Parser
# تحليل إطارات 802.11
# ============================================================

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.utils.validators import is_valid_mac
from app.utils.oui_lookup import lookup as oui_lookup
from app.logger import get_logger

logger = get_logger()


@dataclass
class ParsedFrame:
    frame_type: str = ""             # beacon / probe / deauth / eapol...
    src_mac: str = ""
    dst_mac: str = ""
    bssid: str = ""
    ssid: str = ""
    channel: int = 0
    rssi: int = 0
    timestamp: Optional[datetime] = None
    raw_summary: str = ""


@dataclass
class HandshakeInfo:
    bssid: str
    client_mac: str
    eapol_messages: int = 0
    complete: bool = False
    timestamp: Optional[datetime] = None
    anonce: str = ""
    snonce: str = ""
    mic: str = ""


@dataclass
class PMKIDInfo:
    bssid: str
    client_mac: str
    pmkid: str = ""
    timestamp: Optional[datetime] = None


class FrameParser:
    """
    يحلل إطارات 802.11 من ملفات pcap/pcapng.
    يستخدم scapy.
    """

    @staticmethod
    def is_scapy_available() -> bool:
        try:
            import scapy  # noqa
            return True
        except ImportError:
            return False

    @staticmethod
    def parse_file(pcap_file: Path, max_packets: int = 50000) -> list[ParsedFrame]:
        """تحليل كل الإطارات في الملف."""
        if not FrameParser.is_scapy_available():
            logger.error("scapy غير مثبت")
            return []

        try:
            from scapy.all import rdpcap, Dot11
        except ImportError as e:
            logger.error(f"فشل استيراد scapy: {e}")
            return []

        if not pcap_file.exists():
            return []

        frames = []
        try:
            packets = rdpcap(str(pcap_file))
        except Exception as e:
            logger.exception(f"فشل قراءة {pcap_file}: {e}")
            return []

        for pkt in packets[:max_packets]:
            try:
                if not pkt.haslayer(Dot11):
                    continue
                frame = FrameParser._parse_packet(pkt)
                if frame:
                    frames.append(frame)
            except Exception:
                continue

        return frames

    @staticmethod
    def _parse_packet(pkt) -> Optional[ParsedFrame]:
        from scapy.all import Dot11, Dot11Beacon, Dot11ProbeReq, Dot11Deauth, Dot11Elt

        dot11 = pkt.getlayer(Dot11)
        if dot11 is None:
            return None

        frame = ParsedFrame(
            timestamp=datetime.fromtimestamp(float(pkt.time)),
        )

        # أنواع الإطارات
        type_subtype = (dot11.type, dot11.subtype)

        if type_subtype == (0, 8):    # Beacon
            frame.frame_type = "beacon"
        elif type_subtype == (0, 5):  # Probe Response
            frame.frame_type = "probe_response"
        elif type_subtype == (0, 4):  # Probe Request
            frame.frame_type = "probe_request"
        elif type_subtype == (0, 12): # Deauth
            frame.frame_type = "deauth"
        elif type_subtype == (0, 10): # Disassoc
            frame.frame_type = "disassoc"
        elif type_subtype == (0, 11): # Auth
            frame.frame_type = "auth"
        elif type_subtype == (2, 0):  # Data
            frame.frame_type = "data"
        else:
            frame.frame_type = f"type{type_subtype[0]}_sub{type_subtype[1]}"

        frame.src_mac = (dot11.addr2 or "").upper()
        frame.dst_mac = (dot11.addr1 or "").upper()
        frame.bssid = (dot11.addr3 or "").upper()

        # SSID
        if pkt.haslayer(Dot11Elt):
            elt = pkt.getlayer(Dot11Elt)
            while elt:
                if elt.ID == 0:  # SSID
                    try:
                        frame.ssid = elt.info.decode(errors="ignore")
                    except Exception:
                        pass
                elif elt.ID == 3:  # DS Parameter (channel)
                    try:
                        frame.channel = elt.info[0]
                    except Exception:
                        pass
                elt = elt.payload.getlayer(Dot11Elt)

        frame.raw_summary = pkt.summary()[:200]
        return frame

    # ---------- استخراج المصافحات ----------
    @staticmethod
    def extract_handshakes(pcap_file: Path) -> list[HandshakeInfo]:
        """استخراج معلومات المصافحات من ملف cap."""
        if not FrameParser.is_scapy_available():
            return []

        try:
            from scapy.all import rdpcap, Dot11, EAPOL
        except ImportError:
            return []

        if not pcap_file.exists():
            return []

        handshakes: dict[str, HandshakeInfo] = {}

        try:
            packets = rdpcap(str(pcap_file))
        except Exception as e:
            logger.exception(f"فشل قراءة {pcap_file}: {e}")
            return []

        for pkt in packets:
            try:
                if not pkt.haslayer(EAPOL) or not pkt.haslayer(Dot11):
                    continue

                dot11 = pkt.getlayer(Dot11)
                bssid = (dot11.addr3 or "").upper()
                client = (dot11.addr1 or dot11.addr2 or "").upper()

                if not bssid or not client:
                    continue

                key = f"{bssid}:{client}"
                if key not in handshakes:
                    handshakes[key] = HandshakeInfo(
                        bssid=bssid,
                        client_mac=client,
                    )

                handshakes[key].eapol_messages += 1
                handshakes[key].timestamp = datetime.fromtimestamp(float(pkt.time))

                # 4-way handshake = 4 رسائل EAPOL
                if handshakes[key].eapol_messages >= 4:
                    handshakes[key].complete = True

            except Exception:
                continue

        return list(handshakes.values())


# ------------------------------------------------------------
# دوال مختصرة
# ------------------------------------------------------------
def parse_pcap(pcap_file: Path) -> list[ParsedFrame]:
    return FrameParser.parse_file(pcap_file)


def extract_handshakes(pcap_file: Path) -> list[HandshakeInfo]:
    return FrameParser.extract_handshakes(pcap_file)
