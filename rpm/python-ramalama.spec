%global debug_package %{nil}

%global source_url https://github.com/containers/%{pypi_name}
%global pypi_name ramalama
%global desc RamaLama is a command line tool for working with AI LLM models.
%global _name python%{python3_pkgversion}-%{pypi_name}

%global _python_dist_allow_version_zero 1

Name: python-%{pypi_name}
# DO NOT TOUCH the Version string!
# The TRUE source of this specfile is:
# https://github.com/containers/ramalama/blob/main/rpm/python-ramalama.spec
# If that's what you're reading, Version must be 0, and will be updated by Packit for
# copr and koji builds.
# If you're reading this on dist-git, the version is automatically filled in by Packit.
Version: 0
License: MIT
Release: %autorelease
Summary: RESTful API for RamaLama
URL: %{source_url}
# Tarball fetched from upstream
Source0: %{source_url}/archive/refs/tags/v%{version}.tar.gz
BuildArch: noarch

%description
%desc

On first run RamaLama inspects your system for GPU support, falling back to CPU
support if no GPUs are present. It then uses container engines like Podman to
pull the appropriate OCI image with all of the software necessary to run an
AI Model for your systems setup. This eliminates the need for the user to
configure the system for AI themselves. After the initialization, RamaLama
will run the AI Models within a container based on the OCI image.

%package -n %{_name}
BuildRequires: git-core
BuildRequires: golang
BuildRequires: golang-github-cpuguy83-md2man
BuildRequires: make
BuildRequires: pyproject-rpm-macros

BuildRequires: python%{python3_pkgversion}-argcomplete
BuildRequires: python%{python3_pkgversion}-devel
BuildRequires: python%{python3_pkgversion}-pip
BuildRequires: python%{python3_pkgversion}-setuptools
BuildRequires: python%{python3_pkgversion}-wheel

Requires: python%{python3_pkgversion}-argcomplete

Recommends: podman
Recommends: python%{python3_pkgversion}-huggingface-hub
Recommends: python%{python3_pkgversion}-tqdm

#
Summary: %{summary}
Provides: %{pypi_name} = %{version}-%{release}
%{?python_provide:%python_provide %{_name} }

%description -n %{_name}
%desc

%prep
%autosetup -Sgit -n %{pypi_name}-%{version}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files %{pypi_name}
%{__make} DESTDIR=%{buildroot} PREFIX=%{_prefix} install-shortnames
%{__make} DESTDIR=%{buildroot} PREFIX=%{_prefix} install-docs
%{__make} DESTDIR=%{buildroot} PREFIX=%{_prefix} install-completions

%files -n %{_name}
%license LICENSE
%doc README.md
%{_bindir}/%{pypi_name}
%dir %{_datadir}/%{pypi_name}
%{_datadir}/%{pypi_name}/shortnames.conf
%{_mandir}/man1/%{pypi_name}*
%{_datadir}/bash-completion/completions/%{pypi_name}
%{_datadir}/fish/vendor_completions.d/%{pypi_name}.fish
%{_datadir}/zsh/site/_ramalama
%{python3_sitelib}/%{pypi_name}/
%{python3_sitelib}/%{pypi_name}-%{version}.dist-info/

%changelog
%autochangelog
