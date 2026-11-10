"""Standard-library server for an explicitly selected trusted LAN interface."""
import argparse
import ipaddress
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

PUBLIC = Path(__file__).resolve().parent / 'public'
FILES = {'index.html', 'style.css', 'app.js', 'protocol.js', 'scheduler.js', 'morse_table.json'}


class PublicHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.js': 'text/javascript; charset=utf-8',
                      '.json': 'application/json; charset=utf-8'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)

    def send_head(self):
        name = unquote(urlsplit(self.path).path)
        name = 'index.html' if name == '/' else name.removeprefix('/')
        target = PUBLIC / name
        if name not in FILES or target.is_symlink() or target.resolve().parent != PUBLIC.resolve():
            self.send_error(404, 'Not found')
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(403, 'Directory listing disabled')
        return None

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        super().end_headers()


def interface(value):
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as error:
        raise argparse.ArgumentTypeError('PCのLAN側IPv4アドレスを指定してください。') from error
    if not (address.is_private or address.is_loopback) or address.is_unspecified or address.is_multicast or address.is_reserved or int(address) == 0xffffffff:
        raise argparse.ArgumentTypeError('ワイルドカードや公開IPではなく、PCのLAN側IPv4を指定してください。')
    return str(address)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=interface, default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be 1..65535')
    with ThreadingHTTPServer((args.host, args.port), PublicHandler) as server:
        print(f'Optical sender: http://{args.host}:{args.port}/', flush=True)
        print('Trusted LAN only. Public folder only. Stop: Ctrl+C', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
