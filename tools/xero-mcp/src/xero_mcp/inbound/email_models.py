from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class InboundAttachment:
    name: str
    content_type: str
    data: bytes
    sha256: str = field(default="")

    def __post_init__(self) -> None:
        if not self.sha256:
            self.sha256 = hashlib.sha256(self.data).hexdigest()


@dataclass
class ParsedInboundEmail:
    to_addresses: list[str]
    from_address: str
    subject: str
    attachments: list[InboundAttachment]
    body_text: str = ""
