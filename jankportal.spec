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
%pyproject_save_files -l %{name}
install -d %{buildroot}%{_datadir}/applications
mkdir -p %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/
install -m 644 src/%{name}/assets/%{name}.png %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/%{name}.png
desktop-file-install --dir=%{buildroot}%{_datadir}/applications src/%{name}/assets/%{name}.desktop


%check
%pyproject_check_import


%files -n %{name} -f %{pyproject_files}
%{_bindir}/%{name}
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/256x256/apps/%{name}.png


%changelog
%autochangelog
