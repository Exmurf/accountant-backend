# RFC 2606 reserves these domains so that they can never receive mail. Sending
# to one is a guaranteed bounce, and a run of bounces is what costs a sender its
# reputation, so nothing is ever addressed to them.
PLACEHOLDER_DOMAINS = frozenset({"example.com", "example.org", "example.net"})


def is_placeholder_address(email: str) -> bool:
    return email.rsplit("@", 1)[-1].lower() in PLACEHOLDER_DOMAINS
