#!/bin/bash

available() {
  command -v "$1" >/dev/null
}

is_rhel_based() { # doesn't include openEuler
  # shellcheck disable=SC1091
  source /etc/os-release
  [ "$ID" = "rhel" ] || [ "$ID" = "redhat" ] || [ "$ID" == "centos" ]
}

dnf_install_epel() {
  local rpm_exclude_list="selinux-policy,container-selinux"
  local url="https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm"
  dnf reinstall -y "$url" || dnf install -y "$url" --exclude "$rpm_exclude_list"
  crb enable # this is in epel-release, can only install epel-release via url
}

add_stream_repo() {
  local uname_m
  uname_m="$(uname -m)"
  local url="https://mirror.stream.centos.org/9-stream/$1/$uname_m/os/"
  dnf config-manager --add-repo "$url"
  url="http://mirror.centos.org/centos/RPM-GPG-KEY-CentOS-Official"
  local file="/etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-Official"
  if [ ! -e $file ]; then
    curl --retry 8 --retry-all-errors -o $file "$url"
    rpm --import $file
  fi
}

rm_non_ubi_repos() {
  local dir="/etc/yum.repos.d"
  rm -rf $dir/mirror.stream.centos.org_9-stream_* $dir/epel*
}

git_clone_specific_commit() {
  local repo="${1##*/}"
  git init "$repo"
  cd "$repo" || return 1
  git remote add origin "$1"
  git fetch --depth 1 origin "$2"
  git reset --hard "FETCH_HEAD"
  git submodule update --init --recursive
}
