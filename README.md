# pond-oci

Pond rootfs → OCI 的薄配方，使用 `ca-x/oci-kit`，不修改上游 ISO installer。
**当前为实验性、默认 headless 的 systemd/rootfs 构建配方；还不是经过 LightOS 物理桌面验收的成品。**

## 分工

- 本仓库负责 Pond 上游最新 rootfs 声明、固定摘要、清理策略与 Dockerfile。
- `rootfs-fetch` 只消费通用 URL/摘要，不知道 Pond 或 GitHub。
- `rootfs-cleaner` 只消费显式路径，不内置 Pond 包名，不运行卸载 hooks。
- `lighos-init` 明确是 LightOS 专用 adapter；没有通用 `rootfs-init`。

## 最新版本与可重复下载

**所有下载、依赖安装、Rust 编译、OCI 打包及运行验收均在 GitHub Actions 完成。**
本地只编辑、审阅和通过 SSH 推送源码，以及查看工作流状态；不在本机下载 rootfs 或构建产物。
使用已经完成 CLI 验收的精确 toolkit commit 触发远程构建：

```sh
gh workflow run build.yml --repo dockers-x/pond-oci --ref main \
  -f kit_revision=daaf5723d13ab93999c7c325752ff5ef77c81733
gh run list --repo dockers-x/pond-oci --workflow build.yml
```

工作流在 runner 中 checkout toolkit、编译 `rootfs-fetch`，再运行
`scripts/fetch-rootfs.sh`。脚本默认：

1. 读取 `bflycomputer/iso-installer` 的默认分支及当前 commit。
2. **按固定 commit**读取 `src/backend/model.py`，只解析白名单 AST 声明；不 import/exec 上游代码。
3. 校验 SHA-256 和 Pond 官方下载域名/路径，原子更新 `rootfs.lock.json`。
4. 调用通用下载器，写入 `.cache/<sha256>/pond-rootfs.tar.zst`，完整校验摘要。

“最新”指上游 installer 最新提交所声明的 rootfs，不猜测 bucket 的 latest URL。
installer 更新不代表 rootfs 必然更新；同一摘要不反复改写锁文件。
GitHub API 可通过 `GH_TOKEN` / `GITHUB_TOKEN` 认证；token 不进入 URL、锁文件或镜像。

以下内部命令只在 Actions runner 中执行；需要重用已锁定版本时，不查询最新声明：

```sh
bash scripts/fetch-rootfs.sh --locked
python3 scripts/resolve-rootfs.py --check
```

`--check` 在发现新 rootfs 时退出 1，不写锁文件。下载不需要 ISO 安装器的分区、Btrfs、GRUB 或 EFI 逻辑。

## 先审计，再清理

归档检查同样在 Actions runner 中运行，不将归档下载回本机：

```sh
digest="$(python3 -c 'import json; print(json.load(open("rootfs.lock.json"))["sha256"])')"
../oci-kit/target/release/rootfs-inspect --archive ".cache/$digest/pond-rootfs.tar.zst" \
  --text usr/lib/os-release --select etc/os-release \
  --select usr/share/wayland-sessions > .cache/inspection.json
```

默认 `profiles/cleanup.toml` 只移除实例身份/已知 SSH host keys/包下载缓存，
不盲删内核、firmware、Nix、Flatpak 或桌面组件。
它不是包卸载器，保留 pacman 数据库完整性；更激进的包精简需要真实 rootfs 审计后的独立配方。
禁止把清理工具指向正在运行的系统。
已核验的真实 payload 摘要见 `docs/rootfs-audit.md`；机器身份清理不代表软件包已卸载。
`profiles/masked-units.txt` 是 **Pond 配方**的 headless 服务策略：
关闭 SDDM/getty/seatd 的自动物理显示接管，以及网络重配置、防火墙、时间调整、
无线监管域、引导更新、磁盘裁剪/快照等宿主控制操作。保留 systemd-resolved 和应用内容，
默认启动 `multi-user.target`。这些不是通用清理器内置规则，也不是完整的 GUI 适配。

## 镜像构建

Actions runner 提供 Docker + Buildx，以及相邻的 `oci-kit` 源码。
工作流通过以下内部入口构建；脚本不安装/启动本机 daemon，
默认只输出 runner 内的 OCI archive，不 push，也不上传 rootfs/image artifact：

```sh
KIT_SOURCE=../oci-kit bash scripts/build.sh
```

Dockerfile 接收两个 named build contexts：`oci-kit` 源码、`rootfs` 摘要缓存目录。
Rust/Alpine 阶段构建 musl 工具；独立 staging 阶段使用 bsdtar 保留数字 owner、ACL、xattr，
再清理与安装 LightOS hook。最终 `FROM scratch` 只复制处理后的 rootfs，
不把原始压缩包/构建工具/已删除内容留在先前的最终镜像层里。
默认 `CMD` 为 `/sbin/init`，停止信号为 systemd 的 `SIGRTMIN+3`。
版本锁固定 rootfs 内容，不等同于所有 builder base image 也已按 digest 固定；
正式发布前还应固定 builder digest、工具提交并补齐构建与运行验收。

构建宿主须允许 Linux `openat2`（内核 5.6+）且提供 `/proc`；kit 的 staging
操作会拒绝路径祖先链接及跨挂载解析，不会回退到存在竞态的路径清理方式。

## 初始化参数链路

OCI 格式没有“创建用户表单”协议，镜像 ENV 也不会自动变成 LightOS UI 设置：

```text
LightOS 控制面 → /etc/lightos/seed.env → 平台 lightos-setup.service
              → 用户/密码/平台功能配置 → /var/lib/lightos/initialized
              → lighos-init.service → /etc/oci-kit/lightos.toml → 额外 keyring
```

账号和 SSH 仍由平台负责；kit 不重新读取密码，不覆盖平台注入脚本。
当前只确认过平台消费端，没有审计 UI 生产端，不能假定存在 `LIGHTOS_LOCALE` 等额外字段。
Pond 的 `/etc/skel` 随 rootfs 保留，用于平台创建账号时提供默认配置。
`lighos-init` 的额外 keyring 是非秘密配方配置，不是另一份用户凭据协议。
ISO installer 的 SSH patch 是对“解包后配置”的修改，不会修改已发布 rootfs；本项目不照抄它来冒充镜像适配。

## 验收与发布边界

- source tests、下载器与清理器的 fixture tests 不等于真实 LightOS 启动验收。
- 真实 payload 已完整下载、校验并只读检查；尚需实际构建、systemd 启动、LightOS 账号初始化、Pond keyring 和更新验收。
- Niri 会话、VT 等待、seatd、PAM/logind、用户 D-Bus 不能照搬 Omarchy 的 Hyprland 命令；
  物理桌面适配尚未宣称完成。
- 工作流仅手动构建；不自动上传 rootfs/image，须先确认上游再分发许可。
- 源码仓库创建不表示 rootfs 或应用组件的再分发许可已经获得。

```sh
python3 -m unittest discover -s tests -v
bash -n scripts/fetch-rootfs.sh scripts/build.sh
```
