%global debug_package %{nil}

%global pypi_name ramalama
%global forgeurl https://github.com/containers/%{pypi_name}
# see ramalama/version.py
%global version0 0.0.20
%forgemeta

%global desc RamaLama is a command line tool for working with AI LLM models.

%global _python_dist_allow_version_zero 1

# Temporary removal while we work on getting omlmd package.
%global __requires_exclude omlmd

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
URL: %{forgeurl}
# Tarball fetched from upstream
Source0: %{forgesource}
BuildArch: noarch

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
%if 0%{?fedora} >= 40
BuildRequires: python%{python3_pkgversion}-tqdm
%endif

Requires: python%{python3_pkgversion}-argcomplete


%description
%desc

On first run RamaLama inspects your system for GPU support, falling back to CPU
support if no GPUs are present. It then uses container engines like Podman to
pull the appropriate OCI image with all of the software necessary to run an
AI Model for your systems setup. This eliminates the need for the user to
configure the system for AI themselves. After the initialization, RamaLama
will run the AI Models within a container based on the OCI image.

%package -n python%{python3_pkgversion}-%{pypi_name}
Requires: podman
%if 0%{?fedora} >= 40
Requires: python%{python3_pkgversion}-tqdm
%else
Recommends: python%{python3_pkgversion}-tqdm
%endif
Summary: %{summary}
Provides: %{pypi_name} = %{version}-%{release}
%{?python_provide:%python_provide python%{python3_pkgversion}-%{pypi_name}}

%description -n python%{python3_pkgversion}-%{pypi_name}
%desc

%prep
%forgesetup

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files %{pypi_name}
%{__make} DESTDIR=%{buildroot} PREFIX=%{_prefix} install-docs install-shortnames
%{__make} DESTDIR=%{buildroot} PREFIX=%{_prefix} install-completions

%files -n python%{python3_pkgversion}-%{pypi_name}
%license LICENSE
%doc README.md
%{_bindir}/%{pypi_name}
%{bash_completions_dir}/%{pypi_name}
%{_datadir}/fish/vendor_completions.d/ramalama.fish
%{_datadir}/zsh/vendor-completions/_ramalama
%{python3_sitelib}/%{pypi_name}
%{python3_sitelib}/%{pypi_name}-%{version}.dist-info
%dir %{_datadir}/%{pypi_name}
%{_datadir}/%{pypi_name}/shortnames.conf
%{_datadir}/%{pypi_name}/ramalama.conf
%{_mandir}/man1/ramalama*.1*
%{_mandir}/man5/ramalama*.5*

%changelog
%autochangelog
