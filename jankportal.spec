Name:           jankportal
Version:        %{pkg_version}
Release:        %autorelease
Summary:        %{pkg_summary}

License:        GPL-3.0-or-later
URL:            https://github.com/gminteer/jankportal
Source:         %{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  blueprint-compiler >= 0.20.4
BuildRequires:  glib2-devel >= 2.88.3
Requires:       libadwaita >= 1.9.4
Requires:       python3-gobject >= 3.56.3
Requires:       vte291-gtk4 >= 0.84.1
Requires:       webkitgtk6.0 >= 2.54.0

%global _description %{expand:
A simple GUI to run Bazzite setup scripts/utilities and manage system deployments.}

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
