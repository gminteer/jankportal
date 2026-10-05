Name:           %{pkg_name}
Version:        %{pkg_version}
Release:        %autorelease
Summary:        %{pkg_summary}

License:        %{pkg_license}
URL:            %{pkg_url}
Source:         %{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel %{pkg_build_requires}
Requires:       %{pkg_requires}


%description
%{pkg_description}


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
%{_bindir}/%{name}


%changelog
%autochangelog
