# 升级

## 日常更新

打开 Ubuntu「软件更新器」，或运行 `sudo apt update && sudo apt full-upgrade`。内核更新后重启。

## 首次接入

旧版用户首次接入时，在平板上运行下面三行，然后重启。

```sh
wget -O erhai-archive-keyring_1.1_all.deb https://github.com/yzddmr6/onepluspad-2pro-mainline/releases/download/apt/erhai-archive-keyring_1.1_all.deb
sudo apt install ./erhai-archive-keyring_1.1_all.deb
sudo apt update && sudo apt full-upgrade
```

## 恢复系统

如果系统无法启动，按 [安装指南](FLASHING.md)重装。
