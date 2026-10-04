Name:           jankportal
Version:        %{pkg_version}
Release:        %autorelease
Summary:        %{pkg_summary}

License:        GPL-3.0-or-later
URL:            https://github.com/gminteer/jankportal
Source:         %{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel %{pkg_build_requires}
Requires:       %{pkg_requires}

%global _description %{expand:
Long description goes here and should probably be extracted from pyproject.toml.}

%description %_description


%prep
%autosetup -p1 %{name}-%{version}


%generate_buildrequires
%pyproject_buildrequires


%build
%pyproject_wheel


%install
%pyproject_install
# Automatically extracted from wheel
%pyproject_save_files -l jankportal


%check
%pyproject_check_import


%files -n %{name} -f %{pyproject_files}
%{_bindir}/jankportal


%changelog
%autochangelog
