# Pond rootfs 实测审计

日期：2026-10-28。使用 `rootfs-fetch` 实际下载并校验，使用 `rootfs-inspect`
完整扫描归档；没有执行上游 rootfs 中的程序，没有修改当前运行系统。

## 来源

- 声明来源：`bflycomputer/iso-installer`，commit `79724644c5119f6543ab6a56bf9614a241e461d2`。
- 声明文件：`src/backend/model.py`。
- SHA-256：`8236724d38f0041132220548095ed43f00119ef62c99dcbe24316ec6ccb14001`。
- 实际下载字节数：`2638674881`。
- 实际摘要与声明相同。锁文件记录来源，并不表示具有作者签名或再分发许可。

## 内容

- `usr/lib/os-release`：`ID=pond`、`ID_LIKE=arch`、`BUILD_ID=rolling`。
- `usr/lib/systemd/systemd` 的 ELF header 已只读检查：64-bit x86-64、动态链接器 `/lib64/ld-linux-x86-64.so.2`。`usr/bin/init → ../lib/systemd/systemd`。
- 规范化后的非根逻辑 entry：201,833；常规文件 167,880，目录 15,662，symlink 15,638，hardlink 2,653；不将 PAX 元数据 header 另算文件。
- entry logical payload 合计：6,624,158,834 bytes，不是解包后的物理占用或压缩层大小。
- `/etc/passwd` 没有普通 UID 1000 用户，只有 root 与系统/服务账号；适合由平台创建实例账号。
- `/etc/skel` 24 个 entry，含 fish、kitty、Niri 配置和 Wallpapers 目录，不能整目录删除。
- `/usr/share/wayland-sessions/niri.desktop` 存在，声明 `Exec=niri-session`，不能使用 Omarchy 的 Hyprland 启动命令替代。
- `/usr/share/pacman/keyrings/archlinux.gpg`、`pond.gpg` 均存在。
- pacman local database 有 820 个包目录，包括 `openssh-10.6p1-2`、`niri-26.04-1`、
  `seatd-0.9.3-1`、`sddm-0.21.0-7`、`systemd-262.1-1`、Nix 与 Flatpak。

## 可精简候选，但尚未默认删除

| 子树 | entry payload bytes | 含义 |
| --- | ---: | --- |
| `boot` | 499,693,397 | 物理启动内容 |
| `usr/lib/modules` | 799,353,353 | 内核模块/headers 等 |
| `usr/lib/firmware` | 517,900,197 | firmware |

包数据库确认有 `linux-pond-7.3.0-2`、`linux-pond-lts-6.18.55-4` 及两套 headers，
另有 GRUB、mkinitcpio、linux-firmware 系列。OCI 使用宿主内核，但直接删除这些文件
不是 package-manager 卸载；未来 pacman 更新可能恢复它们或触发磁盘安装 hooks。
正式精简应先确认 Pond metapackage 依赖与 hooks，再在配方中做有依据的包级裁剪。
这些发行版决策不能进入 `rootfs-cleaner` 的内置逻辑。

## 运行风险与当前策略

原始归档启用了 `display-manager.service → sddm.service`、`getty@tty1`、NetworkManager、
UFW、Bluetooth、时间同步、grub-btrfs、snapper、fstrim 和无线监管域 path 等。
它不是一个“只改 CMD 就可安全套用”的容器 rootfs。

当前配方显式屏蔽会接管显示、网络、时间或物理存储的相关服务，默认 headless。
Pond keyring 的恢复 hook 放在平台账号初始化之后。Niri 桌面必须单独完成 VT 交接、
seatd、PAM/logind 和用户 D-Bus 的目标平台验证，再启用物理桌面。

## 证据边界

本地完整报告位于 `.cache/rootfs-inspection.json`，下载归档位于摘要缓存目录，均不入 Git。
以上是归档检查结果，不是 OCI 构建成功、系统启动成功或 LightOS 桌面验收成功。
本机没有 Docker/Buildx；构建脚本已验证会明确拒绝运行，而不会安装或启动宿主 daemon。
