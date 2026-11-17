# Upgrade

## System updates

Open Software Updater, or run `sudo apt update && sudo apt full-upgrade`. Restart after a kernel update.

## First-time setup

On an existing installation, run these commands once on the tablet, then restart.

```sh
wget -O erhai-archive-keyring_1.1_all.deb https://github.com/yzddmr6/onepluspad-2pro-mainline/releases/download/apt/erhai-archive-keyring_1.1_all.deb
sudo apt install ./erhai-archive-keyring_1.1_all.deb
sudo apt update && sudo apt full-upgrade
```

## Recovery

If the system fails to boot, reinstall using the [installation guide](FLASHING.en.md).
