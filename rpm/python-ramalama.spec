%global pypi_name ramalama
%global forgeurl  https://github.com/containers/%{pypi_name}
# see ramalama/version.py
%global version0  0.10.0
%forgemeta

%global summary   RamaLama is a command line tool for working with AI LLM models

%global _python_dist_allow_version_zero 1

Name:             python-%{pypi_name}
# DO NOT TOUCH the Version string!
# The TRUE source of this specfile is:
# https://github.com/containers/ramalama/blob/main/rpm/python-ramalama.spec
# If that's what you're reading, Version must be 0, and will be updated by Packit for
# copr and koji builds.
# If you're reading this on dist-git, the version is automatically filled in by Packit.
Version:          0
License:          MIT
Release:          %{autorelease}
Summary:          %{summary}
URL:              %{forgeurl}
# Tarball fetched from upstream
Source:           %{forgesource}
BuildArch:        noarch

BuildRequires:    git-core
BuildRequires:    golang
BuildRequires:    go-md2man
BuildRequires:    make
BuildRequires:    pyproject-rpm-macros

BuildRequires:    python%{python3_pkgversion}-argcomplete
BuildRequires:    python%{python3_pkgversion}-devel
BuildRequires:    python%{python3_pkgversion}-pip
BuildRequires:    python%{python3_pkgversion}-setuptools
BuildRequires:    python%{python3_pkgversion}-wheel

%description
%summary

On first run RamaLama inspects your system for GPU support, falling back to CPU
support if no GPUs are present. It then uses container engines like Podman to
pull the appropriate OCI image with all of the software necessary to run an
AI Model for your systems setup. This eliminates the need for the user to
configure the system for AI themselves. After the initialization, RamaLama
will run the AI Models within a container based on the OCI image.

%package -n python%{python3_pkgversion}-%{pypi_name}
Recommends: podman
Summary: %{summary}
Provides: %{pypi_name} = %{version}-%{release}

%description -n python%{python3_pkgversion}-%{pypi_name}
%summary

On first run RamaLama inspects your system for GPU support, falling back to CPU
support if no GPUs are present. It then uses container engines like Podman to
pull the appropriate OCI image with all of the software necessary to run an
AI Model for your systems setup. This eliminates the need for the user to
configure the system for AI themselves. After the initialization, RamaLama
will run the AI Models within a container based on the OCI image.


%generate_buildrequires
%pyproject_buildrequires

%prep
%forgeautosetup -p1

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l %{pypi_name}
%{__make} DESTDIR=%{buildroot} PREFIX=%{_prefix} install-docs install-shortnames
%{__make} DESTDIR=%{buildroot} PREFIX=%{_prefix} install-completions

%check
%pyproject_check_import

%files -n python%{python3_pkgversion}-%{pypi_name} -f %{pyproject_files}
%doc README.md
%{_bindir}/%{pypi_name}
%{bash_completions_dir}/%{pypi_name}
%{_datadir}/fish/vendor_completions.d/ramalama.fish
%{zsh_completions_dir}/_ramalama
%dir %{_datadir}/%{pypi_name}
%{_datadir}/%{pypi_name}/shortnames.conf
%{_datadir}/%{pypi_name}/ramalama.conf
%{_mandir}/man1/ramalama*.1*
%{_mandir}/man5/ramalama*.5*
%{_mandir}/man7/ramalama*.7*

%changelog
%autochangelog
