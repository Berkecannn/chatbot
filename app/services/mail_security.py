"""Verified TLS and pinned, public DNS destinations for customer mail servers."""
import ipaddress
import imaplib
import os
import smtplib
import socket
import ssl

def destination(host, port):
    if not isinstance(host,str) or not host or any(c in host for c in '\r\n/\\\x00'):
        raise ValueError('Geçersiz posta sunucusu.')
    approved={h.strip().casefold() for h in os.getenv('ALLOW_PRIVATE_MAIL_HOSTS','').split(',') if h.strip()}
    addresses=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
    if not addresses:
        raise ValueError('Posta sunucusu çözümlenemedi.')
    if host.casefold() not in approved:
        for address in addresses:
            if not ipaddress.ip_address(address[4][0].split('%')[0]).is_global:
                raise ValueError('Özel ağ posta sunucusu için sunucu sahibinin izni gereklidir.')
    # Resolve once and connect to this exact numeric address. TLS still verifies
    # the original DNS hostname, avoiding a second DNS lookup/rebinding window.
    return addresses[0][4][0]

class SafeSMTP(smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        return socket.create_connection((destination(host,port),port),timeout,self.source_address)

class SafeSMTP_SSL(smtplib.SMTP_SSL):
    def _get_socket(self, host, port, timeout):
        raw=socket.create_connection((destination(host,port),port),timeout,self.source_address)
        try:
            return self.context.wrap_socket(raw,server_hostname=host)
        except Exception:
            raw.close()
            raise

class SafeIMAP4_SSL(imaplib.IMAP4_SSL):
    def _create_socket(self, timeout):
        raw=socket.create_connection((destination(self.host,self.port),self.port),timeout)
        try:
            return self.ssl_context.wrap_socket(raw,server_hostname=self.host)
        except Exception:
            raw.close()
            raise
