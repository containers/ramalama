%global pypi_name ramalama
%global desc RamaLama is a command line tool for working with AI LLM models.

%define _python_dist_allow_version_zero 1

Name: python-%{pypi_name}
# DO NOT TOUCH the Version string!
# The TRUE source of this specfile is:
# https://github.com/containers/ramalama/blob/main/rpm/python-ramalama.spec
# If that's what you're reading, Version must be 0, and will be updated by Packit for
# copr and koji builds.
# If you're reading this on dist-git, the version is automatically filled in by Packit.
Version: 0
License: Apache-2.0
Release: %autorelease
Summary: RESTful API for RamaLama
URL: https://github.com/containers/%{pypi_name}
# Tarball fetched from upstream
Source0: %{url}/archive/v%{version}.tar.gz
BuildArch: noarch

%description
%desc

On first run RamaLama inspects your system for GPU support, falling back to CPU
support if no GPUs are present. It then uses container engines like Podman to
pull the appropriate OCI image with all of the software necessary to run an
AI Model for your systems setup. This eliminates the need for the user to
configure the system for AI themselves. After the initialization, RamaLama
will run the AI Models within a container based on the OCI image.

%package -n python%{python3_pkgversion}-%{pypi_name}
BuildRequires: golang
BuildRequires: golang-github-cpuguy83-md2man
BuildRequires: git-core
BuildRequires: make
BuildRequires: python%{python3_pkgversion}-devel
BuildRequires: pyproject-rpm-macros
BuildRequires: python%{python3_pkgversion}-pip
BuildRequires: python%{python3_pkgversion}-setuptools
BuildRequires: python%{python3_pkgversion}-wheel
BuildRequires: python%{python3_pkgversion}-argcomplete
Recommends: podman
Summary: %{summary}
Provides: %{pypi_name} = %{version}-%{release}
%{?python_provide:%python_provide python%{python3_pkgversion}-%{pypi_name}}

%description -n python%{python3_pkgversion}-%{pypi_name}
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

%files -n python%{python3_pkgversion}-%{pypi_name} -f %{pyproject_files}
%license LICENSE
%doc README.md
%{_bindir}/%{pypi_name}
%dir %{_datadir}/%{pypi_name}
%{_datadir}/%{pypi_name}/shortnames.conf
%{_mandir}/man1/%{pypi_name}*
%{_datadir}/bash-completion/completions/%{pypi_name}
%{_datadir}/fish/vendor_completions.d/%{pypi_name}.fish

%changelog
%autochangelog
