#!/usr/bin/env python3
import argparse
import asyncio
import errno
import os
import socket
import stat
import subprocess
import sys
import textwrap

from typing import Coroutine, List


def printerr(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def die(*args, **kwargs):
    printerr(*args, **kwargs)
    sys.exit(1)


def read_assuan_socket_config(path: str) -> (int, bytes):
    """Read a libassuan socket file and return port an secret key."""
    with open(path, 'rb') as f:
        port, key = f.read().split(b'\n', 1)
        port = int(port)
        if port < 0 or port > 65536:
            raise ValueError('Invalid port')
        if len(key) != 16:
            raise ValueError('Expected 16 byte nonce')
        return port, key


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Proxy between a reader/writer pair."""
    try:
        while not reader.at_eof():
            writer.write(await reader.read(4096))
    finally:
        writer.close()


def create_handler(targetpath):
    """Create a connection handler that connects to a libassuan socket."""

    async def handler(local_reader: asyncio.StreamReader, local_writer: asyncio.StreamWriter):
        # Read socket config each time - if the remote daemon restarts, the port number is going to change
        port, key = read_assuan_socket_config(targetpath)
        try:
            remote_reader, remote_writer = await asyncio.open_connection('127.0.0.1', port)
            remote_writer.write(key)
            p1, p2 = pipe(local_reader, remote_writer), pipe(remote_reader, local_writer)
            await asyncio.gather(p1, p2)
        finally:
            local_writer.close()

    return handler


def bridge_sockets(localpath: str, targetpath: str, loop=None) -> Coroutine:
    """Create a socket bridge UNIX listener."""
    # Read the socket early to error out if something is wrong
    read_assuan_socket_config(targetpath)
    return asyncio.start_unix_server(create_handler(targetpath), localpath, loop=loop)


def run_server(bridges: List[Coroutine], loop=None):
    """Run a list of servers until done or Control-C is pressed."""
    if loop is None:
        loop = asyncio.get_event_loop()
    servers = loop.run_until_complete(asyncio.gather(*bridges))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        printerr('Got KeyboardInterrupt, exiting...')

    # Close all socket servers
    waiter = asyncio.gather(*(s.wait_closed() for s in servers))
    for s in servers:
        s.close()
    loop.run_until_complete(waiter)
    loop.close()


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent('''\
        Create UNIX sockets and proxy to the gpg4win agent.

        GPG's libassuan emulates sockets on windows by listening to localhost
        and writing the port and a key to the "socket" file. This utility will
        listen on UNIX sockets in ~/.gnupg and proxy connections to the localhost
        endpoint. With this, gpg in WSL can talk to the gpg4win agent in Windows.        
        '''))
    parser.add_argument('-u', '--user', metavar='USERNAME', type=str,
                        help='The Windows username of the user running gpg4win (default: autodetect)')
    parser.add_argument('-i', '--ignore-existing', action="store_true",
                        help='Ignore already existing sockets.')
    parser.add_argument('--users-dir', type=str, default='/mnt/c/Users',
                        help='Windows Users directory (default: /mnt/c/Users)')
    parser.add_argument('-q', '--quiet', action='store_true')
    args = parser.parse_args()
    user = args.user

    if not os.path.exists(args.users_dir):
        die('User directory does not exist:', args.users_dir)

    if not user:
        # Auto-detect user
        cmd = subprocess.run(['cmd.exe', '/c', 'echo %USERNAME%'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if cmd.returncode != 0:
            die('Unable to determine username, cmd.exe returned:', cmd.returncode, 'stderr:', cmd.stderr)
        user = cmd.stdout.decode('utf8').strip()

    win_home = os.path.join(args.users_dir, user)
    if not os.path.exists(win_home):
        die('User\'s windows profile directory does not exist:', win_home)

    win_gpg = os.path.join(win_home, 'AppData', 'Roaming', 'gnupg')
    if not os.path.exists(win_gpg):
        die('GnuPG directory does not exist:', win_gpg)

    sockets = list(filter(lambda d: d.startswith('S.'), os.listdir(win_gpg)))
    if not sockets:
        die('No gpg sockets found, please make sure the gpg4win agent is running.')

    gpg = os.path.expanduser('~/.gnupg')
    if not os.path.exists(gpg):
        die('~/.gnupg doesn\'t exist!')

    bridges = []
    for s in sockets:
        localp = os.path.join(gpg, s)
        remotep = os.path.join(win_gpg, s)

        in_use = False
        if os.path.exists(localp) and stat.S_ISSOCK(os.stat(localp).st_mode):
            # Oh the horrors of UNIX sockets. https://stackoverflow.com/questions/7405932
            # TL;DR: It doesn't seem possible to detect if a UNIX socket is in use other than trying to connect to it.
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.connect(localp)
                in_use = True
            except OSError as ose:
                if ose.errno == errno.ECONNREFUSED:
                    pass  # Nothing seems to be listening, so we can take it
                else:
                    raise
            finally:
                sock.close()

        if in_use:
            if args.ignore_existing:
                if not args.quiet:
                    printerr('Socket', localp, 'already exists, skipping...')
            else:
                die('Socket', localp, 'already exists!')
        else:
            bridges.append(bridge_sockets(localp, remotep))

    if bridges:
        if not args.quiet:
            printerr('Proxying', len(bridges), 'sockets.')
        run_server(bridges)
    else:
        if not args.quiet:
            printerr('No socket bridges to create, exiting...')


if __name__ == '__main__':
    main()
