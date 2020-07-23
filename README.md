# wsl2gpg

wsl2gpg is a small utility making it possible to use gpg in WSL 
(Windows Subsystem for Linux) with the agent
from [Gpg4win](https://gpg4win.org/).

GnuPG's libassuan emulates sockets on Windows by listening on localhost
and writing the TCP port number and a key to the "socket" file. 
This utility will listen on UNIX sockets in ~/.gnupg and proxy
connections to the localhost TCP port. The key is automatically sent first. 

With this, gpg in WSL can talk to the Gpg4win agent in Windows. 

## Usage

You can either install wsl2gpg with pip:

```shell
pip install wsl2gpg
```

Or alternatively just copy [`__init__.py`](wsl2gpg/__init__.py) somewhere
and make it executable with `chmod +x`

Then, append a line to your `.bashrc` (or rc file of your favorite shell)
to run wsl2gpg when you log in:

```shell
wsl2gpg -q -i &
```

You should then be able to use gpg in WSL as usual. For example, to show
information on a Yubikey / smartcard:

```shell
$ gpg --card-status
Reader ...........: Yubico Yubikey 4 OTP U2F CCID 0
[...]
```

## Potential Issues

Should the Windows user detection not work, you can set the username manually:

```shell
wsl2gpg -u yourwindowsuername
```