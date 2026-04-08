#!/bin/bash
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive
echo net.ipv4.ip_forward=1 >> /etc/sysctl.conf
mkdir -p -m 777 /postgresql-data /seaweedfs-data /registry-data /redis-data /kagenti-keycloak-postgres-data /phoenix-data
touch /etc/adk # used to verify if this is a VM

if [ -n "${CI:-}" ]; then
	apt-mark auto $(apt-mark showmanual)
	sudo apt-mark manual \
		cloud-init \
		dbus \
		dhcpcd \
		iproute2 \
		iptables \
		linux-image-cloud-$(uname -m | sed -e 's/aarch64/arm64/;s/x86_64/amd64/') \
		openssh-server \
		sudo \
		systemd \
		systemd-sysv
fi

apt-get update -y -q
apt-get install -y -q --no-install-recommends \
	containernetworking-plugins \
	cri-o \
	cri-tools \
	kubectl \
	skopeo \
	sshfs

echo 'en_US.UTF-8 UTF-8' >/etc/locale.gen
locale-gen

curl -fsSL "https://github.com/microshift-io/microshift/releases/download/4.21.0_g29f429c21_4.21.0_okd_scos.ec.15/microshift-debs-$(uname -m | sed -e 's/arm64/aarch64/;s/amd64/x86_64/').tgz" | tar -xz -C /tmp
dpkg -i /tmp/microshift_*.deb /tmp/microshift-kindnet_*.deb
echo 'export KUBECONFIG=/var/lib/microshift/resources/kubeadmin/kubeconfig' > /etc/profile.d/kubeconfig.sh

ARCH_HELM=$(uname -m | sed -e 's/aarch64/arm64/;s/x86_64/amd64/')
curl -fsSL "https://get.helm.sh/helm-v4.1.1-linux-${ARCH_HELM}.tar.gz" | tar -xzf - --strip-components=1 -C /usr/local/bin "linux-${ARCH_HELM}/helm"
chmod +x /usr/local/bin/helm

systemctl enable crio
systemctl enable microshift
systemctl stop microshift
systemctl stop crio

if [ -z "${CI:-}" ]; then
	printf '#!/bin/sh\nexec sudo podman "$@"\n' > /usr/local/bin/docker
	chmod +x /usr/local/bin/docker
	echo "deb [trusted=yes] https://mise.jdx.dev/deb stable main" | sudo tee /etc/apt/sources.list.d/mise.list
	apt-get update -y -q
	apt-get install -y -q --no-install-recommends \
		git \
		mise \
		nftables \
		podman
fi

passwd -l root
cloud-init clean --logs
truncate -s 0 /etc/machine-id

if [ -n "${CI:-}" ]; then
	apt-get purge --auto-remove -y --allow-remove-essential \
		apt \
		bash-completion \
		groff-base \
		man-db \
		manpages

	rm -rf \
		/etc/apt/sources.list.d/* \
		/root/.cache \
		/tmp/* \
		/usr/bin/apt* \
		/usr/share/doc/* \
		/usr/share/groff/* \
		/usr/share/i18n/* \
		/usr/share/info/* \
		/usr/share/linda/* \
		/usr/share/lintian/* \
		/usr/share/locale/* \
		/usr/share/man/* \
		/usr/share/vim/* \
		/var/cache/apt/* \
		/var/lib/apt/* \
		/var/lib/dpkg/* \
		/var/lib/microshift/* \
		/var/tmp/* \
		/lib/firmware/*
	find /usr/share/locale -mindepth 1 -maxdepth 1 ! -name 'en*' -exec rm -rf {} +
	find /var/log -type f -exec truncate -s 0 {} +
fi

ARTIFACTS=/build/artifacts
STAGING=/build/staging
mkdir -p "$ARTIFACTS" "$STAGING/rootfs"
trap 'rm -rf "$STAGING"' EXIT
tar -cf - \
	--exclude=./boot \
	--exclude=./build \
	--exclude=./dev \
	--exclude=./etc/cloud \
	--exclude=./etc/ssh/ssh_host_* \
	--exclude=./home \
	--exclude=./lib/firmware \
	--exclude=./lib/modules \
	--exclude=./lost+found \
	--exclude=./media \
	--exclude=./mnt \
	--exclude=./proc \
	--exclude=./run \
	--exclude=./sys \
	--exclude=./tmp \
	--exclude=./var/lib/cloud \
	--numeric-owner \
	-C / . | tar -xf - -C "$STAGING/rootfs"
truncate -s 0 "$STAGING/rootfs/etc/fstab"
for svc in systemd-tmpfiles-setup.service systemd-tmpfiles-clean.service tmp.mount systemd-tmpfiles-setup-dev-early.service systemd-tmpfiles-setup-dev.service; do
  ln -sf /dev/null "$STAGING/rootfs/etc/systemd/system/$svc"
done

cat > "$STAGING/rootfs/etc/systemd/network/eth0.network" <<-EOF
	[Match]
	Name=eth0

	[Network]
	DHCP=true
EOF

cat > "$STAGING/metadata.yaml" <<-EOF
	architecture: $(uname -m | sed -e 's/aarch64/arm64/;s/x86_64/amd64/')
	creation_date: $(date +%s)
	properties:
	  description: MicroShift Kubernetes VM (Debian 13) for Incus
	  os: debian
	  release: trixie
	  variant: microshift
EOF
tar -cf - --numeric-owner -C "$STAGING" metadata.yaml rootfs | gzip > "$ARTIFACTS/incus.tar.gz"
 
rm -f "$STAGING/rootfs/etc/resolv.conf" "$STAGING/rootfs/etc/systemd/network/eth0.network"
for svc in systemd-resolved.service systemd-networkd.service NetworkManager.service; do
  ln -sf /dev/null "$STAGING/rootfs/etc/systemd/system/$svc"
done
cp /build/wsl.conf "$STAGING/rootfs/etc/wsl.conf"
cp /build/wsl-distribution.conf "$STAGING/rootfs/etc/wsl-distribution.conf"
tar -cf - --numeric-owner -C "$STAGING/rootfs" . | gzip > "$ARTIFACTS/rootfs.wsl"
