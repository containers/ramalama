FROM registry.fedoraproject.org/fedora:41

# Support podman in podman
# Reference: https://www.redhat.com/en/blog/podman-inside-container

# Install podman, git, openssl, openssh-server, nano, python and any other requirements 
RUN dnf update -y; \
dnf reinstall shadow-utils -y; \
dnf install git openssl openssh-server nano python3 python3-pip -y; \
dnf install --nobest podman fuse-overlayfs --exclude container-selinux -y; \
rm -rf /var/cache /var/log/dnf* /var/log/yum.*
ENV PYTHONUNBUFFERED 1

# Install ramalama package dependencies 
RUN pip3 install argcomplete

# Create podman:podman user 
RUN useradd -d /home/podman/ -G wheel -g root -p "$(openssl passwd -1 podman)" podman; \
echo podman:10000:5000 > /etc/subuid; \
echo podman:10000:5000 > /etc/subgid;
WORKDIR /home/podman/
VOLUME /home/podman/.local/share/containers
RUN chown -R podman:root /home/podman/
RUN chmod -R 775 /home/podman/
# Create necessary rootless volumes
ADD https://raw.githubusercontent.com/containers/image_build/refs/heads/main/podman/podman-containers.conf /home/podman/.config/containers/containers.conf
RUN mkdir -p /var/lib/shared/overlay-images /var/lib/shared/overlay-layers /var/lib/shared/vfs-images /var/lib/shared/vfs-layers; \
touch /var/lib/shared/overlay-images/images.lock; \
touch /var/lib/shared/overlay-layers/layers.lock; \
touch /var/lib/shared/vfs-images/images.lock;
ENV _CONTAINERS_USERNS_CONFIGURED=""

# Make ramalama folder in container
RUN mkdir -p /home/podman/.local/share/ramalama/
RUN chown -R podman:root /home/podman/.local/share/ramalama/ 

# Run container as user podman 
USER podman